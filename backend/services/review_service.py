"""review_service.py — постановка тем в очередь повторений (ReviewQueue).

Источник истины: specs/student_lesson_fsm_v4.md §1 (ReviewQueue), §8 (контракт
fsm_service → review_service), §2б (side-effects ENQUEUE_*); specs/student_lesson_api_v1
§2.3 (passed_attempt_2 / interval-карточки). Дедуп по (user_id, lesson_id, reason,
due_date) — повторная постановка той же карточки не плодит дублей (v4 §8).

Откат интервала при ошибке R1/R2 (EC-05) и стрик/DailySession — вне этого модуля
(scheduler/streak-срез отложен фаундером); здесь только enqueue по факту прохождения.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from backend import config
from backend.db.models import ReviewQueue, ReviewReason

# Интервал (дни) → причина-карточка (v4 §1 ReviewReason). Источник дней — config.
_INTERVAL_REASON: dict[int, ReviewReason] = {
    1: ReviewReason.INTERVAL_1D,
    3: ReviewReason.INTERVAL_3D,
    7: ReviewReason.INTERVAL_7D,
    14: ReviewReason.INTERVAL_14D,
    30: ReviewReason.INTERVAL_30D,
}


def _today() -> date:
    return datetime.now(UTC).date()


def _exists(
    db: DbSession,
    user_id: int,
    lesson_id: str,
    reason: ReviewReason,
    due_date: date,
) -> bool:
    """Есть ли уже такая карточка (дедуп по 4 полям, v4 §8)."""
    stmt = select(ReviewQueue.id).where(
        ReviewQueue.user_id == user_id,
        ReviewQueue.lesson_id == lesson_id,
        ReviewQueue.reason == reason,
        ReviewQueue.due_date == due_date,
    )
    return db.execute(stmt).first() is not None


def _enqueue(
    db: DbSession,
    user_id: int,
    lesson_id: str,
    reason: ReviewReason,
    due_date: date,
) -> bool:
    """Поставить карточку, если её ещё нет. Возвращает True, если добавлена.

    Не коммитит — фиксацию делает вызывающий слой (fsm_service) одной транзакцией
    атомарно с fsm_state/Progress (v4 §1).
    """
    if _exists(db, user_id, lesson_id, reason, due_date):
        return False
    db.add(
        ReviewQueue(
            user_id=user_id,
            lesson_id=lesson_id,
            reason=reason,
            due_date=due_date,
            done=False,
        )
    )
    return True


def enqueue_interval_reviews(
    db: DbSession,
    user_id: int,
    lesson_id: str,
    *,
    from_date: date | None = None,
) -> int:
    """Поставить интервальные карточки 1/3/7/14/30 дней (v4 §1; side-effect
    ENQUEUE_INTERVAL_REVIEWS). Дни — из config.REVIEW_INTERVALS_DAYS. Возвращает
    число фактически добавленных (дубли пропущены)."""
    base = from_date or _today()
    added = 0
    for days in config.REVIEW_INTERVALS_DAYS:
        reason = _INTERVAL_REASON[days]
        added += _enqueue(db, user_id, lesson_id, reason, base + timedelta(days=days))
    return added


def enqueue_passed_attempt_2(
    db: DbSession,
    user_id: int,
    lesson_id: str,
    *,
    from_date: date | None = None,
) -> bool:
    """Карточка passed_attempt_2 (due — завтра утром; v4 §2б evt_main_correct_attempt2).
    Возвращает True, если добавлена."""
    base = from_date or _today()
    return _enqueue(
        db,
        user_id,
        lesson_id,
        ReviewReason.PASSED_ATTEMPT_2,
        base + timedelta(days=1),
    )


def enqueue_failed_review(
    db: DbSession,
    user_id: int,
    lesson_id: str,
    *,
    from_date: date | None = None,
) -> bool:
    """Карточка провала: interval_1d, due — завтра (v4 §2б evt_lesson_fail_confirmed).
    Возвращает True, если добавлена."""
    base = from_date or _today()
    return _enqueue(
        db,
        user_id,
        lesson_id,
        ReviewReason.INTERVAL_1D,
        base + timedelta(days=1),
    )
