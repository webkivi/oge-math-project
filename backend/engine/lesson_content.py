"""lesson_content.py — контент урока по lesson_id, секвенирование, судейство.

Источник истины: specs/student_lesson_api_v1.md §2.2 (судейство), §3.1/§3.2
(секвенирование внутри урока), §3.4-bis (единое пространство lesson_id, интерфейс
(II) — ленивый аксессор), §3.1-R3 (авто-проскок lesson_hook при отсутствии стадии
hook). Чистый слой над csv_loader: БД здесь НЕ трогается. Оркестрация с Progress и
FSM-движком — зона fsm_service (следующий слой).

Интерфейс (II) §3.4-bis (решение пункта 1a): `csv_loader.load_lessons_dir` (ключ по
имени файла, all-or-nothing) НЕ меняется. Здесь — ленивый аксессор по lesson_id
(col3, единое пространство): индекс `lesson_id → путь` строится по col3 БЕЗ keeper-
валидации (легаси-урок 1_9, FAIL по §3.3, не блокирует индекс), а keeper прогоняется
только при фактической загрузке конкретного урока (`load_lesson`). Запрос урока,
не прошедшего keeper → InvalidCSVError — это штатный fallback EC-08 / F-03, который
обрабатывает вызывающий слой; срез (1_1..1_8) такие уроки не запрашивает.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from backend.engine.csv_loader import LessonMessage, load_lesson
from tools import keeper

logger = logging.getLogger(__name__)

# Имена стадий (snake_case, контракт CSV/keeper). Подмножество keeper.LESSON_STAGES;
# вынесены константами, чтобы не плодить «магические строки» (CLAUDE.md §4).
STAGE_HOOK = "hook"
STAGE_THEORY = "theory"
STAGE_EXAMPLE = "example"
STAGE_TRAINING = "training"
STAGE_MAIN_QUESTION = "main_question"
STAGE_MAIN_QUESTION_BACKUP = "main_question_backup"
STAGE_FINAL = "final"
STAGE_LESSON_FAILED = "lesson_failed"

# LessonProgress (§4.5/§4.5-R3): шкала из 5 стадий-этапов; при наличии hook — 6.
PROGRESS_STAGES = (
    STAGE_THEORY,
    STAGE_EXAMPLE,
    STAGE_TRAINING,
    STAGE_MAIN_QUESTION,
    STAGE_FINAL,
)


class LessonNotFoundError(Exception):
    """lesson_id отсутствует в каталоге контента (вне единого пространства)."""

    def __init__(self, lesson_id: str) -> None:
        self.lesson_id = lesson_id
        super().__init__(f"урок {lesson_id!r} не найден в каталоге контента")


@dataclass(frozen=True)
class Judgement:
    """Итог серверного судейства ответа (§2.2): верность + feedback + цель возврата."""

    is_correct: bool
    feedback: str  # message.feedbacks[selected]; '' если в CSV пусто
    return_target: (
        str | None
    )  # message.returns[selected] при wrong; None при correct/пусто


class LessonRepository:
    """Ленивый доступ к контенту урока по lesson_id (интерфейс (II), §3.4-bis).

    Индекс `lesson_id → путь` строится по col3 один раз (кэшируется); сообщения
    урока грузятся и кэшируются по запросу. keeper прогоняется только в `load_lesson`.
    """

    def __init__(self, content_dir: str | Path) -> None:
        self._dir = Path(content_dir)
        self._index: dict[str, Path] | None = None
        self._cache: dict[str, list[LessonMessage]] = {}

    def _build_index(self) -> dict[str, Path]:
        index: dict[str, Path] = {}
        for path in sorted(self._dir.glob("*.csv")):
            try:
                rows = keeper.read_rows(path)
            except (UnicodeDecodeError, OSError) as exc:
                # Нечитаемый файл не индексируется (его запрос → LessonNotFoundError);
                # битость поймает keeper при фактической загрузке валидных уроков.
                logger.warning("lesson_content: пропуск %s: %s", path.name, exc)
                continue
            data = [r for r in rows[1:] if len(r) == keeper.N_COLUMNS]
            if not keeper.is_lesson(data):
                continue  # системный контент (lesson_id=0/system) — не урок
            # keeper гарантирует единый lesson_id на файл-урок; берём первую
            # не-системную строку (устойчиво к примеси system-строк).
            lesson_id = next(
                (
                    r[keeper.COL_LESSON_ID]
                    for r in data
                    if r[keeper.COL_LESSON_ID] not in keeper.SYSTEM_LESSON_IDS
                ),
                None,
            )
            if lesson_id is not None:
                index[lesson_id] = path
        return index

    def index(self) -> dict[str, Path]:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def has(self, lesson_id: str) -> bool:
        """Есть ли урок с таким lesson_id в каталоге (без загрузки/валидации)."""
        return lesson_id in self.index()

    def messages(self, lesson_id: str) -> list[LessonMessage]:
        """Сообщения урока по lesson_id. LessonNotFoundError, если урока нет в индексе;
        InvalidCSVError (из load_lesson), если урок не прошёл keeper (EC-08/F-03)."""
        cached = self._cache.get(lesson_id)
        if cached is not None:
            return cached
        index = self.index()
        path = index.get(lesson_id)
        if path is None:
            raise LessonNotFoundError(lesson_id)
        messages = load_lesson(path)
        self._cache[lesson_id] = messages
        return messages


# --- Секвенирование внутри урока (§3.1) — чистые функции над плоским списком ---


def _index_of(messages: list[LessonMessage], message_id: str) -> int | None:
    for i, m in enumerate(messages):
        if m.message_id == message_id:
            return i
    return None


def find(messages: list[LessonMessage], message_id: str) -> LessonMessage | None:
    """Сообщение по message_id (или None)."""
    idx = _index_of(messages, message_id)
    return messages[idx] if idx is not None else None


def first_of_stage(messages: list[LessonMessage], stage: str) -> LessonMessage | None:
    """Первое сообщение указанной стадии в порядке файла (§3.1 п.6: активная строка)."""
    return next((m for m in messages if m.stage == stage), None)


def next_in_stage(
    messages: list[LessonMessage], message_id: str
) -> LessonMessage | None:
    """Следующее сообщение ТОЙ ЖЕ стадии после message_id (§3.1 п.2).

    Стадии контигуальны в порядке файла (keeper-контракт), поэтому «следующее в
    стадии» = следующая строка, если её stage совпадает; иначе стадия исчерпана.
    """
    idx = _index_of(messages, message_id)
    if idx is None or idx + 1 >= len(messages):
        return None
    nxt = messages[idx + 1]
    return nxt if nxt.stage == messages[idx].stage else None


def next_message(
    messages: list[LessonMessage], message_id: str
) -> LessonMessage | None:
    """Следующее сообщение в плоском списке (первая строка следующей стадии на
    последнем экране текущей; §3.1 п.3). None, если урок исчерпан."""
    idx = _index_of(messages, message_id)
    if idx is None or idx + 1 >= len(messages):
        return None
    return messages[idx + 1]


def training_remaining(messages: list[LessonMessage], message_id: str) -> bool:
    """Остались ли training-вопросы после текущего (§3.1 п.4, §3.2).

    Истинно, если текущее сообщение — training И за ним есть ещё training-строка
    до первой не-training строки. Сервер считает это сам (анти-подмена, §2.4).
    """
    cur = find(messages, message_id)
    if cur is None or cur.stage != STAGE_TRAINING:
        return False
    return next_in_stage(messages, message_id) is not None


# --- Серверное судейство ответа (§2.2) — чистое, по CSV ---


def is_valid_option(message: LessonMessage, selected: str) -> bool:
    """selected ∈ непустых вариантов вопроса (§2.2 шаг 3; иначе 422 invalid_option)."""
    return selected in message.options


def judge(message: LessonMessage, selected: str) -> Judgement:
    """Осудить ответ по CSV (§2.2 шаги 4–5). Клиент к сравнению не причастен.

    is_correct = (selected == correct_answer); feedback = feedbacks[selected];
    при wrong — return_target = returns[selected] (None, если в CSV пусто → §3.5).
    """
    is_correct = selected == message.correct_answer
    feedback = message.feedbacks.get(selected, "")
    return_target = None if is_correct else (message.returns.get(selected) or None)
    return Judgement(
        is_correct=is_correct, feedback=feedback, return_target=return_target
    )


# --- LessonProgress: наличие hook и размер шкалы (§3.1-R3, §4.5-R3) ---


def has_hook(messages: list[LessonMessage]) -> bool:
    """Есть ли в уроке стадия hook (§3.1-R3). В текущем контенте Блока 1 — нет →
    fsm_service авто-деривит evt_hook_read на старте, ученик попадает в theory[0]."""
    return any(m.stage == STAGE_HOOK for m in messages)


def progress_total(messages: list[LessonMessage]) -> int:
    """Размер шкалы LessonProgress (§4.5-R3): 6 при наличии hook, иначе 5."""
    return 6 if has_hook(messages) else 5
