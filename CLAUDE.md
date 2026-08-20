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
- **Update `CHANGELOG.md` as you go, in the two-tier shape** (ENG-34, `[Unreleased]`
  onwards only — already-released sections keep their old one-paragraph-per-item
  shape). Under each `[Unreleased]` group (Added / Changed / Fixed): a **headline
  list** first — `- **Bold lead** (ID)` and nothing else, short enough to paste
  into Slack — then a `### Details` subsection with the same Added / Changed /
  Fixed grouping, one short paragraph per item under a matching `#### <Group>`
  heading, anchored by the same bold lead + ID so the two halves line up. Not a
  per-tweak log and not a design doc — if a detail needs more than a short
  paragraph, the rest belongs in the write-up on the item's GitHub issue.
- **Never add a `Co-Authored-By: Claude …` trailer** (or any AI co-author line)
  to commit messages.

## Building features

- A user-facing feature is only done when it is exposed on **every** surface —
  the UI **and** the deep link / Share, the CLI, and the headless API — not just
  visually. See *Exposing a feature on every surface* in `@AGENTS.md`.
- **Don't break existing functionality** unless it was explicitly agreed.
- Prefer the **latest dependency versions**; don't add legacy or back-compat
  shims. This is a research tool, not a version-pinned production deployment.
  The exception is **CI tooling** — ruff, build, twine, PyInstaller are pinned
  to an exact version (the `lint` extra in `pyproject.toml` and the workflows),
  because an unpinned linter reds a branch that changed nothing. Bump those
  deliberately, in their own commit, with whatever their new rules find.

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

- **Work lives in [GitHub Issues](https://github.com/lacclab/scanpath-studio/issues).**
  `gh issue list --label status:in-progress`, `gh issue view <n>`,
  `gh issue create`. The in-repo tracker was migrated on 2026-08-20 (ENG-32) and
  is now a **read-only archive** — see *The archive* at the end of this section.
- **Stable IDs are still the currency.** Every issue is titled
  `[VIZ-37] <title>`, because the docs, the `plans/` notes and the git history
  cite items by that ID and always will. A **new** issue takes the next free
  number in its area's prefix — `gh issue list --state all --search "[DATA-" `
  and add one, counting the archive too (`tracker/data.js` holds everything
  closed before the move). Never reuse or renumber an ID. GitHub's own `#N` is
  an implementation detail; cite the tracker ID in commits and prose, and the
  `#N` alongside it when a link helps.
- **Labels carry the workflow.**
  - `status:backlog | planned | in-progress | on-hold | review` — one per issue,
    replaced (not added to) on a move: `gh issue edit <n> --add-label
    status:in-progress --remove-label status:planned`.
  - `area:*` mirrors the old groups (`ux`, `compare`, `viz`, `data`, `perf`,
    `analysis`, `preprocessing`, `export`, `validation`, `bug`, `engineering`)
    and decides the ID prefix.
  - `priority:high` / `priority:low`; Normal is the unlabelled default.
  - `waiting-on-you` — see *Waiting on you* below.
- **Approval gate.** Finishing implementation means `status:review` with the
  issue **open** — never close it yourself. Closing *is* the sign-off, and it is
  the user's to make. An issue closed without being implemented says why in a
  closing comment and uses `--reason "not planned"`.
- **Claim it and move it to `status:in-progress` when you pick it up**, not when
  you finish: `gh issue edit <n> --add-assignee @me --add-label
  status:in-progress --remove-label status:planned`. Several sessions and two
  people share this repo; an unassigned issue reads as unclaimed work.

**Write-up shape.** The issue body is the same four sections the tracker used,
as markdown headings, in this order:

1. `## Request` — what was asked for, in the asker's terms. **Required.**
2. `## What was done` — what actually shipped.
3. `## What's left` — **the developer's** remaining work only; link the
   follow-up issue when the remainder was split out. On a finished item this
   honestly says "Nothing." — the review is not developer work.
4. `## Background` — anchors, design calls, gotchas, related IDs.

An optional `> blockquote` lede above them is the status / "update as of ⟨date⟩"
line. A backlog issue has only *Request* (+ *Background*); the middle two are
required once it reaches `status:in-progress` or `status:review`. Link code with
full blob URLs (`https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/plots.py#L339`)
— a relative path renders dead in an issue.

**Waiting on you.** Everything only the *user* can decide goes in one place: a
`### ⚖ Waiting on you` checklist at the top of the body, plus the
`waiting-on-you` label, so `label:waiting-on-you` is one query for everything
holding on them. That covers the design calls that block the work *and*, once it
is built, the ask to review — name the judgement calls you made and the surfaces
to click. An issue in `status:review` always has at least that entry. Clear an
item the moment it is answered — tick the box, and record the call under
*Background* in the same edit — including when you settled it yourself.

**Keep it current *while* you work.** One commit per feature or fix, not one per
session, and put `(VIZ-37)` in the commit subject so the issue and the code stay
findable from each other. Notice an unrelated problem? Fix it on the spot if it
is small, otherwise `gh issue create` so it does not get lost.

**The archive.** [`tracker/data.js`](tracker/data.js) + `index.html` still hold
the 320 items closed before the migration, with their full write-ups, and
`python3 tracker/server.py` serves them read-only at
<http://127.0.0.1:8765/tracker/>. `tracker/migrated.json` maps each ID that moved
to its issue number. **Do not add to it or edit it** — it is a frozen record, and
`tests/test_tracker_server.py` fails if an open item there has no issue.
[`tracker/to_github_issues.py`](tracker/to_github_issues.py) is the migration
script, kept as the record of how the move was made.

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
