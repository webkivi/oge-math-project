#!/usr/bin/env bash
# PostToolUse hook: при записи/правке спеки или FSM-YAML прогоняет validator.py.
# Реагирует на *.yaml/*.yml и на файлы в specs/*.md (там лежат YAML-блоки FSM).
# exit 0 — ок/не релевантно; exit 2 — validator FAIL (stderr виден Claude).
set -u

input=$(cat)
fp=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$fp" ] && exit 0

case "$fp" in
  *.yaml|*.yml) ;;
  *specs/*.md) ;;
  *) exit 0 ;;
esac

VP="${CLAUDE_PROJECT_DIR}/tools/validator.py"
if [ ! -f "$VP" ]; then
  echo "validator.py не найден в tools/ — пропускаю проверку $fp" >&2
  exit 0
fi

out=$(python3 "$VP" "$fp" 2>&1)
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "validator.py FAIL для $fp:" >&2
  echo "$out" >&2
  exit 2
fi
exit 0
