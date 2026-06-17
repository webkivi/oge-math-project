"""test_registration_fsm.py — тесты автомата регистрации (registration_engine.py).

Покрывают КАЖДЫЙ переход reg v2 §2b, сценарии R-01..R-05, edge cases RC-02..RC-09,
достижимость состояний и отсутствие тупиков (кроме терминального registered).
"""

from __future__ import annotations

from collections import deque

import pytest

from backend.engine.lesson_engine import GuardError, UnknownTransitionError
from backend.engine.registration_engine import (
    END_STATES,
    EVENTS,
    START_STATE,
    STATES,
    TRANSITIONS,
    RegEvent,
    RegSideEffect,
    RegState,
    can_handle,
    dispatch,
    valid_events,
    with_context,
)

S, EV, E = RegState, RegEvent, RegSideEffect

# (src, event, ctx_kwargs, dest, effects) — по одной записи на КАЖДЫЙ переход §2b.
CASES: list[tuple] = [
    (S.UNREGISTERED, EV.OPEN_PWA, {}, S.NAME_ENTRY, (E.CREATE_DRAFT,)),
    (
        S.NAME_ENTRY,
        EV.NAME_SUBMITTED,
        {"name_present": True},
        S.GRADE_ENTRY,
        (E.SAVE_NAME,),
    ),
    (S.NAME_ENTRY, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (
        S.GRADE_ENTRY,
        EV.GRADE_SELECTED,
        {"grade": 8, "is_production": True},
        S.GATE_GRADE8,
        (),
    ),
    (
        S.GRADE_ENTRY,
        EV.GRADE_SELECTED,
        {"grade": 9},
        S.CONSENT_GATE,
        (E.SET_ENROLLMENT_GRADE9, E.READ_POLICY_VERSION),
    ),
    (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 10}, S.OGEPREP_CHECK, ()),
    (S.GRADE_ENTRY, EV.BACK, {}, S.NAME_ENTRY, ()),
    (S.GRADE_ENTRY, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (
        S.OGEPREP_CHECK,
        EV.OGEPREP_YES,
        {},
        S.CONSENT_GATE,
        (E.SET_OGEPREP_YES, E.SET_ENROLLMENT_RETAKE, E.READ_POLICY_VERSION),
    ),
    (S.OGEPREP_CHECK, EV.OGEPREP_NO, {}, S.COURSE_MISMATCH, (E.SET_OGEPREP_NO,)),
    (S.OGEPREP_CHECK, EV.BACK, {}, S.GRADE_ENTRY, ()),
    (S.OGEPREP_CHECK, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (
        S.COURSE_MISMATCH,
        EV.MISMATCH_CONTINUE,
        {},
        S.CONSENT_GATE,
        (E.SET_ENROLLMENT_RETAKE, E.READ_POLICY_VERSION),
    ),
    (S.COURSE_MISMATCH, EV.MISMATCH_LEAVE, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (S.COURSE_MISMATCH, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (
        S.CONSENT_GATE,
        EV.SUBMIT_REGISTRATION,
        {"name_present": True, "grade": 9, "pd_consent_checked": True},
        S.REGISTERED,
        (E.CREATE_ACCOUNT,),
    ),
    (S.CONSENT_GATE, EV.BACK, {}, S.GRADE_ENTRY, (E.RESET_CONSENT,)),
    (S.CONSENT_GATE, EV.CANCEL_REGISTRATION, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
    (S.GATE_GRADE8, EV.GATE_DISMISS, {}, S.UNREGISTERED, (E.DESTROY_DRAFT,)),
]


@pytest.mark.parametrize("src,event,ctx_kwargs,dest,effects", CASES)
def test_transition(src, event, ctx_kwargs, dest, effects):
    result = dispatch(src, event, with_context(**ctx_kwargs))
    assert result.new_state == dest
    assert result.effects == effects


def test_cases_cover_every_transition():
    """Каждый физический переход покрыт ровно одним кейсом (src/event/dest + гард)."""
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
    assert remaining == []
    assert len(CASES) == len(TRANSITIONS)


def test_state_and_event_counts():
    """Регрессия против reg v2 §2b: 8 состояний, 11 событий."""
    assert len(STATES) == 8
    assert len(EVENTS) == 11


# --- Структурные свойства ---


def test_all_states_reachable_from_start():
    adjacency: dict[RegState, list[RegState]] = {s: [] for s in STATES}
    for t in TRANSITIONS:
        adjacency[t.src].append(t.dest)
    reached: set[RegState] = set()
    queue: deque[RegState] = deque([START_STATE])
    while queue:
        cur = queue.popleft()
        if cur in reached:
            continue
        reached.add(cur)
        queue.extend(adjacency[cur])
    assert reached == set(STATES), f"недостижимы: {set(STATES) - reached}"


def test_only_end_states_have_no_outgoing():
    """Тупиков нет, кроме терминала registered (end под-FSM)."""
    with_outgoing = {t.src for t in TRANSITIONS}
    dead = set(STATES) - with_outgoing
    assert dead == END_STATES, f"неожиданные тупики: {dead - END_STATES}"


# --- Взаимоисключающие гарды ветки по классу ---


def test_grade_branch_resolves_uniquely():
    assert (
        dispatch(
            S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=8, is_production=True)
        ).new_state
        == S.GATE_GRADE8
    )
    assert (
        dispatch(S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=9)).new_state
        == S.CONSENT_GATE
    )
    assert (
        dispatch(S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=10)).new_state
        == S.OGEPREP_CHECK
    )
    assert (
        dispatch(S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=11)).new_state
        == S.OGEPREP_CHECK
    )


# --- Edge cases (reg v2 §5) ---


def test_rc02_empty_name_blocked():
    """RC-02: пустое имя — переход не происходит (гард name_present)."""
    with pytest.raises(GuardError):
        dispatch(S.NAME_ENTRY, EV.NAME_SUBMITTED, with_context(name_present=False))


def test_rc03_submit_without_consent_blocked():
    """RC-03: submit без согласия на ПД — отклонён (152-ФЗ, нет согласия)."""
    with pytest.raises(GuardError):
        dispatch(
            S.CONSENT_GATE,
            EV.SUBMIT_REGISTRATION,
            with_context(name_present=True, grade=9, pd_consent_checked=False),
        )


def test_rc04_grade8_production_hard_gate():
    """RC-04: grade=8 в production (минуя UI) — гейт, аккаунт не создаётся."""
    result = dispatch(
        S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=8, is_production=True)
    )
    assert result.new_state == S.GATE_GRADE8
    assert E.CREATE_ACCOUNT not in result.effects


@pytest.mark.parametrize("bad_grade", [7, 12, 0])
def test_rc05_grade_out_of_range_blocked(bad_grade):
    """RC-05: класс вне 8–11 — ни один гард ветки по классу не проходит."""
    with pytest.raises(GuardError):
        dispatch(S.GRADE_ENTRY, EV.GRADE_SELECTED, with_context(grade=bad_grade))


def test_submit_grade_not_allowed_blocked():
    """Submit с классом вне (9,10,11) отклоняется гардом (защита бэкенда)."""
    with pytest.raises(GuardError):
        dispatch(
            S.CONSENT_GATE,
            EV.SUBMIT_REGISTRATION,
            with_context(name_present=True, grade=8, pd_consent_checked=True),
        )


def test_staging_grade8_undefined_in_spec():
    """grade=8 вне production: reg v2 §2b не определяет переход → GuardError.

    Зафиксировано как вопрос к Архитектору (А3): спека закрывает D-6 жёстким
    гейтом только для production; путь staging grade=8 в под-FSM не задан.
    """
    with pytest.raises(GuardError):
        dispatch(
            S.GRADE_ENTRY,
            EV.GRADE_SELECTED,
            with_context(grade=8, is_production=False),
        )


def test_unknown_event_raises():
    # В name_entry нет события grade_selected.
    with pytest.raises(UnknownTransitionError):
        dispatch(S.NAME_ENTRY, EV.GRADE_SELECTED, with_context(grade=9))
    # evt_back из name_entry не определён (первый шаг — назад = cancel).
    with pytest.raises(UnknownTransitionError):
        dispatch(S.NAME_ENTRY, EV.BACK)


# --- Сквозные сценарии R-01..R-05 ---


def _run(path: list[tuple[RegState, RegEvent, dict]]) -> RegState:
    state = path[0][0]
    for src, event, ctx_kwargs in path:
        assert state == src
        state = dispatch(src, event, with_context(**ctx_kwargs)).new_state
    return state


def test_r01_grade9_direct_happy_path():
    end = _run(
        [
            (S.UNREGISTERED, EV.OPEN_PWA, {}),
            (S.NAME_ENTRY, EV.NAME_SUBMITTED, {"name_present": True}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 9}),
            (
                S.CONSENT_GATE,
                EV.SUBMIT_REGISTRATION,
                {"name_present": True, "grade": 9, "pd_consent_checked": True},
            ),
        ]
    )
    assert end == S.REGISTERED


def test_r02_grade10_retake():
    end = _run(
        [
            (S.UNREGISTERED, EV.OPEN_PWA, {}),
            (S.NAME_ENTRY, EV.NAME_SUBMITTED, {"name_present": True}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 10}),
            (S.OGEPREP_CHECK, EV.OGEPREP_YES, {}),
            (
                S.CONSENT_GATE,
                EV.SUBMIT_REGISTRATION,
                {"name_present": True, "grade": 10, "pd_consent_checked": True},
            ),
        ]
    )
    assert end == S.REGISTERED


def test_r03_grade11_mismatch_then_continue():
    end = _run(
        [
            (S.UNREGISTERED, EV.OPEN_PWA, {}),
            (S.NAME_ENTRY, EV.NAME_SUBMITTED, {"name_present": True}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 11}),
            (S.OGEPREP_CHECK, EV.OGEPREP_NO, {}),
            (S.COURSE_MISMATCH, EV.MISMATCH_CONTINUE, {}),
            (
                S.CONSENT_GATE,
                EV.SUBMIT_REGISTRATION,
                {"name_present": True, "grade": 11, "pd_consent_checked": True},
            ),
        ]
    )
    assert end == S.REGISTERED


def test_r04_grade8_gate_dismiss():
    end = _run(
        [
            (S.UNREGISTERED, EV.OPEN_PWA, {}),
            (S.NAME_ENTRY, EV.NAME_SUBMITTED, {"name_present": True}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 8, "is_production": True}),
            (S.GATE_GRADE8, EV.GATE_DISMISS, {}),
        ]
    )
    assert end == S.UNREGISTERED


def test_rc09_back_from_consent_then_grade8_gate():
    """RC-09: назад из consent, смена класса на 8 (prod) → гейт; аккаунт не создан."""
    end = _run(
        [
            (S.UNREGISTERED, EV.OPEN_PWA, {}),
            (S.NAME_ENTRY, EV.NAME_SUBMITTED, {"name_present": True}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 9}),
            (S.CONSENT_GATE, EV.BACK, {}),
            (S.GRADE_ENTRY, EV.GRADE_SELECTED, {"grade": 8, "is_production": True}),
            (S.GATE_GRADE8, EV.GATE_DISMISS, {}),
        ]
    )
    assert end == S.UNREGISTERED


def test_r05_cancel_from_any_step():
    for state, ctx in [
        (S.NAME_ENTRY, {}),
        (S.GRADE_ENTRY, {}),
        (S.OGEPREP_CHECK, {}),
        (S.COURSE_MISMATCH, {}),
        (S.CONSENT_GATE, {}),
    ]:
        result = dispatch(state, EV.CANCEL_REGISTRATION, with_context(**ctx))
        assert result.new_state == S.UNREGISTERED
        assert E.DESTROY_DRAFT in result.effects


# --- Хелперы ---


def test_can_handle_and_valid_events():
    assert can_handle(S.UNREGISTERED, EV.OPEN_PWA) is True
    assert can_handle(S.NAME_ENTRY, EV.GRADE_SELECTED, with_context(grade=9)) is False
    assert valid_events(S.GATE_GRADE8) == {EV.GATE_DISMISS}
    assert EV.SUBMIT_REGISTRATION in valid_events(S.CONSENT_GATE)
