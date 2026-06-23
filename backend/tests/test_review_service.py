"""test_review_service.py — постановка карточек повторений (review_service).

Проверяют specs/student_lesson_fsm_v4.md §1/§8: интервалы 1/3/7/14/30, дедуп по
(user_id, lesson_id, reason, due_date), passed_attempt_2 и провал (interval_1d, завтра).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from backend.db.models import ReviewQueue, ReviewReason
from backend.services import review_service
from backend.tests.conftest import make_student

FROM = date(2026, 6, 23)


def _cards(db, user_id: int) -> list[ReviewQueue]:
    return list(
        db.execute(select(ReviewQueue).where(ReviewQueue.user_id == user_id)).scalars()
    )


def test_enqueue_interval_reviews_creates_five(db):
    student = make_student(db)
    added = review_service.enqueue_interval_reviews(
        db, student.id, "1_1", from_date=FROM
    )
    db.commit()
    assert added == 5
    cards = {(c.reason, c.due_date) for c in _cards(db, student.id)}
    assert cards == {
        (ReviewReason.INTERVAL_1D, FROM + timedelta(days=1)),
        (ReviewReason.INTERVAL_3D, FROM + timedelta(days=3)),
        (ReviewReason.INTERVAL_7D, FROM + timedelta(days=7)),
        (ReviewReason.INTERVAL_14D, FROM + timedelta(days=14)),
        (ReviewReason.INTERVAL_30D, FROM + timedelta(days=30)),
    }


def test_enqueue_interval_reviews_is_deduped(db):
    student = make_student(db)
    review_service.enqueue_interval_reviews(db, student.id, "1_1", from_date=FROM)
    db.commit()
    added_again = review_service.enqueue_interval_reviews(
        db, student.id, "1_1", from_date=FROM
    )
    db.commit()
    assert added_again == 0  # дубли не плодятся (v4 §8)
    assert len(_cards(db, student.id)) == 5


def test_enqueue_passed_attempt_2(db):
    student = make_student(db)
    assert review_service.enqueue_passed_attempt_2(
        db, student.id, "1_1", from_date=FROM
    )
    db.commit()
    cards = _cards(db, student.id)
    assert len(cards) == 1
    assert cards[0].reason == ReviewReason.PASSED_ATTEMPT_2
    assert cards[0].due_date == FROM + timedelta(days=1)


def test_enqueue_failed_review(db):
    student = make_student(db)
    assert review_service.enqueue_failed_review(db, student.id, "1_1", from_date=FROM)
    db.commit()
    cards = _cards(db, student.id)
    assert len(cards) == 1
    assert cards[0].reason == ReviewReason.INTERVAL_1D
    assert cards[0].due_date == FROM + timedelta(days=1)
