#!/bin/sh
# PostToolUse hook: auto-format + lint every Python file Claude edits.
# Enforces the "run ruff first — always" working agreement at edit time.
# Exit 2 feeds ruff's findings back to Claude so it fixes them immediately.

input=$(cat)
f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

case "$f" in
  *.py) ;;
  *) exit 0 ;;
esac

[ -f "$f" ] || exit 0

# Run the ruff pinned in the edited checkout's own pyproject `lint` extra, not
# whatever is on PATH (ENG-48, ENG-69): ruff 0.16 enables ~413 rules where 0.14
# enables a handful, so a stale PATH ruff passes edits that CI's pinned ruff
# rejects. `uvx` runs the pin in its own cached tool environment, so the hook
# never syncs a project venv or writes a lock file — a worktree's edit must not
# touch the main checkout's environment.
root=$(git -C "$(dirname "$f")" rev-parse --show-toplevel 2>/dev/null)
pin=$(grep -oE '"ruff==[0-9][0-9.]*"' "${root:-.}/pyproject.toml" 2>/dev/null | head -1 | tr -d '"')
if [ -n "$pin" ] && command -v uvx >/dev/null 2>&1 && uvx --quiet --from "$pin" ruff --version >/dev/null 2>&1; then
  run_ruff() { uvx --quiet --from "$pin" ruff "$@"; }
elif command -v ruff >/dev/null 2>&1; then
  # Fall back rather than block an edit, but say so: findings may be missing.
  echo "ruff-on-edit: using PATH ruff ($(ruff --version)); the pinned ${pin:-version} is authoritative." >&2
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
