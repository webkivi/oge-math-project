"""config.py — переменные окружения и несущие константы бэкенда.

Секреты в коде запрещены (CLAUDE.md §6) — всё читается из окружения.
Значения по умолчанию безопасны для локального запуска; production задаёт
APP_ENV и DATABASE_URL явно.
"""

from __future__ import annotations

import enum
import os
from typing import Final


class AppEnv(enum.StrEnum):
    """Среда исполнения. Влияет на guard регистрации (D-6, grade=8)."""

    PRODUCTION = "production"
    STAGING = "staging"
    TEST = "test"


def _read_env() -> AppEnv:
    raw = os.getenv("APP_ENV", AppEnv.PRODUCTION.value).strip().lower()
    try:
        return AppEnv(raw)
    except ValueError:
        # Неизвестное значение трактуем как самое строгое — production.
        return AppEnv.PRODUCTION


# --- Среда и подключение к БД ---
APP_ENV: Final[AppEnv] = _read_env()
DATABASE_URL: Final[str] = os.getenv("DATABASE_URL", "sqlite:///./oge_math.sqlite3")

# --- Допустимые классы при регистрации (спека v4 §0 D-6, reg v2 §0) ---
# В production grade=8 — жёсткий гейт (аккаунт не создаётся); в staging — с warning.
# БД хранит 8..11 (staging пишет 8); production-guard живёт в сервисе регистрации.
VALID_GRADES_PRODUCTION: Final[frozenset[int]] = frozenset({9, 10, 11})
VALID_GRADES_STAGING: Final[frozenset[int]] = frozenset({8, 9, 10, 11})
STORABLE_GRADES: Final[frozenset[int]] = VALID_GRADES_STAGING

# --- Курс ---
TOTAL_LESSONS: Final[int] = 27  # спека v4 §2 (course_complete после 27 passed)

# --- Сессия аутентификации (спека v4 §1 Session, §8 контракт auth→Session) ---
SESSION_TTL_DAYS: Final[int] = 30
SESSION_TOKEN_BYTES: Final[int] = 32  # 256-bit random

# --- Неактивность аккаунта (спека v4 §1 инвариант, F-11) ---
INACTIVITY_DELETE_DAYS: Final[int] = 90
INACTIVITY_WARNING_DAYS: Final[int] = 14  # предупреждение за 14 дней до удаления

# --- Интервальные повторения (спека v4 §1 ReviewQueue) ---
REVIEW_INTERVALS_DAYS: Final[tuple[int, ...]] = (1, 3, 7, 14, 30)

# --- Mastery learning (спека v4 §2) ---
MAX_TRAINING_ERRORS: Final[int] = (
    3  # 3 ошибки подряд на один тренировочный вопрос → lesson_failed
)
MAX_MAIN_QUESTION_ATTEMPTS: Final[int] = (
    3  # счётчик 0..3; провал при 2 неверных попытках
)


def valid_grades(env: AppEnv = APP_ENV) -> frozenset[int]:
    """Допустимые для регистрации классы в зависимости от среды (D-6)."""
    return VALID_GRADES_STAGING if env == AppEnv.STAGING else VALID_GRADES_PRODUCTION
