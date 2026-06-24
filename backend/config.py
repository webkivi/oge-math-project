"""config.py — переменные окружения и несущие константы бэкенда.

Секреты в коде запрещены (CLAUDE.md §6) — всё читается из окружения.
Значения по умолчанию безопасны для локального запуска; production задаёт
APP_ENV и DATABASE_URL явно.
"""

from __future__ import annotations

import enum
import os
from pathlib import Path
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

# --- Первый урок курса (детерминированный; reg api §6/§7, решение фаундера) ---
# Курс последовательный: current_lesson_id проставляется этой константой в транзакции
# submit, не результатом внешнего вызова → NOT NULL-колонка всегда заполнена.
FIRST_LESSON_ID: Final[str] = "1_1"

# --- Манифест курса: 27 упорядоченных lesson_id (spec student_lesson_api_v1 §3.3) ---
# Порядок = программа курса (блоки 1–6, Brain §2.4: 9+4+4+2+4+4 = 27). Источник
# секвенирования для guard'ов lesson_select (next_unpassed_lesson / all_lessons_passed).
# Единое пространство lesson_id для COURSE_MANIFEST / Progress.lesson_id / контента
# csv_loader (§3.4-bis). Блок 1 (1_1..1_9) — контент есть; блоки 2–6 форвард-объявлены
# (контент ещё не произведён — зона A1/контент-продюсера).
COURSE_MANIFEST: Final[tuple[str, ...]] = (
    "1_1",
    "1_2",
    "1_3",
    "1_4",
    "1_5",
    "1_6",
    "1_7",
    "1_8",
    "1_9",  # Блок 1 — Практические задачи
    "2_1",
    "2_2",
    "2_3",
    "2_4",  # Блок 2 — Арифметика
    "3_1",
    "3_2",
    "3_3",
    "3_4",  # Блок 3 — Уравнения и графики
    "4_1",
    "4_2",  # Блок 4 — Дополнения
    "5_1",
    "5_2",
    "5_3",
    "5_4",  # Блок 5 — Геометрия
    "6_1",
    "6_2",
    "6_3",
    "6_4",  # Блок 6 — Финал
)

# Инварианты манифеста (spec §3.3) — проверяются при импорте, рассинхрон ловится сразу:
assert (
    len(COURSE_MANIFEST) == TOTAL_LESSONS
), "COURSE_MANIFEST: длина должна быть == TOTAL_LESSONS"
assert (
    COURSE_MANIFEST[0] == FIRST_LESSON_ID
), "COURSE_MANIFEST[0] должен == FIRST_LESSON_ID"
assert len(set(COURSE_MANIFEST)) == len(
    COURSE_MANIFEST
), "COURSE_MANIFEST: lesson_id должны быть уникальны"

# --- Каталог контента уроков (CSV; читается движком, lesson api §3.4-bis) ---
CONTENT_DIR: Final[Path] = Path(__file__).resolve().parents[1] / "content"

# --- Cookie сессии (reg api §6.1) ---
SESSION_COOKIE_NAME: Final[str] = "oge_session"

# --- Политика обработки ПД (reg api E1; текст/версия — зона юриста, Z-2) ---
# Здесь только МЕТАДАННЫЕ (версия/ссылка/доступность); сам текст политики — не тут.
PD_POLICY_VERSION: Final[str] = os.getenv("PD_POLICY_VERSION", "2026-06-19")
PD_POLICY_URL: Final[str] = os.getenv("PD_POLICY_URL", "/policy")
PD_POLICY_AVAILABLE: Final[bool] = (
    os.getenv("PD_POLICY_AVAILABLE", "true").strip().lower() != "false"
)

# --- Z-1: закрыта ли юр-зависимость согласия представителя <14 (reg api §4.2) ---
# Дефолт false (НЕ закрыта) — fail-safe: помечаем когорту grade=9 (RF-08, обратимость).
Z1_CONSENT_RESOLVED: Final[bool] = (
    os.getenv("Z1_CONSENT_RESOLVED", "false").strip().lower() == "true"
)


def is_production(env: AppEnv = APP_ENV) -> bool:
    """В production действует жёсткий гейт grade=8 (D-6, reg api §4.1)."""
    return env == AppEnv.PRODUCTION


def valid_grades(env: AppEnv = APP_ENV) -> frozenset[int]:
    """Допустимые для регистрации классы в зависимости от среды (D-6)."""
    return VALID_GRADES_STAGING if env == AppEnv.STAGING else VALID_GRADES_PRODUCTION
