"""main.py — точка входа FastAPI-приложения (раскладка v4 §7).

Запуск локально: `uvicorn backend.main:app --reload`.
Сейчас подключён только роутер онбординга (регистрация ученика, reg api). Остальные
роутеры (student, progress, push) добавятся со своими спеками.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend import config
from backend.config import AppEnv
from backend.db.database import Base, engine
from backend.routers import auth


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


def create_app() -> FastAPI:
    app = FastAPI(
        title="ОГЭ Математика — бэкенд (ученик)",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.include_router(auth.router)
    return app


app = create_app()
