---
name: preflight
description: Pre-commit gate for scanpath-studio — run ruff check + format, the test suite, and verify the changelog has an entry for the pending work. Run before every commit/push.
disable-model-invocation: true
---

# Preflight — pre-commit gate

Run from the repository root. Run every check even if an earlier one fails,
then report all results together (pass/fail per check with the failing
output). Fix trivial failures (formatting) directly; report anything else.

## Checks

1. **Lint** — `ruff check .`
2. **Format** — `ruff format .` (CI gates on both; this
   one rewrites files — if it changed anything, say which files). Run these
   even for "docs-only" changes — repo rule.
3. **Tests** — `pytest -n auto`, in the project's environment (e.g.
   `uv run --extra test pytest -n auto` — not a bare `pytest` from `PATH`, which
   may be another interpreter and another pandas). If the diff is small and clearly scoped,
   you may first run the affected test files for fast feedback, but the full
   suite is the gate.
4. **Changelog** — `git diff` + `git status` to see the pending work; if it
   is user-visible or a bug fix, `CHANGELOG.md` must have a matching entry
   under `[Unreleased]` in the two-tier shape — a `- **Bold lead** (ID)`
   headline under Added / Changed / Fixed, plus a short paragraph under the
   matching `#### <Group>` in `### Details` (`CLAUDE.md` → *Before every
   commit*). If missing, draft both halves and add them.
5. **Issue** — if the pending work corresponds to a GitHub issue
   (`gh issue list`), check its board Status and body write-up are current.
   Finished work goes to Status **Review** with the review ask in its
   *⚖ Waiting on you* checklist — **never** close the issue yourself; that is
   the user's sign-off. Conventions in `CLAUDE.md` → *Tracking work*.

## Reminders for the commit itself

- Never add a `Co-Authored-By: Claude …` (or any AI co-author) trailer.
- Commit only when the user asked to commit.
- `main` is protected: commit on a branch and land it through a PR.
