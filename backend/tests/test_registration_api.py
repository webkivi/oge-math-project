"""HTTP-тесты онбординга — specs/student_registration_api_v1.md (E1/E2/E3).

Покрытие: сценарии reg_v2 R-01..R-04 (happy path по классам) + edge RC-01/03/04/07
(идемпотентность, согласие, grade=8-гейт, гонка) + E1 (pd-policy), E2 (re-auth),
G0 (отсутствие Idempotency-Key).

Среда тестов переопределяется через app.dependency_overrides: production-гейт grade=8,
фиксированная версия политики, общая in-memory сессия БД.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from backend import config
from backend.config import AppEnv
from backend.db.database import get_db
from backend.db.models import EnrollmentReason, StudentProfile, User, UserRole
from backend.db.models import Session as AuthSession
from backend.main import create_app
from backend.routers.auth import RegRuntime, get_reg_runtime
from backend.services import registration_service

POLICY_VERSION = "testv1"


@pytest.fixture()
def runtime() -> RegRuntime:
    """Production-среда (гейт grade=8 активен), известная версия политики."""
    return RegRuntime(
        app_env=AppEnv.PRODUCTION,
        policy_version=POLICY_VERSION,
        policy_url="/policy",
        policy_available=True,
        z1_resolved=False,
        first_lesson_id="1_1",
    )


def _build_client(db: OrmSession, rt: RegRuntime) -> TestClient:
    app = create_app()

    def _override_db() -> Iterator[OrmSession]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_reg_runtime] = lambda: rt
    return TestClient(app)


@pytest.fixture()
def client(db: OrmSession, runtime: RegRuntime) -> Iterator[TestClient]:
    with _build_client(db, runtime) as test_client:
        yield test_client


def _key() -> str:
    return str(uuid.uuid4())


def _payload(
    *,
    grade: int = 9,
    ogeprep: str | None = None,
    consent: bool = True,
    name: str = "Иван",
    policy: str = POLICY_VERSION,
) -> dict[str, object]:
    body: dict[str, object] = {
        "name": name,
        "grade": grade,
        "pd_consent_checked": consent,
        "policy_version_shown": policy,
    }
    if ogeprep is not None:
        body["ogeprep_answer"] = ogeprep
    return body


def _users(db: OrmSession) -> list[User]:
    return list(db.scalars(select(User)).all())


# --- E1: pd-policy -----------------------------------------------------------


def test_pd_policy_returns_metadata(client: TestClient) -> None:
    resp = client.get("/api/pd-policy")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "policy_version": POLICY_VERSION,
        "policy_url": "/policy",
        "available": True,
    }


# --- E2: re-auth (RC-11) -----------------------------------------------------


def test_session_probe_anonymous_returns_false(client: TestClient) -> None:
    resp = client.get("/api/session")
    assert resp.status_code == 200
    assert resp.json() == {"authenticated": False}


def test_session_probe_authenticated(client: TestClient, db: OrmSession) -> None:
    """RC-11: валидная cookie → ученик распознан, в name_entry не входит."""
    now = datetime.now(UTC)
    user = User(
        role=UserRole.STUDENT,
        name="Иван",
        grade=9,
        pd_consent_at=now,
        pd_consent_version=POLICY_VERSION,
        consent_cohort_flag=True,
        onboarding_session_id=_key(),
    )
    user.profile = StudentProfile(
        current_lesson_id="1_1",
        fsm_state="registered",
        enrollment_reason=EnrollmentReason.GRADE9_DIRECT,
    )
    token = "tok-" + _key()
    user.sessions.append(
        AuthSession(token=token, expires_at=now + timedelta(days=30), revoked=False)
    )
    db.add(user)
    db.commit()

    client.cookies.set(config.SESSION_COOKIE_NAME, token)
    resp = client.get("/api/session")
    assert resp.status_code == 200
    assert resp.json() == {
        "authenticated": True,
        "role": "student",
        "fsm_state": "registered",
        "current_lesson_id": "1_1",
    }


# --- R-01..R-04: happy path по классам ---------------------------------------


def test_r01_grade9_direct(client: TestClient, db: OrmSession) -> None:
    key = _key()
    resp = client.post(
        "/api/registration", json=_payload(grade=9), headers={"Idempotency-Key": key}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "student"
    assert body["grade"] == 9
    assert body["fsm_state"] == "registered"
    assert body["enrollment_reason"] == "grade9_direct"
    assert body["current_lesson_id"] == "1_1"
    assert body["next"] == "daily_start"
    assert isinstance(body["user_id"], str)

    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert config.SESSION_COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" in set_cookie

    users = _users(db)
    assert len(users) == 1
    user = users[0]
    assert user.onboarding_session_id == key
    assert user.grade == 9
    # grade=9 + Z-1 не закрыта → когорта помечена (RF-08, обратимость).
    assert user.consent_cohort_flag is True
    assert user.pd_consent_version == POLICY_VERSION
    assert user.profile.current_lesson_id == "1_1"
    assert user.profile.enrollment_reason == EnrollmentReason.GRADE9_DIRECT
    # Сессия создана как side-effect успешной регистрации.
    assert len(db.scalars(select(AuthSession)).all()) == 1


def test_r02_grade10_retake(client: TestClient, db: OrmSession) -> None:
    resp = client.post(
        "/api/registration",
        json=_payload(grade=10, ogeprep="yes"),
        headers={"Idempotency-Key": _key()},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["grade"] == 10
    assert body["enrollment_reason"] == "grade10plus_retake"
    user = _users(db)[0]
    # grade != 9 → consent_cohort_flag не ставится.
    assert user.consent_cohort_flag is False
    assert user.profile.enrollment_reason == EnrollmentReason.GRADE10PLUS_RETAKE


def test_r03_grade11_mismatch_continue(client: TestClient, db: OrmSession) -> None:
    """R-03: grade=11, «не готовлюсь к ОГЭ», но всё равно начинает — впуск (§1.4)."""
    resp = client.post(
        "/api/registration",
        json=_payload(grade=11, ogeprep="no"),
        headers={"Idempotency-Key": _key()},
    )
    assert resp.status_code == 201
    assert resp.json()["enrollment_reason"] == "grade10plus_retake"
    assert len(_users(db)) == 1


def test_r04_grade8_production_gate(client: TestClient, db: OrmSession) -> None:
    """R-04: grade=8 в production — жёсткий гейт, аккаунт не создаётся (D-6)."""
    resp = client.post(
        "/api/registration", json=_payload(grade=8), headers={"Idempotency-Key": _key()}
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "invalid_grade", "field": "grade"}
    assert _users(db) == []


def test_staging_grade8_dev_affordance(db: OrmSession) -> None:
    """§4.1: в staging grade=8 — dev-аффорданс, ПРИНИМАЕТСЯ (не продуктовое поведение).

    В production эта ветка недостижима (fail-safe). Тест фиксирует, что allow-путь
    valid_grades(STAGING) действительно создаёт аккаунт, а не «фиктивно зелёный».
    """
    staging = RegRuntime(
        app_env=AppEnv.STAGING,
        policy_version=POLICY_VERSION,
        policy_url="/policy",
        policy_available=True,
        z1_resolved=False,
        first_lesson_id="1_1",
    )
    with _build_client(db, staging) as staging_client:
        resp = staging_client.post(
            "/api/registration",
            json=_payload(grade=8),
            headers={"Idempotency-Key": _key()},
        )
    assert resp.status_code == 201
    assert resp.json()["grade"] == 8
    users = _users(db)
    assert len(users) == 1
    assert users[0].grade == 8


# --- RC-01/03/04/07: edge cases ----------------------------------------------


def test_rc01_double_submit_idempotent(client: TestClient, db: OrmSession) -> None:
    """RC-01/RF-07: повтор с тем же ключом → 200, второй аккаунт НЕ создаётся."""
    key = _key()
    first = client.post(
        "/api/registration", json=_payload(grade=9), headers={"Idempotency-Key": key}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/registration", json=_payload(grade=9), headers={"Idempotency-Key": key}
    )
    assert second.status_code == 200
    assert second.json()["enrollment_reason"] == "grade9_direct"
    assert second.json()["current_lesson_id"] == "1_1"
    # Ровно один аккаунт на ключ идемпотентности.
    assert len(_users(db)) == 1


def test_rc01_double_submit_divergent_body_ignored(
    client: TestClient, db: OrmSession
) -> None:
    """§5.1а: повтор с иным телом (grade=8) → 200 исходного аккаунта."""
    key = _key()
    client.post(
        "/api/registration", json=_payload(grade=9), headers={"Idempotency-Key": key}
    )
    replay = client.post(
        "/api/registration", json=_payload(grade=8), headers={"Idempotency-Key": key}
    )
    assert replay.status_code == 200
    # Возвращается исходный валидный аккаунт; тело повтора (grade=8) НЕ применяется.
    assert replay.json()["grade"] == 9
    assert len(_users(db)) == 1


def test_rc03_consent_required(client: TestClient, db: OrmSession) -> None:
    """RC-03: без согласия на ПД регистрация отклоняется (152-ФЗ), аккаунт не создан."""
    resp = client.post(
        "/api/registration",
        json=_payload(grade=9, consent=False),
        headers={"Idempotency-Key": _key()},
    )
    assert resp.status_code == 422
    assert resp.json() == {"error": "consent_required", "field": "pd_consent_checked"}
    assert _users(db) == []


def test_rc04_grade8_backend_guard(client: TestClient, db: OrmSession) -> None:
    """RC-04: подмена grade=8 минуя UI отклоняется на бэкенде — ни User, ни Session."""
    resp = client.post(
        "/api/registration", json=_payload(grade=8), headers={"Idempotency-Key": _key()}
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_grade"
    assert _users(db) == []
    assert db.scalars(select(AuthSession)).all() == []


def test_rc07_race_conflict(
    client: TestClient, db: OrmSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RC-07/§5.1б: гонка двух submit с одним ключом — проигравший получает 409.

    Гонку моделируем детерминированно: lookup по ключу «промахивается» (как если бы
    аккаунт ещё не закоммичен), но строка с этим onboarding_session_id уже есть →
    insert упирается в unique-constraint → 409.
    """
    key = _key()
    now = datetime.now(UTC)
    winner = User(
        role=UserRole.STUDENT,
        name="Уже есть",
        grade=9,
        pd_consent_at=now,
        pd_consent_version=POLICY_VERSION,
        consent_cohort_flag=True,
        onboarding_session_id=key,
    )
    winner.profile = StudentProfile(
        current_lesson_id="1_1",
        fsm_state="registered",
        enrollment_reason=EnrollmentReason.GRADE9_DIRECT,
    )
    db.add(winner)
    db.commit()

    monkeypatch.setattr(registration_service, "_find_account", lambda *_a, **_k: None)

    resp = client.post(
        "/api/registration", json=_payload(grade=9), headers={"Idempotency-Key": key}
    )
    assert resp.status_code == 409
    assert resp.json() == {"error": "registration_conflict", "field": None}
    # Победитель остался единственным аккаунтом.
    assert len(_users(db)) == 1


# --- G0: Idempotency-Key -----------------------------------------------------


def test_missing_idempotency_key_returns_400(
    client: TestClient, db: OrmSession
) -> None:
    resp = client.post("/api/registration", json=_payload(grade=9))
    assert resp.status_code == 400
    assert resp.json() == {"error": "missing_idempotency_key", "field": None}
    assert _users(db) == []


def test_invalid_idempotency_key_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/api/registration",
        json=_payload(grade=9),
        headers={"Idempotency-Key": "not-a-uuid"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "invalid_idempotency_key"
