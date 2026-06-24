"""student.py — HTTP-роутер прохождения урока (api §1.2 E7–E11, пункт 1b).

Тонкий транспорт: эндпоинты валидируют тело, проверяют sequence-эхо (§5.2),
вызывают fsm_service и сериализуют render (§4.1). Бизнес-логика — в fsm_service.
Ошибки (LessonError / InvalidCSVError / LessonNotFoundError) мапятся в коды §5.1/§5.5
через обработчики в main.py.

Эндпоинты (§1.2): E7 GET /api/lesson/current (resume), E8 POST /api/lesson/start,
E9 POST /api/lesson/advance, E10 POST /api/lesson/answer, E11 POST /api/lesson/cancel.
Day-hub/warmup/repeat (E4/E5/E6/E12) — следующая часть 1b.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session as DbSession

from backend import config
from backend.auth.deps import require_student
from backend.db.database import get_db
from backend.db.models import User
from backend.engine.lesson_content import LessonRepository
from backend.services import fsm_service, lesson_render

router = APIRouter()


@lru_cache(maxsize=1)
def _default_repo() -> LessonRepository:
    return LessonRepository(config.CONTENT_DIR)


def get_lesson_repo() -> LessonRepository:
    """Зависимость доступа к контенту (singleton; тесты подменяют через override)."""
    return _default_repo()


CurrentUser = Annotated[User, Depends(require_student)]
Db = Annotated[DbSession, Depends(get_db)]
Repo = Annotated[LessonRepository, Depends(get_lesson_repo)]


class _SeqBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seq: int


class AdvanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["advance"] = "advance"
    seq: int


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: str
    selected: str
    seq: int


@router.get("/api/lesson/current")
def lesson_current(student: CurrentUser, db: Db, repo: Repo) -> dict:
    """E7: render текущего сохранённого сообщения (resume, EC-02)."""
    return lesson_render.serialize(fsm_service.current(db, repo, student.id))


@router.post("/api/lesson/start")
def lesson_start(body: _SeqBody, student: CurrentUser, db: Db, repo: Repo) -> dict:
    """E8: старт следующего незавершённого урока (R3-проскок hook на старте).

    `seq` в теле принимается для единообразия команд, но в старте НЕ используется:
    позиция урока ещё не определена, дедуп не нужен. Идемпотентность повторного
    старта обеспечивает FSM-гард lesson_select (повтор из не-lesson_select → 409)."""
    return lesson_render.serialize(fsm_service.start_lesson(db, repo, student.id))


@router.post("/api/lesson/advance")
def lesson_advance(body: AdvanceBody, student: CurrentUser, db: Db, repo: Repo) -> dict:
    """E9: «Дальше». Дедуп по seq (§5.2б): отставший → 200 идемпотентно."""
    cur = fsm_service.current(db, repo, student.id)
    if body.seq != cur.seq:
        return lesson_render.serialize(
            cur
        )  # шаг уже сделан → текущий render, без повтора
    return lesson_render.serialize(fsm_service.advance(db, repo, student.id))


@router.post("/api/lesson/answer")
def lesson_answer(body: AnswerBody, student: CurrentUser, db: Db, repo: Repo) -> dict:
    """E10: ответ (серверное судейство §2). Дедуп §5.2а: тот же message_id + отставший
    seq → 200 идемпотентно; чужой message_id → 409 (в сервисе).
    """
    cur = fsm_service.current(db, repo, student.id)
    if (
        cur.message is not None
        and body.message_id == cur.message.message_id
        and body.seq != cur.seq
    ):
        return lesson_render.serialize(cur)
    out = fsm_service.answer(
        db, repo, student.id, message_id=body.message_id, selected=body.selected
    )
    return lesson_render.serialize(out)


@router.post("/api/lesson/cancel")
def lesson_cancel(body: _SeqBody, student: CurrentUser, db: Db, repo: Repo) -> dict:
    """E11: выход из урока, прогресс сохранён (S-10)."""
    return lesson_render.serialize(fsm_service.cancel(db, repo, student.id))
