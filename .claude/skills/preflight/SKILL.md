---
name: preflight
description: Pre-commit gate for scanpath-studio — run ruff check + format, the test suite, and verify the changelog has an entry for the pending work; before a PR is opened or updated, also the diff-reviewer. Run before every commit/push.
disable-model-invocation: true
---

# Preflight — pre-commit gate

Run from the repository root. Run every check even if an earlier one fails,
then report all results together (pass/fail per check with the failing
output). Fix trivial failures (formatting) directly; report anything else.

## Checks

1. **Lint** — `uv run --extra lint ruff check .`
2. **Format** — `uv run --extra lint ruff format .` (CI gates on both; this
   one rewrites files — if it changed anything, say which files). Run these
   even for "docs-only" changes — repo rule.
3. **Tests** — the tests for what the diff touches, in the project's
   environment (`uv run --extra test pytest -n auto <files>` — not a bare
   `pytest` from `PATH`, which may be another interpreter and another pandas):
   `tests/test_<module>.py` for each changed module, every test file that names
   a changed function (`grep -l`), and `tests/test_properties.py` when a link,
   settings file or migration changed. CI runs the whole suite on the PR, so
   don't run it here as well — except when the diff changes machinery most
   tests go through (`conftest.py`, the session-state holds in `controls.py`,
   normalization in `data.py`, `plots.FigureSettings`).
4. **Changelog** — `git diff` + `git status` to see the pending work; if it
   is user-visible or a bug fix, it needs a fragment
   `changelog.d/<issue>.<group>.md` (or `<slug>.<group>.md` when there is no
   issue) holding one line of plain text
   (`changelog.d/README.md`). If missing, write it. `CHANGELOG.md` itself must
   **not** be in the diff — only a release edits it. Then
   `python scripts/changelog_fragments.py check`.
5. **Seen working** — for a change a user can observe, run
   `uv run --extra test python scripts/verify_change.py` (the `/verify` skill;
   pass the option's link / flag / keyword when it is a feature option). Report
   its PASS/FAIL lines.
6. **Issue** — if the pending work corresponds to a GitHub issue
   (`gh issue list`), check its board Status and body write-up are current.
   Finished work goes to Status **Review** with the review ask in its
   *⚖ Waiting on you* checklist — **never** close the issue yourself; that is
   the user's sign-off. Conventions in `CLAUDE.md` → *Tracking work*.
7. **Review** — before a PR is opened or updated (not before every commit),
   run the `diff-reviewer` subagent on the branch's diff against `origin/main`,
   plus the specialist whose area the diff touches (`surface-parity-reviewer`
   for a user-facing option or a wire-format key, `perf-reviewer` for anything
   on the rerun path). Fix its **Important** findings before the push, and
   say in the PR which findings were fixed and which were left, with why. A
   later round gets the earlier round's findings, so it checks those and what
   changed since.

## Reminders for the commit itself

- Never add a `Co-Authored-By: Claude …` (or any AI co-author) trailer.
- End the message with a `Verified:` trailer naming what ran (e.g.
  `Verified: harness, tests`), or `Verified: none` and why.
- Commit only when the user asked to commit.
- `main` is protected: commit on a branch and land it through a PR.
