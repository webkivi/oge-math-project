"""deps.py — зависимости аутентификации по сессионной cookie.

reg api E2 (GET /api/session, RC-11): re-auth по httpOnly-cookie `oge_session`.
Сессия валидна, если токен найден, не отозван и не истёк. Cookie недоступен JS
(reg v2 §3 session/read=false) — читается только сервером.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session as DbSession
from starlette.requests import Request

from backend import config
from backend.db.database import get_db
from backend.db.models import Session as AuthSession
from backend.db.models import User, UserRole
from backend.services.fsm_service import LessonError


def _aware_utc(moment: datetime) -> datetime:
    """SQLite возвращает naive datetime; приводим к aware UTC для сравнения."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def current_user_or_none(request: Request, db: DbSession) -> User | None:
    """Вернуть пользователя по валидной сессии из cookie, иначе None (без ошибки).

    Используется E2 (всегда 200): отсутствие/невалидность сессии — норма для
    анонима, а не ошибка.
    """
    token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if not token:
        return None
    auth_session = db.get(AuthSession, token)
    if auth_session is None or auth_session.revoked:
        return None
    if _aware_utc(auth_session.expires_at) <= datetime.now(UTC):
        return None
    return db.get(User, auth_session.user_id)


def require_student(
    request: Request, db: Annotated[DbSession, Depends(get_db)]
) -> User:
    """Зависимость защищённых эндпоинтов урока (E4–E12): валидная сессия ученика.

    Дневной поток требует аутентификации (api §5.1): нет/невалидная сессия или роль
    не student → 401 `unauthorized`. Отличие от E2 онбординга (там аноним — норма).
    """
    user = current_user_or_none(request, db)
    if user is None or user.profile is None or user.role != UserRole.STUDENT:
        raise LessonError("unauthorized", http_status=401)
    return user
