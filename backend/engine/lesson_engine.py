"""lesson_engine.py — конечный автомат роли «Ученик» (spec student_lesson_fsm_v4 §2).

Чистый детерминированный движок: состояния, события, переходы с гардами и
дескрипторами сайд-эффектов. БД здесь НЕ трогается — `dispatch` принимает текущее
состояние, событие и контекст-гардов, возвращает (новое состояние, сайд-эффекты).
Исполнение сайд-эффектов транзакционно и чтение/запись `StudentProfile.fsm_state` —
зона fsm_service (следующий слой, §8 контракты). Это разделение из §7 раскладки.

Источник истины — таблица переходов v4 §2b. Менять автомат только вслед за спекой
(CLAUDE.md §1): код без спеки на новое поведение не пишется.

Соглашение по счётчику попыток главного вопроса (mastery learning, §2):
`main_question_attempts` = число сделанных НЕВЕРНЫХ попыток. В `lesson_main_question`
он равен 0 (первая попытка), в `lesson_main_question_backup` — 1 (вторая попытка).
Неверный ответ на резерве доводит счётчик до 2 → провал. Это согласуется со
сценариями S-02..S-04; гард wrong_attempt2 проверяет вход в резерв (attempts==1),
а не пост-инкремент (в тексте спеки §2b — «==2», это значение ПОСЛЕ инкремента).
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, replace


class State(enum.StrEnum):
    UNREGISTERED = "unregistered"  # start
    ONBOARDING = "onboarding"
    REGISTERED = "registered"
    DAILY_START = "daily_start"
    MORNING_WARMUP = "morning_warmup"
    LESSON_SELECT = "lesson_select"
    LESSON_HOOK = "lesson_hook"
    LESSON_THEORY = "lesson_theory"
    LESSON_EXAMPLE = "lesson_example"
    LESSON_TRAINING = "lesson_training"
    LESSON_MAIN_QUESTION = "lesson_main_question"
    LESSON_THEORY_REVIEW = "lesson_theory_review"
    LESSON_MAIN_QUESTION_BACKUP = "lesson_main_question_backup"
    LESSON_FINAL = "lesson_final"
    LESSON_FAILED = "lesson_failed"
    REPEAT_1H_PENDING = "repeat_1h_pending"
    REPEAT_1H_ACTIVE = "repeat_1h_active"
    REPEAT_EVENING_PENDING = "repeat_evening_pending"
    REPEAT_EVENING_ACTIVE = "repeat_evening_active"
    REVIEW_QUEUE_SCHEDULED = "review_queue_scheduled"
    DAILY_BLOCKED = "daily_blocked"
    DAILY_DONE = "daily_done"
    STREAK_UPDATE = "streak_update"
    COURSE_COMPLETE = "course_complete"


class Event(enum.StrEnum):
    OPEN_PWA = "evt_open_pwa"
    SUBMIT_REGISTRATION = "evt_submit_registration"
    CANCEL_REGISTRATION = "evt_cancel_registration"
    DELETE_ACCOUNT = "evt_delete_account"
    OPEN_APP = "evt_open_app"
    WARMUP_AVAILABLE = "evt_warmup_available"
    WARMUP_SKIP = "evt_warmup_skip"
    WARMUP_COMPLETE = "evt_warmup_complete"
    START_LESSON = "evt_start_lesson"
    NO_LESSON_TODAY = "evt_no_lesson_today"
    ALL_LESSONS_DONE = "evt_all_lessons_done"
    HOOK_READ = "evt_hook_read"
    THEORY_READ = "evt_theory_read"
    EXAMPLE_READ = "evt_example_read"
    ANSWER_CORRECT = "evt_answer_correct"
    ANSWER_WRONG = "evt_answer_wrong"
    TRAINING_MAX_ERRORS = "evt_training_max_errors"
    CANCEL_LESSON = "evt_cancel_lesson"
    MAIN_CORRECT_ATTEMPT1 = "evt_main_correct_attempt1"
    MAIN_WRONG_ATTEMPT1 = "evt_main_wrong_attempt1"
    MAIN_CORRECT_ATTEMPT2 = "evt_main_correct_attempt2"
    MAIN_WRONG_ATTEMPT2 = "evt_main_wrong_attempt2"
    THEORY_REVIEWED = "evt_theory_reviewed"
    LESSON_COMPLETE = "evt_lesson_complete"
    LESSON_FAIL_CONFIRMED = "evt_lesson_fail_confirmed"
    ELAPSED_1H = "evt_1h_elapsed"
    REPEAT_1H_ANSWERED = "evt_repeat_1h_answered"
    EVENING_TIME = "evt_evening_time"
    REPEAT_EVENING_ANSWERED = "evt_repeat_evening_answered"
    SESSION_END = "evt_session_end"
    NEXT_DAY = "evt_next_day"
    DAY_END = "evt_day_end"
    STREAK_UPDATED = "evt_streak_updated"


class SideEffect(enum.StrEnum):
    """Дескрипторы побочных эффектов перехода. Исполняет fsm_service транзакционно."""

    CREATE_STUDENT_ACCOUNT = "create_student_account"  # детали — пункт 4 (регистрация)
    DELETE_ALL_PD = "delete_all_pd"  # каскадное удаление 152-ФЗ (v4 §8)
    UPDATE_LAST_ACTIVE = "update_last_active"
    APPLY_STREAK_UPDATE = "apply_streak_update"
    PERSIST_RESUMABLE_PROGRESS = "persist_resumable_progress"  # cancel_lesson
    RECORD_TRAINING_ERROR = "record_training_error"
    INCREMENT_MAIN_ATTEMPT = "increment_main_attempt"
    RECORD_LESSON_PASSED = "record_lesson_passed"
    SCHEDULE_REPEATS = "schedule_repeats"  # R1 (1ч) + R2 (~21:00)
    ENQUEUE_INTERVAL_REVIEWS = (
        "enqueue_interval_reviews"  # 1/3/7/14/30 (dedup в review_service)
    )
    ENQUEUE_PASSED_ATTEMPT_2_REVIEW = "enqueue_passed_attempt_2_review"
    RECORD_LESSON_FAILED = "record_lesson_failed"  # status=failed_today
    ENQUEUE_FAILED_REVIEW_1D = "enqueue_failed_review_1d"
    RESET_FAILED_TODAY = "reset_failed_today"  # failed_today → not_started (новый день)
    ROLLBACK_R1_INTERVAL = "rollback_r1_interval"
    ROLLBACK_R2_INTERVAL = "rollback_r2_interval"
    SHOW_R1_COUNTDOWN = "show_r1_countdown"
    SHOW_EVENING_PROMPT = "show_evening_prompt"
    SHOW_BLOCKED_MESSAGE = "show_blocked_message"


@dataclass(frozen=True)
class FSMContext:
    """Входы гардов. Значения по умолчанию безопасны (наиболее частый путь)."""

    missed_day_end: bool = False
    review_due: bool = False  # review_queue содержит due_date <= today
    user_skipped_warmup: bool = False  # явное нажатие «пропустить разминку»
    has_next_lesson: bool = False  # есть следующий незавершённый урок
    next_lesson_failed_today: bool = False  # следующий урок в статусе failed_today
    all_lessons_passed: bool = False  # все 27 уроков passed
    training_remaining: bool = False  # остались тренировочные вопросы
    main_question_attempts: int = 0  # сделано неверных попыток главного вопроса
    is_evening: bool = False  # локальное время >= 21:00
    registration_valid: bool = False  # name + grade + pd_consent (детали — пункт 4)


@dataclass(frozen=True)
class Transition:
    src: State
    event: Event
    dest: State
    guard: Callable[[FSMContext], bool] | None = None
    effects: tuple[SideEffect, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class TransitionResult:
    new_state: State
    effects: tuple[SideEffect, ...]


class FSMError(Exception):
    """Базовая ошибка автомата."""


class UnknownTransitionError(FSMError):
    """Для пары (состояние, событие) нет ни одного перехода (тупик/недопустимо)."""


class GuardError(FSMError):
    """Переход(ы) для (состояние, событие) есть, но ни один гард не выполнен."""


class AmbiguousTransitionError(FSMError):
    """Несколько переходов подошло сразу — дефект таблицы (гарды пересекаются)."""


# --- Таблица переходов (v4 §2b). Порядок — как в спеке. ---

_E = SideEffect

TRANSITIONS: tuple[Transition, ...] = (
    # --- Регистрация (внутренности onboarding — пункт 4) ---
    Transition(State.UNREGISTERED, Event.OPEN_PWA, State.ONBOARDING),
    Transition(
        State.ONBOARDING,
        Event.SUBMIT_REGISTRATION,
        State.REGISTERED,
        guard=lambda c: c.registration_valid,
        effects=(_E.CREATE_STUDENT_ACCOUNT,),
        note="name + grade in диапазоне + pd_consent (пункт 4)",
    ),
    Transition(State.ONBOARDING, Event.CANCEL_REGISTRATION, State.UNREGISTERED),
    Transition(State.ONBOARDING, Event.DELETE_ACCOUNT, State.UNREGISTERED),
    # --- Удаление аккаунта (152-ФЗ) ---
    Transition(
        State.REGISTERED,
        Event.DELETE_ACCOUNT,
        State.UNREGISTERED,
        effects=(_E.DELETE_ALL_PD,),
    ),
    # --- Вход в приложение / отложенный streak ---
    Transition(
        State.REGISTERED,
        Event.OPEN_APP,
        State.DAILY_START,
        guard=lambda c: not c.missed_day_end,
        effects=(_E.UPDATE_LAST_ACTIVE,),
    ),
    Transition(
        State.REGISTERED,
        Event.OPEN_APP,
        State.STREAK_UPDATE,
        guard=lambda c: c.missed_day_end,
        note="отложенный streak_update перед daily_start (v4 §2, evt_day_end)",
    ),
    Transition(
        State.REGISTERED,
        Event.DAY_END,
        State.STREAK_UPDATE,
        note="ежедневный job 23:59; в понедельник сбросить freeze_used_this_week",
    ),
    Transition(
        State.STREAK_UPDATE,
        Event.STREAK_UPDATED,
        State.REGISTERED,
        effects=(_E.APPLY_STREAK_UPDATE,),
    ),
    # --- Утренняя разминка (взаимоисключающие гарды) ---
    Transition(
        State.DAILY_START,
        Event.WARMUP_AVAILABLE,
        State.MORNING_WARMUP,
        guard=lambda c: c.review_due,
    ),
    Transition(
        State.DAILY_START,
        Event.WARMUP_SKIP,
        State.LESSON_SELECT,
        guard=lambda c: not c.review_due,
        note="review_queue пуста",
    ),
    Transition(
        State.DAILY_START,
        Event.WARMUP_SKIP,
        State.LESSON_SELECT,
        guard=lambda c: c.review_due and c.user_skipped_warmup,
        note="queue непуста, но ученик явно нажал «пропустить»",
    ),
    Transition(State.MORNING_WARMUP, Event.WARMUP_COMPLETE, State.LESSON_SELECT),
    # --- Выбор урока ---
    Transition(
        State.LESSON_SELECT,
        Event.START_LESSON,
        State.LESSON_HOOK,
        guard=lambda c: c.has_next_lesson and not c.next_lesson_failed_today,
    ),
    Transition(
        State.LESSON_SELECT,
        Event.NO_LESSON_TODAY,
        State.DAILY_DONE,
        guard=lambda c: not c.next_lesson_failed_today,
        note="нет новых уроков",
    ),
    Transition(
        State.LESSON_SELECT,
        Event.NO_LESSON_TODAY,
        State.DAILY_BLOCKED,
        guard=lambda c: c.next_lesson_failed_today,
    ),
    Transition(
        State.LESSON_SELECT,
        Event.ALL_LESSONS_DONE,
        State.COURSE_COMPLETE,
        guard=lambda c: c.all_lessons_passed,
    ),
    # --- Прохождение урока ---
    Transition(State.LESSON_HOOK, Event.HOOK_READ, State.LESSON_THEORY),
    Transition(
        State.LESSON_HOOK,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(State.LESSON_THEORY, Event.THEORY_READ, State.LESSON_EXAMPLE),
    Transition(
        State.LESSON_THEORY,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(State.LESSON_EXAMPLE, Event.EXAMPLE_READ, State.LESSON_TRAINING),
    Transition(
        State.LESSON_EXAMPLE,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(
        State.LESSON_TRAINING,
        Event.ANSWER_CORRECT,
        State.LESSON_TRAINING,
        guard=lambda c: c.training_remaining,
        note="остались тренировочные вопросы",
    ),
    Transition(
        State.LESSON_TRAINING,
        Event.ANSWER_CORRECT,
        State.LESSON_MAIN_QUESTION,
        guard=lambda c: not c.training_remaining,
        note="все Q1..Q3 пройдены — автопереход к главному вопросу",
    ),
    Transition(
        State.LESSON_TRAINING,
        Event.ANSWER_WRONG,
        State.LESSON_TRAINING,
        effects=(_E.RECORD_TRAINING_ERROR,),
        note="возврат по return_X; событие приходит, пока счётчик ошибок < 3",
    ),
    Transition(
        State.LESSON_TRAINING,
        Event.TRAINING_MAX_ERRORS,
        State.LESSON_FAILED,
        note="3 ошибки подряд на одном вопросе",
    ),
    Transition(
        State.LESSON_TRAINING,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    # --- Главный вопрос (mastery learning) ---
    Transition(
        State.LESSON_MAIN_QUESTION,
        Event.MAIN_CORRECT_ATTEMPT1,
        State.LESSON_FINAL,
        guard=lambda c: c.main_question_attempts == 0,
    ),
    Transition(
        State.LESSON_MAIN_QUESTION,
        Event.MAIN_WRONG_ATTEMPT1,
        State.LESSON_THEORY_REVIEW,
        guard=lambda c: c.main_question_attempts == 0,
        effects=(_E.INCREMENT_MAIN_ATTEMPT,),
    ),
    Transition(
        State.LESSON_MAIN_QUESTION,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(
        State.LESSON_THEORY_REVIEW,
        Event.THEORY_REVIEWED,
        State.LESSON_MAIN_QUESTION_BACKUP,
    ),
    Transition(
        State.LESSON_THEORY_REVIEW,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(
        State.LESSON_MAIN_QUESTION_BACKUP,
        Event.MAIN_CORRECT_ATTEMPT2,
        State.LESSON_FINAL,
        guard=lambda c: c.main_question_attempts == 1,
        effects=(_E.ENQUEUE_PASSED_ATTEMPT_2_REVIEW,),
    ),
    Transition(
        State.LESSON_MAIN_QUESTION_BACKUP,
        Event.MAIN_WRONG_ATTEMPT2,
        State.LESSON_FAILED,
        guard=lambda c: c.main_question_attempts == 1,
        effects=(_E.INCREMENT_MAIN_ATTEMPT,),
        note="неверно на резерве (attempts 1→2) → провал; «==2» в §2b — пост-инкремент",
    ),
    Transition(
        State.LESSON_MAIN_QUESTION_BACKUP,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    # --- Финал и провал ---
    Transition(
        State.LESSON_FINAL,
        Event.LESSON_COMPLETE,
        State.COURSE_COMPLETE,
        guard=lambda c: c.all_lessons_passed,
        effects=(_E.RECORD_LESSON_PASSED, _E.ENQUEUE_INTERVAL_REVIEWS),
    ),
    Transition(
        State.LESSON_FINAL,
        Event.LESSON_COMPLETE,
        State.REPEAT_1H_PENDING,
        guard=lambda c: not c.all_lessons_passed,
        effects=(
            _E.RECORD_LESSON_PASSED,
            _E.SCHEDULE_REPEATS,
            _E.ENQUEUE_INTERVAL_REVIEWS,
        ),
    ),
    Transition(
        State.LESSON_FINAL,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    Transition(
        State.LESSON_FAILED,
        Event.LESSON_FAIL_CONFIRMED,
        State.DAILY_BLOCKED,
        effects=(_E.RECORD_LESSON_FAILED, _E.ENQUEUE_FAILED_REVIEW_1D),
    ),
    Transition(
        State.LESSON_FAILED,
        Event.CANCEL_LESSON,
        State.REGISTERED,
        effects=(_E.RECORD_LESSON_FAILED, _E.ENQUEUE_FAILED_REVIEW_1D),
        note="прогресс сохраняется как failed_today; урок в review_queue (interval_1d)",
    ),
    # --- Повторения R1/R2 ---
    Transition(
        State.REPEAT_1H_PENDING,
        Event.OPEN_APP,
        State.REPEAT_1H_PENDING,
        effects=(_E.SHOW_R1_COUNTDOWN,),
        note="самопетля: «R1 будет через N минут»",
    ),
    Transition(State.REPEAT_1H_PENDING, Event.ELAPSED_1H, State.REPEAT_1H_ACTIVE),
    Transition(
        State.REPEAT_1H_ACTIVE,
        Event.REPEAT_1H_ANSWERED,
        State.REPEAT_EVENING_PENDING,
    ),
    Transition(
        State.REPEAT_1H_ACTIVE,
        Event.NEXT_DAY,
        State.REPEAT_EVENING_PENDING,
        effects=(_E.ROLLBACK_R1_INTERVAL,),
        note="R1 пропущен — интервал откатывается",
    ),
    Transition(
        State.REPEAT_EVENING_PENDING,
        Event.EVENING_TIME,
        State.REPEAT_EVENING_ACTIVE,
        guard=lambda c: c.is_evening,
    ),
    Transition(
        State.REPEAT_EVENING_PENDING,
        Event.NEXT_DAY,
        State.REVIEW_QUEUE_SCHEDULED,
        effects=(_E.ROLLBACK_R2_INTERVAL,),
        note="R2 пропущен — интервал откатывается",
    ),
    Transition(
        State.REPEAT_EVENING_ACTIVE,
        Event.OPEN_APP,
        State.REPEAT_EVENING_ACTIVE,
        effects=(_E.SHOW_EVENING_PROMPT,),
        note="самопетля: «Вечернее повторение ждёт тебя»",
    ),
    Transition(
        State.REPEAT_EVENING_ACTIVE,
        Event.REPEAT_EVENING_ANSWERED,
        State.REVIEW_QUEUE_SCHEDULED,
        effects=(_E.ENQUEUE_INTERVAL_REVIEWS,),
        note="при passed_attempt_2 интервалы уже есть — review_service дедуплицирует",
    ),
    # --- Завершение сессии / следующий день ---
    Transition(State.REVIEW_QUEUE_SCHEDULED, Event.SESSION_END, State.REGISTERED),
    Transition(State.DAILY_DONE, Event.SESSION_END, State.REGISTERED),
    Transition(State.DAILY_DONE, Event.NEXT_DAY, State.REGISTERED),
    Transition(
        State.DAILY_BLOCKED,
        Event.NEXT_DAY,
        State.REGISTERED,
        effects=(_E.RESET_FAILED_TODAY,),
    ),
    Transition(
        State.DAILY_BLOCKED,
        Event.OPEN_APP,
        State.DAILY_BLOCKED,
        effects=(_E.SHOW_BLOCKED_MESSAGE,),
        note="самопетля: «Урок доступен завтра»",
    ),
    # --- course_complete (не end: доступ к настройкам/удалению) ---
    Transition(State.COURSE_COMPLETE, Event.OPEN_APP, State.REGISTERED),
    Transition(
        State.COURSE_COMPLETE,
        Event.DELETE_ACCOUNT,
        State.UNREGISTERED,
        effects=(_E.DELETE_ALL_PD,),
    ),
)

START_STATE: State = State.UNREGISTERED


def _transitions_for(state: State, event: Event) -> list[Transition]:
    return [t for t in TRANSITIONS if t.src == state and t.event == event]


def dispatch(
    state: State, event: Event, ctx: FSMContext | None = None
) -> TransitionResult:
    """Выполнить переход по (состояние, событие, контекст).

    Поднимает UnknownTransitionError, если пара (состояние, событие) не определена;
    GuardError — если переходы есть, но ни один гард не прошёл; AmbiguousTransitionError
    — если подходит больше одного (дефект таблицы). Сам автомат ничего не мутирует.
    """
    ctx = ctx or FSMContext()
    candidates = _transitions_for(state, event)
    if not candidates:
        raise UnknownTransitionError(f"нет перехода из {state} по {event}")
    matching = [t for t in candidates if t.guard is None or t.guard(ctx)]
    if not matching:
        raise GuardError(f"из {state} по {event} ни один гард не выполнен (ctx={ctx})")
    if len(matching) > 1:
        dests = [t.dest for t in matching]
        raise AmbiguousTransitionError(
            f"из {state} по {event} подошло несколько переходов: {dests}"
        )
    chosen = matching[0]
    return TransitionResult(new_state=chosen.dest, effects=chosen.effects)


def can_handle(state: State, event: Event, ctx: FSMContext | None = None) -> bool:
    """Можно ли выполнить переход (без исключений)."""
    try:
        dispatch(state, event, ctx)
    except FSMError:
        return False
    return True


def valid_events(state: State) -> set[Event]:
    """Множество событий, объявленных для состояния (без учёта гардов)."""
    return {t.event for t in TRANSITIONS if t.src == state}


def with_context(**overrides: object) -> FSMContext:
    """Удобный конструктор контекста от дефолтного (для вызовов и тестов)."""
    return replace(FSMContext(), **overrides)


# Множества для интроспекции/тестов.
STATES: frozenset[State] = frozenset(State)
EVENTS: frozenset[Event] = frozenset(Event)
