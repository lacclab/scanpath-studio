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

1. **Lint** — `ruff check --exclude other_vis .`
2. **Format** — `ruff format --exclude other_vis .` (CI gates on both; this
   one rewrites files — if it changed anything, say which files). Run these
   even for "docs-only" changes — repo rule.
3. **Tests** — `pytest -n auto`. If the diff is small and clearly scoped,
   you may first run the affected test files for fast feedback, but the full
   suite is the gate.
4. **Changelog** — `git diff` + `git status` to see the pending work; if it
   is user-visible or a bug fix, `CHANGELOG.md` must have a matching
   one-scannable-line entry under `[Unreleased]` (grouped Added / Changed /
   Fixed). If missing, draft the line and add it.
5. **Tracker** — if the pending work corresponds to a tracker item in
   `tracker/data.js`, check its status/write-up is current (finished work →
   `Pending approval`, never straight to `Done`).

## Reminders for the commit itself

- Never add a `Co-Authored-By: Claude …` (or any AI co-author) trailer.
- Commit only when the user asked to commit.
