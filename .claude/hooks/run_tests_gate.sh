#!/usr/bin/env bash
# PreToolUse hook на git commit: блокирует коммит, если pytest красный (CLAUDE.md §5).
# exit 0 — пропустить (тестов нет / зелёные); exit 2 — заблокировать коммит.
set -u

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

cd "${CLAUDE_PROJECT_DIR}" 2>/dev/null || exit 0

# Если тестов ещё нет (ранний этап) — не мешаем.
if [ ! -d tests ] && [ ! -f pytest.ini ] && [ ! -f pyproject.toml ]; then
  exit 0
fi

if command -v pytest >/dev/null 2>&1 || python3 -c "import pytest" 2>/dev/null; then
  out=$(python3 -m pytest -q 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "Тесты красные — коммит заблокирован (CLAUDE.md §5):" >&2
    echo "$out" | tail -n 30 >&2
    exit 2
  fi
fi
exit 0
