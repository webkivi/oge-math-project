"""account_service.py -- удаление аккаунта ученика по spec/student_lesson_fsm_v4.md §8.

Тонкий сервис над ORM: удаляет User, а каскады на FK/relationship дочищают
StudentProfile, Progress, Streak, ReviewQueue, ReminderState, DailySession,
Session и StudentLink.
"""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from backend.db.models import User


def delete_account(db: DbSession, user: User) -> None:
    """Каскадно удалить аккаунт пользователя в рамках текущей транзакции."""
    db.delete(user)
    db.commit()
