"""test_fsm.py — тесты конечного автомата ученика (backend/engine/lesson_engine.py).

Покрывают КАЖДЫЙ переход v4 §2b (happy + ветки гардов), структурные свойства
(достижимость всех состояний из start, отсутствие тупиков), взаимоисключающие
гарды и обработку недопустимых переходов.
"""

from __future__ import annotations

from collections import deque

import pytest

from backend.engine.lesson_engine import (
    EVENTS,
    START_STATE,
    STATES,
    TRANSITIONS,
    Event,
    FSMContext,
    GuardError,
    SideEffect,
    State,
    TransitionResult,
    UnknownTransitionError,
    can_handle,
    dispatch,
    valid_events,
    with_context,
)

S, EV, E = State, Event, SideEffect

# (src, event, ctx_kwargs, dest, effects) — по одной записи на КАЖДЫЙ переход таблицы.
CASES: list[tuple] = [
    (S.UNREGISTERED, EV.OPEN_PWA, {}, S.ONBOARDING, ()),
    (
        S.ONBOARDING,
        EV.SUBMIT_REGISTRATION,
        {"registration_valid": True},
        S.REGISTERED,
        (E.CREATE_STUDENT_ACCOUNT,),
    ),
    (S.ONBOARDING, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, ()),
    (S.ONBOARDING, EV.DELETE_ACCOUNT, {}, S.UNREGISTERED, ()),
    (S.REGISTERED, EV.DELETE_ACCOUNT, {}, S.UNREGISTERED, (E.DELETE_ALL_PD,)),
    (
        S.REGISTERED,
        EV.OPEN_APP,
        {"missed_day_end": False},
        S.DAILY_START,
        (E.UPDATE_LAST_ACTIVE,),
    ),
    (S.REGISTERED, EV.OPEN_APP, {"missed_day_end": True}, S.STREAK_UPDATE, ()),
    (S.REGISTERED, EV.DAY_END, {}, S.STREAK_UPDATE, ()),
    (S.STREAK_UPDATE, EV.STREAK_UPDATED, {}, S.REGISTERED, (E.APPLY_STREAK_UPDATE,)),
    (S.DAILY_START, EV.WARMUP_AVAILABLE, {"review_due": True}, S.MORNING_WARMUP, ()),
    (S.DAILY_START, EV.WARMUP_SKIP, {"review_due": False}, S.LESSON_SELECT, ()),
    (
        S.DAILY_START,
        EV.WARMUP_SKIP,
        {"review_due": True, "user_skipped_warmup": True},
        S.LESSON_SELECT,
        (),
    ),
    (S.MORNING_WARMUP, EV.WARMUP_COMPLETE, {}, S.LESSON_SELECT, ()),
    (S.LESSON_SELECT, EV.START_LESSON, {"has_next_lesson": True}, S.LESSON_HOOK, ()),
    (
        S.LESSON_SELECT,
        EV.NO_LESSON_TODAY,
        {"next_lesson_failed_today": False},
        S.DAILY_DONE,
        (),
    ),
    (
        S.LESSON_SELECT,
        EV.NO_LESSON_TODAY,
        {"next_lesson_failed_today": True},
        S.DAILY_BLOCKED,
        (),
    ),
    (
        S.LESSON_SELECT,
        EV.ALL_LESSONS_DONE,
        {"all_lessons_passed": True},
        S.COURSE_COMPLETE,
        (),
    ),
    (S.LESSON_HOOK, EV.HOOK_READ, {}, S.LESSON_THEORY, ()),
    (
        S.LESSON_HOOK,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (S.LESSON_THEORY, EV.THEORY_READ, {}, S.LESSON_EXAMPLE, ()),
    (
        S.LESSON_THEORY,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (S.LESSON_EXAMPLE, EV.EXAMPLE_READ, {}, S.LESSON_TRAINING, ()),
    (
        S.LESSON_EXAMPLE,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (
        S.LESSON_TRAINING,
        EV.ANSWER_CORRECT,
        {"training_remaining": True},
        S.LESSON_TRAINING,
        (),
    ),
    (
        S.LESSON_TRAINING,
        EV.ANSWER_CORRECT,
        {"training_remaining": False},
        S.LESSON_MAIN_QUESTION,
        (),
    ),
    (
        S.LESSON_TRAINING,
        EV.ANSWER_WRONG,
        {},
        S.LESSON_TRAINING,
        (E.RECORD_TRAINING_ERROR,),
    ),
    (S.LESSON_TRAINING, EV.TRAINING_MAX_ERRORS, {}, S.LESSON_FAILED, ()),
    (
        S.LESSON_TRAINING,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (
        S.LESSON_MAIN_QUESTION,
        EV.MAIN_CORRECT_ATTEMPT1,
        {"main_question_attempts": 0},
        S.LESSON_FINAL,
        (),
    ),
    (
        S.LESSON_MAIN_QUESTION,
        EV.MAIN_WRONG_ATTEMPT1,
        {"main_question_attempts": 0},
        S.LESSON_THEORY_REVIEW,
        (E.INCREMENT_MAIN_ATTEMPT,),
    ),
    (
        S.LESSON_MAIN_QUESTION,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (S.LESSON_THEORY_REVIEW, EV.THEORY_REVIEWED, {}, S.LESSON_MAIN_QUESTION_BACKUP, ()),
    (
        S.LESSON_THEORY_REVIEW,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (
        S.LESSON_MAIN_QUESTION_BACKUP,
        EV.MAIN_CORRECT_ATTEMPT2,
        {"main_question_attempts": 1},
        S.LESSON_FINAL,
        (E.ENQUEUE_PASSED_ATTEMPT_2_REVIEW,),
    ),
    (
        S.LESSON_MAIN_QUESTION_BACKUP,
        EV.MAIN_WRONG_ATTEMPT2,
        {"main_question_attempts": 1},
        S.LESSON_FAILED,
        (E.INCREMENT_MAIN_ATTEMPT,),
    ),
    (
        S.LESSON_MAIN_QUESTION_BACKUP,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (
        S.LESSON_FINAL,
        EV.LESSON_COMPLETE,
        {"all_lessons_passed": True},
        S.COURSE_COMPLETE,
        (E.RECORD_LESSON_PASSED, E.ENQUEUE_INTERVAL_REVIEWS),
    ),
    (
        S.LESSON_FINAL,
        EV.LESSON_COMPLETE,
        {"all_lessons_passed": False},
        S.REPEAT_1H_PENDING,
        (E.RECORD_LESSON_PASSED, E.SCHEDULE_REPEATS, E.ENQUEUE_INTERVAL_REVIEWS),
    ),
    (
        S.LESSON_FINAL,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.PERSIST_RESUMABLE_PROGRESS,),
    ),
    (
        S.LESSON_FAILED,
        EV.LESSON_FAIL_CONFIRMED,
        {},
        S.DAILY_BLOCKED,
        (E.RECORD_LESSON_FAILED, E.ENQUEUE_FAILED_REVIEW_1D),
    ),
    (
        S.LESSON_FAILED,
        EV.CANCEL_LESSON,
        {},
        S.REGISTERED,
        (E.RECORD_LESSON_FAILED, E.ENQUEUE_FAILED_REVIEW_1D),
    ),
    (S.REPEAT_1H_PENDING, EV.OPEN_APP, {}, S.REPEAT_1H_PENDING, (E.SHOW_R1_COUNTDOWN,)),
    (S.REPEAT_1H_PENDING, EV.ELAPSED_1H, {}, S.REPEAT_1H_ACTIVE, ()),
    (S.REPEAT_1H_ACTIVE, EV.REPEAT_1H_ANSWERED, {}, S.REPEAT_EVENING_PENDING, ()),
    (
        S.REPEAT_1H_ACTIVE,
        EV.NEXT_DAY,
        {},
        S.REPEAT_EVENING_PENDING,
        (E.ROLLBACK_R1_INTERVAL,),
    ),
    (
        S.REPEAT_EVENING_PENDING,
        EV.EVENING_TIME,
        {"is_evening": True},
        S.REPEAT_EVENING_ACTIVE,
        (),
    ),
    (
        S.REPEAT_EVENING_PENDING,
        EV.NEXT_DAY,
        {},
        S.REVIEW_QUEUE_SCHEDULED,
        (E.ROLLBACK_R2_INTERVAL,),
    ),
    (
        S.REPEAT_EVENING_ACTIVE,
        EV.OPEN_APP,
        {},
        S.REPEAT_EVENING_ACTIVE,
        (E.SHOW_EVENING_PROMPT,),
    ),
    (
        S.REPEAT_EVENING_ACTIVE,
        EV.REPEAT_EVENING_ANSWERED,
        {},
        S.REVIEW_QUEUE_SCHEDULED,
        (E.ENQUEUE_INTERVAL_REVIEWS,),
    ),
    (S.REVIEW_QUEUE_SCHEDULED, EV.SESSION_END, {}, S.REGISTERED, ()),
    (S.DAILY_DONE, EV.SESSION_END, {}, S.REGISTERED, ()),
    (S.DAILY_DONE, EV.NEXT_DAY, {}, S.REGISTERED, ()),
    (S.DAILY_BLOCKED, EV.NEXT_DAY, {}, S.REGISTERED, (E.RESET_FAILED_TODAY,)),
    (S.DAILY_BLOCKED, EV.OPEN_APP, {}, S.DAILY_BLOCKED, (E.SHOW_BLOCKED_MESSAGE,)),
    (S.COURSE_COMPLETE, EV.OPEN_APP, {}, S.REGISTERED, ()),
    (S.COURSE_COMPLETE, EV.DELETE_ACCOUNT, {}, S.UNREGISTERED, (E.DELETE_ALL_PD,)),
]


@pytest.mark.parametrize("src,event,ctx_kwargs,dest,effects", CASES)
def test_transition(src, event, ctx_kwargs, dest, effects):
    result = dispatch(src, event, with_context(**ctx_kwargs))
    assert isinstance(result, TransitionResult)
    assert result.new_state == dest
    assert result.effects == effects


# --- Полнота покрытия таблицы ---


def test_cases_cover_every_transition():
    """Каждый ФИЗИЧЕСКИЙ переход покрыт ровно одним кейсом (по src/event/dest + гарду).

    Матчим кейс на конкретный переход с учётом гарда (контекста кейса), а не только
    по тройке: иначе два перехода с одинаковыми src/event/dest, но разными гардами
    (daily_start+warmup_skip→lesson_select) схлопнулись бы и допустили ложно-зелёный.
    """
    remaining = list(TRANSITIONS)
    for src, event, ctx_kwargs, dest, _effects in CASES:
        ctx = with_context(**ctx_kwargs)
        matches = [
            t
            for t in remaining
            if t.src == src
            and t.event == event
            and t.dest == dest
            and (t.guard is None or t.guard(ctx))
        ]
        assert len(matches) == 1, f"кейс {src}/{event}→{dest}: матчит {len(matches)}"
        remaining.remove(matches[0])
    assert remaining == [], f"не покрыты переходы: {remaining}"
    assert len(CASES) == len(TRANSITIONS)


def test_state_and_event_counts():
    """Регрессия против спеки v4 §2b: 24 состояния, 33 события."""
    assert len(STATES) == 24
    assert len(EVENTS) == 33


# --- Структурные свойства: достижимость и отсутствие тупиков ---


def test_all_states_reachable_from_start():
    adjacency: dict[State, list[State]] = {s: [] for s in STATES}
    for t in TRANSITIONS:
        adjacency[t.src].append(t.dest)
    reached: set[State] = set()
    queue: deque[State] = deque([START_STATE])
    while queue:
        cur = queue.popleft()
        if cur in reached:
            continue
        reached.add(cur)
        queue.extend(adjacency[cur])
    assert reached == set(STATES), f"недостижимы: {set(STATES) - reached}"


def test_no_dead_end_states():
    """Каждое состояние имеет хотя бы один исходящий переход (нет тупиков)."""
    with_outgoing = {t.src for t in TRANSITIONS}
    assert set(STATES) == with_outgoing, f"тупики: {set(STATES) - with_outgoing}"


# --- Инварианты гардов ---


def test_multi_transition_groups_are_all_guarded():
    """Если из (state,event) >1 перехода — у всех должен быть гард (иначе конфликт)."""
    groups: dict[tuple[State, Event], list] = {}
    for t in TRANSITIONS:
        groups.setdefault((t.src, t.event), []).append(t)
    for key, group in groups.items():
        if len(group) > 1:
            assert all(t.guard is not None for t in group), f"безгардовый дубль: {key}"


def test_mutually_exclusive_guards_resolve_uniquely():
    """Взаимоисключающие гарды дают ровно один переход на любой релевантный контекст."""
    # registered + open_app
    assert (
        dispatch(
            S.REGISTERED, EV.OPEN_APP, with_context(missed_day_end=False)
        ).new_state
        == S.DAILY_START
    )
    assert (
        dispatch(S.REGISTERED, EV.OPEN_APP, with_context(missed_day_end=True)).new_state
        == S.STREAK_UPDATE
    )
    # lesson_select + no_lesson_today
    assert (
        dispatch(
            S.LESSON_SELECT,
            EV.NO_LESSON_TODAY,
            with_context(next_lesson_failed_today=False),
        ).new_state
        == S.DAILY_DONE
    )
    assert (
        dispatch(
            S.LESSON_SELECT,
            EV.NO_LESSON_TODAY,
            with_context(next_lesson_failed_today=True),
        ).new_state
        == S.DAILY_BLOCKED
    )
    # lesson_training + answer_correct
    assert (
        dispatch(
            S.LESSON_TRAINING, EV.ANSWER_CORRECT, with_context(training_remaining=True)
        ).new_state
        == S.LESSON_TRAINING
    )
    assert (
        dispatch(
            S.LESSON_TRAINING, EV.ANSWER_CORRECT, with_context(training_remaining=False)
        ).new_state
        == S.LESSON_MAIN_QUESTION
    )
    # lesson_final + lesson_complete
    assert (
        dispatch(
            S.LESSON_FINAL, EV.LESSON_COMPLETE, with_context(all_lessons_passed=True)
        ).new_state
        == S.COURSE_COMPLETE
    )
    assert (
        dispatch(
            S.LESSON_FINAL, EV.LESSON_COMPLETE, with_context(all_lessons_passed=False)
        ).new_state
        == S.REPEAT_1H_PENDING
    )


def test_no_transition_is_ever_ambiguous():
    """Ни один кейс не приводит к AmbiguousTransitionError."""
    for src, event, ctx_kwargs, _, _ in CASES:
        dispatch(src, event, with_context(**ctx_kwargs))  # не должно бросать Ambiguous


# --- Недопустимые переходы и невыполненные гарды ---


def test_unknown_transition_raises():
    # В registered нет события hook_read.
    with pytest.raises(UnknownTransitionError):
        dispatch(S.REGISTERED, EV.HOOK_READ, FSMContext())
    # В streak_update невозможны иные события, кроме streak_updated.
    with pytest.raises(UnknownTransitionError):
        dispatch(S.STREAK_UPDATE, EV.OPEN_APP, FSMContext())


def test_guard_failure_raises_guard_error():
    # daily_start + warmup_available при пустой очереди — гард не выполнен.
    with pytest.raises(GuardError):
        dispatch(S.DAILY_START, EV.WARMUP_AVAILABLE, with_context(review_due=False))
    # warmup_skip: очередь непуста, «пропустить» не нажато — гард не прошёл.
    with pytest.raises(GuardError):
        dispatch(
            S.DAILY_START,
            EV.WARMUP_SKIP,
            with_context(review_due=True, user_skipped_warmup=False),
        )


def test_start_lesson_blocked_when_failed_today():
    """Нельзя начать урок, если следующий — failed_today (mastery learning)."""
    with pytest.raises(GuardError):
        dispatch(
            S.LESSON_SELECT,
            EV.START_LESSON,
            with_context(has_next_lesson=True, next_lesson_failed_today=True),
        )


# --- Хелперы ---


def test_can_handle_and_valid_events():
    assert can_handle(S.UNREGISTERED, EV.OPEN_PWA) is True
    assert can_handle(S.REGISTERED, EV.HOOK_READ) is False
    assert valid_events(S.STREAK_UPDATE) == {EV.STREAK_UPDATED}
    assert EV.CANCEL_LESSON in valid_events(S.LESSON_TRAINING)


# --- Полный happy-path сценарий S-02 (урок с 1-й попытки) ---


def test_happy_path_lesson_first_attempt():
    """Сквозной путь: open_app → урок → главный вопрос с 1-й попытки → R1 pending."""
    state = S.REGISTERED
    state = dispatch(state, EV.OPEN_APP, with_context(missed_day_end=False)).new_state
    assert state == S.DAILY_START
    state = dispatch(state, EV.WARMUP_SKIP, with_context(review_due=False)).new_state
    assert state == S.LESSON_SELECT
    state = dispatch(
        state, EV.START_LESSON, with_context(has_next_lesson=True)
    ).new_state
    assert state == S.LESSON_HOOK
    state = dispatch(state, EV.HOOK_READ).new_state
    state = dispatch(state, EV.THEORY_READ).new_state
    state = dispatch(state, EV.EXAMPLE_READ).new_state
    assert state == S.LESSON_TRAINING
    # Q1, Q2 верно (остаются вопросы), Q3 верно (вопросов больше нет → главный).
    state = dispatch(
        state, EV.ANSWER_CORRECT, with_context(training_remaining=True)
    ).new_state
    state = dispatch(
        state, EV.ANSWER_CORRECT, with_context(training_remaining=True)
    ).new_state
    state = dispatch(
        state, EV.ANSWER_CORRECT, with_context(training_remaining=False)
    ).new_state
    assert state == S.LESSON_MAIN_QUESTION
    state = dispatch(
        state, EV.MAIN_CORRECT_ATTEMPT1, with_context(main_question_attempts=0)
    ).new_state
    assert state == S.LESSON_FINAL
    result = dispatch(state, EV.LESSON_COMPLETE, with_context(all_lessons_passed=False))
    assert result.new_state == S.REPEAT_1H_PENDING
    assert E.RECORD_LESSON_PASSED in result.effects


def test_failure_path_second_attempt_wrong():
    """Путь провала: главный неверно → теория → резерв неверно → failed → blocked."""
    state = S.LESSON_MAIN_QUESTION
    state = dispatch(
        state, EV.MAIN_WRONG_ATTEMPT1, with_context(main_question_attempts=0)
    ).new_state
    assert state == S.LESSON_THEORY_REVIEW
    state = dispatch(state, EV.THEORY_REVIEWED).new_state
    assert state == S.LESSON_MAIN_QUESTION_BACKUP
    state = dispatch(
        state, EV.MAIN_WRONG_ATTEMPT2, with_context(main_question_attempts=1)
    ).new_state
    assert state == S.LESSON_FAILED
    result = dispatch(state, EV.LESSON_FAIL_CONFIRMED)
    assert result.new_state == S.DAILY_BLOCKED
    assert E.RECORD_LESSON_FAILED in result.effects
