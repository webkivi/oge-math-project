"""registration_engine.py — конечный автомат регистрации ученика (онбординг).

Источник истины: specs/student_registration_fsm_v2.md §2 (под-FSM фазы onboarding,
детализирует переход v4 `unregistered → onboarding → registered`). Чистый
детерминированный движок (как lesson_engine): состояния/события/переходы/гарды +
дескрипторы сайд-эффектов. БД не трогается — `dispatch` возвращает (новое
состояние, эффекты); исполнение (создание аккаунта, идемпотентность по
onboarding_session_id, уничтожение черновика) — зона onboarding/auth-сервиса.

Принципиальное по спеке:
- RegistrationDraft НЕ персистентен (reg v2 §1, 152-ФЗ): живёт в памяти/сессии
  онбординга; в БД пишется только User/StudentProfile/Session на submit.
- grade=8 в production — ЖЁСТКИЙ ГЕЙТ (gate_grade8), аккаунт не создаётся (D-6
  закрыта). Поведение grade=8 вне production спекой v2 не определено (см. note ниже).
- course_mismatch достижим ТОЛЬКО из ogeprep_check (grade 10/11); самооценка
  grade=9 — UI-информер вне FSM (правка №3).
- При входе в consent_gate перечитывается policy_version_shown (правка №6) —
  эффект READ_POLICY_VERSION на переходах в consent_gate.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, replace

# Generic-исключения FSM переиспользуем из lesson_engine (они не привязаны к типам).
from backend.engine.lesson_engine import (
    AmbiguousTransitionError,
    GuardError,
    UnknownTransitionError,
)

# Допустимые для регистрации классы (reg v2: prod 9..11; grade=8 — гейт).
ALLOWED_GRADES = frozenset({9, 10, 11})
OGEPREP_GRADES = frozenset({10, 11})  # уточнение про ОГЭ задаётся только им
GATE_GRADE = 8


class RegState(enum.StrEnum):
    UNREGISTERED = "unregistered"  # start (стык с v4)
    NAME_ENTRY = "name_entry"
    GRADE_ENTRY = "grade_entry"
    OGEPREP_CHECK = "ogeprep_check"
    COURSE_MISMATCH = "course_mismatch"
    CONSENT_GATE = "consent_gate"
    GATE_GRADE8 = "gate_grade8"
    REGISTERED = "registered"  # end под-FSM (стык в v4 → daily_start)


class RegEvent(enum.StrEnum):
    OPEN_PWA = "evt_open_pwa"
    NAME_SUBMITTED = "evt_name_submitted"
    GRADE_SELECTED = "evt_grade_selected"
    OGEPREP_YES = "evt_ogeprep_yes"
    OGEPREP_NO = "evt_ogeprep_no"
    MISMATCH_CONTINUE = "evt_mismatch_continue"
    MISMATCH_LEAVE = "evt_mismatch_leave"
    SUBMIT_REGISTRATION = "evt_submit_registration"
    BACK = "evt_back"
    CANCEL_REGISTRATION = "evt_cancel_registration"
    GATE_DISMISS = "evt_gate_dismiss"


class RegSideEffect(enum.StrEnum):
    """Дескрипторы эффектов. Исполняет onboarding/auth-сервис (БД/сессия)."""

    CREATE_DRAFT = "create_draft"  # RegistrationDraft + onboarding_session_id (не БД)
    SAVE_NAME = "save_name"  # в черновик (не БД)
    SET_ENROLLMENT_GRADE9 = "set_enrollment_grade9_direct"
    SET_ENROLLMENT_RETAKE = "set_enrollment_grade10plus_retake"
    SET_OGEPREP_YES = "set_ogeprep_yes"
    SET_OGEPREP_NO = "set_ogeprep_no"
    READ_POLICY_VERSION = (
        "read_policy_version"  # перечитать policy_version_shown (правка №6)
    )
    RESET_CONSENT = "reset_consent"  # сброс согласия в черновике при evt_back
    # Атомарно: User + StudentProfile + Session; идемпотентно по onboarding_session_id;
    # consent_cohort_flag если grade==9 и Z-1 открыта (reg v2 §1, RC-07/RF-07).
    CREATE_ACCOUNT = "create_account"
    DESTROY_DRAFT = "destroy_draft"  # cancel / гейт / уход — ПД в БД не пишутся


@dataclass(frozen=True)
class RegContext:
    """Входы гардов онбординга. Значения по умолчанию безопасны."""

    name_present: bool = False  # имя непустое после trim
    grade: int | None = None  # выбранный класс
    is_production: bool = True  # среда (D-6: grade=8 гейтится в production)
    pd_consent_checked: bool = False  # согласие на ПД отмечено


@dataclass(frozen=True)
class RegTransition:
    src: RegState
    event: RegEvent
    dest: RegState
    guard: Callable[[RegContext], bool] | None = None
    effects: tuple[RegSideEffect, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class RegTransitionResult:
    new_state: RegState
    effects: tuple[RegSideEffect, ...]


_E = RegSideEffect

TRANSITIONS: tuple[RegTransition, ...] = (
    # --- Вход ---
    RegTransition(
        RegState.UNREGISTERED,
        RegEvent.OPEN_PWA,
        RegState.NAME_ENTRY,
        effects=(_E.CREATE_DRAFT,),
        note="первый вход; создаётся RegistrationDraft с onboarding_session_id (не БД)",
    ),
    # --- Имя ---
    RegTransition(
        RegState.NAME_ENTRY,
        RegEvent.NAME_SUBMITTED,
        RegState.GRADE_ENTRY,
        guard=lambda c: c.name_present,
        effects=(_E.SAVE_NAME,),
        note="name непустое после trim",
    ),
    RegTransition(
        RegState.NAME_ENTRY,
        RegEvent.CANCEL_REGISTRATION,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    # --- Класс / ветка по классу ---
    RegTransition(
        RegState.GRADE_ENTRY,
        RegEvent.GRADE_SELECTED,
        RegState.GATE_GRADE8,
        guard=lambda c: c.grade == GATE_GRADE and c.is_production,
        note="grade=8 в production — жёсткий гейт; User НЕ создаётся (D-6)",
    ),
    RegTransition(
        RegState.GRADE_ENTRY,
        RegEvent.GRADE_SELECTED,
        RegState.CONSENT_GATE,
        guard=lambda c: c.grade == 9,
        effects=(_E.SET_ENROLLMENT_GRADE9, _E.READ_POLICY_VERSION),
        note="grade=9 — прямой вход; ogeprep_answer=null by design",
    ),
    RegTransition(
        RegState.GRADE_ENTRY,
        RegEvent.GRADE_SELECTED,
        RegState.OGEPREP_CHECK,
        guard=lambda c: c.grade in OGEPREP_GRADES,
        note="grade 10/11 — уточнение про ОГЭ/пересдачу",
    ),
    RegTransition(RegState.GRADE_ENTRY, RegEvent.BACK, RegState.NAME_ENTRY),
    RegTransition(
        RegState.GRADE_ENTRY,
        RegEvent.CANCEL_REGISTRATION,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    # --- Уточнение ОГЭ (grade 10/11) ---
    RegTransition(
        RegState.OGEPREP_CHECK,
        RegEvent.OGEPREP_YES,
        RegState.CONSENT_GATE,
        effects=(_E.SET_OGEPREP_YES, _E.SET_ENROLLMENT_RETAKE, _E.READ_POLICY_VERSION),
        note="готовится/пересдаёт — впуск как пересдача",
    ),
    RegTransition(
        RegState.OGEPREP_CHECK,
        RegEvent.OGEPREP_NO,
        RegState.COURSE_MISMATCH,
        effects=(_E.SET_OGEPREP_NO,),
        note="не готовится — экран «курс не подходит» (единственный вход)",
    ),
    RegTransition(RegState.OGEPREP_CHECK, RegEvent.BACK, RegState.GRADE_ENTRY),
    RegTransition(
        RegState.OGEPREP_CHECK,
        RegEvent.CANCEL_REGISTRATION,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    # --- Экран «курс не подходит» (информирующий, не блокирующий) ---
    RegTransition(
        RegState.COURSE_MISMATCH,
        RegEvent.MISMATCH_CONTINUE,
        RegState.CONSENT_GATE,
        effects=(_E.SET_ENROLLMENT_RETAKE, _E.READ_POLICY_VERSION),
        note="ученик решил всё равно начать (§1.4 запрещает блокировку)",
    ),
    RegTransition(
        RegState.COURSE_MISMATCH,
        RegEvent.MISMATCH_LEAVE,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    RegTransition(
        RegState.COURSE_MISMATCH,
        RegEvent.CANCEL_REGISTRATION,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    # --- Согласие ПД + создание аккаунта ---
    RegTransition(
        RegState.CONSENT_GATE,
        RegEvent.SUBMIT_REGISTRATION,
        RegState.REGISTERED,
        guard=lambda c: c.name_present
        and c.grade in ALLOWED_GRADES
        and c.pd_consent_checked,
        effects=(_E.CREATE_ACCOUNT,),
        note="name + grade IN (9,10,11) + pd_consent; идемпотентность по session_id",
    ),
    RegTransition(
        RegState.CONSENT_GATE,
        RegEvent.BACK,
        RegState.GRADE_ENTRY,
        effects=(_E.RESET_CONSENT,),
        note="назад к выбору класса; согласие сбрасывается, policy перечитается заново",
    ),
    RegTransition(
        RegState.CONSENT_GATE,
        RegEvent.CANCEL_REGISTRATION,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
    ),
    # --- Жёсткий гейт grade=8 ---
    RegTransition(
        RegState.GATE_GRADE8,
        RegEvent.GATE_DISMISS,
        RegState.UNREGISTERED,
        effects=(_E.DESTROY_DRAFT,),
        note="тёплый экран «возвращайся в сентябре»; аккаунт не создан, ПД не записаны",
    ),
)

START_STATE: RegState = RegState.UNREGISTERED
END_STATES: frozenset[RegState] = frozenset({RegState.REGISTERED})
STATES: frozenset[RegState] = frozenset(RegState)
EVENTS: frozenset[RegEvent] = frozenset(RegEvent)


def _transitions_for(state: RegState, event: RegEvent) -> list[RegTransition]:
    return [t for t in TRANSITIONS if t.src == state and t.event == event]


def dispatch(
    state: RegState, event: RegEvent, ctx: RegContext | None = None
) -> RegTransitionResult:
    """Выполнить переход онбординга по (состояние, событие, контекст).

    UnknownTransitionError — пара (состояние, событие) не определена; GuardError —
    переходы есть, но ни один гард не прошёл; AmbiguousTransitionError — подошло
    больше одного (дефект таблицы). Движок ничего не мутирует.
    """
    ctx = ctx or RegContext()
    candidates = _transitions_for(state, event)
    if not candidates:
        raise UnknownTransitionError(f"нет перехода из {state} по {event}")
    matching = [t for t in candidates if t.guard is None or t.guard(ctx)]
    if not matching:
        raise GuardError(f"из {state} по {event} ни один гард не выполнен (ctx={ctx})")
    if len(matching) > 1:
        raise AmbiguousTransitionError(
            f"из {state} по {event} подошло несколько: {[t.dest for t in matching]}"
        )
    chosen = matching[0]
    return RegTransitionResult(new_state=chosen.dest, effects=chosen.effects)


def can_handle(state: RegState, event: RegEvent, ctx: RegContext | None = None) -> bool:
    try:
        dispatch(state, event, ctx)
    except (UnknownTransitionError, GuardError, AmbiguousTransitionError):
        return False
    return True


def valid_events(state: RegState) -> set[RegEvent]:
    return {t.event for t in TRANSITIONS if t.src == state}


def with_context(**overrides: object) -> RegContext:
    """Конструктор контекста от дефолтного (для вызовов и тестов)."""
    return replace(RegContext(), **overrides)
