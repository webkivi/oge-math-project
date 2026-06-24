"""main.py — точка входа FastAPI-приложения (раскладка v4 §7).

Запуск локально: `uvicorn backend.main:app --reload`.
Сейчас подключён только роутер онбординга (регистрация ученика, reg api). Остальные
роутеры (student, progress, push) добавятся со своими спеками.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend import config
from backend.config import AppEnv
from backend.db.database import Base, engine
from backend.engine.csv_loader import InvalidCSVError
from backend.engine.lesson_content import LessonNotFoundError
from backend.routers import auth, student
from backend.services.fsm_service import LessonError


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Создать таблицы при старте — ТОЛЬКО вне production (dev/staging/test, SQLite),
    чтобы first-run работал без ручного шага. В production схему ведёт Alembic
    (db/migrations/, А7), а не create_all — поэтому в production-среде здесь НЕ создаём
    (код enforce-ит обещание docstring, а не только документирует его; заодно убирает
    создание файловой БД при backend-тестах, идущих с дефолтным APP_ENV=production).
    Модели зарегистрированы на Base через импорт роутеров (auth → models).
    """
    if config.APP_ENV != AppEnv.PRODUCTION:
        Base.metadata.create_all(bind=engine)
    yield


def _lesson_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """LessonError → {error, field} с http_status (§5.1/§5.5, формат reg api)."""
    assert isinstance(exc, LessonError)
    return JSONResponse(
        status_code=exc.http_status, content={"error": exc.code, "field": exc.field}
    )


def _invalid_csv_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """InvalidCSVError → 503 (контент урока недоступен, EC-08/F-03; §5.5)."""
    return JSONResponse(
        status_code=503,
        content={"error": "lesson_content_unavailable", "field": None},
    )


def _lesson_not_found_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """LessonNotFoundError → 404 (lesson_id вне курса/каталога; §5.1)."""
    return JSONResponse(
        status_code=404, content={"error": "lesson_not_found", "field": None}
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="ОГЭ Математика — бэкенд (ученик)",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.include_router(auth.router)
    app.include_router(student.router)
    app.add_exception_handler(LessonError, _lesson_error_handler)
    app.add_exception_handler(InvalidCSVError, _invalid_csv_handler)
    app.add_exception_handler(LessonNotFoundError, _lesson_not_found_handler)
    return app


app = create_app()
