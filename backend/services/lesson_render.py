"""lesson_render.py — сериализация LessonOutcome в render-payload (api §4.1/§4.9).

Чистый слой: LessonOutcome (fsm_service) → dict для JSON-ответа роутеров (пункт 1b).
Дискриминатор `view` (§4.1/§4.9), блоки message/lesson_progress/feedback, seq,
next_actions (UX-подсказка, НЕ авторитет — §4.1). Пользовательские тексты-обёртки —
зона A8, тут только структура + контентные поля из CSV.
"""

from __future__ import annotations

from backend.engine.csv_loader import LessonMessage
from backend.services.fsm_service import LessonOutcome

# fsm_state → view для безмессаджных/хабовых и репит-состояний (§4.9), когда нет ответа.
_STATE_VIEW: dict[str, str] = {
    "registered": "day_hub",
    "daily_start": "day_hub",
    "review_queue_scheduled": "day_hub",
    "daily_done": "day_done",
    "daily_blocked": "day_blocked",
    "course_complete": "course_complete",
    "morning_warmup": "warmup",
    "repeat_1h_pending": "repeat_pending",
    "repeat_evening_pending": "repeat_pending",
    "repeat_1h_active": "repeat_question",
    "repeat_evening_active": "repeat_question",
    "lesson_final": "lesson_final",
    "lesson_failed": "lesson_failed",
}

# fsm_state → допустимые command'ы (UX-подсказка next_actions, §4.1; сервер всё равно
# проверяет stage и вернёт 409 на неуместное — источник истины серверная проверка).
_STATE_ACTIONS: dict[str, list[str]] = {
    "lesson_hook": ["advance", "cancel"],
    "lesson_theory": ["advance", "cancel"],
    "lesson_example": ["advance", "cancel"],
    "lesson_theory_review": ["advance", "cancel"],
    "lesson_training": ["answer", "cancel"],
    "lesson_main_question": ["answer", "cancel"],
    "lesson_main_question_backup": ["answer", "cancel"],
    "lesson_final": ["advance"],
    "lesson_failed": ["advance"],
    "repeat_1h_active": ["answer"],
    "repeat_evening_active": ["answer"],
    "morning_warmup": ["warmup_answer", "warmup_skip"],
}


def _view(outcome: LessonOutcome) -> str:
    """Дискриминатор экрана (§4.9). Хаб/разминка/репит-состояния — по state (даже с
    feedback); только lesson-вопрос-стадии вне `_STATE_VIEW` — по исходу."""
    state = outcome.fsm_state
    judgement = outcome.judgement
    if outcome.resumable and outcome.message is not None:
        return (
            "lesson_message"  # §4.6 resume: registered+in_progress → урок, не day_hub
        )
    if state in _STATE_VIEW:
        # warmup/day_hub/repeat_*/lesson_final/lesson_failed — приоритет над judgement:
        # R3- и R1/R2-ответы несут feedback, но остаются на своём экране (§4.9).
        return _STATE_VIEW[state]
    if (
        judgement is not None
    ):  # вопрос-стадии урока (training/main/backup/theory_review)
        return "lesson_question" if judgement.is_correct else "lesson_feedback"
    msg = outcome.message
    if msg is not None and msg.is_question:
        return "lesson_question"
    return "lesson_message"


def _message_block(msg: LessonMessage | None) -> dict | None:
    if msg is None:
        return None
    block: dict = {
        "message_id": msg.message_id,
        "stage": msg.stage,
        "text_html": msg.text,
    }
    if msg.options:  # непустые варианты — только на вопрос-стадиях (§4.1)
        block["options"] = [
            {"letter": letter, "text_html": text}
            for letter, text in msg.options.items()
        ]
    return block


def serialize(outcome: LessonOutcome) -> dict:
    """LessonOutcome → render-dict (§4.1). Хаб-блок `day` (E4) добавляется отдельно."""
    render: dict = {
        "fsm_state": outcome.fsm_state,
        "view": _view(outcome),
        "message": _message_block(outcome.message),
        "seq": outcome.seq,
        "next_actions": _STATE_ACTIONS.get(outcome.fsm_state, []),
    }
    if outcome.progress_step is not None and outcome.progress_total is not None:
        render["lesson_progress"] = {
            "step": outcome.progress_step,
            "total": outcome.progress_total,
        }
    if outcome.judgement is not None:
        render["feedback"] = {
            "is_correct": outcome.judgement.is_correct,
            "feedback_html": outcome.judgement.feedback,
            "return_target": outcome.judgement.return_target,
        }
    if outcome.resumable:
        render["resumable"] = True  # §4.6: клиент показывает «Продолжить урок»
    if outcome.day is not None:
        render["day"] = outcome.day  # §4.1 day-блок (E4/E5)
    return render
