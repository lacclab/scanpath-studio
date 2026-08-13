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
  paragraph, the rest belongs in the item's write-up in `tracker/data.js`.
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
- **Write-up shape — structured fields, not bold leads.** Each section is its own
  key on the item, an array of markdown lines: `request` (what was asked, in the
  asker's terms — **required**) · `whatWasDone` · `whatsLeft` (**the developer's**
  remaining work only — think team lead / developer; link the follow-up when the
  remainder was split out) · `background`
  (anchors, design calls, gotchas, related IDs). Optional `statusNote` is the
  lede above them (the status / "update as of ⟨date⟩" line that used to be a
  leading `>` quote). **Never repeat the label inside the field** — the tracker
  prints it. **Omit a field rather than writing an empty array.** A Backlog item
  has only `request` (+ `background`); `whatWasDone` / `whatsLeft` are required
  once the item is `In progress` or `Review`.
  `tests/test_tracker_server.py` enforces this, so a dropped section fails a
  test instead of quietly rotting. Archived items keep the older single `body`
  array — both shapes render; don't convert them.
- **Everything waiting on the user goes in `decisions` — including the review.**
  It's a structured field on the item: an array of one-line calls only the user
  can make, both the design questions that block the work *and*, once it's built,
  the ask to review it (name the judgement calls, the surfaces to click). The
  tracker renders it as the amber *Waiting on you* callout at the top of the
  item, badges the card (**⚖ N for you**), and collects them under the *Waiting
  on me* filter — so one click shows every item holding on the user. Free text
  inside *Background*, or an ask addressed to the user from inside *What's left*,
  gets none of that and generally doesn't get read. The user answers in the
  item's *Instructions for implementation*; whoever implements then clears
  `decisions` and records the call in *Background*. Omit the field entirely when
  nothing is open (ENG-35); an item in `Review` always has at least the review
  ask, and `tests/test_tracker_server.py` enforces both halves.
- **`whatsLeft` on a finished item honestly says "Nothing."** It tracks the
  developer's remainder, so an implemented item awaiting sign-off has nothing
  left in it — the review lives in `decisions`, above.
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
- **Keep it current *while* you work — be on it.** The tracker is a shared,
  multi-person, multi-agent view of the project; a stale one is worse than none.
  1. **Claim it and flip to `In progress` when you pick the item up**, not when
     you finish, so nobody else starts the same thing. Claiming sets `owner` to
     one of the names in `TRACKER.people` (`data.js`) — the **Claim** button in
     the UI, `"owner": "<name>"` if you're editing `state.json` by hand. It works
     from any status, so you can take something that's still Planned (ENG-39).
  2. The moment a decision is answered — even before any code is written — clear
     it out of `decisions` and record the call in `background`, in the same edit.
     A settled question left in the amber box costs the user a review round.
  3. **Commit early and often**: one commit per feature or fix, not one per
     session, with the tracker edit in the same commit as the code it describes.
     Long-lived uncommitted work blocks the other sessions sharing this checkout.
  4. Finish into `Review`, and put the ask to review in `decisions` — `whatsLeft`
     is your own remainder, not a message to the user.

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
