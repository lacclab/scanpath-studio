# Scanpath Studio — Improvements Archive

Signed-off items, moved here from [`IMPROVEMENTS.md`](IMPROVEMENTS.md) to keep the
working tracker focused on open work.

- An item lands here **only after the user gives final sign-off** on the
  implementation (it sits at `Status: Pending approval` in the main file until
  then). See the *Approval gate* note in `IMPROVEMENTS.md`.
- **IDs are stable and preserved** — cite an archived item by the same ID
  (`UX-2`, `ENG-5`, …); it just lives here once signed off. Items stay under
  their original group headings for findability.
- `Skipped` items are **not** archived — they stay in `IMPROVEMENTS.md` with
  their rationale.

### Groups
[UX & Interaction](#ux--interaction) ·
[Bugs](#bugs) ·
[Engineering](#engineering)

---

## UX & Interaction

**UX-1a · Reorder chips in place** — `Status: Done` *(signed off 2026-06-23; sub-item of UX-1, which is still pending)*

Built with `streamlit-sortables` (`sort_items`, new dependency): a two-bucket drag
UI (*Shown · drag to reorder* / *Available*) handles membership **and** order in
one widget, written back to `trial_chip_fields`.

**UX-2 · Welcome tour covers all major components, in reading order** — `Status: Done` *(signed off 2026-06-23)*

`tour._SPOTLIGHT_STEPS` is a 9-step reading-order walk (plot → trial selection →
chips → rail view-modes/controls → bottom subtabs → sidebar data + save/restore),
targeting new keyed wrappers (`tour_grp_plot` / `_trial_select` / `_chips` /
`_subtabs`) added in `tabs.py`.

**UX-2a · Drop the separate Exit button** — `Status: Done` *(signed off 2026-06-23)*

The tour card footer is now Back / Next (or Done); the ✕ (`tour_sp_close`) is the
only close affordance.

**UX-3 · Green/red check & cross in Stimulus & questions** — `Status: Done` *(signed off 2026-06-23)*

The correctness line in `tabs._render_paragraph_panel` uses Streamlit colour
markdown — `:green[✓ correct]` / `:red[✗ incorrect]` (and `✓ yes`/`✗ no`).

---

## Bugs

**BUG-1 · Trial filter persists (incorrectly) when switching datasets** — `Status: Done` *(signed off 2026-06-23)*

`app.main` resets the `filter_*` keys + derived `_trial_filters` on a data-source
change (keyed on `(data_choice, public_dataset_choice)`, matching the col-map
reset), and **stashes/restores** the per-dataset selections so switching back
recovers them.

---

## Engineering

### Code quality

**ENG-5 · Decompose `app.py`** — `Status: Done` *(signed off 2026-06-23)*

`url_state.py` (deep-link/share/config), `wizard.py` (upload wizard), and
`constants.py` (source/view labels) were split out (app.py 4087 → ~1640 lines);
view dispatch is `url_state._active_view` + a 2-branch `if/else` in `main`, and the
data-source strategy is `PUBLIC_DATASET_REGISTRY` + `load_words_and_fixations`.
Column mapping always lived in `controls.py`.

**ENG-7 · Confirm `watchdog` is actually used; drop if not** — `Status: Done` *(signed off 2026-06-23)*

**Keep** — `watchdog` is an optional Streamlit runtime file-watcher (faster hot
reload; not imported by app code). Added a clarifying comment in `pyproject.toml`
+ `requirements.txt`.

### UX / robustness

**ENG-9 · Surface auto-detected columns in the Column Mapping panel** — `Status: Done` *(signed off 2026-06-23)*

`controls.column_mapping_ui` now shows a `✨ auto-detected \`col\`` caption per
field (flagging overrides); the remap editor labels it `currently mapped` instead
(its proposal is the saved mapping, not a fresh detect).

**ENG-10 · Better animation-export errors when Chrome/Chromium is missing** — `Status: Done` *(signed off 2026-06-23)*

> ⚠️ **Not verified by the user** — implemented but the user has not tested this
> end-to-end (no Chrome-missing run confirmed).

`animation_export.chrome_available()` + a shared `CHROME_INSTALL_HINT` (pointing to
`kaleido_get_chrome` / the HTML export); a UI pre-flight before a GIF/MP4 render; a
warm→cold `to_image` fallback when the warm Kaleido server won't start but Chrome
exists; and the static PNG/SVG/PDF export reuses the same hint.
