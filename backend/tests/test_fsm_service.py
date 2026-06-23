"""test_fsm_service.py — оркестрация FSM урока (backend/services/fsm_service.py).

Юнит-тесты против движка (CLAUDE.md §5): happy path + ключевые edge cases из спеки.
Сценарии v4: S-02 (1-я попытка), S-03 (2-я попытка), S-04 (провал), S-06 (тренировка
с ошибкой), S-10 (выход). Серверное судейство §2, секвенирование §3.1, R3-проскок hook.

Уроки — синтетические (FakeRepo), чтобы детерминированно вести по веткам без CSV/keeper.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from backend.db.models import Progress, ProgressStatus, ReviewQueue, ReviewReason
from backend.engine import lesson_content as lc
from backend.engine.csv_loader import LessonMessage
from backend.services import fsm_service
from backend.services.fsm_service import LessonError
from backend.tests.conftest import CONTENT_DIR, make_student


def _m(
    mid: str,
    stage: str,
    *,
    correct: str = "",
    a: str = "",
    b: str = "",
    fa: str = "",
    fb: str = "",
    rb: str = "",
) -> LessonMessage:
    return LessonMessage(
        lesson_id="1_1",
        message_id=mid,
        stage=stage,
        text="<b>x</b>",
        option_a=a,
        option_b=b,
        option_c="",
        option_d="",
        correct_answer=correct,
        feedback_a=fa,
        feedback_b=fb,
        feedback_c="",
        feedback_d="",
        return_a="",
        return_b=rb,
        return_c="",
        return_d="",
    )


class FakeRepo:
    """Утиная замена LessonRepository: lesson_id → список сообщений (без CSV/keeper)."""

    def __init__(self, by_id: dict[str, list[LessonMessage]]) -> None:
        self._m = dict(by_id)

    def has(self, lesson_id: str) -> bool:
        return lesson_id in self._m

    def messages(self, lesson_id: str) -> list[LessonMessage]:
        if lesson_id not in self._m:
            raise lc.LessonNotFoundError(lesson_id)
        return self._m[lesson_id]


def _simple_lesson() -> list[LessonMessage]:
    """2 экрана theory, example, 1 training(A), main(A), backup(A), final, failed."""
    return [
        _m("th1", "theory"),
        _m("th2", "theory"),
        _m("ex1", "example"),
        _m("tq1", "training", correct="A", a="Да", b="Нет", fa="ok", fb="no", rb="th1"),
        _m(
            "mq",
            "main_question",
            correct="A",
            a="Да",
            b="Нет",
            fa="ok",
            fb="no",
            rb="th1",
        ),
        _m(
            "bq", "main_question_backup", correct="A", a="Да", b="Нет", fa="ok", fb="no"
        ),
        _m("fn", "final"),
        _m("fl", "lesson_failed"),
    ]


def _three_training_lesson() -> list[LessonMessage]:
    return [
        _m("th1", "theory"),
        _m("ex1", "example"),
        _m("tq1", "training", correct="A", a="Да", b="Нет", fa="ok", fb="no", rb="th1"),
        _m("tq2", "training", correct="B", a="Да", b="Нет", fa="no", fb="ok", rb="th1"),
        _m("tq3", "training", correct="A", a="Да", b="Нет", fa="ok", fb="no", rb="th1"),
        _m("mq", "main_question", correct="A", a="Да", b="Нет", fa="ok", fb="no"),
        _m(
            "bq", "main_question_backup", correct="A", a="Да", b="Нет", fa="ok", fb="no"
        ),
        _m("fn", "final"),
        _m("fl", "lesson_failed"),
    ]


def _start(db, messages, *, lesson_id="1_1"):
    """Создать ученика в lesson_select, стартовать урок → (student, repo, outcome)."""
    student = make_student(db)
    student.profile.fsm_state = "lesson_select"
    db.flush()
    repo = FakeRepo({lesson_id: messages})
    outcome = fsm_service.start_lesson(db, repo, student.id)
    return student, repo, outcome


def _progress(db, user_id, lesson_id="1_1") -> Progress:
    return db.execute(
        select(Progress).where(
            Progress.user_id == user_id, Progress.lesson_id == lesson_id
        )
    ).scalar_one()


def _reasons(db, user_id) -> set[ReviewReason]:
    return {
        c.reason
        for c in db.execute(
            select(ReviewQueue).where(ReviewQueue.user_id == user_id)
        ).scalars()
    }


# --- Старт урока: R3-проскок hook, манифест ---


def test_start_lesson_auto_skips_hook(db):
    student, _repo, out = _start(db, _simple_lesson())
    assert out.fsm_state == "lesson_theory"  # hook авто-проскочен (§3.1-R3)
    assert out.message.message_id == "th1"
    assert (out.progress_step, out.progress_total) == (1, 5)
    p = _progress(db, student.id)
    assert p.status == ProgressStatus.IN_PROGRESS
    assert p.current_message_id == "th1"
    assert student.profile.current_lesson_id == "1_1"


def test_start_lesson_picks_next_unpassed(db):
    """Манифест (§3.3): пройденный 1_1 пропускается, стартует 1_2."""
    student = make_student(db)
    student.profile.fsm_state = "lesson_select"
    db.add(
        Progress(
            user_id=student.id,
            lesson_id="1_1",
            status=ProgressStatus.PASSED,
            training_errors={},
        )
    )
    db.flush()
    repo = FakeRepo({"1_2": _simple_lesson()})
    out = fsm_service.start_lesson(db, repo, student.id)
    assert out.fsm_state == "lesson_theory"
    assert student.profile.current_lesson_id == "1_2"


# --- S-02: главный вопрос с 1-й попытки ---


def test_walk_pass_on_first_attempt(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    assert fsm_service.advance(db, repo, uid).message.message_id == "th2"  # лист theory
    assert fsm_service.advance(db, repo, uid).fsm_state == "lesson_example"
    assert fsm_service.advance(db, repo, uid).fsm_state == "lesson_training"
    out = fsm_service.answer(db, repo, uid, message_id="tq1", selected="A")
    assert out.fsm_state == "lesson_main_question"  # автопереход (один training)
    out = fsm_service.answer(db, repo, uid, message_id="mq", selected="A")
    assert out.fsm_state == "lesson_final"
    out = fsm_service.advance(db, repo, uid)
    assert out.fsm_state == "repeat_1h_pending"  # не все 27 → R1 (§3)
    p = _progress(db, uid)
    assert p.status == ProgressStatus.PASSED
    assert p.passed_on_attempt == 1
    # passed_attempt_1: интервальные карточки есть, passed_attempt_2 — нет.
    assert ReviewReason.PASSED_ATTEMPT_2 not in _reasons(db, uid)
    assert ReviewReason.INTERVAL_1D in _reasons(db, uid)


# --- S-03: главный вопрос со 2-й попытки ---


def test_walk_pass_on_second_attempt(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    for _ in range(3):  # th1→th2→example→training
        fsm_service.advance(db, repo, uid)
    fsm_service.answer(db, repo, uid, message_id="tq1", selected="A")  # → main_question
    out = fsm_service.answer(db, repo, uid, message_id="mq", selected="B")  # неверно #1
    assert out.fsm_state == "lesson_theory_review"
    assert out.message.message_id == "th1"  # возврат к ключевой теории (return_X)
    out = fsm_service.advance(db, repo, uid)
    assert out.fsm_state == "lesson_main_question_backup"
    out = fsm_service.answer(db, repo, uid, message_id="bq", selected="A")  # верно #2
    assert out.fsm_state == "lesson_final"
    fsm_service.advance(db, repo, uid)
    p = _progress(db, uid)
    assert p.status == ProgressStatus.PASSED
    assert p.passed_on_attempt == 2
    reasons = _reasons(db, uid)
    assert ReviewReason.PASSED_ATTEMPT_2 in reasons
    assert ReviewReason.INTERVAL_1D in reasons  # интервалы тоже (без дублей)


# --- S-04: провал (исчерпаны попытки) ---


def test_walk_fail_on_second_wrong(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    for _ in range(3):
        fsm_service.advance(db, repo, uid)
    fsm_service.answer(db, repo, uid, message_id="tq1", selected="A")
    fsm_service.answer(db, repo, uid, message_id="mq", selected="B")  # неверно #1
    fsm_service.advance(db, repo, uid)  # → backup
    out = fsm_service.answer(db, repo, uid, message_id="bq", selected="B")  # неверно #2
    assert out.fsm_state == "lesson_failed"
    assert out.message.stage == "lesson_failed"  # §4.5/§4.9: render-текст провала
    out = fsm_service.advance(db, repo, uid)  # подтвердить провал
    assert out.fsm_state == "daily_blocked"
    p = _progress(db, uid)
    assert p.status == ProgressStatus.FAILED_TODAY
    assert p.main_question_attempts == 2
    assert ReviewReason.INTERVAL_1D in _reasons(db, uid)  # карточка провала на завтра


# --- S-06: тренировка с ошибкой и 3 ошибки подряд ---


def test_training_wrong_keeps_question_and_records_error(db):
    student, repo, _ = _start(db, _three_training_lesson())
    uid = student.id
    fsm_service.advance(db, repo, uid)  # theory→example
    fsm_service.advance(db, repo, uid)  # example→training (tq1)
    # tq1 (верно=A) отвечаем неверно (B) → остаёмся на tq1, ошибка + возврат.
    out = fsm_service.answer(db, repo, uid, message_id="tq1", selected="B")
    assert out.fsm_state == "lesson_training"  # неверно → остаёмся на том же вопросе
    assert out.message.message_id == "tq1"  # позиция не сдвинулась (повтор)
    assert out.judgement.is_correct is False
    assert out.judgement.return_target == "th1"
    assert _progress(db, uid).training_errors.get("tq1") == 1


def test_training_three_wrong_in_a_row_fails(db):
    student, repo, _ = _start(db, _three_training_lesson())
    uid = student.id
    fsm_service.advance(db, repo, uid)
    fsm_service.advance(db, repo, uid)  # на tq1 (correct=A)
    for _ in range(2):  # 2 неверных подряд (tq1: B неверно)
        out = fsm_service.answer(db, repo, uid, message_id="tq1", selected="B")
        assert out.fsm_state == "lesson_training"
    out = fsm_service.answer(
        db, repo, uid, message_id="tq1", selected="B"
    )  # 3-я подряд
    assert out.fsm_state == "lesson_failed"
    assert out.message.stage == "lesson_failed"
    assert _progress(db, uid).training_errors.get("tq1") == 2  # 3-я не инкрементит


# --- S-10: выход из урока ---


def test_cancel_persists_resumable_progress(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    out = fsm_service.cancel(db, repo, uid)
    assert out.fsm_state == "registered"
    p = _progress(db, uid)
    assert p.status == ProgressStatus.IN_PROGRESS  # возобновляем
    assert p.current_message_id == "th1"  # позиция сохранена (EC-02)


# --- Ошибки доступа/состояния ---


def test_answer_invalid_option(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    for _ in range(3):
        fsm_service.advance(db, repo, uid)  # → training (tq1)
    with pytest.raises(LessonError) as exc:
        fsm_service.answer(db, repo, uid, message_id="tq1", selected="C")  # C пуст
    assert exc.value.code == "invalid_option" and exc.value.http_status == 422


def test_answer_stale_message(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    for _ in range(3):
        fsm_service.advance(db, repo, uid)
    with pytest.raises(LessonError) as exc:
        fsm_service.answer(db, repo, uid, message_id="tq_old", selected="A")
    assert exc.value.code == "stale_message" and exc.value.http_status == 409


def test_answer_in_non_question_state_rejected(db):
    student, repo, _ = _start(db, _simple_lesson())  # сейчас lesson_theory
    uid = student.id
    with pytest.raises(LessonError) as exc:
        fsm_service.answer(db, repo, uid, message_id="th1", selected="A")
    assert exc.value.code == "wrong_action_for_stage"


def test_advance_in_question_state_rejected(db):
    student, repo, _ = _start(db, _simple_lesson())
    uid = student.id
    for _ in range(3):
        fsm_service.advance(db, repo, uid)  # → lesson_training (вопрос-стадия)
    with pytest.raises(LessonError) as exc:
        fsm_service.advance(db, repo, uid)
    assert exc.value.code == "wrong_action_for_stage"


# --- Реальный контент: дымовой старт 1_1 ---


def test_start_lesson_real_content_1_1(db):
    from backend.engine.lesson_content import LessonRepository

    student = make_student(db)
    student.profile.fsm_state = "lesson_select"
    db.flush()
    repo = LessonRepository(CONTENT_DIR)
    out = fsm_service.start_lesson(db, repo, student.id)
    assert out.fsm_state == "lesson_theory"  # у 1_1 нет hook → проскок
    assert out.message is not None and out.message.stage == "theory"
    assert student.profile.current_lesson_id == "1_1"
