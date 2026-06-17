"""test_models.py — тесты модели данных роли «ученик».

Проверяют инварианты из specs/student_lesson_fsm_v4.md §1 и
specs/student_registration_fsm_v2.md §1:
- каскадное удаление всех ПД (152-ФЗ, v4 §8) — DELETE одного User вычищает всё;
- идемпотентность регистрации через unique onboarding_session_id (RC-07/RF-07);
- инварианты данных (grade range, attempts, passed_on_attempt, уникальность Progress);
- round-trip перечислений и JSON;
- связи 1:1 и 1:N.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError

from backend.db.models import (
    DailySession,
    EnrollmentReason,
    LinkType,
    Progress,
    ProgressStatus,
    ReminderState,
    ReviewQueue,
    ReviewReason,
    Session,
    Streak,
    StudentLink,
    StudentProfile,
    User,
    UserRole,
)
from backend.tests.conftest import make_student, session_expiry

# --- Базовое создание и связи ---


def test_create_student_with_profile_roundtrip(db):
    user = make_student(db, name="Иван", grade=9)
    db.commit()

    fetched = db.scalar(select(User).where(User.id == user.id))
    assert fetched is not None
    assert fetched.role is UserRole.STUDENT
    assert fetched.name == "Иван"
    assert fetched.grade == 9
    assert fetched.consent_cohort_flag is False
    # 1:1 профиль доступен через relationship.
    assert fetched.profile is not None
    assert fetched.profile.fsm_state == "registered"
    assert fetched.profile.current_lesson_id == "1_1"
    assert fetched.profile.enrollment_reason is EnrollmentReason.GRADE9_DIRECT


def test_minimal_pd_only_nickname_grade_consent(db):
    """ПД-минимизация: телефона/email/ФИО в модели User нет (reg v2 §1)."""
    columns = set(User.__table__.columns.keys())
    for forbidden in ("phone", "email", "full_name", "birth_date", "real_name"):
        assert forbidden not in columns


def test_pd_consent_required(db):
    """Без согласия User не создаётся (reg v2 §1, RC-03): pd_consent_at NOT NULL."""
    user = User(
        role=UserRole.STUDENT,
        name="Иван",
        grade=9,
        pd_consent_version="v1",
        onboarding_session_id="no-consent",
        # pd_consent_at не задан — согласие не зафиксировано
    )
    db.add(user)
    with pytest.raises(IntegrityError):
        db.flush()


# --- Инварианты данных ---


def test_grade_out_of_range_rejected(db):
    for bad_grade in (7, 12, 0):
        # make_student делает flush — нарушение CHECK всплывает прямо здесь.
        with pytest.raises(IntegrityError):
            make_student(db, grade=bad_grade, onboarding_session_id=f"onb-{bad_grade}")
        db.rollback()


@pytest.mark.parametrize("grade", [8, 9, 10, 11])
def test_grade_storable_values_accepted(db, grade):
    """БД хранит 8..11 (staging пишет 8); prod-guard живёт в сервисе регистрации."""
    make_student(db, grade=grade, onboarding_session_id=f"onb-{grade}")
    db.commit()  # без исключений


def test_onboarding_session_id_unique(db):
    """Идемпотентность submit: два аккаунта с одним onboarding_session_id запрещены."""
    make_student(db, name="Иван", onboarding_session_id="dup-key")
    db.commit()
    # Второй submit с тем же ключом — flush внутри make_student роняет IntegrityError.
    with pytest.raises(IntegrityError):
        make_student(db, name="Пётр", onboarding_session_id="dup-key")


def test_onboarding_session_id_null_allowed_multiple(db):
    """NULL onboarding_session_id — у многих записей (NULL уникальны в SQLite)."""
    make_student(db, name="A", onboarding_session_id=None)
    make_student(db, name="B", onboarding_session_id=None)
    db.commit()  # без исключений


def test_progress_unique_per_user_lesson(db):
    user = make_student(db)
    db.add(Progress(user_id=user.id, lesson_id="1_1"))
    db.commit()
    db.add(Progress(user_id=user.id, lesson_id="1_1"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_progress_main_attempts_check(db):
    user = make_student(db)
    db.add(Progress(user_id=user.id, lesson_id="1_2", main_question_attempts=4))
    with pytest.raises(IntegrityError):
        db.flush()


def test_progress_passed_on_attempt_check(db):
    user = make_student(db)
    db.add(Progress(user_id=user.id, lesson_id="1_3", passed_on_attempt=3))
    with pytest.raises(IntegrityError):
        db.flush()


@pytest.mark.parametrize("attempt", [1, 2, None])
def test_progress_passed_on_attempt_valid(db, attempt):
    user = make_student(db)
    db.add(
        Progress(user_id=user.id, lesson_id=f"1_{attempt}", passed_on_attempt=attempt)
    )
    db.commit()  # без исключений


def test_progress_defaults_and_json_roundtrip(db):
    user = make_student(db)
    p = Progress(user_id=user.id, lesson_id="1_1")
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.status is ProgressStatus.NOT_STARTED
    assert p.main_question_attempts == 0
    assert p.training_errors == {}
    assert p.passed_on_attempt is None

    p.training_errors = {"1.1_q2": 2}
    db.commit()
    db.refresh(p)
    assert p.training_errors == {"1.1_q2": 2}


# --- Round-trip перечислений ---


def test_enums_stored_as_values(db):
    """Enum хранятся как .value (snake_case), а не как имена (контракт CSV/FSM)."""
    user = make_student(db)
    db.add(
        ReviewQueue(
            user_id=user.id,
            lesson_id="1_1",
            reason=ReviewReason.INTERVAL_3D,
            due_date=date.today(),
        )
    )
    db.commit()
    raw_role = (
        db.connection()
        .exec_driver_sql("SELECT role FROM users WHERE id = ?", (user.id,))
        .scalar()
    )
    raw_reason = (
        db.connection()
        .exec_driver_sql(
            "SELECT reason FROM review_queue WHERE user_id = ?", (user.id,)
        )
        .scalar()
    )
    assert raw_role == "student"
    assert raw_reason == "interval_3d"


def test_invalid_enum_value_rejected(db):
    user = make_student(db)
    bad = ReviewQueue(
        user_id=user.id,
        lesson_id="1_1",
        reason="interval_99d",  # нет такого члена — отвергается на bind (flush)
        due_date=date.today(),
    )
    db.add(bad)
    with pytest.raises(StatementError):
        db.flush()


# --- 1:1 и 1:N связи ---


def test_one_to_one_relations(db):
    user = make_student(db)
    user.streak = Streak(current_streak=3, longest_streak=5)
    user.reminder_state = ReminderState(skip_days_count=1)
    db.commit()
    db.refresh(user)
    assert user.streak.current_streak == 3
    assert user.streak.freeze_used_this_week is False
    assert user.reminder_state.skip_days_count == 1


def test_daily_session_unique_per_day(db):
    user = make_student(db)
    today = date.today()
    db.add(DailySession(user_id=user.id, date=today))
    db.commit()
    db.add(DailySession(user_id=user.id, date=today))
    with pytest.raises(IntegrityError):
        db.flush()


def test_session_defaults(db):
    user = make_student(db)
    now = datetime.now(UTC)
    sess = Session(token="t" * 64, user_id=user.id, expires_at=session_expiry(now))
    db.add(sess)
    db.commit()
    db.refresh(sess)
    assert sess.revoked is False
    assert sess.expires_at - sess.created_at >= timedelta(days=29)


# --- Каскадное удаление всех ПД (152-ФЗ, v4 §8) ---


def _attach_full_dataset(db, user: User) -> User | None:
    """Навесить на ученика по записи каждого типа + привязку взрослого."""
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
            ),
            DailySession(user_id=user.id, date=date.today()),
            Session(
                token="tok" + "x" * 60,
                user_id=user.id,
                expires_at=session_expiry(),
            ),
        ]
    )
    adult = User(
        role=UserRole.PARENT,
        name="Родитель",
        pd_consent_at=datetime.now(UTC),
        pd_consent_version="v1",
        onboarding_session_id=None,
    )
    db.add(adult)
    db.flush()
    db.add(
        StudentLink(
            student_user_id=user.id,
            adult_user_id=adult.id,
            link_type=LinkType.PARENT,
            link_code="ABC123",
        )
    )
    db.flush()
    return adult


def test_delete_account_cascades_all_pd(db):
    user = make_student(db)
    _attach_full_dataset(db, user)
    db.commit()

    db.delete(user)
    db.commit()

    # Все ПД ученика удалены.
    assert db.scalar(select(User).where(User.id == user.id)) is None
    assert db.scalars(select(StudentProfile)).all() == []
    assert db.scalars(select(Progress)).all() == []
    assert db.scalars(select(Streak)).all() == []
    assert db.scalars(select(ReminderState)).all() == []
    assert db.scalars(select(ReviewQueue)).all() == []
    assert db.scalars(select(DailySession)).all() == []
    assert db.scalars(select(Session)).all() == []
    # Привязка удалена вместе с учеником…
    assert db.scalars(select(StudentLink)).all() == []
    # …но аккаунт взрослого (отдельный субъект) сохраняется.
    assert len(db.scalars(select(User)).all()) == 1


def test_deleting_adult_removes_link_not_student(db):
    """Удаление взрослого вычищает привязку, но не трогает аккаунт ученика."""
    user = make_student(db)
    adult = _attach_full_dataset(db, user)
    db.commit()

    db.delete(adult)
    db.commit()

    assert db.scalars(select(StudentLink)).all() == []
    assert db.scalar(select(User).where(User.id == user.id)) is not None
    # Прочие данные ученика на месте.
    assert db.scalars(select(Progress)).all() != []
