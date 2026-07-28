# Scanpath Studio — Improvements Archive

Signed-off items, moved here from [`IMPROVEMENTS.md`](IMPROVEMENTS.md) to keep the
working tracker focused on open work.

- An item lands here **only after the user gives final sign-off** on the
  implementation (it sits at `Status: Pending approval` in the main file until
  then). See the *Approval gate* note in `IMPROVEMENTS.md`.
- **IDs are stable and preserved** — cite an archived item by the same ID
  (`UX-2`, `ENG-5`, …); it just lives here once signed off. Items stay under
  their original group headings for findability.
- Items closed **without** being implemented are archived here too, with the
  reason — `IMPROVEMENTS.md` holds only open work.

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

**UX-7 · Clearer "no data" states — say what's missing and how to fix it** — `Status: Done` *(signed off 2026-07-28)*

Two cases, both terse or generic today.

**(a) Filters / selection produced nothing.** [`app.py`](scanpath_studio/app.py:2051)
shows one blanket *"No data after filtering. Loosen the Filter trials panel…"*
for every cause — it doesn't say **which** filter emptied the set (participants,
condition, favourites/tags, the trial-index window), how many rows each dropped,
or offer a one-click **clear filters**. Same for a participant×text combo with no
fixations, and for the raw-gaze-overlay message just above it.

**(b) A public dataset isn't available locally.** Picking a download-on-demand
corpus (OneStop `public`, PoTeC — `download_onestop` / `download_potec` in
[`datasets.py`](scanpath_studio/datasets.py:511)) or a `$ONESTOP_DATA_DIR`-backed
source when the files aren't there surfaces a raw `FileNotFoundError` / loader
message instead of a first-class state. It should name the dataset, say what's
missing (files, or an unset `ONESTOP_DATA_DIR`), how big the download is, and put
the action inline — **Download now**, the env-var instructions, or "you're
offline". The found-vs-download status check already exists
([`datasets.py`](scanpath_studio/datasets.py:501)) — surface it *before* the read.

AC: no blank chart and no bare traceback for either case; every empty state names
the cause and offers the next action.

**Follow-up (2026-07-28), from your review.** Three changes: the count says what
it counts (*"**0** of the **36 trials** in this dataset get through"*, not
"dataset has 36"); each named culprit gets its own **Clear** button beside it
(`controls.clear_trial_filter`, fed by the reset keys `data.diagnose_filters`
now carries per step — the Narrow-by *Text* multiselect is why they can't be
derived from the column name); and both states render as **one** bordered,
amber-tinted panel instead of a warning banner + a grey caption + a body
paragraph + a button, which read as three unrelated messages.

**UX-10 · Sort trial / reader / text pickers by properties** — `Status: Done` *(signed off 2026-07-28)*

The trial-combo selector (`utils.build_combo_options`) lists combos in data
order. Add a sort control keyed on reader properties, text properties, and
trial-level stats (n fixations, reading speed, comprehension correctness) so
outliers and interesting trials surface without scrolling.

**Follow-up (2026-07-28), from your review.** The ordering was invisible — the
key lived in the ⇅ popover, so a sorted pool just looked shuffled. Every option
now ends with that trial's value for the active key (`utils.format_sort_value`:
thousands separators, one decimal, Yes/No, `—` for missing), on both the
selectbox and the slider thumb, and the picker's own label names the ordering:
**Trial ID · by Fixations (n) ↓**. Also `Trial id` → `Trial ID` throughout.

**UX-19 · Layout breaks on smaller laptop screens** — `Status: Done` *(signed off 2026-07-29)*

[`styles.py`](scanpath_studio/styles.py) had **no width breakpoints at all** — the
only `@media` rule was `prefers-color-scheme` — so every layout decision was
fixed-width. Added real breakpoints across ≥1280 px down to ~1024 px for the chip
strip (**UX-11**), the control rail and the header nav. The true-to-scale plot
keeps its scale guarantee: it may scroll, never distort.

**UX-20 · Disclose that the code was written with AI assistance** — `Status: Done` *(signed off 2026-07-29)*

Said plainly where a user will see it — the three places the citation lives: the
About popover (`app._render_about_sidebar`), the README, and `docs/index.md`.

The design constraint took two rounds to get right. A bare "built with AI, there
may be bugs" is unfalsifiable, so the first draft backed it with detail — how the
measures were validated, what to do before publishing, where to report. That was
argued at bullet-list length on all three surfaces, and it also made claims about
*effort* ("we put real effort into validating it", "a trial we traced by hand")
that a reader has no way to check. Both got cut. What shipped is a short paragraph
holding only what a reader can verify for themselves — the ground-truth trial at
`?source=synthetic`, and that pre-computed EyeLink `IA_*` measures are passed
through rather than recomputed — plus the ask (cross-check anything you publish)
and the issues link with the 💾 Save & restore JSON that reproduces the view.
Deliberately not a liability disclaimer: MIT already carries the no-warranty text.

[`tests/test_disclosure.py`](tests/test_disclosure.py) pins the note's own claims,
because a disclosure whose "you can check this yourself" turns out to be wrong is
worse than none: that it's on every surface with the actionable half intact, that
it carries no disclaimer language, that `?source=synthetic` really does load the
ground-truth trial (drafting caught this — the note first said "pick it in the
data-source picker", but that source is deliberately not offered there, so the
deep link is the only route), that `EXPECTED` covers every canonical measure, and
that an `IA_*` value survives both normalization and `compute_word_metrics`
untouched — which is what makes the passthrough claim true.

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

**VIZ-11 · Animate slider: uniform time grid + "elapsed / total seconds" readout** — `Status: Done` *(signed off 2026-07-29)*

Animation frames sit on a **uniform time grid** rather than one per fixation onset,
so the slider is a linear time scrubber and its readout (`elapsed / total s`) means
the same thing for one scanpath or two — the fixation-index readout was ambiguous
in compare mode, where the steps are the union of both onset sets.

The grid was initially decided *for* the user in two module constants, and the
frame cap coarsened the requested step **silently** (on the bundled demo a 100 ms
request became 110 ms). Both knobs are now visible in the Animate ⚙ Playback
popover — **Frame every (ms)** and **Max frames** — and the info box states what
the choice produced: *"361 frames · one every 110 ms of reading — coarsened from
100 ms to stay under the 360-frame cap"*. `plots.animation_timeline_summary`
computes that without building the figure. All four surfaces: the two
`global_anim_*` keys, `anim_grid_step_ms` / `anim_max_frames` in the deep link
(clamped via `_URL_BOUNDED`) and the saved config's `animation` section,
`--anim-grid-step-ms` / `--anim-max-frames` on `render`, and the same two names as
`animate_scanpath` overrides. Defaults unchanged.

**VIZ-16 · Show the word text in the fixation hover** — `Status: Dropped` *(2026-07-29)*

The fixation hover reads `Fixation # / Duration / Word #` — the word *number*, not
the word. The proposal was to add the word text (as the word-box hover already
does) via `customdata`, on the single, compare and animation traces.

**Dropped at the user's request, never implemented** — kept here so the idea and
its reasoning aren't lost, not because it shipped. Nothing in the code changed;
`VIZ-16` stays retired rather than being reused for something else.

**VIZ-18 · Rethink the default palette (contrast, print, greyscale, colourblind)** — `Status: Done` *(signed off 2026-07-29)*

These figures get read on screen, printed in a paper, photocopied in black &
white, and by colourblind viewers — one palette can't be right for all four, so
they're **selectable**: `constants.PALETTES` (colourblind-safe / print-greyscale /
high-contrast, plus the original), applied by `controls.apply_palette` as the
selector's `on_change`.

A palette **presets** rather than replaces the colour controls — it writes into
the same `global_*` keys the ordinary pickers own (`global_fixation_color`,
`global_fixation_colorscale`, `global_heatmap_colorscale`, `global_saccade_color`,
`global_text_color`, `global_highlight_text_color`, one key per editable saccade
class), so every picker stays authoritative and editable afterwards. Background
colour is deliberately excluded (canvas, not marks).

**Follow-up (2026-07-29) — the selector no longer claims a palette you've edited
away from.** `apply_palette` is one-way and fires only on change, so picking
*Colourblind-safe* and hand-editing one colour left the dropdown still reading
"Colourblind-safe" while the figure no longer was. Fixed as **VIZ-12** fixed it
for quick views: `controls._active_palette()` derives the active palette by
comparing live `global_*` values against each palette's `palette_state` (hex
normalized — pickers hand colours back lowercase) and returns `None` once they
diverge. `constants.CUSTOM_PALETTE` is offered as an option *only while it's
true*, captioned with what you drifted from ("Your own colours, edited from
**Colourblind-safe**"); undo the edit and the real palette returns, *Custom*
disappears. Deliberately **not** in `PALETTES`, so `--palette`'s choices,
`api._expand_palette` and `?palette=` still see exactly the four real palettes.
`_collect_viz_settings` derives the name too, so Share, Save & restore and the
export caption report `Custom` instead of a stale palette; `_restore_plot_config`
accepts it rather than flagging the user's own valid file. Tests in
[`tests/test_viz_palette.py`](tests/test_viz_palette.py), including an `AppTest`
driving the real rail, with four mutations run to confirm they discriminate.

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

**BUG-7 · EyeLink `'.'`-sentinel flag columns normalize to all-True** — `Status: Done` *(signed off 2026-07-28)*

`IA_REGRESSION_IN` / `IA_REGRESSION_OUT` in the bundled demo (and any LaCC-style
export) hold **strings** `'0'` / `'1'` / `'.'`; normalization casts them by
truthiness, so the canonical `regression_in_flag` / `regression_out_flag` come
out `True` for **every** row (`'0'` and `'.'` are non-empty strings). Repro:
`sps.load_sample_data()` → `compute_word_metrics(...)` →
`regression_in_flag.value_counts()` = `{True: 3922}`. Fix in the
[`data.py`](scanpath_studio/data.py) normalize path: `pd.to_numeric(errors="coerce")`
(or explicit `'.'`→NaN) before the bool cast, for every flag-like measure
column; add a regression test with a mixed `'0'/'1'/'.'` column. Found while
producing the paper's measure-validation numbers (2026-07-03).

**BUG-10 · Arcs don't clear the text** — `Status: Done` *(signed off 2026-07-28)*

Arc height is a fraction of saccade **length** (`_ARCH_FRAC`), so short saccades —
the majority within a line — arch by only a few pixels and stay inside the line of
text, defeating the point of the mode (the arc should read as a jump *over* the
words). Derive the arch height from the text geometry instead — line pitch /
word-box top (`_line_pitch`, [`plots.py`](scanpath_studio/plots.py:339)) — with a
floor, so every within-line arc sits above the words regardless of length.
Related: **BUG-9**, **VIZ-9**.

**Closed as working-as-intended (2026-07-28).** Arc mode is used for *single sentences*, where an arch proportional to saccade length reads correctly — a floor derived from the line pitch would over-arch the short within-line saccades that dominate there. Left as is.

**BUG-11 · Word box edges don't fall midway between words** — `Status: Done` *(signed off 2026-07-28)* *(reopened and completed the same day — see below)*

> **Reopened 2026-07-28.** The first pass corrected only
> `assign_fixations_to_words` and `build_word_boxes` — two of the nine places
> that read an AOI edge — so the bug was still visible: with the heatmap on, the
> tinted rects were drawn from the raw frame while the outlines came from the
> corrected one, half a space apart. **Second pass:** one pure accessor
> `measures.word_box_bounds(words, *, layout=None)` returns the corrected
> `(x0, y0, x1, y1)` arrays and *every* consumer goes through it —
> `_assign_word_ids_single`, `fixation_in_text_mask`, `build_word_boxes`,
> `_add_word_level_heatmap` (binning) + `_draw_word_value_heatmap` (rects),
> `build_critical_span_overlay`, `aggregation.landing_positions`,
> `plots._snap_fixations_to_words`, `alignment._word_centers_reading_order`,
> `model_scanpaths`, and `data.fill_fixation_xy_from_words`. Returning *arrays*
> rather than a shifted frame is the point: the frame-shaped
> `recentre_word_boxes` could be applied twice and silently double-shift, which
> is what made the first pass fragile. `layout=` covers the subset trap — tiling
> is a property of the whole line, so a highlighted span or the dwelt-on words
> must hand the full frame to the detector or the holes read as glyph-tight
> gaps. Tests in
> [`tests/test_word_box_geometry.py`](tests/test_word_box_geometry.py) (26).

Word box boundaries should sit in the **middle of the whitespace** between two
words; they don't — each box carries the *entire* inter-word space as trailing
padding, so every boundary is pushed a half-space to the right and each word sits
flush against its own left edge with a gap before the next word's glyphs.

**Measured on the bundled demo** (first trial, 19 px/char): every box is exactly
`(n_chars + 1) × 19` px wide and starts at the word's first glyph — `'Robert'`
`x0=358 → x1=491` (6 chars = 114 px of glyphs + 19 px of space), with
`'Myslajek'` starting at exactly `x0=491`. Boxes therefore *tile* the line (0 px
gaps, which is why this doesn't look obviously broken) but are offset by half a
space (~9.5 px here) from where they should be. Fixations landing in the space
before a word are attributed to the *previous* word — this touches
`measures.assign_fixations_to_words`, not just appearance.

Fix by re-centring the boundary — shift each box to
`[x - space/2, x + width - space/2]`, deriving the space width from the layout
(per-line, since it varies with font size) rather than assuming 19 px. Decide
whether that belongs in `data.normalize_words` (fixes geometry once, so measures
and export agree) or in `build_word_boxes`
([`plots.py`](scanpath_studio/plots.py:696)) (appearance only, cheaper, but leaves
assignment wrong). Check the other corpora too — PoTeC / MultiplEYE ship
glyph-tight AOIs and may need the opposite adjustment. Related: **PRE-5** (custom
interest areas), **VAL-1** (validate against the EyeLink-rendered image).

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

**DATA-13 · Data security** — `Status: Done` *(signed off 2026-07-29)*

[`docs/security.md`](docs/security.md) — an evidence-based audit citing the
`module.py:function` each claim was verified in: on-disk residue,
deep-link/saved-config leakage, ingest path handling, the desktop bundle's bind
address, and cross-session cache bleed. 11 findings (S1–S11), severity-ranked,
each with the exact fix; two accepted with reasons. It deliberately changed no
code so the fixes land as reviewable commits — those are tracked separately as
**DATA-16**, which is still open (S1/S2/S4/S5 done, S3/S6/S7/S10/S11 next).

**DATA-11 · Documented "bring your own dataset" pipeline** — `Status: Done` *(signed off 2026-07-29)*

[`docs/bring-your-own-data.md`](docs/bring-your-own-data.md) — the end-to-end path
from a raw export to a loaded dataset: the minimum the app needs (word boxes +
fixations) and what degrades without each field, how auto-detection works and how
to override it, saving and reusing a mapping, worked EyeLink-report and plain-CSV
examples, and a symptom→cause table. Linked from the wizard's first screen and
from `getting-started` / `data-format`. Distinct from **DATA-14** (getting a
dataset *bundled* with the app).

Rewritten 2026-07-29, 435 → ~195 lines: the content was right, the shape wasn't.
It opened with a field-by-field reference and a 12-row candidate-column table
before saying what to *do*; it now leads with the two-sentence answer (EyeLink
users are done) and keeps only the omissions that change behaviour. The candidate
table is gone — it duplicated `data.py` and would rot — replaced by how matching
works. Worked examples and the symptom→cause list are collapsed, so the page is
one screen until you need them.

**DATA-12 · Privacy statement — "we don't use your data"** — `Status: Done` *(signed off 2026-07-29)*

Researchers with participant data need to know where an upload goes *before* they
upload, not to infer it. [`docs/privacy.md`](docs/privacy.md) was written from the
code rather than from intent: where an upload actually goes, the three things that
*do* touch the disk, what a share link and a saved config contain, Streamlit's own
telemetry, and a per-deployment section (local / desktop / hosted demo). In the
app, the wizard states where a file goes above the uploader and About links the
page.

Writing it from the code changed the code twice: the CLI now injects
`--browser.gatherUsageStats=false` (Streamlit's default is opt-*in*, and
`.streamlit/config.toml` resolves against the launch directory, so a pip-installed
run had telemetry on), and the desktop bundle binds loopback.

Rewritten 2026-07-29, 436 → ~170 lines. The draft assumed a reader who knows what
`uuid4`, `SIGKILL`, `SameSite=Lax` and a CSRF double-submit token are — not the
audience for a privacy page. Now: the answer first ("nowhere"), then the one
setting that matters on a shared network, then what's in a link / a config / an
export, then what wasn't checked. Internal class names are gone; the technical
version is [`docs/security.md`](docs/security.md), linked. The rewrite also caught
**three claims that had gone stale** since **DATA-16** landed — that the desktop
bundle serves the whole network (fixed by S1), that a pip install has telemetry on
(fixed by the CLI flag), and that exports carry an absolute local path (fixed by
S4's `strip_local_paths`). A privacy page describing vulnerabilities that no longer
exist is its own kind of wrong.

**DATA-14 · Document how to get a dataset bundled by default** — `Status: Done` *(signed off 2026-07-29)*

[`docs/contributing-a-dataset.md`](docs/contributing-a-dataset.md) — the real
adapter contract, derived from OneStop / MultiplEYE / PoTeC rather than invented:
the raw-frames entry point and its signature, canonical-column mapping and
optional-field registration, registry wiring, licence expectations, bundled vs.
download-on-demand and the size threshold that decides, expected tests, and PR
shape, with one existing adapter walked end to end. Linked from `CONTRIBUTING.md`
and the data-source picker. Distinct from **DATA-11** (loading your own data in
the app).

Rewritten 2026-07-29, 497 → ~240 lines. The reader is technical, but the page
still opened with three sections of preamble before the question that decides
everything — *do you need an adapter at all?* That's now first, as a table of what
each existing adapter solves. The six-part contract is one scannable list with the
schema detail collapsed; the ten-step PoTeC walkthrough became a paragraph naming
the functions to read in order; the tests table became prose keeping the two rules
that matter (never hit the network, hand-compute expectations) and the one trap
that bites (add your `<CORPUS>_DEFAULT_DIR` to the monkeypatched tuple).

---

## Engineering

### Tests

**ENG-1 · Tests for each `aggregation.py` helper + smoke test per new figure** — `Status: Done` *(signed off 2026-07-29)*

Every public helper in `aggregation.py` (36 names, checked by an AST walk) is
covered by a tiny hand-built tidy frame with hand-computed expectations, in
[`tests/test_aggregation.py`](tests/test_aggregation.py); the figure builders get
a structural smoke test each in
[`tests/test_analysis_figures.py`](tests/test_analysis_figures.py). The old
`tests/test_analysis_views.py` was **deleted** — 516 lines of
`assert len(fig.data) >= 1` / `not out.empty` over the same builders; its two
unique regression cases were re-homed first.

Writing it surfaced **two real defects**, both fixed: `add_normalized_column`
filled an undefined z with `0.0`, conflating a zero-variance group (where 0 *is*
the mean) with a genuinely missing observation — so an unfixated word re-entered
the distribution as an exactly-average point and normalizing changed the
observation count; and `word_rate_profile`'s `n` counted **rows**, so a reader who
read a text twice cleared a min-readers guard that `cohort_word_profile` correctly
rejected — the two guards disagreed on the same frame, and the rates were
row-weighted.

**ENG-2 · Cover the OneStop per-pid shard fast-path** — `Status: Done` *(signed off 2026-07-29)*

[`tests/test_onestop_shard.py`](tests/test_onestop_shard.py) — 27 tests, two
layers. A synthetic export tree in `tmp_path` (CSV.zip pair +
`by_pid/{ia,fixations}/<pid>.parquet`) always runs; an agreement check against the
real corpus is gated on `$ONESTOP_DATA_DIR` with an explicit skip reason.

The behaviour worth pinning is the **refusal**: when a participant is named and
their shard is missing, `load_onestop_server_bundle` must *not* fall back to the
15 GB read. Testing that needs `st.stop()` to actually stop; in pytest's bare mode
it is a no-op, so the test swaps in a recorder whose `stop()` raises — without
that the assertion passes straight through to the slow path and still looks green.
Three mutations confirmed the tests discriminate. The separate path-construction
test exists *because* the end-to-end one didn't catch the first mutation: macOS is
case-insensitive, so the filesystem round-trip accepted the wrong case and only
Linux CI would have caught it.

**ENG-3 · Cover MultiplEYE side-data enrichment** — `Status: Done` *(signed off 2026-07-29)*

[`tests/test_multipleye_enrichment.py`](tests/test_multipleye_enrichment.py)
builds a synthetic MultiplEYE tree in `tmp_path` and covers each side-data kind —
comprehension questions, reader metadata, per-reader reading measures, stimulus
images — asserting merged *values* and join keys (no row multiplication), that a
missing file degrades to an absent column rather than a crash, and that malformed
side data can't corrupt the canonical columns.

**ENG-4 · Extend `AppTest` coverage** — `Status: Done` *(signed off 2026-07-29)*

[`tests/test_apptest_flows.py`](tests/test_apptest_flows.py) drives multi-step
flows: overriding a column mapping and checking the re-derived data, narrowing the
pool with the condition + annotation filters (including the UX-7 empty state and
the per-filter clear), and building the bulk-export zip. Render-level checks stay
in `test_apptest.py`. It turned up **BUG-12** — annotation filters skip the
raw-gaze table, so on the bundled demo the all-three-empty guard never fires; the
flow tests use the raw-gaze-free synthetic source to work around it.

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

**ENG-16 · README: one single-scanpath GIF instead of two** — `Status: Done` *(signed off 2026-07-29)*

The README embedded ~3 MB of animation before a reader reached the install line.
It now keeps the single-scanpath hero GIF and shows the dual-reader demo as a
still (`assets/demo_dual_scanpath.png`, 197 KB), captioned with a link to the
animated version on the docs site.

**Both assets are rendered from the real pipeline** — the originals were hand-made
and didn't correspond to any actual reading.
[`assets/render_dual_scanpath.py`](assets/render_dual_scanpath.py) builds them
from the bundled demo (two readers of `2_1_1_Ele`, 305 fixations) through
`plots.make_comparison_figure` and `make_scanpath_animation` +
`animation_export.export_animation` — exactly what the app draws. Committed
alongside its output, following the `project_map.dot` → `.png` precedent, so the
assets can be regenerated rather than rotting. Word boxes are off (212 AOI
outlines fight the scanpaths at README width) and both are palette-quantized: the
still 1.0 MB → 197 KB, the GIF 2.49 MB → 1.36 MB, visually unchanged.

**ENG-18 · Agent-facing docs + an agent-friendly API** — `Status: Done` *(signed off 2026-07-29)*

[`docs/agents.md`](docs/agents.md) is the counterpart to `AGENTS.md` for an agent
asked to *use* Scanpath Studio headlessly rather than develop it: canonical column
names, the minimum input a figure needs, the full parameter set with defaults, and
runnable end-to-end snippets. On the API side, a caller passing a table with the
wrong column names now gets a message naming the canonical field that couldn't be
inferred and the candidates that were tried, instead of a `KeyError` from deep
inside normalization.

**ENG-13 · Document the new analysis sections once built** — `Status: Done` *(signed off 2026-07-29)*

[`docs/corpus-analysis.md`](docs/corpus-analysis.md), in the site nav under *Using
the app*: the three subtabs (Per text · Per reader · Groups), what research
question each view answers, how to read it, the caveat that matters for each, and
the cross-cutting controls (measure picker, aggregation & spread, raw vs.
z-scored, the min-readers guard, tidy-table download) plus how the active filter
and viz settings carry in.

Rewritten 2026-07-29 alongside the other doc pages, 534 → ~315 lines. It's a
reference, meant to be scanned: each view is now Question + what it shows + the
one caveat that changes how you read it, and the ten-row measure table collapsed
to two columns (word-level vs fixation-level), which is the distinction that
actually governs which views accept a measure.

**ENG-15 · Package the app as a standalone desktop application** — `Status: Done` *(signed off 2026-07-29)*

A double-clickable app for Windows / macOS / Linux, so a researcher can use
Scanpath Studio without a Python toolchain, a terminal, or internet access — and
so private eye-tracking data never leaves the machine.

Approach per the ADR ([`plans/eng-15-desktop-app.md`](plans/eng-15-desktop-app.md)):
**PyInstaller onedir + the system default browser** (stlite/WASM rejected —
scipy/Parquet/Kaleido; Electron/Tauri and briefcase/constructor rejected for v1).
[`desktop/`](desktop/) holds `launcher.py` (free-port Streamlit server + branded
theme via `cli._theme_cli_flags` (BUG-6) + health-check browser open +
`--selfcheck`), `scanpath_studio.spec` (packages the **source** + `sample_data/`
— Streamlit re-execs `app.py` from disk — plus streamlit/plotly/sortables/kaleido/
imageio-ffmpeg data; `--global.developmentMode=false` guards frozen Streamlit),
`smoke_test.py` (frozen selfcheck: sample → figure → HTML + full app-module
import; then boot + `/_stcore/health` poll + `GET /`), and `make_icons.py` +
committed `icons/`. CI:
[`.github/workflows/desktop.yml`](.github/workflows/desktop.yml) — 3-OS matrix on
`v*` tags + manual dispatch, builds, smoke-tests, uploads artifacts, attaches
archives to the release.

**Verified on Linux** (507 MB onedir, smoke test green). The other two platforms
and the v1 rough edges are follow-ups, not part of this item: **ENG-19** (the
macOS bundle doesn't work), **ENG-20** (Windows console window + first-run
warning), **ENG-21** (signing / notarization). PNG-GIF export still needing a
system Chrome is **ENG-10**.

---

## Analysis & corpus views

_AN-1 … AN-27 signed off 2026-07-28; **AN-28** (thread the active filter +
visualization settings into Corpus Analysis) landed after and was signed off
2026-07-29 — it's the last entry in this section._

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

**AN-28 · Persist the active filter & visualization controls into Corpus Analysis** — `Status: Done` *(signed off 2026-07-29)*

The trial filters already carried into Corpus Analysis (the view is handed
`words_filtered`/`fixations_filtered`), but the display options didn't: the
per-text stimulus figure **hard-coded** heatmap style/metric/colorscale, colorbar
orientation/font, marker size, label & text styling, fixation-flag highlights and
the stimulus image, so the same trial looked different either side of the view
toggle. `render_corpus_analysis_tab` now takes `viz_settings` —
`app.main` builds it with `controls.viz_settings_from_state`, the non-rendering
reader of the same `global_*` keys the Scanpath rail writes — and the stimulus
figure reads the user's choices instead.

The *other* analysis figures (word profiles, distributions, difference profiles)
still take no colour or colourscale argument at all, and the Corpus view has no
controls of its own to change what it reads. Both are **AN-29**.

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
