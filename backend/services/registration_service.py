"""registration_service.py — submit регистрации ученика (HTTP-фаза onboarding).

Источник истины: specs/student_registration_api_v1.md (§4 guard'ы G0–G6, §5 коды,
§6 side-effect) поверх specs/student_registration_fsm_v2.md.

Принципиальное по спеке:
- Бэкенд НЕ доверяет фронту (CLAUDE.md §6): серверные guard'ы дублируют клиентскую
  валидацию. Каждый отказ → типизированная RegistrationError с HTTP-кодом из §5.
- Идемпотентность по onboarding_session_id (unique-колонка User, Brain 2026-06-17):
  при УЖЕ существующем ключе — короткое замыкание на 200 ДО guard'ов G1–G5; тело
  повтора игнорируется (§5.1а, закрывает «повтор с grade=8»). Гонка двух новых
  submit ловится unique-constraint → 409 (§5.1б).
- ПД пишутся в БД ТОЛЬКО здесь (152-ФЗ): до submit на сервере ничего нет.
- enrollment_reason / consent_cohort_flag / current_lesson_id сервер ДЕРИВИТ —
  от клиента не принимает (§6.2, анти-подмена).
- current_lesson_id детерминирован (config.FIRST_LESSON_ID), NOT NULL — назначается
  здесь; загрузка КОНТЕНТА урока — забота клиента после registered (§7.1, RF-06).
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from backend import config
from backend.config import AppEnv
from backend.db.models import EnrollmentReason, StudentProfile, User, UserRole
from backend.db.models import Session as AuthSession

_OGEPREP_GRADES = frozenset({10, 11})
_REGISTERED_STATE = "registered"
_MAX_NAME_LEN = 120  # = User.name String(120) (модель ae6e765)
_MAX_POLICY_VERSION_LEN = 40  # = User.pd_consent_version String(40)
_MAX_IDEMPOTENCY_KEY_LEN = 64  # = User.onboarding_session_id String(64)


class RegistrationError(Exception):
    """Отказ guard'а submit. Несёт код ошибки, поле и HTTP-статус (reg api §5)."""

    def __init__(self, code: str, *, field: str | None, http_status: int) -> None:
        super().__init__(code)
        self.code = code
        self.field = field
        self.http_status = http_status


@dataclass(frozen=True)
class RegistrationResult:
    """Итог submit для роутера: значения ответа + токен сессии + флаг 201/200."""

    user_id: int
    grade: int
    enrollment_reason: EnrollmentReason
    current_lesson_id: str
    fsm_state: str
    session_token: str
    created: bool  # True → 201 (новый аккаунт); False → 200 (идемпотентный повтор)


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def _new_session_token() -> str:
    return secrets.token_urlsafe(config.SESSION_TOKEN_BYTES)


def _find_account(db: DbSession, idempotency_key: str) -> User | None:
    """Найти уже созданный аккаунт по ключу идемпотентности (onboarding_session_id)."""
    return db.execute(
        select(User).where(User.onboarding_session_id == idempotency_key)
    ).scalar_one_or_none()


def _issue_session(db: DbSession, user_id: int, now: datetime) -> str:
    """Создать новую сессию для пользователя и вернуть её токен (cookie re-issue)."""
    token = _new_session_token()
    db.add(
        AuthSession(
            token=token,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(days=config.SESSION_TTL_DAYS),
            revoked=False,
        )
    )
    db.commit()
    return token


def _validate_idempotency_key(idempotency_key: str) -> None:
    """G0 (значение): корректный UUID, длина ≤ 64. Отсутствие ключа → 400 в роутере."""
    if len(idempotency_key) > _MAX_IDEMPOTENCY_KEY_LEN:
        raise RegistrationError("invalid_idempotency_key", field=None, http_status=422)
    try:
        uuid.UUID(idempotency_key)
    except ValueError as exc:
        raise RegistrationError(
            "invalid_idempotency_key", field=None, http_status=422
        ) from exc


def _validate_body(
    *,
    name: str,
    grade: int,
    ogeprep_answer: str | None,
    pd_consent_checked: bool,
    policy_version_shown: str,
    app_env: AppEnv,
    current_policy_version: str,
) -> str:
    """Guard'ы reg api §4 (G1→G1b→G2→G3→G4→G5); вернуть trim(name)."""
    trimmed = name.strip()
    # G1: имя непустое после trim.
    if len(trimmed) < 1:
        raise RegistrationError("empty_name", field="name", http_status=422)
    # G1b: верхняя граница + нормализация (CLAUDE.md §6, схема String(120)).
    if len(trimmed) > _MAX_NAME_LEN or _has_control_chars(trimmed):
        raise RegistrationError("invalid_name", field="name", http_status=422)
    # G2/G2-env: класс из множества среды (grade=8 в production — гейт D-6).
    if grade not in config.valid_grades(app_env):
        raise RegistrationError("invalid_grade", field="grade", http_status=422)
    # G3: согласие на ПД (152-ФЗ — без него регистрации нет).
    if pd_consent_checked is not True:
        raise RegistrationError(
            "consent_required", field="pd_consent_checked", http_status=422
        )
    # G4: версия политики — непустая, ≤ 40, совпадает с действующей (иначе 409).
    if not policy_version_shown or len(policy_version_shown) > _MAX_POLICY_VERSION_LEN:
        raise RegistrationError(
            "invalid_policy_version", field="policy_version_shown", http_status=422
        )
    if policy_version_shown != current_policy_version:
        raise RegistrationError(
            "policy_version_mismatch", field="policy_version_shown", http_status=409
        )
    # G5: ogeprep_answer консистентен с grade (анти-подмена ветки).
    if grade == 9 and ogeprep_answer is not None:
        raise RegistrationError(
            "inconsistent_ogeprep", field="ogeprep_answer", http_status=422
        )
    if grade in _OGEPREP_GRADES and ogeprep_answer not in ("yes", "no"):
        raise RegistrationError(
            "inconsistent_ogeprep", field="ogeprep_answer", http_status=422
        )
    return trimmed


def _derive_enrollment(grade: int) -> EnrollmentReason:
    # grade==9 → прямой вход; 10/11 (дошли до submit) → пересдача (reg api §6 шаг 4).
    return (
        EnrollmentReason.GRADE9_DIRECT
        if grade == 9
        else EnrollmentReason.GRADE10PLUS_RETAKE
    )


def submit(
    db: DbSession,
    *,
    name: str,
    grade: int,
    ogeprep_answer: str | None,
    pd_consent_checked: bool,
    policy_version_shown: str,
    idempotency_key: str,
    app_env: AppEnv,
    z1_resolved: bool,
    current_policy_version: str,
    first_lesson_id: str,
) -> RegistrationResult:
    """Выполнить submit регистрации (reg api E3). Атомарно создать аккаунт ИЛИ вернуть
    уже созданный (идемпотентный повтор). Отказы guard'ов → RegistrationError (§5).
    """
    _validate_idempotency_key(idempotency_key)

    # §5.1а: повтор с уже существующим ключом → 200 ДО guard'ов; тело игнорируется.
    existing = _find_account(db, idempotency_key)
    if (
        existing is not None
        and existing.profile is not None
        and existing.grade is not None
    ):
        now = datetime.now(UTC)
        token = _issue_session(db, existing.id, now)
        return RegistrationResult(
            user_id=existing.id,
            grade=existing.grade,  # серверное значение, не тело повтора (§5.1а)
            enrollment_reason=existing.profile.enrollment_reason,
            current_lesson_id=existing.profile.current_lesson_id,
            fsm_state=existing.profile.fsm_state,
            session_token=token,
            created=False,
        )

    trimmed = _validate_body(
        name=name,
        grade=grade,
        ogeprep_answer=ogeprep_answer,
        pd_consent_checked=pd_consent_checked,
        policy_version_shown=policy_version_shown,
        app_env=app_env,
        current_policy_version=current_policy_version,
    )

    enrollment = _derive_enrollment(grade)
    # consent_cohort_flag — только сервер: grade=9 пока Z-1 не закрыта (§4.2, RF-08).
    cohort_flag = grade == 9 and not z1_resolved
    now = datetime.now(UTC)

    user = User(
        role=UserRole.STUDENT,
        name=trimmed,
        grade=grade,
        created_at=now,
        pwa_push_token=None,
        pd_consent_at=now,
        pd_consent_version=policy_version_shown,
        consent_cohort_flag=cohort_flag,
        onboarding_session_id=idempotency_key,
    )
    user.profile = StudentProfile(
        current_lesson_id=first_lesson_id,
        fsm_state=_REGISTERED_STATE,
        enrollment_reason=enrollment,
        course_started_at=now,
        last_active_at=now,
    )
    token = _new_session_token()
    user.sessions.append(
        AuthSession(
            token=token,
            created_at=now,
            expires_at=now + timedelta(days=config.SESSION_TTL_DAYS),
            revoked=False,
        )
    )

    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # §5.1б: гонка — проигравший на unique-constraint onboarding_session_id → 409.
        db.rollback()
        raise RegistrationError(
            "registration_conflict", field=None, http_status=409
        ) from exc

    db.refresh(user)
    return RegistrationResult(
        user_id=user.id,
        grade=grade,
        enrollment_reason=enrollment,
        current_lesson_id=first_lesson_id,
        fsm_state=_REGISTERED_STATE,
        session_token=token,
        created=True,
    )
