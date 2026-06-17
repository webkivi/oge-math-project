"""csv_loader.py — чтение контента уроков из CSV.

Контракт (specs/student_lesson_fsm_v4.md §8): загрузчик отдаёт List[LessonMessage];
если keeper.py-проверка провалилась — поднимает InvalidCSVError, урок не
регистрируется. keeper.py — единственный источник правил парсинга и валидации
байтового/структурного контракта (CLAUDE.md §3), здесь он не дублируется.

Lesson / LessonMessage в БД не хранятся (читаются из CSV) — см. backend/db/models.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from tools import keeper

logger = logging.getLogger(__name__)

# Буквы вариантов в порядке колонок: A→option_a, … (позиция = индекс, §10.2).
ANSWER_LETTERS = ("A", "B", "C", "D")


class InvalidCSVError(Exception):
    """CSV не прошёл keeper.py — урок не загружается."""

    def __init__(self, path: str | Path, errors: list[str]) -> None:
        self.path = str(path)
        self.errors = list(errors)
        detail = "; ".join(self.errors) if self.errors else "нет деталей"
        super().__init__(f"keeper.py отклонил {self.path}: {detail}")


@dataclass(frozen=True)
class LessonMessage:
    """Одно сообщение урока из CSV (specs/student_lesson_fsm_v4.md §1).

    text/feedback — HTML; буквы вариантов — позиционные (A=option_a …).
    """

    lesson_id: str
    message_id: str
    stage: str
    text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_answer: str
    feedback_a: str
    feedback_b: str
    feedback_c: str
    feedback_d: str
    return_a: str
    return_b: str
    return_c: str
    return_d: str

    @property
    def is_question(self) -> bool:
        """Вопрос с вариантами (training/main_question/backup/repeat_*)."""
        return self.stage in keeper.QUESTION_STAGES

    @property
    def options(self) -> dict[str, str]:
        """Непустые варианты ответа: {'A': option_a, …}."""
        raw = (self.option_a, self.option_b, self.option_c, self.option_d)
        return {
            ltr: val
            for ltr, val in zip(ANSWER_LETTERS, raw, strict=True)
            if val.strip()
        }

    @property
    def feedbacks(self) -> dict[str, str]:
        """Непустые обратные связи по буквам: {'A': feedback_a, …}."""
        raw = (self.feedback_a, self.feedback_b, self.feedback_c, self.feedback_d)
        return {
            ltr: val
            for ltr, val in zip(ANSWER_LETTERS, raw, strict=True)
            if val.strip()
        }

    @property
    def returns(self) -> dict[str, str]:
        """Непустые возвраты: {'A': return_a, …} (message_id для return_X)."""
        raw = (self.return_a, self.return_b, self.return_c, self.return_d)
        return {
            ltr: val
            for ltr, val in zip(ANSWER_LETTERS, raw, strict=True)
            if val.strip()
        }


def _row_to_message(row: list[str]) -> LessonMessage:
    return LessonMessage(
        lesson_id=row[2],
        message_id=row[3],
        stage=row[4],
        text=row[5],
        option_a=row[6],
        option_b=row[7],
        option_c=row[8],
        option_d=row[9],
        correct_answer=row[10],
        feedback_a=row[11],
        feedback_b=row[12],
        feedback_c=row[13],
        feedback_d=row[14],
        return_a=row[15],
        return_b=row[16],
        return_c=row[17],
        return_d=row[18],
    )


def load_lesson(path: str | Path) -> list[LessonMessage]:
    """Прочитать и провалидировать один CSV-урок.

    Сначала прогоняет keeper.py; при ошибках — InvalidCSVError (урок не
    регистрируется). Предупреждения keeper (например, мета-урок без example)
    логируются, но не блокируют. Возвращает сообщения в порядке файла.
    """
    path = Path(path)
    result = keeper.check_csv(path)
    if not result.ok:
        raise InvalidCSVError(path, result.errors)
    for warning in result.warnings:
        logger.warning("keeper: %s: %s", path.name, warning)

    rows = keeper.read_rows(path)
    return [_row_to_message(row) for row in rows[1:] if len(row) == keeper.N_COLUMNS]


def load_lessons_dir(content_dir: str | Path) -> dict[str, list[LessonMessage]]:
    """Загрузить все уроки каталога, ключ — имя файла без расширения.

    Системный контент (напоминания, lesson_id=0/system) пропускается — это не
    уроки. Любой урок, отклонённый keeper.py, пробрасывает InvalidCSVError.
    Разрешение идентичности урока в курсе — забота FSM-движка (пункт 3).
    """
    content_dir = Path(content_dir)
    lessons: dict[str, list[LessonMessage]] = {}
    for csv_path in sorted(content_dir.glob("*.csv")):
        # check_csv не бросает исключений (битый/не-UTF8 файл → ошибки в result);
        # сначала валидируем, потом читаем — никакого голого UnicodeDecodeError.
        result = keeper.check_csv(csv_path)
        if not result.ok:
            raise InvalidCSVError(csv_path, result.errors)
        for warning in result.warnings:
            logger.warning("keeper: %s: %s", csv_path.name, warning)

        rows = keeper.read_rows(csv_path)
        data = [r for r in rows[1:] if len(r) == keeper.N_COLUMNS]
        if not keeper.is_lesson(data):
            continue  # системный контент (напоминания) — не урок
        lessons[csv_path.stem] = [_row_to_message(row) for row in data]
    return lessons
