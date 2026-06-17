"""database.py — подключение к SQLite, фабрика сессий, декларативная база.

Для SQLite внешние ключи по умолчанию выключены — включаем PRAGMA на каждое
соединение, иначе ondelete=CASCADE (каскадное удаление ПД по 152-ФЗ, спека v4 §8)
не сработает.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import DATABASE_URL


class Base(DeclarativeBase):
    """Общая декларативная база для всех ORM-моделей."""


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:
    """Включить enforcement внешних ключей для каждого SQLite-соединения."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def make_engine(url: str = DATABASE_URL, **engine_kwargs) -> Engine:
    """Создать движок. Для SQLite навешивает PRAGMA foreign_keys=ON.

    Доп. kwargs (например, poolclass=StaticPool для in-memory тестов) пробрасываются
    в create_engine — чтобы тесты не дублировали навешивание FK-listener вручную.
    """
    connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
    engine = create_engine(url, connect_args=connect_args, future=True, **engine_kwargs)
    if _is_sqlite(url):
        event.listen(engine, "connect", _enable_sqlite_fk)
    return engine


engine: Engine = make_engine()
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, future=True
)


def get_db() -> Iterator[Session]:
    """FastAPI-зависимость: выдать сессию БД и гарантированно закрыть её."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
