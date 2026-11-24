@AGENTS.md

# Working agreements

`@AGENTS.md` (imported above) is the architecture + conventions map — modules,
pipeline, canonical columns, code style, gotchas, the "adding a new …" recipes,
and releasing. This file adds the workflow rules every contributor follows.
Contributor setup is in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Before every commit / push

- **Run ruff first — always.** `uv run --extra lint ruff check .` and
  `uv run --extra lint ruff format .` — the pinned ruff; the one on PATH may be
  older. CI's Lint job gates on **both**, so a missed format fails the build,
  even for a docs-only change.
- **Add a changelog fragment, never edit `CHANGELOG.md`.** Each item is one
  file, `changelog.d/<issue>.<group>.md` (`341.fixed.md`; several issues join
  with `+`), or `changelog.d/<slug>.<group>.md` when there is no issue — the
  release cites the PR that merged it. It holds one line of plain text: what
  changed, for the user, with no bullet and no number. Groups are Keep a
  Changelog's (`added` / `changed` / `fixed`, …). `/release` writes the
  fragments into `CHANGELOG.md`, so parallel PRs never conflict over it. The
  reasoning goes in the PR description, or the issue when there is one. See
  `changelog.d/README.md`.
- **Never add a `Co-Authored-By: Claude …` trailer** (or any AI co-author line)
  to commit messages.
- **Say how the commit was verified.** End the message with a `Verified:`
  trailer naming what ran — `Verified: harness, apptest, browser`,
  `Verified: tests`, or `Verified: none` with the reason (docs only). The
  commit-gate hook logs commits without one (see *Repo automation*).

## Building features

- A user-facing feature is only done when it is exposed on **every** surface —
  the UI **and** the deep link / Share, the CLI, and the headless API — not just
  visually. See *Exposing a feature on every surface* in `@AGENTS.md`.
- **Don't break existing functionality** unless it was explicitly agreed.
- Prefer the **latest dependency versions**; don't add shims to keep old
  dependency versions working. This is a research tool, not a version-pinned
  production deployment. The exception is **CI tooling** — ruff, build, twine,
  PyInstaller are pinned to an exact version (the `lint` extra in
  `pyproject.toml` and the workflows), because an unpinned linter reds a branch
  that changed nothing. Bump those deliberately, in their own commit, with
  whatever their new rules find.
- **Consider backward compatibility; you don't always have to keep it.** The
  app is released, so people already hold things it reads back: share links and
  URL params, settings files, saved datasets and the recovery cache,
  `annotations.json`, CLI flags and scripts calling `api.py`, export formats.
  Before changing one, work out what breaks for an existing user and say so in
  the PR. Keep it working when that is cheap — a settings-file migration
  (`PLOT_CONFIG_SCHEMA_VERSION` + `url_state._PLOT_CONFIG_MIGRATIONS`), an old
  URL value read as its new one, a deprecated alias for a CLI flag or API
  parameter. When it isn't worth the cost, break it on purpose and say so in the
  changelog fragment (`changed` / `removed`). Old code nothing a user saved or
  scripted depends on can simply be deleted.
- **Comments describe the code as it is now.** Explain what it does and why —
  the constraint, the quirk, the invariant. No issue numbers, dates, review
  rounds or "used to" history in comments, docstrings or docs: that belongs in
  the commit message, the PR and the issue.

## Verifying a change

- **See it work before calling it done.** Run `/verify` on every change a user
  can observe: `scripts/verify_change.py` boots the app headless and renders
  through the CLI and the API, and a visible change gets looked at in a browser.
  Tests passing is not the same as the feature working.
- **Three rounds, then ask.** If a check still fails after three attempts at
  fixing it, stop and tell the user what fails, what you tried, and what you
  suspect.
- **Flaky tests get fixed, not quieted.** Never add a `sleep`, a retry, a
  `skip` or a looser assertion to get a test green. Find the cause; if it can't
  be found, delete the test and give the reason in the commit message. A flaky
  test teaches everyone to rerun instead of reading the failure.
- **State invariants as property tests.** A round-trip (a link value written
  and read back), an idempotent step (a migration, a normalization) or a rule
  that must hold for every input goes in `tests/test_properties.py` as a
  Hypothesis test, not as three hand-picked examples.
- **Turn a miss into a check.** A bug that review should have caught and that
  has happened twice becomes a `REVIEW.md` item (a trigger readable from a
  diff, the check, the PRs behind it) — or better, a test. Prune items a test
  now covers.

## Tracking work

Work lives in [GitHub Issues](https://github.com/lacclab/scanpath-studio/issues),
on the [Scanpath Studio board](https://github.com/orgs/lacclab/projects/5)
(project 5). **Use `/track`** to open, update or move one; it holds the
conventions — the board's Status and Priority, issue types, `area:*` labels,
the four-section body and the *⚖ Waiting on you* checklist.

- **GitHub's `#N` is the ID.** Commits, PRs and changelog fragments cite it;
  never mint a `[VIZ-37]`-style one (older history has them, and
  `gh issue list --state all --search "VIZ-37"` still finds the issue).
- **Not every change gets an issue.** One finished inside a session is cited by
  its PR. Open an issue when the item reaches **Review**, is blocked on a
  decision only the user can make, or is carried across sessions. If unsure,
  open it.
- **Claim it when you pick it up** (`gh issue edit <n> --add-assignee @me`, board
  Status *In progress*) — several people and sessions share this repo.
- **Approval gate.** Finished means Status **Review** with the issue **open**.
  Never close it yourself: closing is the user's sign-off.
- **One commit per feature or fix**, with `(#N)` in the subject. Notice an
  unrelated problem? Fix it on the spot if it is small, otherwise
  `gh issue create` so it does not get lost.

## Repo automation (`.claude/`)

- **Skills** — `/release` (cutting a release, including the `__release__` +
  `CITATION.cff` bump), `/track`, `/new-feature`, `/preflight` and `/verify`
  package the workflows above; invoke them instead of re-deriving the steps.
  `/verify` keeps a feature map (`.claude/skills/verify/feature-map.md`) — add
  a row when a feature lands.
- **Hooks** — every edited `.py` file is auto-run through `ruff format` +
  `ruff check` (`.claude/hooks/ruff-on-edit.sh`); fix what it reports
  immediately rather than batching. `git commit` goes through
  `.claude/hooks/commit-gate.sh`, which logs to `.claude/commit-gate.log`
  whether the message has a `Verified:` trailer. It only observes by default;
  `SCANPATH_COMMIT_GATE=enforce` blocks a commit without one (letting the third
  try through), `off` disables it.
- **Subagents** — `diff-reviewer` is the primary reviewer: it applies the
  `REVIEW.md` items the diff triggers, reading the checklist from `origin/main`
  so a change can't weaken its own checks. `surface-parity-reviewer`
  (four-surface rule, wire-format keys, true-scale chart path) and
  `perf-reviewer` (`@st.cache_data` + `frame_fingerprint` conventions) go
  deeper on their areas. Run `diff-reviewer` on every PR before it is opened
  or updated (`/preflight` check 7) and before setting an issue to *Review*,
  plus the specialist whose area the diff touches; give a later round the
  earlier round's findings, so it checks those and what changed since.
- **Guardrails** — edits to `uv.lock`, `site/`, and `*.egg-info` are denied
  in `.claude/settings.json`; they are generated artifacts.
