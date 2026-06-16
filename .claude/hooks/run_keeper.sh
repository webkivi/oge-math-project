#!/usr/bin/env bash
# PostToolUse hook: при записи/правке *.csv прогоняет keeper.py.
# exit 0 — ок/не CSV; exit 2 — keeper FAIL (stderr показывается Claude, он исправляет).
# Зависимость: jq. CLAUDE_PROJECT_DIR выставляет Claude Code.
set -u

input=$(cat)
fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$fp" ] && exit 0

case "$fp" in
  *.csv) ;;
  *) exit 0 ;;
esac

# Найди keeper.py (поправь путь под свою раскладку, если нужно).
KP="${CLAUDE_PROJECT_DIR}/tools/keeper.py"
[ -f "$KP" ] || KP="${CLAUDE_PROJECT_DIR}/keeper.py"
if [ ! -f "$KP" ]; then
  echo "keeper.py не найден (ожидался в tools/ или в корне) — пропускаю проверку $fp" >&2
  exit 0
fi

# Подстрой вызов под фактический CLI твоего keeper.py (файл-аргумент или скан всего).
out=$(python3 "$KP" "$fp" 2>&1)
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "keeper.py FAIL для $fp:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
