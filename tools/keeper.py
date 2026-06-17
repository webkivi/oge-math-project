#!/usr/bin/env python3
"""keeper.py — Хранитель CSV-контента (Агент 5, детерминированный шлюз).

Стережёт байтовый и структурный контракт CSV уроков ДО попадания в движок
(Methodology §3.7 «CSV-структура», §10–11; CLAUDE.md §3; Project Brain §6).
Источник истины по контракту — Methodology / Brain; менять контракт только
через А3 → А4 → этот файл (CLAUDE.md §3), не молча в коде.

Проверки (для лесон-файлов — полный набор; для системного контента, напр.
напоминаний с lesson_id=0/system — только байтовые/общие):
  Байтовые/общие (любой CSV):
    1. UTF-8 с BOM.
    2. Переводы строк — CRLF (нет «голых» LF).
    3. Ровно 19 колонок в каждой строке; заголовок — канонический.
    4. lesson_id (колонка 3) без точек.
    5. Нет «сырых» переносов внутри ячеек (только <br>).
    6. Парность HTML-тегов (b/i/code/s/u) в текстовых колонках.
    7. Эмодзи — из whitelist; запрещённые (blacklist/флаги) отклоняются.
  Структура урока (только лесон-файлы):
    8. stage — из известного набора стадий урока.
    9. correct_answer для вопросов — буква A/B/C/D, и она указывает на
       непустую опцию; у не-вопросов correct_answer пуст.
   10. return_X ссылается на существующий message_id того же урока; нет
       висячих ссылок и самоссылок (петля).
   11. Наличие обязательных стадий: theory, training, main_question, final,
       repeat_1h, repeat_evening, repeat_morning (Methodology §11).
   12. Распределение букв (§3.3, §8.2): в одном «заходе» — не более 2 одинаковых
       верных ответов подряд. Заход = последовательность подряд идущих вопросов
       ОДНОЙ стадии (training / main_question / repeat_*). Одинаковые ответы на
       стыке РАЗНЫХ стадий — это разные заходы, не нарушение (решение фаундера
       2026-06-17, Вариант 1; §8.2 обязывает keeper стеречь распределение букв).

Вход: путь к .csv. Выход: PASS / список ошибок (+ предупреждения).
Код возврата: 0 (PASS, в т.ч. с warnings) или 1 (FAIL). Только stdlib.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --- Контракт колонок (Methodology §10.1, CLAUDE.md §3) ---
N_COLUMNS = 19
EXPECTED_HEADER = [
    "ID", "ID", "lesson_id", "message_id", "stage", "text",
    "option_a", "option_b", "option_c", "option_d", "correct_answer",
    "feedback_a", "feedback_b", "feedback_c", "feedback_d",
    "return_a", "return_b", "return_c", "return_d",
]  # fmt: skip

COL_LESSON_ID = 2
COL_MESSAGE_ID = 3
COL_STAGE = 4
COL_CORRECT = 10
OPTION_COLS = {"A": 6, "B": 7, "C": 8, "D": 9}
RETURN_COLS = {"A": 15, "B": 16, "C": 17, "D": 18}
# Текстовые колонки, где допустим HTML и эмодзи: text, option_a..d, feedback_a..d.
TEXT_COLS = (5, 6, 7, 8, 9, 11, 12, 13, 14)

# --- Стадии урока (Methodology §11; specs/student_lesson_fsm_v4.md §1) ---
LESSON_STAGES = frozenset(
    {
        "theory", "example", "training", "main_question", "main_question_backup",
        "final", "lesson_failed", "repeat_1h", "repeat_evening", "repeat_morning",
    }
)  # fmt: skip
# Вопросы (есть correct_answer + опции): тренировка, главный/резервный вопрос
# и повторения R1/R2/R3 — это active recall (Methodology §11, факт CSV).
QUESTION_STAGES = frozenset(
    {
        "training", "main_question", "main_question_backup",
        "repeat_1h", "repeat_evening", "repeat_morning",
    }
)  # fmt: skip
# Обязательные стадии (Methodology §11 «как минимум один каждого»).
REQUIRED_STAGES = frozenset(
    {
        "theory", "training", "main_question", "final",
        "repeat_1h", "repeat_evening", "repeat_morning",
    }
)  # fmt: skip
# Рекомендуемые: их отсутствие — WARN, не ошибка (1.9 — мета-урок без example).
RECOMMENDED_STAGES = frozenset({"example", "main_question_backup", "lesson_failed"})

# lesson_id системного контента — структурные проверки урока к нему не применяются.
SYSTEM_LESSON_IDS = frozenset({"0", "system"})

VALID_ANSWERS = frozenset({"A", "B", "C", "D"})
HTML_TAGS = ("b", "i", "code", "s", "u")
# §3.3: не более 2 одинаковых верных ответов подряд в одном заходе (3-й подряд → FAIL).
MAX_SAME_ANSWERS_IN_A_ROW = 2

# --- Эмодзи (Methodology «Эмодзи и символы») ---
# Базовые кодпойнты без variation selector; whitelist из таблицы методологии.
ALLOWED_EMOJI = frozenset(
    "✅\U0001f4a1\U0001f447⚡\U0001f3af\U0001f525\U0001f4da"
    "\U0001f914✏\U0001f4ca\U0001f9ee\U0001f393✓⏰\U0001f4aa☀"
)  # ✅💡👇⚡🎯🔥📚🤔✏📊🧮🎓✓⏰💪☀
BLACKLIST_EMOJI = frozenset(
    "❌\U0001f622\U0001f97a\U0001f62d\U0001f44d\U0001f44f\U0001f389"
    "\U0001f4f1\U0001f4bb\U0001f310"
)  # ❌😢🥺😭👍👏🎉📱💻🌐
# Модификаторы/служебные — не считаем самостоятельными эмодзи.
_EMOJI_MODIFIERS = frozenset("️︎‍⃣")
_SKIN_TONES = range(0x1F3FB, 0x1F3FF + 1)
_REGIONAL = range(0x1F1E6, 0x1F1FF + 1)  # индикаторы стран → флаги (blacklist)
_EMOJI_RANGES = (
    (0x2300, 0x23FF), (0x2600, 0x26FF), (0x2700, 0x27BF),
    (0x2B00, 0x2BFF), (0x1F000, 0x1FAFF),
)  # fmt: skip


@dataclass
class KeeperResult:
    """Итог проверки одного CSV."""

    path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _is_emoji_char(ch: str) -> bool:
    code = ord(ch)
    if code in _REGIONAL:
        return True
    return any(lo <= code <= hi for lo, hi in _EMOJI_RANGES)


def _parse_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text), delimiter=";", quotechar='"'))


def read_rows(path: Path) -> list[list[str]]:
    """Прочитать CSV (UTF-8 BOM, разделитель ';') в список строк-списков."""
    return _parse_rows(path.read_bytes().decode("utf-8-sig"))


def _check_bytes(raw: bytes, res: KeeperResult) -> None:
    """BOM и CRLF на уровне байт (Methodology §3.7, CLAUDE.md §3)."""
    if not raw.startswith(b"\xef\xbb\xbf"):
        res.errors.append("нет UTF-8 BOM в начале файла")
    bare_lf = raw.count(b"\n") - raw.count(b"\r\n")
    if bare_lf > 0:
        res.errors.append(f"найдены «голые» LF без CR ({bare_lf}); требуется CRLF")


def _check_header(rows: list[list[str]], res: KeeperResult) -> None:
    if not rows:
        res.errors.append("файл пуст")
        return
    header = rows[0]
    if len(header) != N_COLUMNS:
        res.errors.append(f"в заголовке {len(header)} колонок, ожидалось {N_COLUMNS}")
    elif header != EXPECTED_HEADER:
        res.errors.append(f"заголовок не соответствует контракту: {header}")


def _check_html_parity(cell: str, msg_id: str, res: KeeperResult) -> None:
    for tag in HTML_TAGS:
        opens = len(re.findall(rf"<{tag}>", cell))
        closes = len(re.findall(rf"</{tag}>", cell))
        if opens != closes:
            res.errors.append(
                f"msg={msg_id}: тег <{tag}> непарный ({opens} vs {closes})"
            )


def _check_emoji(
    cell: str, msg_id: str, res: KeeperResult, enforce_whitelist: bool
) -> None:
    """Blacklist (флаги/запрещённые) — всегда; whitelist — только для уроков.

    Системный контент (напоминания) в тоне «старший товарищ» использует более
    широкий дружелюбный набор (👋🙂💙); whitelist уроков к нему не применяется.
    """
    prev_regional = False
    for ch in cell:
        code = ord(ch)
        if ch in _EMOJI_MODIFIERS or code in _SKIN_TONES:
            continue
        if code in _REGIONAL:
            # Флаг = пара regional indicators; сообщаем один раз на серию.
            if not prev_regional:
                res.errors.append(
                    f"msg={msg_id}: запрещённый флаг (regional indicator)"
                )
            prev_regional = True
            continue
        prev_regional = False
        if not _is_emoji_char(ch):
            continue
        if ch in BLACKLIST_EMOJI:
            res.errors.append(
                f"msg={msg_id}: запрещённый эмодзи/символ {ch!r} (U+{code:04X})"
            )
        elif enforce_whitelist and ch not in ALLOWED_EMOJI:
            res.errors.append(
                f"msg={msg_id}: эмодзи {ch!r} (U+{code:04X}) вне whitelist"
            )


def _check_row_cells(
    row: list[str], idx: int, res: KeeperResult, enforce_whitelist: bool
) -> None:
    """Проверки ячеек строки (любой CSV): сырые переносы, HTML, эмодзи."""
    msg_id = row[COL_MESSAGE_ID] if len(row) > COL_MESSAGE_ID else f"строка {idx}"
    for col in TEXT_COLS:
        if col >= len(row):
            continue
        cell = row[col]
        if "\n" in cell or "\r" in cell:
            res.errors.append(
                f"msg={msg_id}: сырой перенос строки в ячейке (нужен <br>)"
            )
        _check_html_parity(cell, msg_id, res)
        _check_emoji(cell, msg_id, res, enforce_whitelist)


def is_lesson(data: list[list[str]]) -> bool:
    """Учебный файл? (есть строки с lesson_id вне системного набора)."""
    ids = {r[COL_LESSON_ID] for r in data if len(r) > COL_LESSON_ID}
    return bool(ids - SYSTEM_LESSON_IDS)


def _check_lesson_structure(data: list[list[str]], res: KeeperResult) -> None:
    """Структурные проверки урока: стадии, correct_answer, return_X."""
    message_ids = {r[COL_MESSAGE_ID] for r in data if len(r) > COL_MESSAGE_ID}
    stages_present: set[str] = set()

    for r in data:
        if len(r) < N_COLUMNS:
            continue
        msg_id = r[COL_MESSAGE_ID]
        stage = r[COL_STAGE]
        stages_present.add(stage)

        if stage not in LESSON_STAGES:
            res.errors.append(f"msg={msg_id}: неизвестная stage {stage!r}")

        ca = r[COL_CORRECT].strip()
        if stage in QUESTION_STAGES:
            if ca not in VALID_ANSWERS:
                res.errors.append(
                    f"msg={msg_id}: correct_answer {ca!r} не из A/B/C/D для вопроса"
                )
            elif not r[OPTION_COLS[ca]].strip():
                res.errors.append(
                    f"msg={msg_id}: correct_answer={ca}, но option_{ca.lower()} пуст"
                )
            elif r[RETURN_COLS[ca]].strip():
                res.errors.append(
                    f"msg={msg_id}: return_{ca.lower()} верного ответа должен быть пуст"
                )
        elif ca:
            res.errors.append(
                f"msg={msg_id}: correct_answer {ca!r} у не-вопроса (stage={stage})"
            )

        for letter, col in RETURN_COLS.items():
            target = r[col].strip()
            if not target:
                continue
            if target == msg_id:
                res.errors.append(
                    f"msg={msg_id}: return_{letter.lower()} ссылается сам на себя"
                )
            elif target not in message_ids:
                res.errors.append(
                    f"msg={msg_id}: return_{letter.lower()}={target!r} — нет message_id"
                )

    for stage in sorted(REQUIRED_STAGES - stages_present):
        res.errors.append(f"отсутствует обязательная stage: {stage}")
    for stage in sorted(RECOMMENDED_STAGES - stages_present):
        res.warnings.append(f"нет рекомендуемой stage: {stage}")

    _check_answer_distribution(data, res)


def _check_answer_distribution(data: list[list[str]], res: KeeperResult) -> None:
    """§3.3: в одном заходе не более 2 одинаковых верных ответов подряд.

    Заход = подряд идущие строки-вопросы ОДНОЙ стадии. На стыке разных стадий
    (например, A на repeat_1h и A на repeat_evening) — это разные заходы, не
    нарушение (решение фаундера 2026-06-17, Вариант 1).
    """
    run_stage: str | None = None
    run_answers: list[str] = []

    def flush() -> None:
        streak = 1
        for i in range(1, len(run_answers)):
            streak = streak + 1 if run_answers[i] == run_answers[i - 1] else 1
            if streak > MAX_SAME_ANSWERS_IN_A_ROW:
                res.errors.append(
                    f"stage {run_stage}: {streak} одинаковых ответов "
                    f"{run_answers[i]!r} подряд в одном заходе (макс "
                    f"{MAX_SAME_ANSWERS_IN_A_ROW}, §3.3)"
                )
                return  # одной ошибки на заход достаточно

    for r in data:
        stage = r[COL_STAGE]
        ans = r[COL_CORRECT].strip()
        is_q = stage in QUESTION_STAGES and ans in VALID_ANSWERS
        if is_q and stage == run_stage:
            run_answers.append(ans)
        else:
            flush()
            run_stage = stage if is_q else None
            run_answers = [ans] if is_q else []
    flush()


def check_csv(path: Path) -> KeeperResult:
    """Полная проверка одного CSV-файла. Возвращает KeeperResult (errors/warnings)."""
    res = KeeperResult(path=str(path))
    try:
        raw = path.read_bytes()
    except OSError as exc:
        res.errors.append(f"не удалось прочитать файл: {exc}")
        return res

    _check_bytes(raw, res)
    try:
        rows = _parse_rows(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, csv.Error) as exc:
        res.errors.append(f"не удалось распарсить CSV: {exc}")
        return res

    _check_header(rows, res)
    data = rows[1:]
    valid_rows = [r for r in data if len(r) == N_COLUMNS]
    lesson = bool(valid_rows) and is_lesson(valid_rows)

    for i, row in enumerate(data, start=2):  # +2: 1-based + строка заголовка
        if len(row) != N_COLUMNS:
            res.errors.append(f"строка {i}: {len(row)} колонок, ожидалось {N_COLUMNS}")
            continue
        if "." in row[COL_LESSON_ID]:
            res.errors.append(
                f"строка {i}: lesson_id {row[COL_LESSON_ID]!r} содержит точку"
            )
        _check_row_cells(row, i, res, enforce_whitelist=lesson)

    if lesson:
        _check_lesson_structure(valid_rows, res)
    return res


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print("использование: python tools/keeper.py <lesson.csv>", file=sys.stderr)
        return 0 if argv[1:] in (["-h"], ["--help"]) else 2
    path = Path(argv[1])
    if not path.exists():
        print(f"файл не найден: {path}", file=sys.stderr)
        return 2

    res = check_csv(path)
    for w in res.warnings:
        print(f"[warn] {w}", file=sys.stderr)
    if res.errors:
        print(f"keeper.py FAIL ({len(res.errors)}) для {path}:", file=sys.stderr)
        for e in res.errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"keeper.py PASS: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
