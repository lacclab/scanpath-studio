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
[Visualization](#visualization) ·
[Datasets & ingestion](#datasets--ingestion) ·
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

**UX-4 · Replace the same-text ★ marker in trial selectors with a text-like icon** — `Status: Done` *(signed off 2026-06-25)*

`SAME_TEXT_MARKER` changed from `"★"` to `"📄"` in
[`utils.py`](scanpath_studio/utils.py:503). The ★ glyph read as "favorite" when
it actually means "same stimulus text as the primary trial"; 📄 makes the meaning
immediately obvious. The 👤 same-participant marker is unchanged. ★ is now free
for the upcoming favorites indicator (**UX-6**). Help text in the compare selector
(`tabs.py`) updated to match; docstrings in `build_comparison_options` updated.

**UX-5 · Keep the main Filter-by + trial selectors stable; move extra filter columns under "More"** — `Status: Done` *(signed off 2026-06-26)*

Composite-trial-id components that are also **More**-popover condition columns
(e.g. `repeated_reading_trial`) no longer get their own cascading trial selector.
`utils.select_trial` gained a `filter_cols` argument; `tabs.py` passes
`controls._filter_fields_for(...)` so those components are dropped from the
cascade — the picker shows the same canonical **Participant / Text** selectors
regardless of which condition columns a dataset carries. Residual ambiguity (e.g.
first vs. repeated reading sharing participant+text) falls to the existing
"Reading" selector; the dropped columns narrow via **More** (guaranteed present,
since `filter_cols` *is* the More field list). Test:
`test_filter_col_component_dropped_from_cascade`
([`tests/test_composite_selection.py`](tests/test_composite_selection.py)).

**UX-6 · Mark annotation state (favorites ★ / tags / notes) in the trial selector** — `Status: Done` *(signed off 2026-06-26)*

New `utils.annotation_markers(participant, trial)` returns composable markers —
`★` favorite · `🏷️` tagged · `📝` noted — read from the session annotation store
(`annotations.get_entry`). Applied via `format_func` in the main trial picker
(selectbox + scrubbing slider, `_select_trial_none_mode`) and the composite
"Reading" selector (`_select_trial_composite_mode`), and appended to the
`build_comparison_options` marker string so they sit alongside the 📄/👤 relation
icons in the compare selector. Markers are independent and stack (zero → all
three). Test: `test_annotation_markers_compose`
([`tests/test_composite_selection.py`](tests/test_composite_selection.py)).

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

## Visualization

**VIZ-6 · Replace the "hollow" fixation marker style with an opacity control** — `Status: Done` *(signed off 2026-06-23)*

The binary *Hollow circles* checkbox (global + per-scanpath) is replaced by a
marker **opacity** slider — `global_fixation_opacity` and `cmp{idx}_opacity`,
**default 0.7** so overlapping fixations show through (drag to 1.0 for fully
opaque). Threaded through `make_scanpath_figure`, `make_scanpath_animation`, and
the comparison `_add_comparison_fixation_trace` (via the per-scanpath style dict),
plus `tabs._build_figure_settings`, `export.bulk_export`, and the save/restore +
deep-link maps in `url_state.py`. The alpha is set **explicitly even at 1.0** so it
overrides Plotly's ~0.7 default for variable-size scatter markers — without this,
"opacity at 1" rendered translucent. `hollow_fixations` stays a plot-builder /
headless-API param (and a restore/deep-link key) for backward compatibility; only
the UI control changed.

**VIZ-7 · Fixation-index range selector on the main scanpath plot** — `Status: Done` *(signed off 2026-06-23)*

A `single_fix_range` slider in the ⚙️ Fixation-style popover (`controls.sidebar_controls`
→ `_render_fix_range_slider`, seeded in `_VIZ_WIDGET_DEFAULTS`, read in
`_collect_viz_settings` as `fix_index_range`) windows the main plot to a
`(start, end)` `order_in_trial` range — drawing only those fixations and their
saccades. `tabs._slice_fix_range` applies the window to the frames feeding the
static, animation, and comparison builders (and thus the "This trial" export);
the chips, panels, and bulk multi-trial export keep the full trial. The slider
max is the selected trial's fixation count and clamps across trial switches
(mirroring the Generations tab's `multi_fix_range`); a <2-fixation trial clears
the window. Sized via a new `fix_range_fixations=` kwarg on `sidebar_controls`.

**VIZ-12 · Quick views: show which preset is active (Scanpath selected by default)** — `Status: Done` *(signed off 2026-06-25)*

The active Quick-view button (👁️ Scanpath / 🔥 Heatmap) now renders as
`type="primary"` when the current layer toggles exactly match that preset's
`_VIEW_PRESETS` layer set; both buttons render as secondary when the user has
customized layers away from either preset. Implemented via a new
`_active_quick_view()` helper in [`controls.py`](scanpath_studio/controls.py)
that derives the active preset from live session state (no extra stored key).
Scanpath is highlighted on first load since the widget defaults match that preset.

**VIZ-13 · Improve word-hover tooltip text + add a configurable measure (TFD by default)** — `Status: Done` *(signed off 2026-06-25)*

Word-label hover now reads `Word: <text>` / `Word #N` / `Line #N` (added colon,
changed "ID" → `#`, added `#` on line). A configurable reading-measure line is
appended (default: `Total fixation: N ms`). New **Hover: show measure** selectbox
in the ⚙️ Text & highlight popover — options: Total fixation (TFD), FFD, FPRT,
RPD, Fixation count, Off. Implemented via `_HOVER_MEASURE_LABELS` + a new
`word_hover_measure` parameter on `_add_word_label_trace` and `make_scanpath_figure`
([`plots.py`](scanpath_studio/plots.py)); `global_word_hover_measure` seeded in
`_VIZ_WIDGET_DEFAULTS` and collected by `_collect_viz_settings`
([`controls.py`](scanpath_studio/controls.py)); threaded through
`_build_figure_settings` ([`tabs.py`](scanpath_studio/tabs.py)); added to
`_SHARE_VALUE_PARAMS` ([`url_state.py`](scanpath_studio/url_state.py)) so Share
links preserve the choice.

**VIZ-1 · Warn that font sizes are px, not pt** — `Status: Done` *(signed off 2026-07-03)*

A note near the font-size controls explains px vs pt (+ the DPI conversion); also
documented in [`docs/rendering.md`](docs/rendering.md) (ENG-12).

**VIZ-2 · Increase font size across the app where possible** — `Status: Done` *(signed off 2026-07-03)*

A gentle, targeted bump on the smallest native text (captions, widget labels,
radio/checkbox options, help tooltips → 0.92rem) + the custom chip/stat classes,
all in [`styles.py`](scanpath_studio/styles.py); no global root-font change, so
dense layouts don't reflow.

**VIZ-3 · Alternative heatmap normalization (Linear/Log)** — `Status: Done` *(signed off 2026-07-03)*

A **Color scaling** control (`Linear` | `Log`) in the ⚙️ Heatmap-style popover; Log
maps colour to `log1p(value)` across all three heatmap styles (`_apply_heatmap_norm`).
Every surface (UI / Share `heatmap_norm` / Save & restore / CLI `--heatmap-norm` /
API).

---

## Bugs

**BUG-1 · Trial filter persists (incorrectly) when switching datasets** — `Status: Done` *(signed off 2026-06-23)*

`app.main` resets the `filter_*` keys + derived `_trial_filters` on a data-source
change (keyed on `(data_choice, public_dataset_choice)`, matching the col-map
reset), and **stashes/restores** the per-dataset selections so switching back
recovers them.

**BUG-2 · Upload box appears twice during data upload** — `Status: Done` *(signed off 2026-06-23)*

In the Upload / Add-dataset wizard the whole step-3 upload group (Raw gaze +
**Fixations** + Words) rendered a second, greyed-out copy while a large file was
being read — so the **Fixations** uploader ("Fixations table(s)") appeared
**twice**, both showing the same file.

_Root cause:_ a Streamlit layout-shift ghost. The "⬆️ Upload … to begin" call to
action + the "large dataset" tip rendered at the top of step 3 only *before*
anything was uploaded. The moment a file was added they vanished, shifting every
following element up two delta-paths. Reading a large upload blocks the rerun
(the `@st.cache_data(show_spinner="Reading uploaded data…")` reader in
[`app.py`](scanpath_studio/app.py:784)), so Streamlit froze the half-reconciled
DOM and left the pre-shift copy of the whole upload group on screen as a
greyed ghost.

_Fix:_ render that guidance into a **container that is always created** (even
when empty) so the upload boxes keep a fixed position in the element tree and
never shift ([`wizard.py`](scanpath_studio/wizard.py:1194)). Verified with
Playwright + a 26 MB zip: before, two "Fixations table(s)" uploaders appeared
during the read; after, exactly one throughout. `pytest` wizard/apptest/
column-mapping suites green (89 passed).

**BUG-3 · MultiplEYE: stimulus text renders misaligned** — `Status: Done` *(signed off 2026-07-03)*

The loader reads the stimulus config's `FONT_SIZE`/`FONT` and stamps
`stimulus_font_px`/`stimulus_font_family`; the app snaps its font controls to them
on a source switch; `scale_text_to_boxes` now budgets from the line **pitch** (not
the glyph-tight box height) with a script-aware width cap. MultiplEYE word text
sits in its boxes without manual font tweaks; OneStop byte-identical. *(Residual
sub-pixel offset tracked separately as BUG-4.)*

---

## Datasets & ingestion

The data-source UI overhaul (**DATA-4 … DATA-7**), signed off 2026-06-26. All four
touched the sidebar source UI — `app.render_sidebar_data_source`, the
`PUBLIC_DATASET_REGISTRY` + `_load_public_dataset`, and the per-corpus loaders
`_load_potec_source` / `_load_multipleye_source` / `_load_onestop_public_source`.

**DATA-4 · Public-datasets browser that scales to ~40 corpora** — `Status: Done` *(signed off 2026-06-26)*

The flat dataset radio became a **searchable `st.selectbox`** (`_load_public_dataset`)
showing each corpus' **short name** + a *language · size* caption, one-line
description, and **Dataset home ↗** link. `PUBLIC_DATASET_REGISTRY` was promoted
from `{label: {loader, monitor}}` to a structured entry (adds `short` / `language`
/ `size` / `description` / `link`; `loader` + `monitor` preserved). Local/private
upload stays the primary path; selection still rides `public_dataset_choice` (full
label, so deep-link/session round-trips). Feature flag `public_datasets_enabled()`
unchanged.

**DATA-5 · Drop the per-source participant/text filtering from the loaders** — `Status: Done` *(signed off 2026-06-26)*

Removed PoTeC's **Texts** + **Readers** controls and MultiplEYE's **Sessions** +
**Stimuli** multiselects; each loader now reads the **whole corpus**
(`potec_raw_frames(root)` / `multipleye_raw_frames(root, …)`) and the global
**Narrow by** trial filters scope it. The app-side cached wrappers lost their
`readers`/`texts`/`sessions`/`stimuli`/`download` args; the headless
`load_potec`/`load_multipleye` keep theirs. MultiplEYE's **Fixation source** radio
stays (a load variant, not filtering).

**DATA-6 · Surface the expected file names / directory structure per corpus** — `Status: Done` *(signed off 2026-06-26)*

Each loader shows an **"Expected files"** expander (shared `_dataset_dir_input`)
next to its *Data directory* input, listing the file-name patterns + sub-directory
tree it looks for (`_POTEC_STRUCTURE_MD` / `_MULTIPLEYE_STRUCTURE_MD` /
`_onestop_structure_md(regime)`).

**DATA-7 · Rework the download + mapping flow (button, not a checkbox)** — `Status: Done` *(signed off 2026-06-26)*

The always-on *Download if missing* checkbox was replaced by a shared
**found-vs-Download** status (`_dataset_access_status`): it detects the corpus on
disk (`datasets.potec_present` / `onestop_present` / `multipleye_inventory`) and
either shows **"Found in `<dir>`"** (no network) or a one-click **⬇ Download**
button (PoTeC / OneStop; `download_potec` / `download_onestop`). MultiplEYE (no
public URL) shows a missing-data note. Public-corpus frames still flow through the
generic auto-detect → **Column-mapping** panels. Tests: `potec_present` /
`onestop_present` ([`tests/test_dataset_support.py`](tests/test_dataset_support.py));
picker + per-loader access UI ([`tests/test_apptest.py`](tests/test_apptest.py)).

**DATA-8 · Show the column-mapping override for the Bundled Demo too** — `Status: Done` *(signed off 2026-07-02)*

`prepare_data`'s `allow_override` gate also fires for the **Bundled Demo**
(`data_choice in (PUBLIC_DATASETS_CHOICE, DEMO_CHOICE)`,
[`app.py`](scanpath_studio/app.py)), so the **Column mapping — Words/IA** and
**Column mapping — Fixations** panels render on the default first-load source —
pre-filled with auto-detection, so an untouched mapping normalizes identically.
Makes the re-mapping capability discoverable. Verified via `AppTest` (both panels
present, no errors).

**DATA-3 · Broaden OneStop public-dataset support (all regimes · all parts · public + LaCC lab)** — `Status: Done` *(signed off 2026-07-03)*

OneStop in the Public-datasets picker across the whole corpus surface: all four
regimes × seven parts × two variants (public OSF download-on-demand / lacclab local
export). Loader `datasets.onestop_raw_frames` / `load_onestop`; sidebar
`_load_onestop_public_source`; CLI `render --onestop …`; docs
[`onestop.md`](docs/onestop.md). The public source **and** its variant/regime/parts
are shareable via deep link (`?source=onestop_public&onestop_regime=…`, DATA-3
follow-up signed off 2026-07-03).

**DATA-9 · Reorganize the Data sidebar (merge source + selection, nest setup/mapping)** — `Status: Done` *(signed off 2026-07-03)*

Flat tagged source picker (🧪 demo · 🔒 private · 🌐 public) + one ordered config
group (Description → Options → Data location → Experimental Setup → Column mapping);
native 📁 Browse folder picker (`_pick_directory_dialog`); relative-path anchoring
to the project root (`_resolve_data_dir`); Save & restore split to its own
top-level section.

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

**ENG-11 · Version saved plot-config JSON + migration path** — `Status: Done` *(signed off 2026-07-03)*

`url_state.PLOT_CONFIG_SCHEMA` (single source of truth, stamped by both writers —
`tabs._build_studio_config` + `wizard._wizard_setup_config`) +
`_migrate_plot_config`/`_detect_config_schema`/`_PLOT_CONFIG_MIGRATIONS`: an older
config upgrades forward on load; a newer one restores best-effort with a warning
toast. Scoped to the Save & restore surface. An adversarial review fixed an
`Infinity`-schema `OverflowError` that aborted the whole restore.

**ENG-12 · Document the true-to-scale text rendering model** — `Status: Done` *(signed off 2026-07-03)*

New [`docs/rendering.md`](docs/rendering.md) (in the MkDocs nav): the
data-space→screen-px model, line-pitch font budgeting, script-aware width fitting,
the pixels-vs-points distinction (folds in VIZ-1), and why the spatial plot uses
the true-scale embed instead of `st.plotly_chart`.
