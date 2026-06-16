#!/usr/bin/env python3
"""validator.py — детерминированный шлюз на артефакты Архитектора (Агент 3).

Читает FSM-YAML и матрицу прав по контракту А3 и механически проверяет:
  - ровно одно состояние type: start на роль;
  - каждое не-end состояние имеет хотя бы один исходящий переход;
  - переходы ссылаются только на определённые states и events;
  - достижимость всех состояний из start (BFS); недостижимые — нарушение;
  - матрица прав: operation из допустимого набора, allow — bool,
    нет дублей (role, resource, operation) с конфликтом, перечисляет покрытие.

Вход: путь к .yaml/.yml ИЛИ к specs/*.md (тогда извлекаются ```yaml блоки).
Выход: печатает PASS / список нарушений; код возврата 0 (PASS) или 1 (FAIL).

Зависимость: pyyaml (pip install pyyaml).
Контракт менять только связкой А3 -> А4 -> validator (Brain, решение 2026-06-16).
"""
from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    print("validator.py: нужен pyyaml -> pip install pyyaml", file=sys.stderr)
    sys.exit(2)

VALID_STATE_TYPES = {"start", "normal", "end"}
VALID_OPERATIONS = {"read", "write", "create", "delete"}
_SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
_YAML_BLOCK = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)


def _extract_docs(path: Path) -> list[dict[str, Any]]:
    """Вернуть список YAML-документов из файла (.yaml целиком или ```yaml из .md)."""
    text = path.read_text(encoding="utf-8")
    raw_blocks: list[str]
    if path.suffix.lower() in {".yaml", ".yml"}:
        raw_blocks = [text]
    else:
        raw_blocks = _YAML_BLOCK.findall(text)
        if not raw_blocks:
            return []
    docs: list[dict[str, Any]] = []
    for block in raw_blocks:
        for doc in yaml.safe_load_all(block):
            if isinstance(doc, dict):
                docs.append(doc)
    return docs


def _check_fsm(doc: dict[str, Any], errors: list[str]) -> None:
    """Проверить один FSM-блок (имеет ключи role/states/transitions)."""
    role = doc.get("role", "<без role>")
    states = doc.get("states") or []
    events = doc.get("events") or []
    transitions = doc.get("transitions") or []

    state_ids: dict[str, str] = {}
    for st in states:
        sid = st.get("id")
        stype = st.get("type")
        if not sid or not _SNAKE.match(str(sid)):
            errors.append(f"[{role}] state.id не snake_case: {sid!r}")
            continue
        if stype not in VALID_STATE_TYPES:
            errors.append(f"[{role}] state {sid}: type {stype!r} не из {VALID_STATE_TYPES}")
        state_ids[sid] = stype

    starts = [s for s, t in state_ids.items() if t == "start"]
    if len(starts) != 1:
        errors.append(f"[{role}] должно быть ровно одно state type:start, найдено {len(starts)}: {starts}")

    event_ids = {e.get("id") for e in events if e.get("id")}

    outgoing: dict[str, int] = {s: 0 for s in state_ids}
    adjacency: dict[str, list[str]] = {s: [] for s in state_ids}
    for tr in transitions:
        frm, ev, to = tr.get("from"), tr.get("event"), tr.get("to")
        if frm not in state_ids:
            errors.append(f"[{role}] transition.from {frm!r} не объявлен в states")
        if to not in state_ids:
            errors.append(f"[{role}] transition.to {to!r} не объявлен в states")
        if ev not in event_ids:
            errors.append(f"[{role}] transition.event {ev!r} не объявлен в events")
        if frm in outgoing:
            outgoing[frm] += 1
            if to in state_ids:
                adjacency[frm].append(to)

    for sid, stype in state_ids.items():
        if stype != "end" and outgoing.get(sid, 0) == 0:
            errors.append(f"[{role}] состояние {sid} (type {stype}) без исходящих переходов — тупик")

    # Достижимость из start (если start ровно один).
    if len(starts) == 1:
        reached: set[str] = set()
        q: deque[str] = deque([starts[0]])
        while q:
            cur = q.popleft()
            if cur in reached:
                continue
            reached.add(cur)
            for nxt in adjacency.get(cur, []):
                if nxt not in reached:
                    q.append(nxt)
        unreachable = set(state_ids) - reached
        if unreachable:
            errors.append(f"[{role}] недостижимы из start: {sorted(unreachable)}")


def _check_permissions(perms: list[dict[str, Any]], errors: list[str]) -> set[tuple[str, str]]:
    """Проверить матрицу прав. Вернуть множество (role, resource) для отчёта покрытия."""
    seen: dict[tuple[str, str, str], bool] = {}
    coverage: set[tuple[str, str]] = set()
    for p in perms:
        role = p.get("role")
        resource = p.get("resource")
        operation = p.get("operation")
        allow = p.get("allow")
        if operation not in VALID_OPERATIONS:
            errors.append(f"permission {role}/{resource}: operation {operation!r} не из {VALID_OPERATIONS}")
        if not isinstance(allow, bool):
            errors.append(f"permission {role}/{resource}/{operation}: allow должен быть true|false, а не {allow!r}")
        key = (role, resource, operation)
        if key in seen and seen[key] != allow:
            errors.append(f"permission {role}/{resource}/{operation}: конфликт allow ({seen[key]} vs {allow})")
        seen[key] = allow if isinstance(allow, bool) else seen.get(key, False)
        if role and resource:
            coverage.add((role, resource))
    return coverage


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    docs = _extract_docs(path)
    if not docs:
        return [f"в {path} не найдено YAML-блоков (FSM/permissions)"]

    fsm_count = 0
    perm_count = 0
    coverage: set[tuple[str, str]] = set()
    for doc in docs:
        if "permissions" in doc and isinstance(doc["permissions"], list):
            perm_count += 1
            coverage |= _check_permissions(doc["permissions"], errors)
        if "states" in doc and "transitions" in doc:
            fsm_count += 1
            _check_fsm(doc, errors)

    if fsm_count == 0 and perm_count == 0:
        errors.append("ни одного валидного FSM- или permissions-блока не распознано")

    # Отчёт покрытия прав — не ошибка, подсказка для А4/фаундера про NULL-ячейки.
    if coverage:
        pairs = ", ".join(f"{r}/{res}" for r, res in sorted(coverage))
        print(f"[i] матрица прав покрывает пары роль/ресурс: {pairs}", file=sys.stderr)

    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print("использование: python tools/validator.py <spec.md | fsm.yaml>", file=sys.stderr)
        return 0 if argv[1:] == ["--help"] or argv[1:] == ["-h"] else 2
    path = Path(argv[1])
    if not path.exists():
        print(f"файл не найден: {path}", file=sys.stderr)
        return 2
    errors = validate(path)
    if errors:
        print(f"validator.py FAIL ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("validator.py PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
