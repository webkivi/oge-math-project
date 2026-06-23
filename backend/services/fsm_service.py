"""fsm_service.py — оркестрация FSM урока: БД ↔ движок (specs/student_lesson_api_v1 §2).

Слой между HTTP-роутерами (пункт 1b) и чистым автоматом lesson_engine. Здесь:
- читает StudentProfile.fsm_state (канон, v4 §1; не из клиента);
- строит FSMContext из Progress + COURSE_MANIFEST + контента (счётчики — ДО
  инкремента, §2.2-bis);
- судит ответ СЕРВЕРНО (lesson_content.judge, §2.2; клиент не присылает исход);
- деривит событие FSM (§2.3 ответ, §1.3 «Дальше»); клиент шлёт действие, не evt;
- диспатчит lesson_engine.dispatch и исполняет side-effects ТРАНЗАКЦИОННО, обновляя
  fsm_state атомарно с Progress (v4 §1: «fsm_state атомарно с Progress»);
- секвенирует сообщения урока (§3.1/§3.2) + R3-авто-проскок hook (§3.1-R3).

Вне охвата пункта 1a (отложено): HTTP-транспорт, sequence-эхо/409-дедуп (§5.2 → 1b),
scheduler-события (R1/R2-таймеры, evt_day_end) и стрик/DailySession (scheduler-срез),
утренняя разминка/повторения R1-R2-ответы и day-hub (последующие пункты).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from backend import config
from backend.db.models import Progress, ProgressStatus, StudentProfile
from backend.engine import lesson_content as lc
from backend.engine import lesson_engine as fsm
from backend.engine.csv_loader import LessonMessage
from backend.engine.lesson_engine import Event, SideEffect, State
from backend.services import review_service

logger = logging.getLogger(__name__)


class LessonError(Exception):
    """Отказ операции урока. Код + HTTP-статус (api §5); 1b мапит на ответ."""

    def __init__(
        self, code: str, *, http_status: int, field: str | None = None
    ) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.field = field


@dataclass(frozen=True)
class LessonOutcome:
    """Итог операции для слоя рендера (1b): новое состояние + текущее сообщение."""

    fsm_state: str
    lesson_id: str
    message: (
        LessonMessage | None
    )  # текущее сообщение урока (None на безмессаджных состояниях)
    judgement: lc.Judgement | None  # при answer — итог судейства; иначе None
    progress_step: int | None  # LessonProgress.step (§4.5-R3); None вне шкалы
    progress_total: int | None
    effects: tuple[SideEffect, ...]  # для прозрачности/тестов


# Деривация «Дальше» (E9, §1.3): fsm_state → событие (одношаговые не-вопросные стадии).
_ADVANCE_EVENT: dict[State, Event] = {
    State.LESSON_HOOK: Event.HOOK_READ,
    State.LESSON_THEORY: Event.THEORY_READ,
    State.LESSON_EXAMPLE: Event.EXAMPLE_READ,
    State.LESSON_THEORY_REVIEW: Event.THEORY_REVIEWED,
    State.LESSON_FINAL: Event.LESSON_COMPLETE,
    State.LESSON_FAILED: Event.LESSON_FAIL_CONFIRMED,
}
# Многоэкранные не-вопросные стадии: «Дальше» сначала листает внутри стадии (§3.1 п.3).
_MULTISCREEN = {State.LESSON_HOOK, State.LESSON_THEORY, State.LESSON_EXAMPLE}

# Состояние урока → стадия CSV первого экрана (§3.1 п.6).
_STATE_STAGE: dict[State, str] = {
    State.LESSON_HOOK: lc.STAGE_HOOK,
    State.LESSON_THEORY: lc.STAGE_THEORY,
    State.LESSON_EXAMPLE: lc.STAGE_EXAMPLE,
    State.LESSON_TRAINING: lc.STAGE_TRAINING,
    State.LESSON_MAIN_QUESTION: lc.STAGE_MAIN_QUESTION,
    State.LESSON_MAIN_QUESTION_BACKUP: lc.STAGE_MAIN_QUESTION_BACKUP,
    State.LESSON_FINAL: lc.STAGE_FINAL,
    State.LESSON_FAILED: lc.STAGE_LESSON_FAILED,  # §4.5/§4.9: render-текст провала
}
_QUESTION_STATES = {
    State.LESSON_TRAINING,
    State.LESSON_MAIN_QUESTION,
    State.LESSON_MAIN_QUESTION_BACKUP,
}
# Базовый шаг LessonProgress по состоянию (шкала без hook, §4.5-R3); при total=6 — +1.
_PROGRESS_STEP_BASE: dict[State, int] = {
    State.LESSON_THEORY: 1,
    State.LESSON_EXAMPLE: 2,
    State.LESSON_TRAINING: 3,
    State.LESSON_MAIN_QUESTION: 4,
    State.LESSON_MAIN_QUESTION_BACKUP: 4,
    State.LESSON_THEORY_REVIEW: 4,  # повтор теории внутри попытки — тот же шаг
    State.LESSON_FINAL: 5,
}
# Side-effects, отложенные к scheduler/streak-срезу (исполняются там, не здесь).
_DEFERRED_EFFECTS = {
    SideEffect.SCHEDULE_REPEATS,
    SideEffect.APPLY_STREAK_UPDATE,
    SideEffect.ROLLBACK_R1_INTERVAL,
    SideEffect.ROLLBACK_R2_INTERVAL,
    SideEffect.SHOW_R1_COUNTDOWN,
    SideEffect.SHOW_EVENING_PROMPT,
    SideEffect.SHOW_BLOCKED_MESSAGE,
    SideEffect.UPDATE_LAST_ACTIVE,
}


# --- Загрузка профиля/прогресса ---


def _load_profile(db: DbSession, user_id: int) -> StudentProfile:
    profile = db.get(StudentProfile, user_id)
    if profile is None:
        raise LessonError("no_profile", http_status=404)
    return profile


def _progress_by_lesson(db: DbSession, user_id: int) -> dict[str, Progress]:
    rows = db.execute(select(Progress).where(Progress.user_id == user_id)).scalars()
    return {p.lesson_id: p for p in rows}


def _get_or_create_progress(
    db: DbSession, user_id: int, lesson_id: str, now: datetime
) -> Progress:
    existing = db.execute(
        select(Progress).where(
            Progress.user_id == user_id, Progress.lesson_id == lesson_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    progress = Progress(
        user_id=user_id,
        lesson_id=lesson_id,
        status=ProgressStatus.NOT_STARTED,
        main_question_attempts=0,
        training_errors={},
        started_at=now,
    )
    db.add(progress)
    return progress


# --- Манифест курса (§3.3): следующий незавершённый урок / все пройдены ---


def _first_non_passed(by_lesson: dict[str, Progress]) -> tuple[str | None, bool]:
    """(lesson_id, failed_today) первого урока манифеста со статусом != passed.

    Возвращает (None, False), если все 27 уроков passed (course_complete).
    """
    for lesson_id in config.COURSE_MANIFEST:
        p = by_lesson.get(lesson_id)
        if p is None or p.status != ProgressStatus.PASSED:
            return lesson_id, (
                p is not None and p.status == ProgressStatus.FAILED_TODAY
            )
    return None, False


def _all_passed_after(by_lesson: dict[str, Progress], current_lesson_id: str) -> bool:
    """Будут ли все 27 уроков passed, если текущий (сейчас завершаемый) считать passed.

    Гард lesson_final → course_complete проверяется ПОСЛЕ записи текущего как passed
    (v4 §2б), поэтому текущий урок исключаем из проверки.
    """
    for lesson_id in config.COURSE_MANIFEST:
        if lesson_id == current_lesson_id:
            continue
        p = by_lesson.get(lesson_id)
        if p is None or p.status != ProgressStatus.PASSED:
            return False
    return True


# --- LessonProgress (§4.5-R3) ---


def _progress_indicator(
    messages: list[LessonMessage], state: State
) -> tuple[int | None, int | None]:
    total = lc.progress_total(messages)  # 5 без hook, 6 с hook
    if state == State.LESSON_HOOK and total == 6:
        return 1, 6
    base = _PROGRESS_STEP_BASE.get(state)
    if base is None:
        return None, None  # lesson_failed / авто-проскок hook — ячейки нет (§4.5-R3)
    return (base + 1 if total == 6 else base), total


# --- Исполнение side-effects (транзакционно, атомарно с fsm_state) ---


def _apply_effects(
    db: DbSession,
    profile: StudentProfile,
    progress: Progress,
    effects: tuple[SideEffect, ...],
    *,
    answered_message_id: str | None,
    now: datetime,
) -> None:
    for effect in effects:
        if effect in _DEFERRED_EFFECTS:
            continue  # scheduler/streak-срез
        _apply_one(
            db,
            profile,
            progress,
            effect,
            answered_message_id=answered_message_id,
            now=now,
        )


def _apply_one(
    db: DbSession,
    profile: StudentProfile,
    progress: Progress,
    effect: SideEffect,
    *,
    answered_message_id: str | None,
    now: datetime,
) -> None:
    user_id = progress.user_id
    lesson_id = progress.lesson_id
    if effect == SideEffect.PERSIST_RESUMABLE_PROGRESS:
        if progress.status == ProgressStatus.NOT_STARTED:
            progress.status = ProgressStatus.IN_PROGRESS
    elif effect == SideEffect.RECORD_TRAINING_ERROR:
        # JSON-словарь: переприсваиваем (SQLAlchemy не ловит in-place мутацию).
        key = answered_message_id or ""
        counts = dict(progress.training_errors)
        counts[key] = counts.get(key, 0) + 1
        progress.training_errors = counts
    elif effect == SideEffect.INCREMENT_MAIN_ATTEMPT:
        progress.main_question_attempts += 1
    elif effect == SideEffect.RECORD_LESSON_PASSED:
        progress.status = ProgressStatus.PASSED
        progress.completed_at = now
        # passed_on_attempt: 1 — с первой попытки главного вопроса; 2 — с резерва.
        progress.passed_on_attempt = 1 if progress.main_question_attempts == 0 else 2
    elif effect == SideEffect.ENQUEUE_INTERVAL_REVIEWS:
        review_service.enqueue_interval_reviews(db, user_id, lesson_id)
    elif effect == SideEffect.ENQUEUE_PASSED_ATTEMPT_2_REVIEW:
        review_service.enqueue_passed_attempt_2(db, user_id, lesson_id)
    elif effect == SideEffect.RECORD_LESSON_FAILED:
        progress.status = ProgressStatus.FAILED_TODAY
        progress.completed_at = now
    elif effect == SideEffect.ENQUEUE_FAILED_REVIEW_1D:
        review_service.enqueue_failed_review(db, user_id, lesson_id)
    elif effect == SideEffect.RESET_FAILED_TODAY:
        if progress.status == ProgressStatus.FAILED_TODAY:
            progress.status = ProgressStatus.NOT_STARTED
    else:  # pragma: no cover — незаявленный для среза эффект
        logger.error("fsm_service: необработанный side-effect %s", effect.value)
        raise LessonError("fsm_internal_error", http_status=500)


def _dispatch(state: State, event: Event, ctx: fsm.FSMContext) -> fsm.TransitionResult:
    """Диспатч движка с маппингом исключений на коды (§5.5)."""
    try:
        return fsm.dispatch(state, event, ctx)
    except (fsm.UnknownTransitionError, fsm.GuardError) as exc:
        raise LessonError("wrong_action_for_stage", http_status=409) from exc
    except fsm.AmbiguousTransitionError as exc:  # pragma: no cover — дефект таблицы
        raise LessonError("ambiguous_transition", http_status=500) from exc


def _state(profile: StudentProfile) -> State:
    return State(profile.fsm_state)


def _outcome(
    profile: StudentProfile,
    messages: list[LessonMessage],
    message: LessonMessage | None,
    effects: tuple[SideEffect, ...],
    judgement: lc.Judgement | None = None,
) -> LessonOutcome:
    state = _state(profile)
    step, total = _progress_indicator(messages, state)
    return LessonOutcome(
        fsm_state=profile.fsm_state,
        lesson_id=profile.current_lesson_id,
        message=message,
        judgement=judgement,
        progress_step=step,
        progress_total=total,
        effects=effects,
    )


# --- Публичные операции (вызываются роутерами 1b) ---


def start_lesson(
    db: DbSession, repo: lc.LessonRepository, user_id: int
) -> LessonOutcome:
    """lesson_select → следующий незавершённый урок (§3.3). R3: при отсутствии hook
    авто-проскок lesson_hook → lesson_theory[0] (§3.1-R3). Создаёт/находит Progress."""
    profile = _load_profile(db, user_id)
    now = datetime.now(UTC)
    by_lesson = _progress_by_lesson(db, user_id)
    lesson_id, failed_today = _first_non_passed(by_lesson)

    if lesson_id is None:
        # Все 27 пройдены → course_complete (evt_all_lessons_done).
        result = _dispatch(
            _state(profile),
            Event.ALL_LESSONS_DONE,
            fsm.with_context(all_lessons_passed=True),
        )
        profile.fsm_state = result.new_state.value
        db.commit()
        return _outcome(profile, [], None, result.effects)
    if failed_today:
        # Следующий урок заблокирован на сегодня → daily_blocked (no_lesson_today).
        result = _dispatch(
            _state(profile),
            Event.NO_LESSON_TODAY,
            fsm.with_context(next_lesson_failed_today=True),
        )
        profile.fsm_state = result.new_state.value
        db.commit()
        return _outcome(profile, [], None, result.effects)

    # Старт урока: evt_start_lesson → lesson_hook.
    ctx = fsm.with_context(has_next_lesson=True, next_lesson_failed_today=False)
    result = _dispatch(_state(profile), Event.START_LESSON, ctx)
    profile.fsm_state = result.new_state.value
    profile.current_lesson_id = lesson_id
    profile.last_active_at = now
    progress = _get_or_create_progress(db, user_id, lesson_id, now)
    if progress.status == ProgressStatus.NOT_STARTED:
        progress.status = ProgressStatus.IN_PROGRESS
    messages = repo.messages(lesson_id)

    # R3-авто-проскок: hook-сообщения нет → сразу lesson_theory[0] (§3.1-R3).
    if not lc.has_hook(messages):
        skip = _dispatch(_state(profile), Event.HOOK_READ, fsm.with_context())
        profile.fsm_state = skip.new_state.value

    state = _state(profile)
    entry = lc.first_of_stage(messages, _STATE_STAGE[state])
    progress.current_message_id = entry.message_id if entry else None
    db.commit()
    return _outcome(profile, messages, entry, result.effects)


def advance(db: DbSession, repo: lc.LessonRepository, user_id: int) -> LessonOutcome:
    """«Дальше» (E9): лист многоэкранной стадии или read-событие (§1.3, §3.1)."""
    profile = _load_profile(db, user_id)
    state = _state(profile)
    if state not in _ADVANCE_EVENT:
        raise LessonError("wrong_action_for_stage", http_status=409)
    progress = _require_active_progress(db, profile)
    messages = repo.messages(profile.current_lesson_id)

    # Многоэкранная стадия: пролистнуть к следующему экрану БЕЗ FSM-события (§3.1 п.3).
    if state in _MULTISCREEN and progress.current_message_id is not None:
        nxt = lc.next_in_stage(messages, progress.current_message_id)
        if nxt is not None:
            progress.current_message_id = nxt.message_id
            db.commit()
            return _outcome(profile, messages, nxt, ())

    # Последний экран стадии → read-событие → следующая стадия.
    if state == State.LESSON_FINAL:
        # lesson_final → course_complete (все 27) ИЛИ repeat_1h_pending (иначе), §3.
        all_passed = _all_passed_after(
            _progress_by_lesson(db, user_id), profile.current_lesson_id
        )
        ctx = fsm.with_context(all_lessons_passed=all_passed)
    else:
        ctx = fsm.with_context()
    result = _dispatch(state, _ADVANCE_EVENT[state], ctx)
    _apply_effects(
        db,
        profile,
        progress,
        result.effects,
        answered_message_id=progress.current_message_id,
        now=datetime.now(UTC),
    )
    profile.fsm_state = result.new_state.value
    new_state = _state(profile)
    entry = (
        lc.first_of_stage(messages, _STATE_STAGE[new_state])
        if new_state in _STATE_STAGE
        else None
    )
    if entry is not None:
        progress.current_message_id = entry.message_id
    db.commit()
    return _outcome(profile, messages, entry, result.effects)


def answer(
    db: DbSession,
    repo: lc.LessonRepository,
    user_id: int,
    *,
    message_id: str,
    selected: str,
) -> LessonOutcome:
    """Ответ (E10): серверное судейство (§2.2) → деривация evt (§2.3) → dispatch."""
    profile = _load_profile(db, user_id)
    state = _state(profile)
    if state not in _QUESTION_STATES:
        raise LessonError("wrong_action_for_stage", http_status=409)
    progress = _require_active_progress(db, profile)
    # Анти-stale (§2.2 шаг 2): отвечать можно только на текущий вопрос.
    if message_id != progress.current_message_id:
        raise LessonError("stale_message", http_status=409)
    messages = repo.messages(profile.current_lesson_id)
    message = lc.find(messages, message_id)
    if message is None:
        raise LessonError("stale_message", http_status=409)
    if not lc.is_valid_option(message, selected):
        raise LessonError("invalid_option", http_status=422, field="selected")

    judgement = lc.judge(message, selected)  # серверное сравнение с CSV (§2.2 шаг 4)
    event = _derive_answer_event(
        state, judgement.is_correct, progress, messages, message_id
    )
    # ctx — счётчики ДО инкремента (§2.2-bis); training_remaining — по контенту (§3.1).
    ctx = fsm.with_context(
        training_remaining=lc.training_remaining(messages, message_id),
        main_question_attempts=progress.main_question_attempts,
    )
    result = _dispatch(state, event, ctx)
    _apply_effects(
        db,
        profile,
        progress,
        result.effects,
        answered_message_id=message_id,
        now=datetime.now(UTC),
    )
    profile.fsm_state = result.new_state.value
    new_state = _state(profile)
    next_message = _resolve_after_answer(
        new_state, state, messages, message_id, judgement
    )
    if next_message is not None:
        progress.current_message_id = next_message.message_id
    db.commit()
    return _outcome(profile, messages, next_message, result.effects, judgement)


def cancel(db: DbSession, repo: lc.LessonRepository, user_id: int) -> LessonOutcome:
    """«Выйти» (E11): evt_cancel_lesson → registered, прогресс сохранён (S-10)."""
    profile = _load_profile(db, user_id)
    state = _state(profile)
    progress = _require_active_progress(db, profile)
    result = _dispatch(state, Event.CANCEL_LESSON, fsm.with_context())
    _apply_effects(
        db,
        profile,
        progress,
        result.effects,
        answered_message_id=progress.current_message_id,
        now=datetime.now(UTC),
    )
    profile.fsm_state = result.new_state.value
    db.commit()
    return _outcome(profile, [], None, result.effects)


# --- Внутренние помощники операций ---


def _require_active_progress(db: DbSession, profile: StudentProfile) -> Progress:
    progress = db.execute(
        select(Progress).where(
            Progress.user_id == profile.user_id,
            Progress.lesson_id == profile.current_lesson_id,
        )
    ).scalar_one_or_none()
    if progress is None:
        raise LessonError("no_active_lesson", http_status=409)
    return progress


def _derive_answer_event(
    state: State,
    is_correct: bool,
    progress: Progress,
    messages: list[LessonMessage],
    message_id: str,
) -> Event:
    """Событие ответа (§2.3). Счётчики серверные, ДО инкремента (§2.2-bis)."""
    if state == State.LESSON_TRAINING:
        if is_correct:
            return (
                Event.ANSWER_CORRECT
            )  # движок выберет remaining/main по training_remaining
        errors = progress.training_errors.get(message_id, 0)
        if errors >= config.MAX_TRAINING_ERRORS - 1:  # этот wrong — 3-й подряд
            return Event.TRAINING_MAX_ERRORS
        return Event.ANSWER_WRONG
    if state == State.LESSON_MAIN_QUESTION:
        return Event.MAIN_CORRECT_ATTEMPT1 if is_correct else Event.MAIN_WRONG_ATTEMPT1
    # LESSON_MAIN_QUESTION_BACKUP
    return Event.MAIN_CORRECT_ATTEMPT2 if is_correct else Event.MAIN_WRONG_ATTEMPT2


def _resolve_after_answer(
    new_state: State,
    prev_state: State,
    messages: list[LessonMessage],
    answered_message_id: str,
    judgement: lc.Judgement,
) -> LessonMessage | None:
    """Какое сообщение показать после ответа (§3.1/§3.2; wrong-возврат — §2.2 шаг 8)."""
    # Тренировка, верно, остались вопросы → следующий training-вопрос.
    if new_state == State.LESSON_TRAINING and prev_state == State.LESSON_TRAINING:
        if judgement.is_correct:
            return lc.next_in_stage(messages, answered_message_id)
        # Неверно (не 3-й): остаёмся на ТОМ ЖЕ вопросе для повторной попытки;
        # render несёт feedback + цель возврата (§2.2 шаг 8). Позиция не двигается.
        return lc.find(messages, answered_message_id)
    # Главный вопрос неверно #1 → повтор теории (return_X; §3.5 fallback).
    if new_state == State.LESSON_THEORY_REVIEW:
        target = judgement.return_target
        return (
            lc.find(messages, target)
            if target
            else lc.first_of_stage(messages, lc.STAGE_THEORY)
        )
    # Иначе — первое сообщение стадии нового состояния.
    stage = _STATE_STAGE.get(new_state)
    return lc.first_of_stage(messages, stage) if stage else None
