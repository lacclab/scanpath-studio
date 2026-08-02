#!/bin/sh
# PostToolUse hook: auto-format + lint every Python file Claude edits.
# Enforces the "run ruff first — always" working agreement at edit time.
# Exit 2 feeds ruff's findings back to Claude so it fixes them immediately.

input=$(cat)
f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$f" in
  */other_vis/*) exit 0 ;;
  *.py) ;;
  *) exit 0 ;;
esac

[ -f "$f" ] || exit 0
command -v ruff >/dev/null 2>&1 || exit 0

ruff format --quiet "$f" >/dev/null 2>&1

if ! out=$(ruff check "$f" 2>&1); then
  printf '%s\n' "$out" >&2
  exit 2
fi
exit 0
