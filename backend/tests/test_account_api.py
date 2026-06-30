"""HTTP-тесты удаления аккаунта ученика по specs/student_lesson_fsm_v4.md §8."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from backend import config
from backend.db.database import get_db
from backend.db.models import (
    DailySession,
    Progress,
    ReminderState,
    ReviewQueue,
    ReviewReason,
    Session as AuthSession,
    Streak,
    StudentProfile,
    User,
)
from backend.main import create_app
from backend.tests.conftest import make_student, session_expiry

TOKEN = "delete-me-token"


def _build_client(db: OrmSession, *, with_cookie: bool) -> TestClient:
    app = create_app()

    def _override_db() -> Iterator[OrmSession]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    cookies = {config.SESSION_COOKIE_NAME: TOKEN} if with_cookie else None
    return TestClient(app, cookies=cookies)


def _seed_student_dataset(db: OrmSession) -> User:
    user = make_student(db, onboarding_session_id="delete-account-student")
    user.streak = Streak()
    user.reminder_state = ReminderState()
    db.add_all(
        [
            Progress(user_id=user.id, lesson_id="1_1"),
            ReviewQueue(
                user_id=user.id,
                lesson_id="1_1",
                reason=ReviewReason.INTERVAL_1D,
                due_date=date.today(),
                done=False,
            ),
            DailySession(user_id=user.id, date=date.today()),
            AuthSession(
                token=TOKEN,
                user_id=user.id,
                expires_at=session_expiry(datetime.now(UTC)),
                revoked=False,
            ),
        ]
    )
    db.commit()
    return user


def test_delete_account_requires_session(db: OrmSession) -> None:
    with _build_client(db, with_cookie=False) as client:
        response = client.delete("/api/account")
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized", "field": None}


def test_delete_account_cascades_related_records(db: OrmSession) -> None:
    student = _seed_student_dataset(db)

    with _build_client(db, with_cookie=True) as client:
        response = client.delete("/api/account")

    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "").lower()
    assert f"{config.SESSION_COOKIE_NAME}=" in set_cookie
    assert "max-age=0" in set_cookie

    assert db.scalar(select(User).where(User.id == student.id)) is None
    assert db.scalars(select(StudentProfile)).all() == []
    assert db.scalars(select(Progress)).all() == []
    assert db.scalars(select(Streak)).all() == []
    assert db.scalars(select(ReminderState)).all() == []
    assert db.scalars(select(ReviewQueue)).all() == []
    assert db.scalars(select(DailySession)).all() == []
    assert db.scalars(select(AuthSession)).all() == []
