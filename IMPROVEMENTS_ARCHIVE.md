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
[Compare mode](#compare-mode) ·
[Bugs](#bugs) ·
[Engineering](#engineering)

---

## UX & Interaction

**UX-1 · Move the trial-chip field picker into the main plot chip row** — `Status: Done` *(signed off 2026-06-23)*

The sidebar `🏷️ Trial chips` picker is gone; an inline **✏️ Edit chips** `st.popover`
sits at the right end of the chip row (`tabs.render_single_trial_tab`), hosting
`controls.render_trial_chip_picker`. Polish: the redundant `?` marker removed; the
✏️ trigger shrunk to chip size and pulled next to **More**; the chip strip's
**More** dropdown carries the full chip list (so any chip clipped at the line edge
is reachable at any width / sidebar state) alongside the summary stats. (A
client-side "move only the overflow" version was tried but Streamlit's plot-embed
layout makes the strip width unstable to measure, so More just holds everything.)

**UX-1a · Reorder chips in place** — `Status: Done` *(signed off 2026-06-23; sub-item of UX-1)*

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

## Compare mode

**CMP-1 · Move the trial comparison selector into the main plot area** — `Status: Done` *(signed off 2026-06-23)*

The **Compare** toggle stays in the rail's View modes; the second-trial selector
(`tabs._render_compare_selector`) renders above the chips and mirrors the main
picker — the selectbox shows the **trial id** + ★ (same text) / 👤 (same
participant) markers (a `?` spells them out), the slider shows `index/N · <trial
id>`, options ordered stars → same-participant → rest
(`utils.build_comparison_options` returns `(participant, trial, label, markers)`
4-tuples). The overlay/layout + show-A/B-legend **config moved into the rail's
⚙️ Compare popover** (`single_compare_layout`, read via session_state). The
`■ A … ■ B compared with:` legend line is gone — each chip strip's trial id is
coloured to its scanpath (A = primary colour, B = compared) and "(compared)" dropped.

**CMP-2 · Optionally hide the compared-trial legend, hidden by default** — `Status: Done` *(signed off 2026-06-23)*

`global_show_compare_legend` (default off) threads `show_legend` into
`make_comparison_figure` / the split figure **and** the animated dual overlay
(`make_scanpath_animation`). The **"Overlay comparison" / "Stacked / Side-by-side
comparison" figure titles were removed** and the top reserve fully reclaimed when
the legend is hidden. Toggle lives in the rail ⚙️ Compare popover.

**CMP-3 · Fix compare default colors not matching the actual rendered values** — `Status: Done` *(signed off 2026-06-23)*

A single `constants.compare_palette_color(idx)` is the one source of truth for the
per-scanpath style seeding/collection and `plots._comparison_scanpath_style`. Also
**fixed the "fixations turn black when making changes" bug** — the per-scanpath
colour pickers (rendered only when Compare is on) desynced to black
(`st.color_picker` without an explicit `value=`) and committed that on the next
interaction; they now pass `value=` (no pre-seed) and a falsy colour can't leak
(`_collect_compare_styles` / `_comparison_scanpath_style` `or default`).

**CMP-4 · Remove redundant saccade-color control in compare mode** — `Status: Done` *(signed off 2026-06-23)*

In compare mode the global Saccade colour/style/width controls stay hidden (dead
for the overlay). Per user feedback, **"Color fixations by" (+ Colorscale + range)
is restored in compare** — it sets the fixation *hue* by the chosen numeric metric
for **both** scanpaths (shared scale, one colorbar), with the per-scanpath flat
colour kept as a *separate* field used as the A/B marker outline. Global Size /
Hollow stay hidden (the per-scanpath versions cover those).

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
