@AGENTS.md

# Working agreements

`@AGENTS.md` (imported above) is the architecture + conventions map — modules,
pipeline, canonical columns, code style, the "adding a new …" patterns, and
releasing. This file adds the cross-cutting workflow rules every contributor
should follow. The detailed per-module reference + gotchas live in
[`scanpath_studio/CLAUDE.md`](scanpath_studio/CLAUDE.md) (loads automatically when
you work under `scanpath_studio/`); contributor setup is in
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## Before every commit / push

- **Run ruff first — always.** `ruff check --exclude other_vis .` and
  `ruff format --exclude other_vis .`. CI's Lint job gates on **both**, so a
  missed format fails the build. Don't skip it, even for "docs-only" changes.
- **Update `CHANGELOG.md` as you go** — **one scannable line per item** under the
  `[Unreleased]` section (grouped Added / Changed / Fixed), not a per-tweak log
  and not a design doc. If it needs a paragraph, the paragraph belongs in the
  item's write-up in `tracker/data.js`; the changelog gets the one-line
  version. A bug fix may take two lines when the *wrong* behaviour needs naming.
- **Never add a `Co-Authored-By: Claude …` trailer** (or any AI co-author line)
  to commit messages.

## Building features

- A user-facing feature is only done when it is exposed on **every** surface —
  the UI **and** the deep link / Share, the CLI, and the headless API — not just
  visually. See *Exposing a feature on every surface* in `@AGENTS.md`.
- **Don't break existing functionality** unless it was explicitly agreed.
- Prefer the **latest dependency versions**; don't add legacy or back-compat
  shims. This is a research tool, not a version-pinned production deployment.

## Dev loop

- **Code change not showing? Restart the server.** Streamlit doesn't reload
  imported modules on rerun, and `st.cache_data` doesn't hash transitively-called
  helpers — a rerun / "Clear cache" isn't enough. See CONTRIBUTING →
  *If a code change doesn't show up*.
- Prefer headless `AppTest.from_file("streamlit_app.py")` for verifying behavior;
  the live preview is slow to spin up.
- **The spatial plot must stay on `tabs._render_true_scale_chart`** (never
  `st.plotly_chart`), and deep-link / restore relies on the `global_*` /
  `single_*` / `filter_*` widget keys — don't rename them. More in
  `scanpath_studio/CLAUDE.md → Gotchas`.

## Tracking work

- All work — open **and** archived — lives in [`tracker/data.js`](tracker/data.js),
  one object per item with a stable ID (e.g. `CMP-3`), a `Status`, a group, and a
  `body` array of markdown lines. Edit that file; open
  [`tracker/index.html`](tracker/index.html) in a browser to read it (search,
  status/group filters, cross-referenced IDs, `#ID` deep links). It replaces the
  old `IMPROVEMENTS.md` / `IMPROVEMENTS_ARCHIVE.md` pair.
- **New items get `"added": "<today's date>"`**, set once at creation and never
  edited afterwards — even when `note`/`date` (which track a later status
  milestone, e.g. implemented/signed-off) stay empty.
- **Write-up shape.** Four bold-led paragraphs in this order — **Request** (what
  was asked, in the asker's terms) · **What was done** · **What's left** (or
  "Nothing" — say it either way, and link the follow-up when the remainder was
  split out) · **Background (technical)** (anchors, design calls, gotchas,
  related IDs). A Backlog item has only *Request* + *Background*. The tracker's
  *How this works* panel carries the same convention.
- **Statuses.** The live workflow has six: `Backlog`, `Planned`, `In progress`,
  `On hold`, `Review`, `Closed` (see `@AGENTS.md` → *Improvements tracker
  handoff*). Older items in `tracker/data.js` still carry the retired wording
  (`Pending approval`, `Done`, `Parked`, `Dropped`) — don't copy it into new or
  edited items, and don't mass-rewrite the historical ones either.
- **Approval gate.** Finished implementing → `Status: Review`; **never** jump
  straight to `Closed`. On the user's sign-off, set `"status": "Closed"` **and**
  `"archived": true` (same for an item closed without being implemented — record
  the reason in `note`). Archived items are hidden until *Show archived*.
- **IDs are stable** — never renumber. New items take the next free number in
  their prefix (the app's *How this works* panel prints it).
- **Notice an unrelated issue?** Fix it on the spot if it's small; otherwise add
  an item to `tracker/data.js` so it doesn't get lost.

## On release

See *Releasing* in `@AGENTS.md`: bump `__version__` in
`scanpath_studio/__init__.py` **and** `version` + `date-released` in
`CITATION.cff` (a test enforces version parity).

## Repo automation (`.claude/`)

- **Skills** — `/release`, `/track`, `/new-feature`, `/preflight`,
  `/paper-figs` package the workflows above; invoke them instead of
  re-deriving the steps.
- **Hook** — every edited `.py` file is auto-run through `ruff format` +
  `ruff check` (`.claude/hooks/ruff-on-edit.sh`); fix what it reports
  immediately rather than batching.
- **Subagents** — `surface-parity-reviewer` (four-surface rule, wire-format
  keys, true-scale chart path) and `perf-reviewer` (`@st.cache_data` +
  `frame_fingerprint` conventions) review a diff; run both before setting a
  tracker item to *Review*.
- **Guardrails** — edits to `uv.lock`, `site/`, and `*.egg-info` are denied
  in `.claude/settings.json`; they are generated artifacts.
