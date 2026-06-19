"""auth.py — роутер онбординга: pd-policy, сессия (re-auth), регистрация (submit).

Источник истины: specs/student_registration_api_v1.md (E1/E2/E3). Тонкий транспорт:
эндпоинты валидируют заголовки, вызывают registration_service / auth.deps и мапят
RegistrationError → HTTP-коды (§5). Бизнес-логика — в сервисе, не здесь.

Эндпоинты (reg api §1):
- GET  /api/pd-policy   — E1: метаданные Политики ПД (версия/ссылка/доступность).
- GET  /api/session     — E2: re-auth по httpOnly-cookie (RC-11), всегда 200.
- POST /api/registration — E3: единственный submit, идемпотентный по Idempotency-Key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DbSession
from starlette.requests import Request

from backend import config
from backend.auth.deps import current_user_or_none
from backend.config import AppEnv
from backend.db.database import get_db
from backend.services import registration_service
from backend.services.registration_service import RegistrationError

router = APIRouter()


@dataclass(frozen=True)
class RegRuntime:
    """Среда выполнения регистрации (то, что роутер передаёт в сервис).

    Вынесено в зависимость, чтобы тесты могли подменять (production-гейт grade=8,
    доступность политики, статус Z-1) через app.dependency_overrides.
    """

    app_env: AppEnv
    policy_version: str
    policy_url: str
    policy_available: bool
    z1_resolved: bool
    first_lesson_id: str


def get_reg_runtime() -> RegRuntime:
    return RegRuntime(
        app_env=config.APP_ENV,
        policy_version=config.PD_POLICY_VERSION,
        policy_url=config.PD_POLICY_URL,
        policy_available=config.PD_POLICY_AVAILABLE,
        z1_resolved=config.Z1_CONSENT_RESOLVED,
        first_lesson_id=config.FIRST_LESSON_ID,
    )


class RegistrationRequest(BaseModel):
    """Тело E3 (reg api §3). onboarding_session_id — в заголовке, не здесь;
    enrollment_reason/consent_cohort_flag/current_lesson_id сервер деривит сам."""

    # Лишние поля тела отвергаются (CLAUDE.md §6; reg api §2.2 — ключ только в
    # заголовке): попытка прислать onboarding_session_id/enrollment_reason → 422.
    model_config = ConfigDict(extra="forbid")

    name: str
    grade: int
    ogeprep_answer: Literal["yes", "no"] | None = None
    pd_consent_checked: bool
    policy_version_shown: str


def _error(status: int, code: str, field: str | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "field": field})


@router.get("/api/pd-policy")
def pd_policy(rt: Annotated[RegRuntime, Depends(get_reg_runtime)]) -> Response:
    """E1: метаданные Политики ПД. 503, если политика недоступна (RF-04)."""
    if not rt.policy_available:
        return JSONResponse(status_code=503, content={"error": "pd_policy_unavailable"})
    return JSONResponse(
        status_code=200,
        content={
            "policy_version": rt.policy_version,
            "policy_url": rt.policy_url,
            "available": True,
        },
    )


@router.get("/api/session")
def session_probe(
    request: Request, db: Annotated[DbSession, Depends(get_db)]
) -> Response:
    """E2: re-auth по cookie (RC-11). Всегда 200; различие — поле authenticated."""
    user = current_user_or_none(request, db)
    if user is None or user.profile is None:
        return JSONResponse(status_code=200, content={"authenticated": False})
    return JSONResponse(
        status_code=200,
        content={
            "authenticated": True,
            "role": "student",
            "fsm_state": user.profile.fsm_state,
            "current_lesson_id": user.profile.current_lesson_id,
        },
    )


@router.post("/api/registration", response_model=None)
def register(
    payload: RegistrationRequest,
    response: Response,
    db: Annotated[DbSession, Depends(get_db)],
    rt: Annotated[RegRuntime, Depends(get_reg_runtime)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object] | JSONResponse:
    """E3: единственный submit. Создаёт аккаунт (201) или возвращает уже созданный
    (200, идемпотентный повтор). Отказы guard'ов → коды §5. Cookie сессии — на успехе.
    """
    # G0 (наличие заголовка): отсутствие обязательного Idempotency-Key → 400.
    if idempotency_key is None:
        return _error(400, "missing_idempotency_key")

    try:
        result = registration_service.submit(
            db,
            name=payload.name,
            grade=payload.grade,
            ogeprep_answer=payload.ogeprep_answer,
            pd_consent_checked=payload.pd_consent_checked,
            policy_version_shown=payload.policy_version_shown,
            idempotency_key=idempotency_key,
            app_env=rt.app_env,
            z1_resolved=rt.z1_resolved,
            current_policy_version=rt.policy_version,
            first_lesson_id=rt.first_lesson_id,
        )
    except RegistrationError as exc:
        return _error(exc.http_status, exc.code, exc.field)

    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=result.session_token,
        max_age=config.SESSION_TTL_DAYS * 86_400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.status_code = 201 if result.created else 200
    return {
        "user_id": str(result.user_id),
        "role": "student",
        "grade": result.grade,
        "fsm_state": result.fsm_state,
        "enrollment_reason": result.enrollment_reason.value,
        "current_lesson_id": result.current_lesson_id,
        "next": "daily_start",
    }
