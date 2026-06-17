"""models.py — ORM-модели роли «ученик».

Источник истины: specs/student_lesson_fsm_v4.md §1 (словарь сущностей, инварианты)
и specs/student_registration_fsm_v2.md §1 (атрибуты онбординга).

Принципиальное по спеке:
- RegistrationDraft / OnboardingSession НЕ персистентны (reg v2 §1, 152-ФЗ минимизация):
  таблицы под них нет. Идемпотентность submit — через unique-колонку
  User.onboarding_session_id (RC-07/RF-07).
- Lesson / LessonMessage читаются из CSV движком (csv_loader, пункт 2), в БД нет.
- Classes — вне охвата спеки (deny для student), модели нет.
- StudentProfile.fsm_state — единственный канонический источник текущего состояния FSM;
  при расхождении с Progress.status приоритетен fsm_state (v4 §1). Набор значений
  валидируется FSM-движком (пункт 3), на уровне модели — строка snake_case.
- Каскадное удаление всех ПД (152-ФЗ, v4 §8) обеспечено ondelete=CASCADE на FK +
  ORM-каскадом; для SQLite требует PRAGMA foreign_keys=ON (см. database.py).
"""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_col(py_enum: type[enum.Enum]) -> SAEnum:
    """Хранить значение enum (.value), а не имя; без нативного ENUM (для SQLite)."""
    return SAEnum(
        py_enum,
        values_callable=lambda e: [m.value for m in e],
        native_enum=False,
        validate_strings=True,
    )


# --- Перечисления (без «магических строк», CLAUDE.md §4) ---


class UserRole(enum.StrEnum):
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"
    TUTOR = "tutor"


class ProgressStatus(enum.StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED_TODAY = "failed_today"


class ReviewReason(enum.StrEnum):
    PASSED_ATTEMPT_2 = "passed_attempt_2"
    INTERVAL_1D = "interval_1d"
    INTERVAL_3D = "interval_3d"
    INTERVAL_7D = "interval_7d"
    INTERVAL_14D = "interval_14d"
    INTERVAL_30D = "interval_30d"


class EnrollmentReason(enum.StrEnum):
    GRADE9_DIRECT = "grade9_direct"
    GRADE10PLUS_RETAKE = "grade10plus_retake"


class LinkType(enum.StrEnum):
    PARENT = "parent"
    TEACHER = "teacher"
    TUTOR = "tutor"


# --- Модели ---


class User(Base):
    """Аккаунт пользователя (в текущей поверхности — только ученик).

    Собираемые ПД минимальны (152-ФЗ): никнейм + класс + согласие на политику ПД.
    Настоящее ФИО/телефон/email не собираются (v4 §1 инвариант, reg v2 §1).
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "grade IS NULL OR grade IN (8, 9, 10, 11)", name="ck_user_grade_range"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[UserRole] = mapped_column(_enum_col(UserRole), nullable=False)
    # Отображаемое имя/ник — НЕ настоящее ФИО (reg v2 §1 инвариант).
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Класс: 9..11 (prod) / 8..11 (staging). NULL для не-student ролей (вне охвата).
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    pwa_push_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Согласие на обработку ПД обязательно: без него регистрация не завершается
    # (reg v2 §1 инвариант, RC-03) — поэтому NOT NULL.
    pd_consent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pd_consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    # consent_cohort_flag (reg v2 §1, RF-08): помечает grade=9-аккаунты, созданные
    # до закрытия Z-1, для обратимости. НЕ ПД сам по себе.
    consent_cohort_flag: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # Idempotency-key submit-а регистрации (reg v2 §1, RC-07/RF-07).
    # NULL допустим (несколько NULL уникальны в SQLite); у созданного через
    # регистрацию ученика — заполнен и уникален.
    onboarding_session_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True
    )

    profile: Mapped[StudentProfile | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    streak: Mapped[Streak | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reminder_state: Mapped[ReminderState | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    progress_records: Mapped[list[Progress]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    review_items: Mapped[list[ReviewQueue]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    daily_sessions: Mapped[list[DailySession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    # Привязки взрослых (StudentLink) удаляются при удалении любого из участников.
    links_as_student: Mapped[list[StudentLink]] = relationship(
        back_populates="student",
        foreign_keys="StudentLink.student_user_id",
        cascade="all, delete",
        passive_deletes=True,
    )
    links_as_adult: Mapped[list[StudentLink]] = relationship(
        back_populates="adult",
        foreign_keys="StudentLink.adult_user_id",
        cascade="all, delete",
        passive_deletes=True,
    )


class StudentProfile(Base):
    """Расширенный профиль ученика (1:1 → User)."""

    __tablename__ = "student_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_lesson_id: Mapped[str] = mapped_column(String(40), nullable=False)
    course_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    # Каноничное текущее состояние FSM (snake_case). Набор значений — за FSM-движком.
    fsm_state: Mapped[str] = mapped_column(String(64), nullable=False)
    # Причина зачисления (reg v2 §1) — для метрик доходимости, НЕ ПД.
    enrollment_reason: Mapped[EnrollmentReason] = mapped_column(
        _enum_col(EnrollmentReason), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Progress(Base):
    """Состояние прохождения одного урока учеником (v4 §1)."""

    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),
        CheckConstraint(
            "main_question_attempts >= 0 AND main_question_attempts <= 3",
            name="ck_progress_main_attempts",
        ),
        CheckConstraint(
            "passed_on_attempt IS NULL OR passed_on_attempt IN (1, 2)",
            name="ck_progress_passed_on_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[ProgressStatus] = mapped_column(
        _enum_col(ProgressStatus), nullable=False, default=ProgressStatus.NOT_STARTED
    )
    main_question_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # Счётчик ошибок по тренировочному вопросу: {message_id: count} (v4 §1, D-2).
    training_errors: Mapped[dict[str, int]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    current_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # На какой попытке пройден главный вопрос: 1 / 2 / NULL (ещё не пройден).
    passed_on_attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user: Mapped[User] = relationship(back_populates="progress_records")


class Streak(Base):
    """Счётчик непрерывных учебных дней (1:1 → User, v4 §1)."""

    __tablename__ = "streaks"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Сброс происходит в job evt_day_end при weekday()==0 (понедельник), v4 §1.
    freeze_used_this_week: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    user: Mapped[User] = relationship(back_populates="streak")


class ReviewQueue(Base):
    """Очередь тем для повторения, interval ≥ 1 день (v4 §1)."""

    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lesson_id: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[ReviewReason] = mapped_column(
        _enum_col(ReviewReason), nullable=False
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="review_items")


class ReminderState(Base):
    """Флаги триггеров push-напоминаний (1:1 → User, v4 §1)."""

    __tablename__ = "reminder_states"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    last_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    skip_days_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    freeze_applied_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(back_populates="reminder_state")


class DailySession(Base):
    """Агрегат активности за учебный день (v4 §1)."""

    __tablename__ = "daily_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_session_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    lessons_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reviews_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    morning_warmup_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # evt_day_end наступил, но ученик был не в registered — streak_update отложен.
    missed_day_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="daily_sessions")


class Session(Base):
    """Сессионный токен аутентификации (httpOnly cookie, v4 §1, §8)."""

    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class StudentLink(Base):
    """Связь ученика со взрослым пользователем (родитель/учитель/репетитор, v4 §1)."""

    __tablename__ = "student_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    adult_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    link_type: Mapped[LinkType] = mapped_column(_enum_col(LinkType), nullable=False)
    link_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    student: Mapped[User] = relationship(
        back_populates="links_as_student", foreign_keys=[student_user_id]
    )
    adult: Mapped[User] = relationship(
        back_populates="links_as_adult", foreign_keys=[adult_user_id]
    )
