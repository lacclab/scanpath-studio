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
- **Update `CHANGELOG.md` as you go** — a concise line or two under the
  `[Unreleased]` section (grouped Added / Changed / Fixed), not a per-tweak log.
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

- Open work lives in [`IMPROVEMENTS.md`](IMPROVEMENTS.md): grouped sections with
  stable IDs (e.g. `CMP-3`) and a `Status`. When an item is signed off, **cut it
  from that file** and write it up as `Done` in
  [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md) — `IMPROVEMENTS.md` lists
  only open work (plus a one-line per-section pointer to the archive).
- **Notice an unrelated issue?** Fix it on the spot if it's small; otherwise add
  it to `IMPROVEMENTS.md` so it doesn't get lost.

## On release

See *Releasing* in `@AGENTS.md`: bump `__version__` in
`scanpath_studio/__init__.py` **and** `version` + `date-released` in
`CITATION.cff` (a test enforces version parity).
