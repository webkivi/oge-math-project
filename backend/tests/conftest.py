"""conftest.py — общие фикстуры тестов бэкенда.

БД для тестов — изолированный in-memory SQLite на каждый тест, со включённым
enforcement внешних ключей (как в проде), чтобы проверять каскадное удаление.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from backend.config import SESSION_TTL_DAYS
from backend.db.database import Base, make_engine
from backend.db.models import EnrollmentReason, StudentProfile, User, UserRole


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
