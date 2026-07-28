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
[Analysis & corpus views](#analysis--corpus-views) ·
[Export](#export) ·
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

**UX-16 · About popover: collapse the citation by default** — `Status: Done` *(signed off 2026-07-28)*

The BibTeX block filled the popover and pushed everything under it out of view.
It now opens from a **Show BibTeX** expander inside a divider-separated
*📖 Citing Scanpath Studio* section, so version, authors, affiliations and the
links read first. The About panel was tightened at the same time: Documentation
and Code merged into one line of bare links, the two lab links that duplicated
the affiliations line were dropped, and every co-author is linked.

**UX-17 · Link to the documentation site from the app** — `Status: Done` *(signed off 2026-07-28)*

`CITATION["docs_url"]` is the single source; it's linked from the sidebar Help
group (a `link_button` marked **↗** so it reads as leaving the app) and from the
About popover. Both say "opens in a new tab".

**UX-18 · Make the Corpus Analysis view more discoverable** — `Status: Done` *(signed off 2026-07-28)*

The only door to the corpus-level half of the app was a plain secondary button,
routinely missed. Outbound it now renders `primary` with a **→** cue and a
spelled-out help string; the return trip stays quiet (secondary, **←**) so the
two don't compete. Still one button, not a second navigation system. (A
"what's over there" caption was tried and removed at review — the button carries
it.)

**UX-8 · Collapsed-sidebar hover expand is hard to dismiss** — `Status: Done` *(signed off 2026-07-28)*

The real obstacle wasn't the hover zone: Streamlit's only exit from an open
sidebar is the `«` collapse control, and it ships `visibility: hidden` until the
pointer is already inside the sidebar — so dismissing one meant hunting for a
target that was both invisible and icon-small. [`styles.py`](scanpath_studio/styles.py)
now pins `[data-testid="stSidebarCollapseButton"]` visible (muted at 0.6 opacity,
full on hover) and gives it — and the matching `»` expand control in the header —
a 2.4 rem hit area with a brand-tinted hover, so the pair reads as one toggle.

**UX-12 · "Don't show again" for the welcome tour** — `Status: Done` *(signed off 2026-07-28)*

A **Don't show this again** checkbox on the welcome and final tour steps, backed
by a first-party `sps_tour_optout` cookie (`tour.TOUR_OPTOUT_COOKIE`) rather than
session state: there are no accounts, session state dies with the tab, and a
cookie is the one browser-side store Python can also *read*
(`st.context.cookies`) — `localStorage` would need a bidirectional custom
component to get the value back to the server. The box writes it from a
same-origin script (`_tour_optout_script`); `tour_opted_out()` gates both
`spotlight_tour_pending` and `maybe_show_welcome_tour`. The sidebar's **🎓 Show
tutorial** deliberately ignores the opt-out and renders the box pre-ticked, so
the choice is reversible from the same place. Tests: `TestTourOptOut`
([`tests/test_tour.py`](tests/test_tour.py)).

**UX-13 · Detach "Snap fixations above words" from Drift correction** — `Status: Done` *(signed off 2026-07-28)*

`global_fixation_snap_to_word` sat flush under the **Drift correction** selectbox,
which made it read as a drift-correction option — it is not; it's the fixation
half of the VIZ-9 linear-reading schematic. It keeps its home under **Fixations**
(it moves fixations, and VIZ-9 sign-off put it there deliberately) but now sits in
its own divider-separated *Linear-reading schematic* block, and the help spells
out the contrast: schematic layout vs. nudging raw coordinates onto their true
line. The Saccade **Line shape → Arc** control and this one now name each other.

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

**UX-9 · Numeric entry (text box or ± buttons) alongside sliders** — `Status: Done` *(signed off 2026-07-28)*

Sliders (marker size, opacity, short/long ms thresholds, line width, font size)
can't be set to an exact value. Pair the `global_*` sliders in
[`controls.py`](scanpath_studio/controls.py) with a number input or stepper so a
precise value can be typed. Purely a widget change — the session keys and every
downstream surface stay as they are.

**UX-11 · Redesign the trial chip strip** — `Status: Done` *(signed off 2026-07-28)*

The `Field = Value` chip strip above the plot
(`tabs._render_trial_condition_chips` [`tabs.py`](scanpath_studio/tabs.py:1803))
is **awkward as it stands and needs a rethink, not a patch** — treat the current
symptoms as evidence of the wrong shape rather than as the work items:

- The **More** disclosure repeats every chip already visible inline, so the same
  facts are shown twice. This is deliberate today — the comment at
  [`tabs.py`](scanpath_studio/tabs.py:1871) argues that which chips fit is a
  live-width question Python can't answer, so *More* always carries everything —
  which is exactly the constraint the redesign has to escape.
- The last chip is clipped by the **More** toggle.
- The inline ✏️ edit toggle sits too high relative to the chip baseline.

**Approach:** start from what the strip is *for* — "what am I looking at" at a
glance, plus the full trial detail on demand — and pick a form that survives any
window width. Options worth weighing: real CSS overflow (a wrapping or
horizontally-scrolling row, so nothing is silently cut and *More* isn't needed as
a fallback); a fixed small set of primary chips with everything else behind one
explicit **Details** control; or dropping the one-line constraint entirely and
letting the strip wrap to two lines. Whatever lands should keep the configurable
field list (the ✏️ picker, `controls.render_trial_chip_picker`) and the
condition colouring (`_chip_color`). Related: **UX-19** (the same strip is one of
the first things to break on a narrow laptop).

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

**VIZ-4 · Improve image-based stimuli support** — `Status: Done` *(signed off 2026-07-03)*

Any dataset can show a stimulus image: an **upload overrides** a dataset's built-in
image, and the `image_path`/`image_x`/`image_y` column convention declares native
per-trial images for any dataset. **Align to text** controls (image X/Y offset +
scale) manually fit the image to the word boxes / fixations — handling
text-area-only (OneStop) and off-origin (MultiplEYE) images. Opacity + alignment on
every surface (UI / Share / Save & restore); CLI `--stimulus-image*`, API
`background_image*`. On-disk folder + naming-pattern resolver deferred to **VIZ-14**.

**VIZ-5 · Export the plot as separable layers** — `Status: Done` *(signed off 2026-07-03)*

A bulk **Separable layers** toggle writes one file per layer (word boxes / fixations
/ saccades / heatmap / labels / stimulus image / frame) that register when stacked;
CLI `--separable-layers` + `save_figure_layers()` / `split_scanpath_layers()`. Fix:
bulk export now uses `extract_trial` and skips a trial only when **both** frames are
empty, so a fixations-only / non-joining-words dataset exports instead of reporting
"empty data" for every trial.

**VIZ-8 · Color saccades by saccade type** — `Status: Done` *(signed off 2026-07-03)*

A **Saccade color** mode (Uniform / By type) colours each saccade by reading class
(forward / skip / refixation / return-sweep / regression, + grey *other*) via a new
`measures.classify_saccades`; the class colours are editable (and seed correctly
now, not black) with an optional **Show legend** toggle. Every surface (Share
`saccade_color_mode` / `saccade_type_legend` / `saccade_color_<class>`; CLI
`--saccade-color-by-type` / `--saccade-type-color` / `--no-saccade-type-legend`; API).

**VIZ-9 · "Linear reading" view — saccades as arcs, fixations above the words** — `Status: Done` *(signed off 2026-07-03)*

A **Line shape** control (Straight / Arc) arches the saccades; **Snap fixations
above words** (now under Fixations) places each fixation at the top-centre of its
word — the classic reading diagram. Both off by default, every surface (Share /
Save & restore / CLI `--saccade-arcs` / `--snap-fixations` / API).

**VIZ-10 · Animate: autoplay on by default + a start/stop autoplay control** — `Status: Done` *(signed off 2026-07-03)*

The replay autoplays on load at the configured speed (an **Autoplay on load**
checkbox turns it off). The kickoff polls for Plotly + the real frame list
(`_transitionData._frames`, not the always-`undefined` `gd.frames` — the bug that
made it never fire) then plays from the first frame. Every surface (Share
`anim_autoplay` / Save & restore / CLI `--animate --no-autoplay` / API
`animate_scanpath(autoplay=…)`, honoured by `save_figure` for HTML).

**VIZ-17 · Default fixations to one colour (colour vs. size is redundant)** — `Status: Done` *(signed off 2026-07-28)*

Marker size and marker hue both encoded fixation duration, double-encoding one
variable and spending the colour channel on nothing. `constants.UNIFORM_COLOR_FIELD`
(`"(uniform)"`) leads the **Color fixations by** list and is the default on every
surface — the app, `?color_by=`, `--color-by`, and `api.CANONICAL_FIGURE_DEFAULTS`
— with a `fixation_color` picker/kwarg for the flat colour. Colour-by is now an
explicit opt-in for a *second* variable (surprisal, frequency, line, pass index),
and the fixation colorscale picker only appears once one is chosen.

**VIZ-19 · Simpler saccade colouring** — `Status: Done` *(signed off 2026-07-28)*

A third mode, **Forward / regression**, sits between one uniform colour and the
five-way *By type* split — the distinction most reading figures actually draw.
It reuses the whole by-type machinery: `constants.SACCADE_DIRECTION_FOLD` collapses
the five reading classes into two buckets before the segments are built, so the
colour pickers, the legend toggle, the deep link, `--saccade-color-by-direction`
and the headless API are unchanged. The control surface shrank with it — only the
two class colours that mode actually draws are shown. A test asserts the fold
draws the same number of segment points as the five-way split, so nothing is lost.

---

**VIZ-15 · Fixation marker shape control** — `Status: Done` *(signed off 2026-07-28)*

Fixation markers are configurable in size, colour, opacity and hollow/filled, but
the **symbol** is fixed. Add a shape picker (circle / square / diamond / cross /
triangle …) as a `global_*` key threaded through `_collect_viz_settings` →
`make_scanpath_figure`, plus deep link / CLI / headless API per *AGENTS.md →
Exposing a feature on every surface*. Pairs with **VIZ-17** (a shape becomes a
second channel once colour stops duplicating size) and **VIZ-18** (shape carries
the distinction in print / greyscale).

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

**BUG-5 · Upload crashes on Streamlit Community Cloud (works locally)** — `Status: Done` *(signed off 2026-07-03)*

Root cause: a large (often zipped) upload decompresses + parses into several
in-memory copies that OOM-kill the ~1 GB hosted demo with no traceback. Fix: a
pre-parse size guard (`data.upload_exceeds_limit`, ~25 MB) warns and requires an
explicit opt-in before parsing (one click locally), wired into
`app._read_uploaded_frame`.

**BUG-6 · Accent color differs: blue locally vs. red on the deployed app** — `Status: Done` *(signed off 2026-07-03)*

The theme (`primaryColor` blue) is pinned in `.streamlit/config.toml`, but Streamlit
only auto-loads that relative to the launch dir — so `python -m scanpath_studio`
from elsewhere fell back to red. `cli.launch_app` now injects the theme as
`--theme.*` flags from `constants.APP_THEME` (parity-tested against the config
file), so every launch path renders the same theme.


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

**ENG-8 · Resolve / promote the "Generations (WIP)" tab** — `Status: Done` *(signed off 2026-07-03)*

Became the data-driven **🔬 Comparisons** subtab: pick a **Comparison column** and
score the selected scanpath against every other scanpath of the same text grouped
by it (NLD; the closest shown in a grid). **📐 Line assignment** unnested to its own
top-level subtab; the redundant fixation-index slider + stimulus panel removed.
Synthetic `model_scanpaths.py` is now app-unused (tests only) — a delete candidate.

**ENG-14 · Replace the provisional/TBD author list with the real co-authors** — `Status: Done` *(signed off 2026-07-03)*

Full author list + affiliations in order (Shubi · Gruteke Klein · Lion — LACC Lab,
Technion · Jacobi · Reiche [also U Potsdam] · Jäger — DiLi Lab, UZH · Berzak)
across `CITATION.cff`, the README, the About panel (BibTeX + credits), and
`constants.CITATION`.

---

## Analysis & corpus views

_Signed off 2026-07-28. **AN-28** (thread the active filter + visualization
settings into Corpus Analysis) is the one piece that did not land and stays open
in [`IMPROVEMENTS.md`](IMPROVEMENTS.md)._

**Goal:** replace the single *Corpus Analysis → Aggregated Views* subtab with a
set of analysis sections, each answering one question — *what does a text look
like? a reader? a group? two groups against each other?* All sections obey the
active trial filters and the metric picker.

**Implementation convention:** keep aggregation logic **pure** in
[`aggregation.py`](scanpath_studio/aggregation.py) (one helper per view → tidy
DataFrame), build figures in [`plots.py`](scanpath_studio/plots.py) via the
`make_*_figure` pattern, wire into [`tabs.py`](scanpath_studio/tabs.py). Add a
smoke test per figure against the bundled sample (3 pid × 2 articles).

> **Note (2026-07-03):** the user asked to **keep this epic open** (not signing off
> yet). *Generations* has since moved out to the Scanpath view's Comparisons
> subtab (ENG-8), so Corpus Analysis is now **Per text · Per reader · Groups**.

**Status (`Pending approval`):** the whole epic is implemented. *Aggregated Views*
is replaced by four question-oriented subtabs — **Per text · Per reader · Per
group · Group comparison** (`render_per_text_tab` / `render_per_reader_tab` /
`render_per_group_tab` / `render_group_comparison_tab`) — alongside *Generations
(WIP)*. Pure helpers + a `Measure` registry live in `aggregation.py`, builders in
`plots.py`, cross-cutting controls + cached wrappers in `tabs.py`; groups are
defined by splitting a field **or** by two independent filter sets. Tests in
[`tests/test_analysis_views.py`](tests/test_analysis_views.py) (unit per helper +
smoke per figure on the bundled sample); `scipy` added for AN-21. Docs synced
(CHANGELOG / AGENTS / `scanpath_studio/CLAUDE.md` / `docs/`).

### Per text — one `paragraph_id`/`trial_id`, many readers

**AN-1 · Stacked per-reader word profiles (small multiples)** — `Status: Done` *(signed off 2026-07-28)* *(primary request)*

X = `word_id` (reading order), Y = chosen measure (TFD default; switch FFD/FPRT/
RPD/`n_fixations`). One panel per `participant_id`, stacked with shared X
(`make_subplots`, `shared_xaxes`). Optional faint cohort-mean overlay per panel.

**AN-2 · Word × reader heatmap** — `Status: Done` *(signed off 2026-07-28)*

Same data collapsed to one heatmap: rows = participants, cols = `word_id`, color =
measure. Bright columns = universally hard words; bright rows = uniformly slow
reader. Reuses word-level heatmap machinery.

**AN-3 · Cohort word profile with spread band** — `Status: Done` *(signed off 2026-07-28)*

Mean measure per word + shaded IQR/±1 SD band across readers — the "average
reader of this text" with uncertainty.

**AN-4 · Word difficulty annotated on the stimulus** — `Status: Done` *(signed off 2026-07-28)*

The text laid out (true-to-scale renderer), each word tinted by aggregate measure
or `skip_rate` / `regression_in_rate` — corpus-level scanpath, no fixations drawn.

**AN-5 · Measure vs. linguistic feature scatter** — `Status: Done` *(signed off 2026-07-28)*

Per-word mean measure vs. a bundled feature (`gpt2_surprisal`,
`wordfreq_frequency`, `word_length`, `universal_pos`) with a trend line. OneStop
sample ships these columns.

**AN-6 · Skip / regression rate per word** — `Status: Done` *(signed off 2026-07-28)*

Bar/lollipop of `skip_flag` and `regression_in_flag` rates by `word_id`.

### Per participant — one `participant_id`, many trials

**AN-7 · Measure distributions vs. cohort** — `Status: Done` *(signed off 2026-07-28)*

Histogram/violin/box of fixation `duration_ms`, `saccade_amplitude`, per-word
TFD/FFD for the selected reader, with the cohort distribution behind. Optional KDE.

**AN-8 · Reading speed & summary card** — `Status: Done` *(signed off 2026-07-28)*

WPM, mean fixation duration, fixation count, regression rate, skip rate, mean
saccade amplitude — compact stat strip + cohort percentiles.

**AN-9 · Fixation duration over time** — `Status: Done` *(signed off 2026-07-28)*

X = `timestamp_ms` (or `order_in_trial`), Y = `duration_ms` — within-trial
fatigue/settling. Faceted by trial or averaged.

**AN-10 · Saccade amplitude vs. fixation duration** — `Status: Done` *(signed off 2026-07-28)*

2D density / hexbin — the classic oculomotor scatter (careful vs. skimming).

**AN-11 · Progressive vs. regressive saccades** — `Status: Done` *(signed off 2026-07-28)*

Counts/share of `is_regression` / `regression_out_flag` per trial.

**AN-12 · Launch-site / landing-position curves** — `Status: Done` *(signed off 2026-07-28)*

Histogram of landing position within words (needs `first_fix_x` relative to word
box) — the preferred-viewing-location curve. Overlaps **PRE-4**'s
`initial_landing_position`.

**AN-13 · Per-trial trend for this reader** — `Status: Done` *(signed off 2026-07-28)*

The existing Trends line filtered to one participant — does this person slow down
across the session?

### Per group — a cohort defined by the active filter

**AN-14 · Group distribution summaries** — `Status: Done` *(signed off 2026-07-28)*

Per-participant distributions pooled across the group (violin/box of fixation
duration, saccade amplitude, TFD, reading speed).

**AN-15 · Group word profile** — `Status: Done` *(signed off 2026-07-28)*

Cohort word profile (mean + band) computed within the group, for a selected text.

**AN-16 · Per-reader summary table for the group** — `Status: Done` *(signed off 2026-07-28)*

Sortable table, one row per participant, columns = summary stats — spot outliers.

**AN-17 · Group trend** — `Status: Done` *(signed off 2026-07-28)*

Trends line averaged within the group (optionally per-participant faint behind).

### Group comparison — two groups side by side

**AN-18 · Overlaid distributions** — `Status: Done` *(signed off 2026-07-28)*

Two groups' fixation-duration / saccade-amplitude / TFD distributions on shared
axes (violin halves or overlaid KDE).

**AN-19 · Difference word profile** — `Status: Done` *(signed off 2026-07-28)*

Per-word measure A − B along the text with a zero reference line and diverging
colormap — *where* the groups diverge (Adv vs. Ele, L1 vs. L2).

**AN-20 · Paired summary bars** — `Status: Done` *(signed off 2026-07-28)*

Side-by-side group-mean bars per measure with error bars (SD / SEM / bootstrap CI).

**AN-21 · Effect size + simple test** — `Status: Done` *(signed off 2026-07-28)*

Per measure: mean difference, Cohen's *d*, Mann–Whitney / t-test p-value, with a
clear "exploratory, not pre-registered" caveat.

**AN-22 · Two-group word heatmap, stacked** — `Status: Done` *(signed off 2026-07-28)*

Group A heatmap above group B (shared word axis) for direct visual comparison.

### Cross-cutting controls for the analysis sections

**AN-23 · Shared measure picker** — `Status: Done` *(signed off 2026-07-28)*

One measure picker (TFD/FFD/FPRT/RPD/`n_fixations`/skip/regression) every section
reads from.

**AN-24 · Aggregation & spread choice** — `Status: Done` *(signed off 2026-07-28)*

Mean/median/sum aggregation and SD/IQR/SEM/bootstrap-CI spread where a band or
error bar is drawn.

**AN-25 · Normalization toggle (raw vs. z-scored within reader)** — `Status: Done` *(signed off 2026-07-28)*

So slow and fast readers compare on shape, not absolute level.

**AN-26 · Min-readers / min-trials guard** — `Status: Done` *(signed off 2026-07-28)*

Gray out / warn when a per-word cell is backed by too few observations.

**AN-27 · Download the underlying tidy table per view** — `Status: Done` *(signed off 2026-07-28)*

Reuse the export plumbing so users can re-plot elsewhere.

---

## Export

**EXP-1 · Customizable export file / folder names** — `Status: Done` *(signed off 2026-07-28)*

Export uses fixed naming, so a zip of many trials lands with names that don't
match how the user organizes figures. Let the user supply a filename / folder
**pattern** built from trial fields — e.g.
`{participant_id}/{trial_id}_{measure}.png` — validated against the available
fields, with a live preview of the resulting paths and a safe fallback for
missing or unsafe values.

**EXP-2 · Titles and captions on exports** — `Status: Done` *(signed off 2026-07-28)*

Add an optional figure **title** and **caption**, either auto-generated from the
trial (participant, text, condition, and the settings that produced the figure) or
hand-written, rendered into the exported image and recorded in the export
manifest — so a figure pulled into a paper or slide carries its own provenance.
Related: **EXP-1**, **AN-27** (tidy-table download).
