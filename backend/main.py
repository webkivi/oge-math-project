"""main.py — точка входа FastAPI-приложения (раскладка v4 §7).

Запуск локально: `uvicorn backend.main:app --reload`.
Сейчас подключён только роутер онбординга (регистрация ученика, reg api). Остальные
роутеры (student, progress, push) добавятся со своими спеками.
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.routers import auth


def create_app() -> FastAPI:
    app = FastAPI(title="ОГЭ Математика — бэкенд (ученик)", version="0.1.0")
    app.include_router(auth.router)
    return app


app = create_app()
