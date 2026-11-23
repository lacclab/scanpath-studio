#!/bin/sh
# PreToolUse hook on Bash: a commit says how it was verified.
#
# Every commit Claude makes should carry a `Verified:` trailer naming what ran
# (`Verified: harness, apptest, browser`, `Verified: tests`, or
# `Verified: none — docs only`), so an unverified commit can be found later
# with `git log --grep='^Verified: none'`, and one with no trailer at all
# stands out.
#
# SCANPATH_COMMIT_GATE picks the mode:
#   observe (default) — never blocks; logs each commit to
#                       .claude/commit-gate.log with whether it had a trailer
#                       and whether the session ran any tests, so false
#                       positives show up before anything is enforced.
#   enforce           — blocks a commit with no trailer, and says why. After
#                       two blocks in one session the next commit goes through,
#                       so a session can't get stuck on the gate.
#   off               — does nothing.
#
# It is a convention check, not a security boundary: the agent writes the
# trailer itself, and enforce mode lets the third try through on purpose. So it
# fails open — no jq, unreadable input — rather than wedging a session.

mode=${SCANPATH_COMMIT_GATE:-observe}
[ "$mode" = off ] && exit 0

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)

case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac
# An amend that keeps its message, or a merge commit, has nothing to check.
case "$cmd" in
  *"--no-edit"*) exit 0 ;;
esac

# The id names this session's lines in the logs; keep it to safe characters,
# since it is matched as text below.
session=$(printf '%s' "$input" | jq -r '.session_id // "unknown"' 2>/dev/null | tr -cd 'A-Za-z0-9_-')
session=${session:-unknown}
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null)
root=${CLAUDE_PROJECT_DIR:-.}

# The message is in the command (-m, a heredoc) or in the file -F names.
message=$cmd
file=$(printf '%s' "$cmd" | sed -nE 's/.*(-F|--file)[ =]([^ ]*).*/\2/p' | head -1)
if [ -n "$file" ] && [ -f "$file" ]; then
  message=$(cat "$file")
fi

# A trailer is a line of its own that starts with `Verified:`.
if printf '%s\n' "$message" | grep -Eq '^[[:space:]]*Verified:'; then
  trailer=yes
else
  trailer=no
fi

# Did the session run anything? Only the shell commands it issued count: the
# project instructions name `verify_change.py` and `pytest` and sit in every
# transcript. Each command is cut at its `git commit` (the message may name
# them too) and split into the programs it chains; a program counts when, past
# its environment assignments, `time` and `uv run` options, it is Python running
# the harness, or pytest. Reading a file about either (`grep pytest …`) is not
# a run.
programs='select(.type == "assistant") | .message.content[]?
  | select(.type == "tool_use" and .name == "Bash") | .input.command // empty
  | sub("git commit[\\s\\S]*"; "")
  | splits("[;&|()\\n]+")
  | sub("^\\s+"; "")
  | sub("^((\\w+=\\S*|env|(\\S*/)?time|-p)\\s+)*"; "")
  | sub("^uv\\s+run\\s+((--(extra|with|python|group|package|directory|project)\\s+\\S+|--?[\\w-]+)\\s+)*"; "")
  | sub("^(\\S*/)?python[\\d.]*\\s+((-[IuBO]|-m)\\s+)*"; "")'
ran=none
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  run=$(jq -r "$programs" "$transcript" 2>/dev/null)
  if printf '%s\n' "$run" | grep -Eq '^(\S*/)?verify_change\.py([[:space:]]|$)'; then
    ran=harness
  elif printf '%s\n' "$run" | grep -Eq '^(\S*/)?pytest([[:space:]]|$)'; then
    ran=tests
  fi
fi

log="$root/.claude/commit-gate.log"
printf '%s\t%s\tmode=%s\ttrailer=%s\tran=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$session" "$mode" "$trailer" "$ran" >>"$log" 2>/dev/null

[ "$mode" = enforce ] || exit 0
[ "$trailer" = yes ] && exit 0

# Let the third attempt through, so the gate can't wedge a session.
blocks=$(cut -f1 "$root/.claude/commit-gate-blocks.log" 2>/dev/null | grep -cxF -- "$session")
if [ "${blocks:-0}" -ge 2 ]; then
  exit 0
fi
printf '%s\t%s\n' "$session" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"$root/.claude/commit-gate-blocks.log" 2>/dev/null

cat >&2 <<EOF
commit-gate: this commit message has no \`Verified:\` trailer.
Add one naming what you ran — e.g. \`Verified: harness, apptest, browser\` or
\`Verified: tests\` — or \`Verified: none\` with the reason (docs only, a
tooling change the app can't exercise). The /verify skill runs the harness.
(This session's tests so far: $ran.)
EOF
exit 2
