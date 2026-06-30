"""test_csv_loader.py — тесты движка чтения CSV (backend/engine/csv_loader.py).

Проверяют контракт specs/student_lesson_fsm_v4.md §8: загрузчик отдаёт
List[LessonMessage]; при провале keeper.py — InvalidCSVError; предупреждения
keeper не блокируют загрузку.
"""

from __future__ import annotations

import logging

import pytest

from backend.engine.csv_loader import (
    InvalidCSVError,
    LessonMessage,
    load_lesson,
    load_lessons_dir,
)
from backend.tests.conftest import (
    CONTENT_DIR,
    lesson_row,
    valid_lesson_rows,
    write_lesson_csv,
)

LESSON_1_1 = CONTENT_DIR / "Контент_урок_1_1.csv"
LESSON_1_9 = CONTENT_DIR / "Контент_урок_1_9.csv"


def test_load_lesson_returns_messages(tmp_path):
    path = write_lesson_csv(tmp_path, valid_lesson_rows())
    messages = load_lesson(path)
    assert all(isinstance(m, LessonMessage) for m in messages)
    assert [m.message_id for m in messages][:2] == ["m_theory", "m_example"]
    assert len(messages) == len(valid_lesson_rows())


def test_load_real_lesson_1_1():
    messages = load_lesson(LESSON_1_1)
    assert len(messages) >= 10
    first = messages[0]
    assert first.lesson_id == "1_1"  # уникальный lesson_id (api §3.4-bis)
    assert first.stage == "theory"
    assert "<" in first.text  # HTML-разметка сохранена


def test_lesson_message_question_helpers(tmp_path):
    path = write_lesson_csv(tmp_path, valid_lesson_rows())
    messages = load_lesson(path)
    by_id = {m.message_id: m for m in messages}

    train = by_id["m_train"]
    assert train.is_question is True
    assert train.correct_answer == "A"
    assert train.options == {"A": "Да", "B": "Нет"}
    assert train.returns == {"B": "m_theory"}  # return верного (A) пуст
    assert set(train.feedbacks) == {"A", "B"}

    theory = by_id["m_theory"]
    assert theory.is_question is False
    assert theory.options == {}


def test_load_lesson_raises_on_invalid_csv(tmp_path):
    path = write_lesson_csv(tmp_path, valid_lesson_rows(), bom=False)
    with pytest.raises(InvalidCSVError) as exc:
        load_lesson(path)
    assert exc.value.errors  # причины проброшены
    assert "BOM" in str(exc.value)


def test_load_lesson_warns_but_loads_when_only_warning(tmp_path, caplog):
    """Урок без example (только WARN) грузится; предупреждение логируется."""
    rows = [r for r in valid_lesson_rows() if r[4] != "example"]
    path = write_lesson_csv(tmp_path, rows)
    with caplog.at_level(logging.WARNING):
        messages = load_lesson(path)
    assert messages
    assert any("example" in rec.message for rec in caplog.records)


def test_load_real_lesson_1_9():
    """1.9 принят 2026-06-28 (§3.3 закрыт) — мета-урок грузится без InvalidCSVError."""
    messages = load_lesson(LESSON_1_9)
    assert len(messages) >= 10
    assert messages[0].lesson_id == "1_9"


def test_load_lessons_dir_skips_system_and_loads_lessons(tmp_path):
    """Каталог: грузит уроки, пропускает системный контент (напоминания)."""
    write_lesson_csv(tmp_path, valid_lesson_rows(), name="Контент_урок_A.csv")
    write_lesson_csv(tmp_path, valid_lesson_rows(), name="Контент_урок_B.csv")
    # Системный файл (lesson_id=0) — должен быть пропущен.
    write_lesson_csv(
        tmp_path,
        [lesson_row("trigger_x", "trigger", text="Привет 🙂", lesson_id="0")],
        name="Контент_напоминания.csv",
    )
    lessons = load_lessons_dir(tmp_path)
    assert set(lessons) == {"Контент_урок_A", "Контент_урок_B"}
    assert all(isinstance(v, list) and v for v in lessons.values())


def test_load_lessons_dir_real_content_all_pass():
    """Реальный content/ — грузятся все lesson-CSV, системный файл не попадает в lessons."""
    lessons = load_lessons_dir(CONTENT_DIR)
    expected = {
        path.stem for path in CONTENT_DIR.glob("Контент_урок_*.csv") if path.is_file()
    }
    assert set(lessons) == expected
    assert "Контент_напоминания" not in lessons
    assert "Контент_урок_1_9" in lessons


def test_load_lessons_dir_raises_on_invalid_lesson(tmp_path):
    """Каталог с одним невалидным уроком (§3.3) → fail-fast InvalidCSVError."""
    write_lesson_csv(tmp_path, valid_lesson_rows(), name="Контент_урок_ok.csv")
    bad_rows = [
        lesson_row("th1", "theory"),
        lesson_row(
            "tq1",
            "training",
            correct_answer="A",
            option_a="Да",
            option_b="Нет",
            feedback_a="ok",
            feedback_b="no",
        ),
        lesson_row(
            "tq2",
            "training",
            correct_answer="A",
            option_a="Да",
            option_b="Нет",
            feedback_a="ok",
            feedback_b="no",
        ),
        lesson_row(
            "tq3",
            "training",
            correct_answer="A",
            option_a="Да",
            option_b="Нет",
            feedback_a="ok",
            feedback_b="no",
        ),
    ]
    write_lesson_csv(tmp_path, bad_rows, name="Контент_урок_bad.csv")
    with pytest.raises(InvalidCSVError):
        load_lessons_dir(tmp_path)


def test_load_lessons_dir_non_utf8_file_raises_invalid_csv(tmp_path):
    """Не-UTF8 файл в каталоге → InvalidCSVError (§8), не голый UnicodeDecodeError."""
    bad = tmp_path / "Контент_урок_bad.csv"
    bad.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81;;;")
    with pytest.raises(InvalidCSVError):
        load_lessons_dir(tmp_path)
