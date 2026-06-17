"""conftest.py — общие фикстуры тестов бэкенда.

БД для тестов — изолированный in-memory SQLite на каждый тест, со включённым
enforcement внешних ключей (как в проде), чтобы проверять каскадное удаление.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.config import SESSION_TTL_DAYS
from backend.db.database import Base, make_engine
from backend.db.models import EnrollmentReason, StudentProfile, User, UserRole
from tools.keeper import EXPECTED_HEADER

# Каталог реального контента (для регрессионных тестов keeper/loader).
CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


@pytest.fixture()
def db() -> Iterator[Session]:
    """Свежая in-memory БД и сессия на каждый тест.

    make_engine сам навешивает FK-listener для SQLite — дублировать не нужно.
    StaticPool держит одно соединение, чтобы in-memory БД жила весь тест.
    """
    engine = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_student(
    db: Session,
    *,
    name: str = "Иван",
    grade: int = 9,
    onboarding_session_id: str | None = "onb-1",
    consent_cohort_flag: bool = False,
) -> User:
    """Фабрика зарегистрированного ученика с профилем (минимальный валидный набор)."""
    now = datetime.now(UTC)
    user = User(
        role=UserRole.STUDENT,
        name=name,
        grade=grade,
        pd_consent_at=now,
        pd_consent_version="v1",
        consent_cohort_flag=consent_cohort_flag,
        onboarding_session_id=onboarding_session_id,
    )
    user.profile = StudentProfile(
        current_lesson_id="1_1",
        fsm_state="registered",
        enrollment_reason=(
            EnrollmentReason.GRADE9_DIRECT
            if grade == 9
            else EnrollmentReason.GRADE10PLUS_RETAKE
        ),
    )
    db.add(user)
    db.flush()
    return user


def session_expiry(now: datetime | None = None) -> datetime:
    """Срок жизни сессии = now + SESSION_TTL_DAYS (контракт auth→Session, v4 §8)."""
    base = now or datetime.now(UTC)
    return base + timedelta(days=SESSION_TTL_DAYS)


# --- CSV-фабрика для тестов keeper / csv_loader ---


def lesson_row(
    message_id: str,
    stage: str,
    *,
    text: str = "<b>текст</b>",
    lesson_id: str = "1",
    option_a: str = "",
    option_b: str = "",
    option_c: str = "",
    option_d: str = "",
    correct_answer: str = "",
    feedback_a: str = "",
    feedback_b: str = "",
    feedback_c: str = "",
    feedback_d: str = "",
    return_a: str = "",
    return_b: str = "",
    return_c: str = "",
    return_d: str = "",
) -> list[str]:
    """Собрать одну строку CSV (19 колонок) в порядке контракта."""
    return [
        "", "", lesson_id, message_id, stage, text,
        option_a, option_b, option_c, option_d, correct_answer,
        feedback_a, feedback_b, feedback_c, feedback_d,
        return_a, return_b, return_c, return_d,
    ]  # fmt: skip


def serialize_csv(
    rows: list[list[str]],
    *,
    bom: bool = True,
    newline: str = "\r\n",
    include_header: bool = True,
) -> bytes:
    """Сериализовать строки в байты CSV (по умолчанию: UTF-8 BOM + CRLF + ';')."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quotechar='"', lineterminator=newline)
    if include_header:
        writer.writerow(EXPECTED_HEADER)
    writer.writerows(rows)
    payload = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" if bom else b"") + payload


def write_lesson_csv(
    tmp_path: Path, rows: list[list[str]], *, name: str = "lesson.csv", **kwargs
) -> Path:
    """Записать CSV во временный файл и вернуть путь."""
    path = Path(tmp_path) / name
    path.write_bytes(serialize_csv(rows, **kwargs))
    return path


def valid_lesson_rows() -> list[list[str]]:
    """Свежая копия минимального валидного урока (все стадии, 0 предупреждений)."""
    return [
        lesson_row("m_theory", "theory", text="<b>Теория.</b> 💡 Идея."),
        lesson_row("m_example", "example", text="Пример расчёта."),
        lesson_row(
            "m_train",
            "training",
            text="✏️ Вопрос 1.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅ Верно.",
            feedback_b="Подумай ещё.",
            return_b="m_theory",
        ),
        lesson_row(
            "m_main",
            "main_question",
            text="🎯 Главный вопрос.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅ Верно.",
            feedback_b="Нет.",
            return_b="m_theory",
        ),
        lesson_row(
            "m_backup",
            "main_question_backup",
            text="Резервный вопрос.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅",
            feedback_b="Нет.",
            return_b="m_theory",
        ),
        lesson_row("m_final", "final", text="🎓 День 1 ✓"),
        lesson_row("m_failed", "lesson_failed", text="Вернёмся завтра."),
        lesson_row(
            "m_r1",
            "repeat_1h",
            text="⏰ Повтор.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅",
            feedback_b="Нет.",
            return_b="m_theory",
        ),
        lesson_row(
            "m_r2",
            "repeat_evening",
            text="Вечерний повтор.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅",
            feedback_b="Нет.",
            return_b="m_theory",
        ),
        lesson_row(
            "m_r3",
            "repeat_morning",
            text="☀️ Утро.",
            option_a="Да",
            option_b="Нет",
            correct_answer="A",
            feedback_a="✅",
            feedback_b="Нет.",
            return_b="m_theory",
        ),
    ]
