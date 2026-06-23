# Scanpath Studio — Improvements & Roadmap

Working tracker for planned features, improvements, and bug fixes. Each item has a
stable **ID** (e.g. `UX-1`) you can cite in chat ("let's do `CMP-3`"), a
**Status**, and a short description with the relevant code anchors.

## How to use this file

- **Status:** `Backlog` (captured, not scheduled) · `Planned` (next-ish, scoped)
  · `In progress` · `Blocked` · `Pending approval` (implemented, awaiting the
  user's final sign-off) · `Done` (signed off — moved to the archive) ·
  `Skipped` (closed without implementing — stays here for the rationale, **not**
  archived).
- **Approval gate.** When an item's implementation is finished, mark it
  `Pending approval` — **never** jump straight to `Done`. Only after the user
  gives the final confirmation does it become `Done` **and move to**
  [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md), so this file stays scoped
  to open and recently-finished work. `Skipped` items are **not** archived.
- **IDs are stable.** Don't renumber when an item is finished. New items get the
  next free number in their group; archived items keep their ID over there.
- **Composite asks are split** into sub-items so they can land independently.
- When implementing an item, ask for clarification as needed before starting.

### Currently in progress
- **PERF-1** — Plotly → matplotlib migration ([PR #83](https://github.com/lacclab/scanpath-studio/pull/83), `matplotlib-migration` branch).
- **DATA-1** — Broaden dataset support (ongoing epic).

### Awaiting your approval
Implemented, not yet signed off (→ `Done` + archive on your confirmation):
_None — CMP-1…CMP-4 were signed off 2026-06-23 (see the archive)._

### Terminology
Canonical measures (per `AGENTS.md`): **FFD** (`first_fixation_ms`), **FPRT**
(`first_pass_gaze_duration_ms`), **RPD / go-past** (`regression_path_duration_ms`),
**TFD** (`total_fixation_duration_ms`), plus `n_fixations`, `skip_flag`,
`regression_in/out_flag`. Canonical keys: `participant_id`, `trial_id`,
`paragraph_id`, `word_id`, `line_idx`.

### Groups
[UX & Interaction](#ux--interaction) ·
[Compare mode](#compare-mode) ·
[Visualization & display](#visualization--display) ·
[Datasets & ingestion](#datasets--ingestion) ·
[Performance](#performance) ·
[Analysis & corpus views](#analysis--corpus-views) ·
[Preprocessing — eyekit parity](#preprocessing--eyekit-parity) ·
[Validation](#validation) ·
[Bugs](#bugs) ·
[Engineering](#engineering)

---

## UX & Interaction

_UX-1 · UX-1a · UX-2 · UX-2a · UX-3 signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md). Next item: `UX-4`._

---

## Compare mode

The "Compare with trial" flow (`single_compare_toggle`) and its per-scanpath
styling live in [`controls.py`](scanpath_studio/controls.py:622)
(`_COMPARE_SCANPATHS`, `_render_compare_fix_styles`,
`_render_compare_saccade_styles`, `_collect_compare_styles`); the overlay figure
is built in [`plots.py`](scanpath_studio/plots.py).

**CMP-1 · CMP-2 · CMP-3 · CMP-4** — `Status: Done (signed off 2026-06-23)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md). Selector moved above
the chips and made to mirror the main picker (trial id + ★/👤 markers, `index/N ·
id` slider); config moved into the rail **⚙️ Compare** popover; optional A/B legend
+ figure titles removed; per-scanpath colours fixed (incl. the "fixations turn black"
bug); and **Color fixations by** restored in compare mode.

---

## Visualization & display

**VIZ-1 · Warn that font sizes are px, not pt** — `Status: Planned`

All font-size controls are in **pixels** (e.g. `format="%.1f px"`,
`global_order_font_size`, `global_colorbar_tickfont_size` in
[`controls.py`](scanpath_studio/controls.py:1052)), but stimulus typography is
usually specified in **points**. Add a short note/warning near the font controls
explaining the difference (and that matching the original stimulus requires a
px↔pt conversion via DPI).

**VIZ-2 · Increase font size across the app where possible** — `Status: Planned`

General readability pass on app chrome (labels, captions, table text). Likely
[`styles.py`](scanpath_studio/styles.py) / theme. Keep within Streamlit theming;
don't regress dense layouts.

**VIZ-3 · Alternative heatmap normalization** — `Status: Backlog`

Explore normalization options for the heatmap views (e.g. per-trial vs per-corpus
max, log scaling, per-word-area density). Related but distinct from the new
`duration_mass` heatmap style (**PRE-8**).

**VIZ-4 · Improve image-based stimuli support** — `Status: Backlog`

Better handling/rendering when the stimulus is an image rather than laid-out text
(scaling, alignment to fixation space, AOIs over images). Ties into the
stimulus-image fallback used for unsupported scripts in **PRE-6**.

**VIZ-5 · Export the plot as separable layers** — `Status: Backlog`

Add an export mode that keeps the figure's layers **separable** in the output
file instead of one flattened image — so a *word boxes / fixations / saccades /
heatmap / labels / stimulus image* split can be toggled and restyled in
Illustrator / Inkscape for publication figures. Options to explore: vector
(SVG/PDF) with one named `<g>` group per layer (Plotly traces already map cleanly
to the per-layer helpers in [`plots.py`](scanpath_studio/plots.py) —
`_add_saccade_layer`, `_add_raw_gaze_layer`, the `_add_*_heatmap` family, and the
words/fixations cores), and/or a set of per-layer files dropped into the export
zip. Wire into `export.ExportOptions` / `render_export_options` / `bulk_export`
([`export.py`](scanpath_studio/export.py:47)) alongside the existing
PNG/SVG/PDF/HTML formats, and surface it in the **Export** subtab
(`tabs._render_export_panel`).

**VIZ-6 · Replace the "hollow" fixation marker style with an opacity control** — `Status: Done (signed off 2026-06-23)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-7 · Fixation-index range selector on the main scanpath plot** — `Status: Done (signed off 2026-06-23)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-8 · Color saccades by saccade type** — `Status: Backlog`

Encode each saccade by its reading type — *forward saccade / skip / refixation /
return sweep / regression* (the classic schematic). Saccades currently draw as one
trace in a single global colour (`global_saccade_color` + style/width,
[`controls.py`](scanpath_studio/controls.py:1188); `plots._add_saccade_layer`
[`plots.py`](scanpath_studio/plots.py:671)). The app computes per-fixation
`is_regression` and word-level `regression_in/out_flag`
([`measures.py`](scanpath_studio/measures.py:161)) but never uses them for saccade
encoding, and the forward/skip/refixation/return-sweep distinction isn't classified
yet. Plan: derive a per-saccade `saccade_type` in `enrich_fixations` from
consecutive fixations' `word_id` + line membership (`measures.cluster_word_lines`
[`measures.py`](scanpath_studio/measures.py:257)) and `is_regression`; add an
"Off / By type" mode + 5-swatch palette to the saccade popover
(`global_saccade_type_*`, seeded in `_VIZ_WIDGET_DEFAULTS`); render one sub-trace
per type in `_add_saccade_layer` with a small legend. Related: **CMP-4**, **VIZ-6**.

**VIZ-9 · "Linear reading" view — saccades as arcs, fixations above the words** — `Status: Backlog`

A stylized reading-diagram mode (cf. the schematic): draw saccades as curved
**arcs/arches** instead of straight connectors, and snap each fixation directly
**above the word** it lands on rather than at its raw gaze point. Straight
connectors come from `plots._saccade_segments` → `_add_saccade_layer`
([`plots.py`](scanpath_studio/plots.py:671)); fixations use raw x/y in the marker
trace; word-box geometry comes from `build_word_boxes` and line membership from
`measures.cluster_word_lines`. Plan: add viz-mode keys (e.g.
`global_saccade_render_mode` = straight|arc, `global_fixation_snap_to_word`) in
`_VIZ_WIDGET_DEFAULTS`, surface a Render-style selectbox + snap checkbox in the
saccade popover, thread them through `_collect_viz_settings` →
`make_scanpath_figure`, add a `_curved_saccade_segments` Bézier variant, and
reposition fixation y to each word's top-center (reuse `assign_fixations_to_words`).
Must stay on the true-scale path (`tabs._render_true_scale_chart`) and include the
mode in the figure cache key. Related: **PRE-3** (`snap_to_lines`), **VIZ-5**.

---

## Datasets & ingestion

**DATA-1 · Broaden dataset support (epic)** — `Status: In progress`

Ongoing work to load more corpora beyond the bundled sample / OneStop. Track
per-dataset adapters in [`datasets.py`](scanpath_studio/datasets.py) /
[`data.py`](scanpath_studio/data.py). Related: MultiplEYE support, EyeLink `.asc`
import (**PRE-7**), RTL/multilingual rendering (**PRE-6**), non-English validation
(**VAL-3**).

**DATA-2 · Integrate experimental-setup parameters into display/data settings** — `Status: Backlog`

Fold experimental-setup values (screen resolution, viewing distance, DPI, stimulus
font pt, etc.) into the display/data settings so true-to-scale rendering and the
px↔pt note (**VIZ-1**) can use them directly instead of being implicit.

---

## Performance

**PERF-1 · Replace Plotly with matplotlib (or lighter renderer) for speed** — `Status: In progress`

Interactivity isn't essential for the core spatial plot; a static renderer should
be much faster. Tracked in [PR #83](https://github.com/lacclab/scanpath-studio/pull/83)
(`matplotlib-migration` branch). Keep the spatial plot on the true-scale path.

**PERF-2 · Investigate (and warn about) slowdowns from keeping many fields** — `Status: Backlog`

Hypothesis: selecting many columns/measures/metadata fields slows the app.
**First verify** whether it's actually true (profile a wide vs narrow frame); if
so, add a note/warning. If not, close this item.

---

## Analysis & corpus views

**Goal:** replace the single *Corpus Analysis → Aggregated Views* subtab with a
set of analysis sections, each answering one question — *what does a text look
like? a reader? a group? two groups against each other?* All sections obey the
active trial filters and the metric picker.

**Implementation convention:** keep aggregation logic **pure** in
[`aggregation.py`](scanpath_studio/aggregation.py) (one helper per view → tidy
DataFrame), build figures in [`plots.py`](scanpath_studio/plots.py) via the
`make_*_figure` pattern, wire into [`tabs.py`](scanpath_studio/tabs.py). Add a
smoke test per figure against the bundled sample (3 pid × 2 articles).

### Per text — one `paragraph_id`/`trial_id`, many readers

**AN-1 · Stacked per-reader word profiles (small multiples)** — `Status: Planned` *(primary request)*

X = `word_id` (reading order), Y = chosen measure (TFD default; switch FFD/FPRT/
RPD/`n_fixations`). One panel per `participant_id`, stacked with shared X
(`make_subplots`, `shared_xaxes`). Optional faint cohort-mean overlay per panel.

**AN-2 · Word × reader heatmap** — `Status: Backlog`

Same data collapsed to one heatmap: rows = participants, cols = `word_id`, color =
measure. Bright columns = universally hard words; bright rows = uniformly slow
reader. Reuses word-level heatmap machinery.

**AN-3 · Cohort word profile with spread band** — `Status: Backlog`

Mean measure per word + shaded IQR/±1 SD band across readers — the "average
reader of this text" with uncertainty.

**AN-4 · Word difficulty annotated on the stimulus** — `Status: Backlog`

The text laid out (true-to-scale renderer), each word tinted by aggregate measure
or `skip_rate` / `regression_in_rate` — corpus-level scanpath, no fixations drawn.

**AN-5 · Measure vs. linguistic feature scatter** — `Status: Backlog`

Per-word mean measure vs. a bundled feature (`gpt2_surprisal`,
`wordfreq_frequency`, `word_length`, `universal_pos`) with a trend line. OneStop
sample ships these columns.

**AN-6 · Skip / regression rate per word** — `Status: Backlog`

Bar/lollipop of `skip_flag` and `regression_in_flag` rates by `word_id`.

### Per participant — one `participant_id`, many trials

**AN-7 · Measure distributions vs. cohort** — `Status: Backlog`

Histogram/violin/box of fixation `duration_ms`, `saccade_amplitude`, per-word
TFD/FFD for the selected reader, with the cohort distribution behind. Optional KDE.

**AN-8 · Reading speed & summary card** — `Status: Backlog`

WPM, mean fixation duration, fixation count, regression rate, skip rate, mean
saccade amplitude — compact stat strip + cohort percentiles.

**AN-9 · Fixation duration over time** — `Status: Backlog`

X = `timestamp_ms` (or `order_in_trial`), Y = `duration_ms` — within-trial
fatigue/settling. Faceted by trial or averaged.

**AN-10 · Saccade amplitude vs. fixation duration** — `Status: Backlog`

2D density / hexbin — the classic oculomotor scatter (careful vs. skimming).

**AN-11 · Progressive vs. regressive saccades** — `Status: Backlog`

Counts/share of `is_regression` / `regression_out_flag` per trial.

**AN-12 · Launch-site / landing-position curves** — `Status: Backlog`

Histogram of landing position within words (needs `first_fix_x` relative to word
box) — the preferred-viewing-location curve. Overlaps **PRE-4**'s
`initial_landing_position`.

**AN-13 · Per-trial trend for this reader** — `Status: Backlog`

The existing Trends line filtered to one participant — does this person slow down
across the session?

### Per group — a cohort defined by the active filter

**AN-14 · Group distribution summaries** — `Status: Backlog`

Per-participant distributions pooled across the group (violin/box of fixation
duration, saccade amplitude, TFD, reading speed).

**AN-15 · Group word profile** — `Status: Backlog`

Cohort word profile (mean + band) computed within the group, for a selected text.

**AN-16 · Per-reader summary table for the group** — `Status: Backlog`

Sortable table, one row per participant, columns = summary stats — spot outliers.

**AN-17 · Group trend** — `Status: Backlog`

Trends line averaged within the group (optionally per-participant faint behind).

### Group comparison — two groups side by side

**AN-18 · Overlaid distributions** — `Status: Backlog`

Two groups' fixation-duration / saccade-amplitude / TFD distributions on shared
axes (violin halves or overlaid KDE).

**AN-19 · Difference word profile** — `Status: Backlog`

Per-word measure A − B along the text with a zero reference line and diverging
colormap — *where* the groups diverge (Adv vs. Ele, L1 vs. L2).

**AN-20 · Paired summary bars** — `Status: Backlog`

Side-by-side group-mean bars per measure with error bars (SD / SEM / bootstrap CI).

**AN-21 · Effect size + simple test** — `Status: Backlog`

Per measure: mean difference, Cohen's *d*, Mann–Whitney / t-test p-value, with a
clear "exploratory, not pre-registered" caveat.

**AN-22 · Two-group word heatmap, stacked** — `Status: Backlog`

Group A heatmap above group B (shared word axis) for direct visual comparison.

### Cross-cutting controls for the analysis sections

**AN-23 · Shared measure picker** — `Status: Backlog`

One measure picker (TFD/FFD/FPRT/RPD/`n_fixations`/skip/regression) every section
reads from.

**AN-24 · Aggregation & spread choice** — `Status: Backlog`

Mean/median/sum aggregation and SD/IQR/SEM/bootstrap-CI spread where a band or
error bar is drawn.

**AN-25 · Normalization toggle (raw vs. z-scored within reader)** — `Status: Backlog`

So slow and fast readers compare on shape, not absolute level.

**AN-26 · Min-readers / min-trials guard** — `Status: Backlog`

Gray out / warn when a per-word cell is backed by too few observations.

**AN-27 · Download the underlying tidy table per view** — `Status: Backlog`

Reuse the export plumbing so users can re-plot elsewhere.

**AN-28 · Persist the active filter & visualization controls into Corpus Analysis** — `Status: Backlog`

The Aggregated Views subtab (`tabs.render_aggregated_views_tab`
[`tabs.py`](scanpath_studio/tabs.py:2528)) already receives
`words_filtered`/`fixations_filtered`, so the **trial filters** (participants, text,
metadata, favourites/tags via `controls.read_trial_filters`) **do** carry over
(matching the section goal above). But it does **not** receive `viz_settings`, so
its per-text heatmap (the `make_scanpath_figure` call around
[`tabs.py`](scanpath_studio/tabs.py:2647)) **hard-codes** the display options —
heatmap style/metric/colorscale, colorbar orientation/font, marker size, label &
text styling, fixation-flag highlights, stimulus image — instead of reading the
user's `global_*` choices, unlike `render_multiple_comparison_tab`, which threads
`viz_settings` through. Pass `viz_settings` from `render_corpus_analysis_tab` into
`render_aggregated_views_tab` and replace the hard-coded figure args with reads
from it; audit the trend / distribution figures for the same gap. Related:
**AN-23**, **AN-24**.

---

## Preprocessing — eyekit parity

**Epic.** Scanpath Studio is strong at *visualization* and *corpus aggregation*
but does almost no *data preprocessing* — [eyekit](https://jwcarr.github.io/eyekit/)'s
home turf. These items close the gap.

**Build order:** `PRE-0` → `PRE-1` → (`PRE-2`, `PRE-3`); `PRE-4` → `PRE-5`;
`PRE-6`, `PRE-7`, `PRE-8` independent.

```mermaid
flowchart LR
    PRE0[PRE-0 ADR] --> PRE1[PRE-1 pipeline]
    PRE0 --> PRE7[PRE-7 ASC]
    PRE1 --> PRE2[PRE-2 cleaning]
    PRE1 --> PRE3[PRE-3 drift]
    PRE0 --> PRE3
    PRE4[PRE-4 measures] --> PRE5[PRE-5 custom IAs]
    PRE6[PRE-6 RTL]
    PRE8[PRE-8 duration_mass]
```

**Milestones:** M1 foundation (`PRE-0`, `PRE-1`) · M2 flagship (`PRE-2`, `PRE-3`)
· M3 analysis (`PRE-4`, `PRE-5`) · M4 reach (`PRE-6`, `PRE-7`, `PRE-8`).

**Cross-cutting acceptance criteria** (every item): new processing is optional &
off by default · visible in the true-scale plot where applicable · reflected in
measures + export · respects `global_*`/`single_*`/`filter_*` session-state
conventions · spatial plot stays on `tabs._render_true_scale_chart` · CHANGELOG
updated.

**PRE-0 · ADR: adopt eyekit as a dependency vs. reimplement** — `Status: Decided 2026-06-23 — reimplement natively` *(blocks PRE-3, PRE-5, PRE-7)*

**Decision: do NOT adopt eyekit; port the algorithms natively.** eyekit is
**GPL-3.0** (copyleft), incompatible with this MIT project distributed on PyPI —
taking it as a runtime dependency would impose GPL on the combined work. The
canonical algorithm code (`jwcarr/drift`, the Carr et al. 2021 companion repo) is
**CC BY 4.0**, so we port with attribution; only `scipy` (BSD-3) is added (the
optimizer + k-means a few algorithms need). Reading measures (**PRE-4**) likewise
stay native. This reverses the earlier "adopt eyekit" recommendation, on the
licence finding above. Full rationale + per-item design (this doc serves as the
ADR): [`plans/pre-3-vertical-drift-correction.md`](plans/pre-3-vertical-drift-correction.md). Deliverable: `scipy` in `pyproject.toml` when PRE-3 lands. **PRE-7**
(`import_asc`) must also be reimplemented or sourced from a non-GPL parser.

**PRE-1 · Preprocessing pipeline stage (foundation)** — `Status: Backlog` *(depends PRE-0)*

Optional stage between `data.normalize_fixations` and
`measures.enrich_fixations`/`compute_per_word_measures`. Fixations gain an
`excluded` flag (soft-exclude, not hard-drop) + a derived-column convention so
corrections keep the original. New **"Preprocessing"** panel, `global_preproc_*`
keys, off by default, with a recompute trigger. Fold preproc settings into the
cache key (don't break the OneStop `frame_fingerprint`/`st.cache_data` fast path).
AC: disabled = byte-identical output to today.

**PRE-2 · Fixation cleaning: discard short / long / out-of-bounds + purge** — `Status: Partly done (visualization-only)`

**Visualization-only version shipped** (per the user's 2026-06-23 reframing): under
the ⚙ Fixation style controls, **short / long / out-of-bounds** each get
Off / **Highlight** (chosen marker + colour) / **Discard** (hide from the plot
only), with editable short/long ms thresholds (defaults 80 / 800). Threaded as a
`fixation_flags` dict through `_collect_viz_settings` → `make_scanpath_figure`
(classify on `ordered`, drop Discards before the marker trace, overlay Highlights);
saccade lines still bridge across discarded fixations. Replaces the old
out-of-text marker toggle (`global_highlight_out_of_text` removed → `fixation_flags`).
Does **not** touch reading measures or exports.

Still **Backlog** (the eyekit preprocessing version): a real `excluded` soft-flag in
the pipeline (depends PRE-1), an "N excluded" count, and `purge` (hard-drop +
reindex) that propagates to measures + export.

**PRE-3 · Vertical drift correction (`snap_to_lines`) + before/after viz** — `Status: Backlog` *(depends PRE-1, PRE-0)*

The headline gap (today only a 50px nearest-word fallback exists in
[`measures.py`](scanpath_studio/measures.py)). **This is the "support fixation
alignment algorithms" request.** Wrap eyekit `FixationSequence.snap_to_lines`
(Carr et al. 2022): `chain / cluster / merge / regress / segment / slice / split /
stretch / warp`. Adapter: word boxes → line y-centers (reuse
`measures.cluster_word_lines`); write corrected y to a derived column. Algorithm
picker + per-algorithm params in the Preprocessing panel. Before/after toggle on
the true-scale plot (ghost originals, arrows to corrected, optional color-by line).

▶ **Detailed plan:** [`plans/pre-3-vertical-drift-correction.md`](plans/pre-3-vertical-drift-correction.md) *(approved 2026-06-23; implementation deferred)*. Revises the approach above per the **PRE-0** decision (**port natively, not eyekit**): a new `alignment.py`, a comparison-grid subtab, and an in-place main-plot correction. The set is the Carr et al. (2021) **10** — `attach / chain / cluster / compare / merge / regress / segment / split / stretch / warp` — which adds `attach`/`compare` and **drops `slice`** (a post-2021 eyekit addition) versus the list above.

**PRE-4 · Reading-measure parity** — `Status: Backlog`

Extend `measures.compute_per_word_measures`: `initial_landing_position` and
`initial_landing_distance`; `number_of_regressions_in` as an integer count (app
has only the boolean flag); `second_pass_duration`; `single_fixation_duration`
(FFD when exactly one first-pass fixation). Audit that the app's
`regression_path_duration` == eyekit `go_past_duration`. Surface in per-word
export, color-by options, corpus aggregation; keep IA_* pre-aggregated precedence.

**PRE-5 · Custom interest areas + IA-level reports** — `Status: Backlog` *(depends PRE-4)*

Today AOIs == precomputed per-word boxes only. Define IAs per text by word range,
regex over word text, or eyekit-style `[bracket]{id}` markup (union of member word
boxes). Render as distinct highlighted regions in
[`plots.py`](scanpath_studio/plots.py). IA-level measures (reuse PRE-4) →
`interest_area_report`-style table for Corpus Analysis + export. Persist
definitions per `text_id` via the Save & restore JSON.

**PRE-6 · RTL & multilingual text rendering** — `Status: Backlog`

Lab is Technion (Hebrew); MultiplEYE anticipates an RTL sample. Today the
true-scale renderer assumes LTR monospace. Add a `right_to_left` flag (per
dataset/trial, auto-detect from script) that flips word/line order + label
anchoring; Arabic shaping/bidi; a CJK-capable font option. Ensure reading-order
inference, line clustering, landing-position direction (**PRE-4**), and order
numbers respect direction. Keep stimulus-image background as fallback (**VIZ-4**).

**PRE-7 · EyeLink `.asc` import** — `Status: Backlog` *(depends PRE-0)*

App requires pre-extracted fixations today. Wrap `eyekit.io.import_asc` (EFIX
fixations; optional messages/variables) → normalized fixation schema; derive
participant/trial from filename (like the MultiplEYE path). New "Dataset format"
in the upload wizard; optional raw-sample surfacing; message-based trial
segmentation. Word boxes/AOIs still come from a separate stimulus file. Feeds
**DATA-1**.

**PRE-8 · `duration_mass` probabilistic heatmap** — `Status: Backlog`

Add eyekit `measure.duration_mass` as a 4th heatmap style (alongside
word/density/interpolated): spread each fixation's duration across nearby
characters via a Gaussian (sigma in chars) instead of hard word assignment. New
style + sigma param in the existing heatmap control; render through the existing
heatmap path in [`plots.py`](scanpath_studio/plots.py). Related to **VIZ-3**.

---

## Validation

**VAL-1 · Validate against the EyeLink-rendered image** — `Status: Backlog`

Confirm the true-to-scale rendering matches what EyeLink produced for the same
trial (word boxes / fixation positions overlay correctly).

**VAL-2 · Validate OneStop text-spacing v1 (1px difference)** — `Status: Backlog`

Verify the 1-pixel text-spacing difference in OneStop spacing version 1 shows up
correctly in the layout.

**VAL-3 · Check additional datasets, especially non-English** — `Status: Backlog`

Smoke-test loading/rendering on non-English corpora. Surfaces RTL needs (**PRE-6**)
and feeds **DATA-1**.

---

## Bugs

**BUG-2 · Upload box appears twice during data upload** — `Status: Backlog`

In the Upload / Add-dataset wizard the **Fixations** uploader ("Fixations
table(s)") renders **twice** — the active box plus a second, greyed duplicate
lower down (below "Raw gaze (optional)"). Looks like the grouped upload section
(`wizard._render_data_setup` → the `upload_box` helper for raw gaze / fixations /
words, [`wizard.py`](scanpath_studio/wizard.py:1220)) gets emitted more than once
(e.g. the active main-area flow *and* the collapsed "Data & mapping" panel both
rendering it). Find the double render and emit each uploader once.

_BUG-1 (trial filter persists across datasets) signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

---

## Engineering

Lower priority than features, but tracked.

### Tests

**ENG-1 · Tests for each `aggregation.py` helper + smoke test per new figure** — `Status: Backlog`

Pure functions → feed a tiny tidy frame, assert grouped output.

**ENG-2 · Cover the OneStop per-pid shard fast-path** — `Status: Backlog`

Gated on `$ONESTOP_DATA_DIR`.

**ENG-3 · Cover MultiplEYE side-data enrichment** — `Status: Backlog`

Questions / reader meta / measures / images.

**ENG-4 · Extend `AppTest` coverage** — `Status: Backlog`

Column-mapping UI, trial filters, bulk-export zip.

### Code quality

_ENG-5 (decompose `app.py`) · ENG-7 (`watchdog`) signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

**ENG-6 · Centralize `st.session_state` keys** — `Status: Skipped`

Skipped at the user's request (2026-06-23): the app has hundreds of keys and
deep-links seed many pre-widget, so a full typed migration is high-risk for low
payoff right now.

**ENG-8 · Resolve / promote the "Generations (WIP)" tab** — `Status: Backlog`

Finish it or hide it (`model_scanpaths.py` / `similarity.py` / `synthetic.py`).

### UX / robustness

_ENG-9 (surface auto-detected columns) · ENG-10 (animation-export errors when
Chrome is missing) signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

**ENG-11 · Version saved plot-config JSON + migration path** — `Status: Backlog`

So old saved configs keep loading as the schema evolves.

### Docs

**ENG-12 · Document the true-to-scale text rendering model** — `Status: Backlog`

Data-space word size → screen px; currently only in code comments. (Relates to
VIZ-1 px↔pt and DATA-2.)

**ENG-13 · Document the new analysis sections once built** — `Status: Backlog`

Add to `docs/` after AN-* land.

---

> When any view, measure, severity, or path here lands, update `AGENTS.md`,
> `scanpath_studio/CLAUDE.md`, `CHANGELOG.md`, and the `docs/` site in the same
> change (project convention: keep docs in sync with code).
