"""test_keeper.py — тесты Хранителя CSV (tools/keeper.py).

Покрывают каждую проверку контракта (Methodology §3.7/§10–11, CLAUDE.md §3):
байтовые (BOM/CRLF), структурные (19 колонок, lesson_id без точек, HTML-парность,
эмодзи whitelist/blacklist), стадии, correct_answer, return_X. Плюс регрессия на
реальном контенте: все content/*.csv (включая 1.9, принят 2026-06-28) должны быть
PASS; 1.9 несёт WARN мета-урока (нет стадии example — ожидаемо для архетипа).
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from backend.tests.conftest import (
    CONTENT_DIR,
    lesson_row,
    valid_lesson_rows,
    write_lesson_csv,
)
from tools import keeper


def _errors(tmp_path, rows, **kwargs) -> list[str]:
    path = write_lesson_csv(tmp_path, rows, **kwargs)
    return keeper.check_csv(path).errors


# --- Регрессия: реальный контент проходит ---


LESSON_1_9 = CONTENT_DIR / "Контент_урок_1_9.csv"


def _content_files() -> list[str]:
    return sorted(glob.glob(str(CONTENT_DIR / "*.csv")))


@pytest.mark.parametrize("path", _content_files())
def test_real_content_passes_keeper(path):
    """Все реальные CSV (1.1–1.9 + напоминания) — PASS. Блок 1 закрыт контентно."""
    res = keeper.check_csv(Path(path))
    assert res.ok, f"{path}: {res.errors}"


def test_lesson_1_9_keeps_meta_lesson_warning():
    """Урок 1.9 (мета-урок, принят 2026-06-28) — PASS, но несёт WARN об отсутствии
    стадии example: ожидаемо для архетипа «мета» (нет отдельного примера —
    задачи вперемешку и есть содержание урока)."""
    res = keeper.check_csv(LESSON_1_9)
    assert res.ok
    assert any("example" in w for w in res.warnings)


def test_baseline_valid_lesson_is_clean(tmp_path):
    path = write_lesson_csv(tmp_path, valid_lesson_rows())
    res = keeper.check_csv(path)
    assert res.ok and res.warnings == []


# --- Байтовые проверки ---


def test_missing_bom_rejected(tmp_path):
    errs = _errors(tmp_path, valid_lesson_rows(), bom=False)
    assert any("BOM" in e for e in errs)


def test_bare_lf_rejected(tmp_path):
    errs = _errors(tmp_path, valid_lesson_rows(), newline="\n")
    assert any("LF" in e for e in errs)


def test_raw_newline_in_cell_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[0][5] = "строка1\nстрока2"  # сырой перенос вместо <br>
    errs = _errors(tmp_path, rows)
    assert any("сырой перенос" in e for e in errs)


# --- Структура колонок ---


def test_wrong_column_count_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows.append(["", "", "1", "m_extra", "theory"])  # 5 колонок
    errs = _errors(tmp_path, rows)
    assert any("колонок" in e for e in errs)


def test_bad_header_rejected(tmp_path):
    rows = valid_lesson_rows()
    errs = _errors(tmp_path, rows, include_header=False)  # нет строки заголовка
    # первая строка данных встанет на место заголовка → несоответствие контракту
    assert any("заголов" in e for e in errs)


def test_lesson_id_with_dot_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[0][2] = "1.1"
    errs = _errors(tmp_path, rows)
    assert any("точку" in e for e in errs)


# --- HTML и эмодзи ---


def test_unbalanced_html_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[0][5] = "<b>без закрытия"
    errs = _errors(tmp_path, rows)
    assert any("<b>" in e and "непарный" in e for e in errs)


def test_blacklist_emoji_rejected_in_lesson(tmp_path):
    rows = valid_lesson_rows()
    rows[0][5] = "плохо ❌"
    errs = _errors(tmp_path, rows)
    assert any("запрещённый" in e for e in errs)


def test_whitelist_violation_rejected_in_lesson(tmp_path):
    rows = valid_lesson_rows()
    rows[0][5] = "привет 🙂"  # не из whitelist уроков
    errs = _errors(tmp_path, rows)
    assert any("whitelist" in e for e in errs)


def test_whitelist_not_enforced_for_system_content(tmp_path):
    """Системный контент (lesson_id=0): 🙂 допустим, whitelist уроков не действует."""
    rows = [
        lesson_row("trigger_x", "trigger", text="Привет 🙂", lesson_id="0"),
        lesson_row("streak_y", "streak", text="💙 Счёт сброшен.", lesson_id="0"),
    ]
    errs = _errors(tmp_path, rows)
    assert errs == []


def test_blacklist_emoji_rejected_in_system_too(tmp_path):
    rows = [lesson_row("trigger_x", "trigger", text="плохо ❌", lesson_id="0")]
    errs = _errors(tmp_path, rows)
    assert any("запрещённый" in e for e in errs)


def test_flag_reported_once(tmp_path):
    """Флаг (пара regional indicators) даёт ровно одно сообщение об ошибке."""
    rows = valid_lesson_rows()
    rows[0][5] = "флаг 🇷🇺 тут"
    errs = _errors(tmp_path, rows)
    flag_errs = [e for e in errs if "флаг" in e]
    assert len(flag_errs) == 1


# --- Стадии ---


def test_unknown_stage_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows.append(lesson_row("m_weird", "weird_stage"))
    errs = _errors(tmp_path, rows)
    assert any("неизвестная stage" in e for e in errs)


def test_missing_required_stage_rejected(tmp_path):
    rows = [r for r in valid_lesson_rows() if r[4] != "final"]
    errs = _errors(tmp_path, rows)
    assert any("обязательная stage: final" in e for e in errs)


def test_missing_example_is_warning_not_error(tmp_path):
    rows = [r for r in valid_lesson_rows() if r[4] != "example"]
    path = write_lesson_csv(tmp_path, rows)
    res = keeper.check_csv(path)
    assert res.ok
    assert any("example" in w for w in res.warnings)


# --- correct_answer ---


def test_correct_answer_invalid_letter_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[2][10] = "X"  # m_train (training) — невалидная буква
    errs = _errors(tmp_path, rows)
    assert any("не из A/B/C/D" in e for e in errs)


def test_correct_answer_points_to_empty_option_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[2][10] = "C"  # option_c пуст
    rows[2][17] = ""  # return_c пуст, чтобы не словить «return верного непуст»
    errs = _errors(tmp_path, rows)
    assert any("пуст" in e for e in errs)


def test_correct_answer_on_non_question_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[0][10] = "A"  # m_theory — не вопрос
    errs = _errors(tmp_path, rows)
    assert any("у не-вопроса" in e for e in errs)


def test_return_of_correct_answer_must_be_empty(tmp_path):
    rows = valid_lesson_rows()
    rows[2][15] = "m_theory"  # return_a при correct_answer=A
    errs = _errors(tmp_path, rows)
    assert any("верного ответа должен быть пуст" in e for e in errs)


# --- return_X ---


def test_dangling_return_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[2][16] = "no_such_message"  # return_b
    errs = _errors(tmp_path, rows)
    assert any("нет message_id" in e for e in errs)


def test_self_reference_return_rejected(tmp_path):
    rows = valid_lesson_rows()
    rows[2][16] = "m_train"  # return_b ссылается на собственный message_id
    errs = _errors(tmp_path, rows)
    assert any("сам на себя" in e for e in errs)


# --- §3.3 распределение букв ответов ---


def _lesson_with_training(answers: list[str]) -> list[list[str]]:
    """Урок с несколькими тренировочными вопросами и заданными верными буквами."""
    rows: list[list[str]] = []
    inserted = False
    for row in valid_lesson_rows():
        if row[4] == "training":
            if not inserted:
                for i, ans in enumerate(answers):
                    # return вешаем на НЕверную опцию (у верной return пуст, §10.3).
                    wrong_is_a = ans != "A"
                    rows.append(
                        lesson_row(
                            f"m_t{i}",
                            "training",
                            text="✏️ Вопрос.",
                            option_a="Да",
                            option_b="Нет",
                            correct_answer=ans,
                            feedback_a="✅",
                            feedback_b="Нет.",
                            return_a="m_theory" if wrong_is_a else "",
                            return_b="" if wrong_is_a else "m_theory",
                        )
                    )
                inserted = True
            continue  # пропустить исходную единственную training-строку
        rows.append(row)
    return rows


def test_three_same_answers_in_one_stage_rejected(tmp_path):
    """3 одинаковых верных подряд в тренировке (один заход) — FAIL (§3.3, Вариант 1)."""
    errs = _errors(tmp_path, _lesson_with_training(["A", "A", "A"]))
    assert any("§3.3" in e for e in errs)


def test_two_same_answers_in_one_stage_ok(tmp_path):
    """2 одинаковых подряд — допустимо (граница §3.3)."""
    path = write_lesson_csv(tmp_path, _lesson_with_training(["A", "A", "B"]))
    res = keeper.check_csv(path)
    assert res.ok, res.errors


def test_same_answers_across_different_stages_not_flagged(tmp_path):
    """Одинаковые ответы на стыке разных стадий — разные заходы, не нарушение.

    Базовый валидный урок: main_question=A и repeat_1h/2/3=A (5 раз A подряд во
    флэт-последовательности, но по одной на стадию) — PASS.
    """
    path = write_lesson_csv(tmp_path, valid_lesson_rows())
    res = keeper.check_csv(path)
    assert res.ok, res.errors
