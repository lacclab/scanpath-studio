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

session=$(printf '%s' "$input" | jq -r '.session_id // "unknown"' 2>/dev/null)
transcript=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null)
root=${CLAUDE_PROJECT_DIR:-.}

# The message is in the command (-m, a heredoc) or in the file -F names.
message=$cmd
file=$(printf '%s' "$cmd" | sed -nE 's/.*(-F|--file)[ =]([^ ]*).*/\2/p' | head -1)
if [ -n "$file" ] && [ -f "$file" ]; then
  message=$(cat "$file")
fi

if printf '%s' "$message" | grep -q 'Verified:'; then
  trailer=yes
else
  trailer=no
fi

# Did the session run anything? A cheap look at the transcript, for the log.
ran=none
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  if grep -q 'verify_change.py' "$transcript"; then
    ran=harness
  elif grep -q 'pytest' "$transcript"; then
    ran=tests
  fi
fi

log="$root/.claude/commit-gate.log"
printf '%s\t%s\tmode=%s\ttrailer=%s\tran=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$session" "$mode" "$trailer" "$ran" >>"$log" 2>/dev/null

[ "$mode" = enforce ] || exit 0
[ "$trailer" = yes ] && exit 0

# Let the third attempt through, so the gate can't wedge a session.
blocks=$(grep -c "^$session	" "$root/.claude/commit-gate-blocks.log" 2>/dev/null)
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
