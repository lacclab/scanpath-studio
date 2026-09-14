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

# Use the ruff pinned in pyproject's `lint` extra, not whatever is on PATH
# (ENG-48). This matters more than it looks: ruff 0.16 enables ~413 rules by
# default where 0.14 enables a handful, so a stale PATH ruff passes edits at
# the keyboard that CI's pinned ruff then rejects — which is exactly how five
# findings accumulated on main while every local run looked clean.
[ -n "$CLAUDE_PROJECT_DIR" ] && cd "$CLAUDE_PROJECT_DIR" 2>/dev/null
if command -v uv >/dev/null 2>&1 && uv run --extra lint ruff --version >/dev/null 2>&1; then
  run_ruff() { uv run --extra lint ruff "$@"; }
elif command -v ruff >/dev/null 2>&1; then
  # Fall back rather than block an edit, but say so: findings may be missing.
  echo "ruff-on-edit: using PATH ruff ($(ruff --version)); the pinned version is authoritative." >&2
  run_ruff() { ruff "$@"; }
else
  exit 0
fi

run_ruff format --quiet "$f" >/dev/null 2>&1

if ! out=$(run_ruff check "$f" 2>&1); then
  printf '%s\n' "$out" >&2
  exit 2
fi
exit 0
