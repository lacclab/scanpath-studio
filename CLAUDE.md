@AGENTS.md

# Working agreements

`@AGENTS.md` (imported above) is the architecture + conventions map — modules,
pipeline, canonical columns, code style, gotchas, the "adding a new …" recipes,
and releasing. This file adds the workflow rules every contributor follows.
Contributor setup is in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Before every commit / push

- **Run ruff first — always.** `ruff check .` and `ruff format .`. CI's Lint
  job gates on **both**, so a missed format fails the build, even for a
  docs-only change.
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

## Dev loop

- **Code change not showing? Restart the server.** Streamlit doesn't reload
  imported modules on rerun, and `st.cache_data` doesn't hash transitively-called
  helpers — a rerun / "Clear cache" isn't enough. See CONTRIBUTING →
  *If a code change doesn't show up*.
- Prefer headless `AppTest.from_file("streamlit_app.py")` for verifying behavior;
  the live preview is slow to spin up.
- **The spatial plot must stay on `tabs._render_true_scale_chart`** (never
  `st.plotly_chart`; the cached replay uses its two halves,
  `_true_scale_plot_html` + `_render_true_scale_plot`), and deep-link / restore
  relies on the `global_*` / `single_*` / `filter_*` widget keys — don't rename
  them. More under *Gotchas* in `@AGENTS.md`.

## Tracking work

- **Work lives in [GitHub Issues](https://github.com/lacclab/scanpath-studio/issues)**,
  arranged on the **[Scanpath Studio board](https://github.com/orgs/lacclab/projects/5)**
  (project 5). `gh issue view <n>`, `gh issue create`,
  `gh project item-list 5 --owner lacclab`.
- **GitHub's own `#N` is the ID.** Issues get a plain title, and commits, PRs
  and changelog fragments cite `#N`. Older issues and git history also carry
  `[VIZ-37]`-style IDs from an earlier tracker; never mint a new one, and
  `gh issue list --state all --search "VIZ-37"` still finds the issue.
- **Not every change gets an issue.** Work picked up and finished inside one
  session, whose reasoning fits in its PR description, is cited by its PR
  number — its changelog fragment takes a slug name and the release fills the
  PR number in. Open an issue when an item needs what an issue is *for*: when it
  reaches **Review** (the approval gate — the sign-off needs somewhere to
  happen), when it is blocked on a decision only the user can make
  (`waiting-on-you`), or when it is carried across sessions and needs a place to
  hold the brief. If you are unsure, open the issue.
- **Prefer GitHub's structured fields to labels.** Status, priority and kind are
  native — the board's `Status` and `Priority` single-selects and the org's
  issue types — so they are *not* also labels. Only two labels remain, for the
  two things GitHub has no field for: `area:*` and `waiting-on-you`.
- **Where each fact lives.**
  - **Status** → the board's `Status` column: `Backlog · Planned · In progress ·
    On hold · Review`. Closing the issue is the sixth state. Move it on the board,
    or with `gh project item-edit` (needs the `project` token scope —
    `gh auth refresh -s project` once).
  - **Priority** → the board's `Priority` column: `Urgent · High · Medium · Low`.
    Medium is the default.
  - **Kind** → the native issue type: `Bug` · `Feature` (a capability) · `Task`
    (a chore, a validation pass, infrastructure). `gh` has no flag for it; set it
    with `gh api -X PATCH repos/lacclab/scanpath-studio/issues/<n> -f type=Task`.
  - **Area** → an `area:*` label (`ux`, `compare`, `viz`, `data`, `perf`,
    `analysis`, `preprocessing`, `export`, `validation`, `bug`, `engineering`).
  - **Blocking the user** → the `waiting-on-you` label; see below.
- **Approval gate.** Finishing implementation means board Status **Review** with
  the issue **open** — never close it yourself. Closing *is* the sign-off, and it
  is the user's to make. An issue closed without being implemented says why in a
  closing comment and uses `--reason "not planned"`.
- **Claim it and move it to *In progress* when you pick it up**, not when you
  finish: `gh issue edit <n> --add-assignee @me`, and set the board's Status.
  Several people and sessions share this repo; an unassigned issue reads as
  unclaimed work.

**Write-up shape.** The issue body has four sections, as markdown headings, in
this order:

1. `## Request` — what was asked for, in the asker's terms. **Required.**
2. `## What was done` — what actually shipped.
3. `## What's left` — **the developer's** remaining work only; link the
   follow-up issue when the remainder was split out. On a finished item this
   honestly says "Nothing." — the review is not developer work.
4. `## Background` — anchors, design calls, gotchas, related issues.

An optional `> blockquote` lede above them carries the current status. A backlog
issue has only *Request* (+ *Background*); the middle two are required once it
reaches *In progress* or *Review*. Link code with full blob URLs
(`https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/plots.py#L339`)
— a relative path renders dead in an issue.

**Waiting on you.** Everything only the *user* can decide goes in one place: a
`### ⚖ Waiting on you` checklist at the top of the body, plus the
`waiting-on-you` label, so `gh issue list --label waiting-on-you` answers "what
is holding on me" without a project call. That covers the design calls that
block the work *and*, once it is built, the ask to review — name the judgement
calls you made and the surfaces to click. An issue in *Review* always has at
least that entry. Clear an item the moment it is answered — tick the box, and
record the call under *Background* in the same edit — including when you
settled it yourself.

**Keep it current *while* you work.** One commit per feature or fix, not one per
session, with the issue in the commit subject — `(#341)` — so the issue and the
code stay findable from each other (with no issue, the PR's squash-merge subject
carries its own number). Notice an unrelated problem? Fix it on the spot if it
is small, otherwise `gh issue create` so it does not get lost.

## On release

See *Releasing* in `@AGENTS.md`: bump `__release__` in
`scanpath_studio/__init__.py` **and** `version` + `date-released` in
`CITATION.cff` (a test enforces version parity).

## Repo automation (`.claude/`)

- **Skills** — `/release`, `/track`, `/new-feature`, `/preflight` and `/verify`
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
  deeper on their areas. Run `diff-reviewer` before setting an issue to
  *Review*, plus the specialist whose area the diff touches; give a later round
  the earlier round's findings, so it checks those and what changed since.
- **Guardrails** — edits to `uv.lock`, `site/`, and `*.egg-info` are denied
  in `.claude/settings.json`; they are generated artifacts.
