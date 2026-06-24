"""test_student_api.py — HTTP-эндпоинты урока E7–E11 (api §1.2/§4/§5, пункт 1b).

Покрытие: 401 без сессии, walk до прохождения (render-payload §4.1), коды §5.1
(422 invalid_option, 409 stale_message / wrong_action_for_stage), дедуп §5.2
(идемпотентный повтор по seq для advance и training-wrong answer).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from backend import config
from backend.db.database import get_db
from backend.db.models import Progress, ProgressStatus
from backend.db.models import Session as AuthSession
from backend.engine import lesson_content as lc
from backend.engine.csv_loader import LessonMessage
from backend.main import create_app
from backend.routers.student import get_lesson_repo
from backend.tests.conftest import make_student, session_expiry

TOKEN = "test-session-token"


def _m(
    mid: str,
    stage: str,
    *,
    correct: str = "",
    a: str = "",
    b: str = "",
    fa: str = "",
    fb: str = "",
    rb: str = "",
) -> LessonMessage:
    return LessonMessage(
        lesson_id="1_1",
        message_id=mid,
        stage=stage,
        text="<b>x</b>",
        option_a=a,
        option_b=b,
        option_c="",
        option_d="",
        correct_answer=correct,
        feedback_a=fa,
        feedback_b=fb,
        feedback_c="",
        feedback_d="",
        return_a="",
        return_b=rb,
        return_c="",
        return_d="",
    )


def _lesson() -> list[LessonMessage]:
    return [
        _m("th1", "theory"),
        _m("th2", "theory"),
        _m("ex1", "example"),
        _m("tq1", "training", correct="A", a="Да", b="Нет", fa="ok", fb="no", rb="th1"),
        _m(
            "mq",
            "main_question",
            correct="A",
            a="Да",
            b="Нет",
            fa="ok",
            fb="no",
            rb="th1",
        ),
        _m(
            "bq", "main_question_backup", correct="A", a="Да", b="Нет", fa="ok", fb="no"
        ),
        _m("fn", "final"),
        _m("fl", "lesson_failed"),
    ]


class FakeRepo:
    def __init__(self, messages: list[LessonMessage]) -> None:
        self._m = {"1_1": messages}

    def has(self, lesson_id: str) -> bool:
        return lesson_id in self._m

    def messages(self, lesson_id: str) -> list[LessonMessage]:
        if lesson_id not in self._m:
            raise lc.LessonNotFoundError(lesson_id)
        return self._m[lesson_id]


@pytest.fixture()
def client(db: OrmSession) -> Iterator[TestClient]:
    """Авторизованный клиент: ученик в lesson_select + сессия-cookie + FakeRepo."""
    student = make_student(db)
    student.profile.fsm_state = "lesson_select"
    db.add(
        AuthSession(
            token=TOKEN, user_id=student.id, expires_at=session_expiry(), revoked=False
        )
    )
    db.commit()

    app = create_app()

    def _override_db() -> Iterator[OrmSession]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_lesson_repo] = lambda: FakeRepo(_lesson())
    with TestClient(app, cookies={config.SESSION_COOKIE_NAME: TOKEN}) as c:
        yield c


def _only_progress(db: OrmSession) -> Progress:
    """Единственный Progress в тест-БД (один ученик, один урок)."""
    return db.execute(select(Progress)).scalars().one()


# --- Аутентификация ---


def test_requires_session(db: OrmSession):
    app = create_app()

    def _override_db() -> Iterator[OrmSession]:
        yield db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_lesson_repo] = lambda: FakeRepo(_lesson())
    with TestClient(app) as anon:  # без cookie
        r = anon.get("/api/lesson/current")
    assert r.status_code == 401
    assert r.json()["error"] == "unauthorized"


# --- Walk до прохождения (render-payload §4.1) ---


def test_start_renders_theory_with_auto_skipped_hook(client: TestClient):
    r = client.post("/api/lesson/start", json={"seq": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["fsm_state"] == "lesson_theory"  # R3 авто-проскок hook
    assert body["view"] == "lesson_message"
    assert body["message"]["message_id"] == "th1"
    assert body["lesson_progress"] == {"step": 1, "total": 5}
    assert "advance" in body["next_actions"]


def test_full_walk_pass_first_attempt(client: TestClient, db: OrmSession):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):  # th1→th2→example→training
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    body = client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "A", "seq": seq}
    ).json()
    assert body["fsm_state"] == "lesson_main_question"
    assert body["view"] == "lesson_question"
    assert body["feedback"]["is_correct"] is True
    assert body["message"]["options"]  # вопрос несёт варианты
    seq = body["seq"]
    r = client.post(
        "/api/lesson/answer", json={"message_id": "mq", "selected": "A", "seq": seq}
    )
    assert r.json()["view"] == "lesson_final"
    seq = r.json()["seq"]
    r = client.post("/api/lesson/advance", json={"seq": seq})
    assert r.json()["fsm_state"] == "repeat_1h_pending"
    assert r.json()["view"] == "repeat_pending"
    p = _only_progress(db)
    assert p.status == ProgressStatus.PASSED
    assert p.passed_on_attempt == 1


def _walk_to_main_question(client: TestClient) -> int:
    """start → theory → example → training → tq1 верно → lesson_main_question."""
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    return client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "A", "seq": seq}
    ).json()["seq"]


def test_view_lesson_feedback_on_main_wrong_first(client: TestClient):
    seq = _walk_to_main_question(client)
    body = client.post(
        "/api/lesson/answer", json={"message_id": "mq", "selected": "B", "seq": seq}
    ).json()
    assert body["view"] == "lesson_feedback"  # §4.9 main-wrong#1
    assert body["fsm_state"] == "lesson_theory_review"
    assert body["feedback"]["is_correct"] is False
    assert body["feedback"]["return_target"] == "th1"


def test_view_lesson_failed_on_main_wrong_second(client: TestClient):
    seq = _walk_to_main_question(client)
    seq = client.post(
        "/api/lesson/answer", json={"message_id": "mq", "selected": "B", "seq": seq}
    ).json()["seq"]
    seq = client.post("/api/lesson/advance", json={"seq": seq}).json()[
        "seq"
    ]  # → backup
    body = client.post(
        "/api/lesson/answer", json={"message_id": "bq", "selected": "B", "seq": seq}
    ).json()
    assert body["view"] == "lesson_failed"  # §4.9 main-wrong#2
    assert body["message"]["stage"] == "lesson_failed"


def test_resume_after_cancel_returns_lesson_view(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]  # → th2
    client.post("/api/lesson/cancel", json={"seq": seq})  # → registered, in_progress
    body = client.get("/api/lesson/current").json()
    assert body["fsm_state"] == "registered"
    assert body["view"] == "lesson_message"  # §4.6 resume, НЕ day_hub
    assert body["resumable"] is True
    assert body["message"]["message_id"] == "th2"


def test_answer_wrong_returns_feedback_view(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    r = client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "B", "seq": seq}
    )
    body = r.json()
    assert body["view"] == "lesson_feedback"  # wrong с возвратом (R1-№6)
    assert body["feedback"]["is_correct"] is False
    assert body["feedback"]["return_target"] == "th1"
    assert body["fsm_state"] == "lesson_training"  # остаёмся на вопросе


# --- Коды §5.1 ---


def test_answer_invalid_option_422(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    r = client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "C", "seq": seq}
    )
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_option"


def test_answer_stale_message_409(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    r = client.post(
        "/api/lesson/answer", json={"message_id": "ghost", "selected": "A", "seq": seq}
    )
    assert r.status_code == 409
    assert r.json()["error"] == "stale_message"


def test_advance_in_question_state_409(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    # сейчас lesson_training (вопрос-стадия) — advance недопустим
    r = client.post("/api/lesson/advance", json={"seq": seq})
    assert r.status_code == 409
    assert r.json()["error"] == "wrong_action_for_stage"


# --- Дедуп §5.2 (идемпотентность) ---


def test_advance_idempotent_on_stale_seq(client: TestClient):
    start_seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    r1 = client.post("/api/lesson/advance", json={"seq": start_seq}).json()
    assert r1["message"]["message_id"] == "th2"
    # Повтор с УСТАРЕВШИМ seq (дабл-клик) → 200 идемпотентно, без второго сдвига.
    r2 = client.post("/api/lesson/advance", json={"seq": start_seq})
    assert r2.status_code == 200
    assert r2.json()["message"]["message_id"] == "th2"  # позиция не уехала на ex1


def test_answer_idempotent_on_stale_seq_training_wrong(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    for _ in range(3):
        seq = client.post("/api/lesson/advance", json={"seq": seq}).json()["seq"]
    # Первый неверный ответ — ошибка зафиксирована.
    client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "B", "seq": seq}
    )
    # Повтор с тем же message_id и старым seq → 200 идемпотентно (без задвоения).
    r = client.post(
        "/api/lesson/answer", json={"message_id": "tq1", "selected": "B", "seq": seq}
    )
    assert r.status_code == 200
    assert r.json()["message"]["message_id"] == "tq1"


# --- Выход и resume ---


def test_cancel_returns_to_day_hub(client: TestClient):
    client.post("/api/lesson/start", json={"seq": 0})
    r = client.post("/api/lesson/cancel", json={"seq": 0})
    assert r.status_code == 200
    assert r.json()["fsm_state"] == "registered"
    assert r.json()["view"] == "day_hub"


def test_current_resume(client: TestClient):
    seq = client.post("/api/lesson/start", json={"seq": 0}).json()["seq"]
    client.post("/api/lesson/advance", json={"seq": seq})  # → th2
    r = client.get("/api/lesson/current")
    assert r.status_code == 200
    assert r.json()["message"]["message_id"] == "th2"  # resume на сохранённой позиции
    assert "feedback" not in r.json()  # resume не несёт результата ответа
