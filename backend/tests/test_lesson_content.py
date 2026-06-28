"""test_lesson_content.py — тесты доступа к контенту, секвенирования и судейства.

Проверяют specs/student_lesson_api_v1.md §2.2 (судейство), §3.1/§3.2 (секвенирование),
§3.4-bis (интерфейс (II): ленивый индекс по lesson_id, толерантность к keeper-FAIL),
§3.1-R3 (наличие hook). Чистый слой — БД не нужна.
"""

from __future__ import annotations

import pytest

from backend.engine.csv_loader import InvalidCSVError, LessonMessage
from backend.engine.lesson_content import (
    LessonNotFoundError,
    LessonRepository,
    find,
    first_of_stage,
    has_hook,
    is_valid_option,
    judge,
    next_in_stage,
    next_message,
    progress_total,
    training_remaining,
)
from backend.tests.conftest import (
    CONTENT_DIR,
    lesson_row,
    valid_lesson_rows,
    write_lesson_csv,
)


def _msg(
    message_id: str,
    stage: str,
    *,
    correct: str = "",
    a: str = "",
    b: str = "",
    fa: str = "",
    fb: str = "",
    ra: str = "",
    rb: str = "",
    lesson_id: str = "L",
) -> LessonMessage:
    """Собрать LessonMessage напрямую (для тестов чистых функций без CSV/keeper)."""
    return LessonMessage(
        lesson_id=lesson_id,
        message_id=message_id,
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
        return_a=ra,
        return_b=rb,
        return_c="",
        return_d="",
    )


# Синтетический урок без hook: 2×theory, example, 3×training, main_question, final.
SEQ: list[LessonMessage] = [
    _msg("t1", "theory"),
    _msg("t2", "theory"),
    _msg("e1", "example"),
    _msg("q1", "training", correct="A", a="Да", b="Нет", fa="ok", fb="нет", rb="t1"),
    _msg("q2", "training", correct="B", a="Да", b="Нет", fa="нет", fb="ok", rb="t1"),
    _msg("q3", "training", correct="A", a="Да", b="Нет", fa="ok", fb="нет", rb="t1"),
    _msg("mq", "main_question", correct="A", a="Да", b="Нет", fa="ok", fb="нет"),
    _msg("fin", "final"),
]


def _lesson_rows_with_id(lesson_id: str) -> list[list[str]]:
    """Валидный (keeper-PASS) урок из conftest с проставленным lesson_id (col3)."""
    rows = valid_lesson_rows()
    for r in rows:
        r[2] = lesson_id  # COL_LESSON_ID
    return rows


# --- LessonRepository: индекс по lesson_id, ленивая загрузка (§3.4-bis) ---


def test_repository_indexes_by_lesson_id(tmp_path):
    write_lesson_csv(tmp_path, _lesson_rows_with_id("1_1"), name="Контент_урок_1_1.csv")
    write_lesson_csv(tmp_path, _lesson_rows_with_id("1_2"), name="Контент_урок_1_2.csv")
    repo = LessonRepository(tmp_path)
    assert set(repo.index()) == {"1_1", "1_2"}
    assert repo.has("1_1") and repo.has("1_2")
    assert not repo.has("9_9")
    messages = repo.messages("1_2")
    assert messages and all(m.lesson_id == "1_2" for m in messages)


def test_repository_skips_system_content(tmp_path):
    write_lesson_csv(tmp_path, _lesson_rows_with_id("1_1"), name="Контент_урок_1_1.csv")
    write_lesson_csv(
        tmp_path,
        [lesson_row("trigger_x", "trigger", text="Привет 🙂", lesson_id="0")],
        name="Контент_напоминания.csv",
    )
    repo = LessonRepository(tmp_path)
    assert set(repo.index()) == {"1_1"}  # системный lesson_id=0 не индексируется


def test_repository_unknown_lesson_raises(tmp_path):
    write_lesson_csv(tmp_path, _lesson_rows_with_id("1_1"), name="Контент_урок_1_1.csv")
    repo = LessonRepository(tmp_path)
    with pytest.raises(LessonNotFoundError):
        repo.messages("7_7")


def test_repository_lazy_load_tolerates_keeper_fail(tmp_path):
    """Урок, не прошедший keeper, ОСТАЁТСЯ в индексе (has=True), но messages() →
    InvalidCSVError (EC-08/F-03). Ленивость: один битый урок не рушит весь каталог."""
    write_lesson_csv(tmp_path, _lesson_rows_with_id("1_1"), name="Контент_урок_1_1.csv")
    # Урок 'bad' структурно читается, но keeper-FAIL (нет обязательных стадий).
    write_lesson_csv(
        tmp_path,
        [lesson_row("only_theory", "theory", text="<b>Тео</b>", lesson_id="bad")],
        name="Контент_урок_bad.csv",
    )
    repo = LessonRepository(tmp_path)
    assert repo.has("bad")  # в индексе
    assert repo.messages("1_1")  # валидный сосед грузится
    with pytest.raises(InvalidCSVError):
        repo.messages("bad")  # битый — только при фактическом запросе


def test_repository_real_content_block1_loads():
    """Реальный content/: 1_1..1_9 индексируются и грузятся (keeper PASS, Блок 1
    закрыт контентно 2026-06-28)."""
    repo = LessonRepository(CONTENT_DIR)
    for n in range(1, 10):
        lesson_id = f"1_{n}"
        assert repo.has(lesson_id)
        assert repo.messages(lesson_id)


# --- Секвенирование (§3.1) ---


def test_find_and_first_of_stage():
    assert find(SEQ, "e1").stage == "example"
    assert find(SEQ, "nope") is None
    assert first_of_stage(SEQ, "training").message_id == "q1"
    assert first_of_stage(SEQ, "main_question").message_id == "mq"
    assert first_of_stage(SEQ, "hook") is None


def test_next_in_stage_within_and_at_boundary():
    assert next_in_stage(SEQ, "t1").message_id == "t2"  # ещё экран theory
    assert next_in_stage(SEQ, "t2") is None  # дальше уже example — стадия исчерпана
    assert next_in_stage(SEQ, "q1").message_id == "q2"


def test_next_message_crosses_stage_boundary():
    assert next_message(SEQ, "t2").message_id == "e1"  # первая строка следующей стадии
    assert next_message(SEQ, "fin") is None  # урок исчерпан


def test_training_remaining():
    assert training_remaining(SEQ, "q1") is True
    assert training_remaining(SEQ, "q2") is True
    assert training_remaining(SEQ, "q3") is False  # последний training-вопрос
    assert training_remaining(SEQ, "t1") is False  # не training-стадия


# --- Судейство (§2.2) ---


def test_judge_correct():
    j = judge(find(SEQ, "q1"), "A")
    assert j.is_correct is True
    assert j.feedback == "ok"
    assert j.return_target is None  # при correct возврата нет


def test_judge_wrong_carries_feedback_and_return():
    j = judge(find(SEQ, "q1"), "B")
    assert j.is_correct is False
    assert j.feedback == "нет"
    assert j.return_target == "t1"  # message.returns[selected]


def test_judge_wrong_without_return_target():
    j = judge(_msg("q", "training", correct="A", a="Да", b="Нет", fb="нет"), "B")
    assert j.is_correct is False
    assert (
        j.return_target is None
    )  # return_b пуст → §3.5 fallback (на стороне fsm_service)


def test_is_valid_option():
    q1 = find(SEQ, "q1")
    assert is_valid_option(q1, "A") is True
    assert is_valid_option(q1, "C") is False  # вариант C пуст


# --- LessonProgress: наличие hook (§3.1-R3 / §4.5-R3) ---


def test_has_hook_and_progress_total():
    assert has_hook(SEQ) is False
    assert progress_total(SEQ) == 5  # текущий контент Блока 1: */5
    with_hook = [_msg("h1", "hook"), *SEQ]
    assert has_hook(with_hook) is True
    assert progress_total(with_hook) == 6
