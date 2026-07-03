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

### Signed off 2026-07-03 (moved to the archive)
**VIZ-1** (px-vs-pt note) · **VIZ-2** (larger small fonts) · **VIZ-3** (heatmap
Linear/Log) · **BUG-3** (MultiplEYE text alignment) · **DATA-3** (OneStop public +
shareable) · **DATA-9** (Data-sidebar reorg) · **ENG-11** (versioned Save & restore)
· **ENG-12** (rendering docs).

### Awaiting your approval
Implemented, not yet signed off (→ `Done` + archive on your confirmation):
**AN-1 … AN-28** (the *Analysis & corpus views* epic — *you asked to keep this
open*); **PRE-3** (vertical drift correction — *you'll revisit*); **VIZ-11**
(animation slider readout — *you'll revisit*).

### Your requested changes are now implemented (2026-07-03) — awaiting sign-off
The whole "changes requested" + "ready" batch is done, tested (749 pass, ruff
clean, docs build strict), and on every surface. **Please review + sign off** (→
`Done` + archive):
- **VIZ-4** — upload now overrides the dataset image; **Align to text** (image
  X/Y offset + scale) added; `image_path`/`image_x`/`image_y` column convention
  generalizes native images to any dataset. *(A per-trial image folder + naming
  pattern resolver is split out as **VIZ-14** below.)*
- **VIZ-5** — bulk export no longer skips every trial with "empty data" (words
  that don't join / fixations-only datasets now export).
- **VIZ-8** — class colour pickers seed correctly (not black); **Show legend**
  toggle makes the by-type key optional.
- **VIZ-9** — **Snap fixations above words** moved from Saccades to Fixations.
- **VIZ-10** — autoplay actually fires now (polls for Plotly + the real frame
  list, `_transitionData._frames`); on by default.
- **ENG-8** — Generations → **Comparisons** (data-driven), **Line assignment**
  unnested to its own subtab, redundant fixation-index slider + stimulus panel
  removed.
- **ENG-14** — full author list + affiliations applied everywhere.
- **BUG-5** — pre-parse upload-size guard (warn + opt-in above ~25 MB).
- **BUG-6** — branded theme now applies from any launch dir (CLI `--theme.*`
  injection); parity-tested against `.streamlit/config.toml`.

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
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

**UX-4 · Replace the same-text ★ marker in trial selectors with a text-like icon** — `Status: Done (signed off 2026-06-25)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**UX-5 · Keep the main Filter-by + trial selectors stable; move extra filter columns under "More"** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**UX-6 · Mark annotation state (favorites ★ / tags / notes) in the trial selector** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

_Next item: `UX-7`._

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

**VIZ-1 · Warn that font sizes are px, not pt** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-2 · Increase font size across the app where possible** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-3 · Alternative heatmap normalization** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-4 · Improve image-based stimuli support** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Implemented 2026-07-03 (awaiting sign-off).** Was requested:
> 1. **Bundled-demo image overrides the uploaded one.** For the bundled demo the
>    dataset's built-in `image_path` wins over an uploaded image; the upload should
>    take effect (fix the precedence so an explicit upload overrides the dataset
>    image).
> 2. **Use the image to reposition the text.** Text can be placed anywhere on the
>    screen; let the image serve as a manual reference to **adjust the text
>    position** (an offset/nudge for the word layer so labels line up on the image).
> 3. **Generalize native image support.** MultiplEYE stamps images natively — make
>    this general: in addition to the ad-hoc upload, let a dataset **declare an
>    image path / naming convention** (+ whatever else is needed) so any dataset
>    that ships stimulus images can use them.
> 4. **Text-area-only images (OneStop).** In OneStop the image covers only the text
>    area, not the whole screen — handle a **partial-coverage** image in the general
>    case (correct origin/extent so it aligns with the AOIs).

**Implemented (2026-07-02).** Image stimuli are no longer limited to the bundled
corpora that stamp a per-trial `image_path`. Two additions:
- **Upload a stimulus image for any dataset** — the **⚙️ Stimulus image** popover
  (next to the layer toggle) has a `file_uploader`; the image is base64-encoded to
  a `data:` URI (`controls._uploaded_image_data_uri`, cached by file id) and
  stretched to fill the whole monitor (origin `(0,0)`, size = canvas) so it lines
  up with the fixation coordinates. Session-only — an uploaded image can't ride a
  deep link (the Share panel already caveats non-rebuildable sources); precise crop
  placement is available headless via `background_image_size` / `_origin`.
- **Image opacity** (`background_image_opacity`, new arg on `make_scanpath_figure`
  + `make_scanpath_animation`; applied to the `layout.image`) — an **Image
  opacity** slider dims a busy stimulus so the AOIs / fixations / saccades read
  over it. Applies to dataset images (MultiplEYE) too.

Exposed on **every surface**: UI (`global_stimulus_image_opacity` slider +
uploader, collected by `_collect_viz_settings` as `stimulus_image_opacity` /
`stimulus_image_upload_uri`, placed by `tabs.render_single_trial_tab`); Share deep
link (`stimulus_image_opacity` in `_SHARE_FLOAT_PARAMS` + `_URL_BOUNDED`); 💾 Save
& restore (`coloring.stimulus_image_opacity`); CLI (`render --stimulus-image PATH`
`--stimulus-image-size WxH` `--stimulus-image-origin X,Y` `--stimulus-image-opacity
O`, honoured by `--animate` too); headless API (`background_image_opacity` in
`CANONICAL_FIGURE_DEFAULTS`; `background_image*` already existed). AOIs already
draw *over* the image (word boxes are `layout.shapes` above the `layer="below"`
image). Tests: `tests/test_plots.py` (`TestStimulusImageOpacity`),
`tests/test_cli.py`, plus the Share + Save/restore round-trips. Ties into the
stimulus-image fallback used for unsupported scripts in **PRE-6**.

_Original ask:_ Better handling/rendering when the stimulus is an image rather
than laid-out text (scaling, alignment to fixation space, AOIs over images).

**VIZ-5 · Export the plot as separable layers** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Fixed 2026-07-03 (awaiting sign-off).** Was: with the **Separable layers**
> toggle on, **no matter which format is selected the export produces an
> "empty data" warning and nothing is written.** Repro + fix the separable-layer
> export path (`export.bulk_export` layer branch / `layer_formats()` /
> `split_scanpath_layers`); check the format-selection gating and the
> figure-availability guard.

**Implemented (2026-07-02).** Chose the **per-layer file set** approach over
one-named-`<g>`-per-layer SVG surgery (Plotly's flat SVG doesn't cleanly map
traces/shapes/images to groups, and word boxes vs heatmap rects are
indistinguishable by geometry). New `plots.split_scanpath_layers(fig)` splits a
built figure into `{layer: figure}` — each a `copy.deepcopy` of the full figure
with only that layer's traces/shapes/images kept and a transparent background, so
**layout (axis ranges + size + equal-aspect scaleanchor) stays byte-identical and
the layers register perfectly when stacked**. Elements are tagged with their layer:
shapes carry a `_LAYER_SHAPE_TAG`-prefixed `name` at creation (`build_word_boxes`,
`build_critical_span_overlay`, `_draw_word_value_heatmap`, the plot border), traces
are classified by their stable `name` (`_trace_layer` — `words`→labels, the saccade
traces, `Raw gaze`, any `…heatmap…`; everything else is a fixation-marker variant),
and the single `layout.image` is the stimulus. Layers:
*stimulus_image / heatmap / word_boxes / saccades / fixations / raw_gaze / labels /
frame* (only the visible ones). Surfaces (an export *action*, so no
deep-link/Save-restore surface): **UI** — a **Separable layers** toggle in the bulk
Export subtab (`export.ExportOptions.separable_layers` +
`render_export_options`; `bulk_export` writes `per_trial/<slug>/layers/<layer>.<fmt>`
using the selected non-HTML formats, or SVG when none is picked); **CLI** —
`render --separable-layers` writes an `<output>_layers/` folder (static image output
only); **API** — `save_figure_layers(fig, dir, fmt="svg")` + the exposed
`split_scanpath_layers`. Tests: `tests/test_plots.py` (`TestSplitScanpathLayers` —
complete/disjoint partition, identical registration, transparent bg, correct
element→layer routing), `tests/test_export.py` (`TestSeparableLayers`),
`tests/test_api.py`, `tests/test_cli.py`. An adversarial review pass then fixed
two real defects: the per-layer render loop shared the combined-figure `try`, so a
layer failure was mis-reported as "figure export failed" and could leave the
combined figure silently un-flagged — now its own `try` reporting "layer export
failed" (combined figures survive; `tests/test_export.py::…layer_failure_reported_distinctly`);
and the bulk toggle silently fell back to SVG (needs Kaleido) when only HTML was
picked — now a UI caption warns.

_Original ask:_ keep the figure's layers **separable** in the output instead of one
flattened image, so a word-boxes / fixations / saccades / heatmap / labels /
stimulus-image split can be restyled in Illustrator / Inkscape.

**VIZ-6 · Replace the "hollow" fixation marker style with an opacity control** — `Status: Done (signed off 2026-06-23)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-7 · Fixation-index range selector on the main scanpath plot** — `Status: Done (signed off 2026-06-23)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-8 · Color saccades by saccade type** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Implemented 2026-07-03 (awaiting sign-off).** Was requested (looked good otherwise):
> 1. **Colour-picker defaults show black.** In "By type" mode the per-class colour
>    pickers render **black** even though the plot draws the correct class colours —
>    seed each picker with its actual class colour (`SACCADE_CLASS_COLORS`) so the
>    swatches match the plot.
> 2. **Make the legend optional.** The by-type legend **always** shows; it should be
>    a toggle like the other legends/colour bars.

**Implemented (2026-07-02).** A new **Saccade color** mode (`Uniform` | `By type`)
in the ⚙️ Saccade-style popover encodes each saccade by its reading class —
*forward / skip / refixation / return sweep / regression* (the classic schematic),
plus a grey `other` catch-all for off-text endpoints. New pure classifier
`measures.classify_saccades(fixations, words)` labels each *outgoing* saccade from
the departing fixation's `word_id` delta + line membership
(`measures.assign_fixation_lines`); it's computed at **render time** inside
`make_scanpath_figure` (like `color_by_line`), so it needs no pipeline
pre-enrichment and works headless. `plots._add_saccade_layer` splits into one
legended sub-trace per class (colours from `constants.SACCADE_CLASS_COLORS`,
five recolourable in the UI); arrows stay a single colour (they encode
direction). Exposed on **every surface**: UI (`global_saccade_color_mode` +
`global_saccade_class_color_*` in `_VIZ_WIDGET_DEFAULTS`, collected by
`_collect_viz_settings`); deep link / Share (`saccade_color_mode` +
`saccade_color_<class>` in `url_state._SHARE_VALUE_PARAMS`, both read & write);
💾 Save & restore JSON (writer `tabs._build_studio_config` + reader
`url_state._restore_plot_config`); CLI (`render --saccade-color-by-type` /
repeatable `--saccade-type-color CLASS=COLOR`); headless API
(`saccade_color_mode` / `saccade_class_colors` in `CANONICAL_FIGURE_DEFAULTS`).
Tests: `tests/test_measures.py` (`TestClassifySaccades`), `tests/test_plots.py`
(`TestSaccadeColorByType`), `tests/test_cli.py`, `tests/test_api.py`,
`tests/test_app.py` + `tests/test_plot_config_restore.py` (round-trips). An
adversarial review pass caught + fixed three defects before sign-off: a
pandas-3.0 `None`→`NaN` dtype coercion in `classify_saccades` (now
`dtype=object`; CI's pandas 3.0.3 would have failed while the stale local 2.3.3
passed), the Save & restore surface gap above, and the `other` class rendering
in the uniform colour instead of grey in the UI (palette now merges over the
full defaults).

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
*(Note: implemented as a render-time `saccade_class` rather than an
`enrich_fixations` column, and named distinctly to avoid clobbering the existing
source-passthrough `saccade_type` column that the trial filter reads.)*

**VIZ-9 · "Linear reading" view — saccades as arcs, fixations above the words** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Implemented 2026-07-03 (awaiting sign-off).** Was requested: move the **Snap
> fixations above words** control out of the ⚙️ Saccade-style popover and into the
> **Fixations** controls (it's a fixation setting, not a saccade one).
> `global_fixation_snap_to_word` stays the same key; just relocate the widget.

**Implemented (2026-07-02).** A **Line shape** selector (`Straight` | `Arc`) in
the ⚙️ Saccade-style popover draws saccades as upward Bézier arches
(`plots._arch_points` → `_saccade_render_mode`, apex above the chord under the
reversed y-axis, threaded through `_saccade_segments` / `_saccade_segments_by_class`
so it composes with VIZ-8 by-type colouring), and a **Snap fixations above words**
checkbox (`plots._snap_fixations_to_words`) moves each fixation to the top-centre
of its assigned word (unassigned fixations keep their raw gaze point). Both apply
on the true-scale path via a `render_fix` snapped copy used by the saccade layer
+ fixation markers (the heatmap keeps the raw gaze density). Off by default.
Exposed on **every surface**: UI (`global_saccade_render_mode` /
`global_fixation_snap_to_word` in `_VIZ_WIDGET_DEFAULTS`, collected by
`_collect_viz_settings`); Share deep link (`saccade_render_mode` +
`snap_fixations`); 💾 Save & restore; CLI (`render --saccade-arcs` /
`--snap-fixations`); headless API (`CANONICAL_FIGURE_DEFAULTS`). Tests:
`tests/test_plots.py` (`TestLinearReadingView`), `tests/test_cli.py`,
`tests/test_api.py`, plus the Share + Save/restore round-trips. An adversarial
review pass found the every-surface wiring clean but caught a real **arc-apex
clipping** bug — a wide top-line arch rose above the view and was cut off (both
fit modes); fixed by reserving exact Bézier-apex headroom at the top of the
y-range in Arc mode only (the default view is byte-identical) — plus two
mutation-surviving test gaps (the x-snap and the `rise = frac·|dx|` formula),
now pinned with mutation-verified assertions.

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

**VIZ-10 · Animate: autoplay on by default + a start/stop autoplay control** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Fixed 2026-07-03 (awaiting sign-off).** Was: **autoplay doesn't actually
> fire.** It's already on by default (`global_anim_autoplay=True`), but the replay
> doesn't start on load — pressing/toggling it does nothing, even after switching
> trials. The `Plotly.animate` kick-off (`plots.animation_autoplay_post_script`
> emitted via `to_html(post_script=…)` in `tabs._render_true_scale_chart`) isn't
> triggering in the user's environment — investigate the post-script injection /
> the `{plot_id}` substitution / whether the frames exist at kick-off time. Keep
> autoplay **on by default** once fixed.

**Implemented (2026-07-02).** The animated replay now **autoplays on load** by
default, *at the configured playback speed*. Plotly's built-in `auto_play`
ignores the configured `frame_duration` (it runs at Plotly's own default), so the
autoplay is a small client-side kick-off: `make_scanpath_animation(autoplay=True)`
stamps the autoplay intent + the resolved per-frame duration on `fig.layout.meta`,
and every HTML-embedding surface (`tabs._render_true_scale_chart` via
`to_html(post_script=…)`, `api.save_figure` via `write_html`) emits a
`Plotly.animate(gd, null, {frame:{duration, redraw:false}, fromcurrent:true})`
kick-off at that speed (`plots.animation_autoplay_post_script` /
`animation_autoplay_frame_duration`). The figure is always built paused, so
autoplay-off (and static figures) stay paused. A new **Autoplay on load** checkbox
lives in the Animate ⚙️ Playback popover (`global_anim_autoplay`, default on,
seeded in `_VIZ_WIDGET_DEFAULTS`, collected by `_collect_viz_settings` as
`anim_autoplay`). Exposed on **every surface**: UI toggle; Share deep link
(`anim_autoplay` in `_SHARE_TOGGLE_PARAMS`); 💾 Save & restore (`layers.autoplay`
writer + `_PLOT_CONFIG_LAYER_KEYS` reader); CLI (`render --animate --no-autoplay`);
headless API (`animate_scanpath(..., autoplay=…)`, honoured by `save_figure`).
Tests: `tests/test_plots.py` (`TestAnimationAutoplay`), `tests/test_api.py`,
`tests/test_cli.py`, plus the Share + Save/restore round-trips. An adversarial
review pass caught one every-surface gap: the **downloaded** animation HTML
(`tabs._render_animation_export`) used a plain `to_html`, so it wouldn't autoplay
at the configured speed like the live embed / API — now routed through the same
`animation_autoplay_post_script` kick-off.

Make the animated scanpath **autoplay on load** by default, and add a user option
to turn autoplay on/off (start/stop). Today the true-scale embed forces the
animation to start paused — `tabs._render_true_scale_chart` passes `auto_play=False`
to `fig.to_html` ([`tabs.py`](scanpath_studio/tabs.py:178)) so the figure only plays
at the configured speed when the user presses ▶ Play (`plots._animation_play_buttons`
[`plots.py`](scanpath_studio/plots.py:1827)). Note the original reason for
`auto_play=False`: Plotly's default autoplay ignores the configured playback speed
and runs at its own default frame duration — so flipping the default isn't a
one-liner; autoplay needs to honor `frame_duration`/playback speed (likely by
emitting a small client-side `Plotly.animate(...)` kickoff after mount using the
computed `avg_frame_duration`, rather than relying on `to_html(auto_play=True)`).
Plan: add an `global_anim_autoplay` viz key (default **on**) to `_VIZ_WIDGET_DEFAULTS`
+ a toggle in the Animate ⚙ popover (`controls.py` / the Animate view-mode controls
in `tabs.render_single_trial_tab`), thread it through `_collect_viz_settings` into
the animation render so the embed kicks off (or skips) playback at the right speed.
Expose on **every surface** per *AGENTS.md → Exposing a feature on every surface*:
the deep link / Share contract in `url_state.py` (`_URL_PRESETS` / `_build_share_query`),
a `--no-autoplay` (or `--autoplay`) flag on `cli.py render --animate`, and an
`autoplay` parameter on `api.animate_scanpath` + `CANONICAL_FIGURE_DEFAULTS`.
Related: **VIZ-9**, **CMP-4**.

**VIZ-11 · Animate slider: uniform time grid + "elapsed / total seconds" readout** — `Status: Pending approval`

> **Note (2026-07-03):** the user will **revisit this later** before signing off.

**Implemented (2026-07-02).** Frames now sit on a uniform time grid
(`plots._anim_timeline` → `_ANIM_GRID_STEP_MS` / `_ANIM_MAX_FRAMES`, returning
`(frame_times, frame_duration_ms, reading_span_ms)`); the slider
(`_animation_time_slider(frame_times, total_ms)`) labels each step `elapsed /
total s` and dropped the `Elapsed:` prefix. Uniform per-frame duration keeps the
GIF/MP4 export bounded. Display-only (no deep-link/CLI/API surface). Tests in
[`tests/test_plots.py`](tests/test_plots.py) (`TestScanpathAnimation` /
`TestDualScanpathAnimation` / `TestAnimationPlaybackTiming`).

Improve the animation time slider so its readout and stepping are **time-based**
rather than fixation-onset-based, and the readout shows elapsed **out of total**
seconds — e.g. **"1.2 / 30.0s"** instead of the current bare **"Elapsed: X.Xs"**.

**Why not fixation index:** the obvious "Fixation N / TOTAL" readout breaks for a
**comparison** animation (two overlaid scanpaths). In Plotly the slider's stops
*are* the frames, and frames are currently emitted at every distinct fixation
*onset across all scanpaths* (`_anim_timeline`
[`plots.py`](scanpath_studio/plots.py:1745)), so with two readers the steps are
the *union* of both onset sets — no single fixation index is meaningful, and the
slider steps bunch wherever fixations cluster instead of scrubbing linearly.

**Plan — switch the frame grid from onsets to uniform time.** Generate one frame
every fixed interval (≈100 ms) instead of one per onset; the per-frame *content*
logic already works unchanged (`searchsorted(onsets, t)` shows every fixation
whose onset ≤ t — `make_scanpath_animation` [`plots.py`](scanpath_studio/plots.py:2283)).
This makes the slider a linear time scrubber, makes the readout naturally
time-based for **any** number of scanpaths (the two-scanpath problem disappears),
and simplifies playback (uniform per-frame duration — the variable-duration
bookkeeping in `_anim_timeline` mostly goes away). In `_animation_time_slider`
([`plots.py`](scanpath_studio/plots.py:1896)) drop the `prefix="Elapsed: "` and
set each step `label` to `f"{t / 1000:.1f} / {total / 1000:.1f}s"`.
- **Bound the frame count:** an adaptive grid `step = max(100ms, span / MAX_FRAMES)`
  (cap ~300–400 frames) so a long reading gets a coarser grid instead of thousands
  of frames — otherwise the GIF/MP4 export (`animation_export.export_animation`)
  balloons. Quantization is ≤ one grid-step (a 0.13 s onset shows at the 0.2 s
  frame); negligible at 100 ms.
- **Single-scanpath bonus:** when exactly one scanpath is animated the fixation
  index *is* unambiguous, so optionally append it there only —
  `Fixation 5 / 42 · 1.2 / 30.0s` — and omit it in comparison mode.

Display-only; no deep-link/CLI/API surface needed. Related: **VIZ-10**, **CMP-4**.

**VIZ-12 · Quick views: show which preset is active (Scanpath selected by default)** — `Status: Done (signed off 2026-06-25)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-13 · Improve word-hover tooltip text + add a configurable measure (TFD by default)** — `Status: Done (signed off 2026-06-25)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**VIZ-14 · Per-trial stimulus images from a folder + naming pattern** — `Status: Backlog`

Split out of VIZ-4 (2026-07-03). The `image_path` / `image_x` / `image_y` column
convention already lets *any* dataset declare embedded/absolute per-trial images,
and an uploaded image can be aligned via VIZ-4's **Align to text** controls. What's
still missing is the case the user raised — a dataset that stores images **on disk
keyed by a column value**: a UI to point at an **image folder** + a **filename
pattern / column** (e.g. `{text_id}.png`) so per-trial images resolve without
embedding them. Local-only (folders aren't reachable on the hosted demo); generalize
`data._resolve_sample_image_paths` from the bundled `sample_data` dir to a
user-supplied root. Keep it deferred until someone needs it on a real on-disk corpus.

_Next item: `VIZ-15`._

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

**DATA-3 · Broaden OneStop public-dataset support (all regimes · all parts · public + LaCC lab)** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md). *(Public source + variant/regime/parts now shareable via `?source=onestop_public`.)*

### Data-source UI overhaul (DATA-4 … DATA-7)

Cross-cutting goal: make the **data-source picker** clear and pretty as the public
corpus list grows toward ~40, while keeping **load a local private dataset** the
primary, most prominent path. All four touch the sidebar source UI
(`app.render_sidebar_data_source` [`app.py`](scanpath_studio/app.py:995), the
`PUBLIC_DATASET_REGISTRY` + `_load_public_dataset`
[`app.py`](scanpath_studio/app.py:513), and the per-corpus loaders
`_load_potec_source` / `_load_multipleye_source` / `_load_onestop_public_source`).

**DATA-4 · Public-datasets browser that scales to ~40 corpora** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**DATA-5 · Drop the per-source participant/text filtering from the loaders** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**DATA-6 · Surface the expected file names / directory structure per corpus** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**DATA-7 · Rework the download + mapping flow (button, not a checkbox)** — `Status: Done (signed off 2026-06-26)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**DATA-8 · Show the column-mapping override for the Bundled Demo too** — `Status: Done (signed off 2026-07-02)` →
moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**DATA-9 · Reorganize the Data sidebar to be intuitive (merge source + selection, nest setup/mapping)** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

_Next item: `DATA-10`._

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

**AN-1 · Stacked per-reader word profiles (small multiples)** — `Status: Pending approval` *(primary request)*

X = `word_id` (reading order), Y = chosen measure (TFD default; switch FFD/FPRT/
RPD/`n_fixations`). One panel per `participant_id`, stacked with shared X
(`make_subplots`, `shared_xaxes`). Optional faint cohort-mean overlay per panel.

**AN-2 · Word × reader heatmap** — `Status: Pending approval`

Same data collapsed to one heatmap: rows = participants, cols = `word_id`, color =
measure. Bright columns = universally hard words; bright rows = uniformly slow
reader. Reuses word-level heatmap machinery.

**AN-3 · Cohort word profile with spread band** — `Status: Pending approval`

Mean measure per word + shaded IQR/±1 SD band across readers — the "average
reader of this text" with uncertainty.

**AN-4 · Word difficulty annotated on the stimulus** — `Status: Pending approval`

The text laid out (true-to-scale renderer), each word tinted by aggregate measure
or `skip_rate` / `regression_in_rate` — corpus-level scanpath, no fixations drawn.

**AN-5 · Measure vs. linguistic feature scatter** — `Status: Pending approval`

Per-word mean measure vs. a bundled feature (`gpt2_surprisal`,
`wordfreq_frequency`, `word_length`, `universal_pos`) with a trend line. OneStop
sample ships these columns.

**AN-6 · Skip / regression rate per word** — `Status: Pending approval`

Bar/lollipop of `skip_flag` and `regression_in_flag` rates by `word_id`.

### Per participant — one `participant_id`, many trials

**AN-7 · Measure distributions vs. cohort** — `Status: Pending approval`

Histogram/violin/box of fixation `duration_ms`, `saccade_amplitude`, per-word
TFD/FFD for the selected reader, with the cohort distribution behind. Optional KDE.

**AN-8 · Reading speed & summary card** — `Status: Pending approval`

WPM, mean fixation duration, fixation count, regression rate, skip rate, mean
saccade amplitude — compact stat strip + cohort percentiles.

**AN-9 · Fixation duration over time** — `Status: Pending approval`

X = `timestamp_ms` (or `order_in_trial`), Y = `duration_ms` — within-trial
fatigue/settling. Faceted by trial or averaged.

**AN-10 · Saccade amplitude vs. fixation duration** — `Status: Pending approval`

2D density / hexbin — the classic oculomotor scatter (careful vs. skimming).

**AN-11 · Progressive vs. regressive saccades** — `Status: Pending approval`

Counts/share of `is_regression` / `regression_out_flag` per trial.

**AN-12 · Launch-site / landing-position curves** — `Status: Pending approval`

Histogram of landing position within words (needs `first_fix_x` relative to word
box) — the preferred-viewing-location curve. Overlaps **PRE-4**'s
`initial_landing_position`.

**AN-13 · Per-trial trend for this reader** — `Status: Pending approval`

The existing Trends line filtered to one participant — does this person slow down
across the session?

### Per group — a cohort defined by the active filter

**AN-14 · Group distribution summaries** — `Status: Pending approval`

Per-participant distributions pooled across the group (violin/box of fixation
duration, saccade amplitude, TFD, reading speed).

**AN-15 · Group word profile** — `Status: Pending approval`

Cohort word profile (mean + band) computed within the group, for a selected text.

**AN-16 · Per-reader summary table for the group** — `Status: Pending approval`

Sortable table, one row per participant, columns = summary stats — spot outliers.

**AN-17 · Group trend** — `Status: Pending approval`

Trends line averaged within the group (optionally per-participant faint behind).

### Group comparison — two groups side by side

**AN-18 · Overlaid distributions** — `Status: Pending approval`

Two groups' fixation-duration / saccade-amplitude / TFD distributions on shared
axes (violin halves or overlaid KDE).

**AN-19 · Difference word profile** — `Status: Pending approval`

Per-word measure A − B along the text with a zero reference line and diverging
colormap — *where* the groups diverge (Adv vs. Ele, L1 vs. L2).

**AN-20 · Paired summary bars** — `Status: Pending approval`

Side-by-side group-mean bars per measure with error bars (SD / SEM / bootstrap CI).

**AN-21 · Effect size + simple test** — `Status: Pending approval`

Per measure: mean difference, Cohen's *d*, Mann–Whitney / t-test p-value, with a
clear "exploratory, not pre-registered" caveat.

**AN-22 · Two-group word heatmap, stacked** — `Status: Pending approval`

Group A heatmap above group B (shared word axis) for direct visual comparison.

### Cross-cutting controls for the analysis sections

**AN-23 · Shared measure picker** — `Status: Pending approval`

One measure picker (TFD/FFD/FPRT/RPD/`n_fixations`/skip/regression) every section
reads from.

**AN-24 · Aggregation & spread choice** — `Status: Pending approval`

Mean/median/sum aggregation and SD/IQR/SEM/bootstrap-CI spread where a band or
error bar is drawn.

**AN-25 · Normalization toggle (raw vs. z-scored within reader)** — `Status: Pending approval`

So slow and fast readers compare on shape, not absolute level.

**AN-26 · Min-readers / min-trials guard** — `Status: Pending approval`

Gray out / warn when a per-word cell is backed by too few observations.

**AN-27 · Download the underlying tidy table per view** — `Status: Pending approval`

Reuse the export plumbing so users can re-plot elsewhere.

**AN-28 · Persist the active filter & visualization controls into Corpus Analysis** — `Status: Pending approval`

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

**PRE-3 · Vertical drift correction (`snap_to_lines`) + before/after viz** — `Status: Pending approval` *(implemented 2026-06-28)*

> **Note (2026-07-03):** the user will **revisit this later** before signing off.

The headline gap (today only a 50px nearest-word fallback exists in
[`measures.py`](scanpath_studio/measures.py)). **This is the "support fixation
alignment algorithms" request.** Wrap eyekit `FixationSequence.snap_to_lines`
(Carr et al. 2022): `chain / cluster / merge / regress / segment / slice / split /
stretch / warp`. Adapter: word boxes → line y-centers (reuse
`measures.cluster_word_lines`); write corrected y to a derived column. Algorithm
picker + per-algorithm params in the Preprocessing panel. Before/after toggle on
the true-scale plot (ghost originals, arrows to corrected, optional color-by line).

▶ **Detailed plan:** [`plans/pre-3-vertical-drift-correction.md`](plans/pre-3-vertical-drift-correction.md) *(approved 2026-06-23; **implemented 2026-06-28**)*. Per the **PRE-0** decision (**port natively, not eyekit**): a new [`alignment.py`](scanpath_studio/alignment.py) (native CC BY 4.0 port, see [`NOTICE`](NOTICE)), a **📐 Line assignment** comparison-grid subtab, and an in-place main-plot correction (**Fixations ⚙️ → Drift correction** + optional connectors). The set is the Carr et al. (2021) **10** — `attach / chain / cluster / compare / merge / regress / segment / split / stretch / warp` — which adds `attach`/`compare` and **drops `slice`** (a post-2021 eyekit addition) versus the original list above. *Note:* not yet exposed on the CLI/headless-API surfaces (drift correction is a viz-time transform applied in `tabs.py`, not a `make_scanpath_figure` parameter); `alignment.correct` is importable for scripting.

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

**PRE-9 · Expose drift correction on the deep-link / CLI / headless API surfaces** — `Status: Backlog`

PRE-3 shipped vertical drift correction as a viz-time transform applied in
[`tabs.py`](scanpath_studio/tabs.py) (the `global_align_algorithm` /
`global_align_connectors` viz keys → `alignment.correct`), so it's live in the
UI but **not yet on the other three surfaces** (see *AGENTS.md → Exposing a
feature on every surface*): (1) **deep link / Share** — add `align_algorithm` /
`align_connectors` to `url_state._URL_PRESETS` + `_apply_url_preset` (read) and
`_build_share_query` (write) so a shared link round-trips the applied algorithm;
(2) **CLI** — a `render` flag on [`cli.py`](scanpath_studio/cli.py) (e.g.
`--drift-correct <algo>` / `--drift-connectors`); (3) **headless API** — since
correction happens outside `make_scanpath_figure`, either add an
`align`/`drift_correct` parameter to `api.plot_scanpath` that calls
`alignment.correct` before building, or document `alignment.correct` as the
scripting entry point. (4) **💾 Save & restore** — `align_algorithm` /
`align_connectors` are collected in `controls._collect_viz_settings` but written
by neither `tabs._build_studio_config` nor read by `url_state._restore_plot_config`,
so a saved plot-config JSON doesn't round-trip the drift setting either (add an
`alignment` config section + reader). Keep all surfaces in sync. Follows **PRE-3**.

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

_BUG-1, BUG-2 signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

**BUG-3 · MultiplEYE: stimulus text renders misaligned (fixations + image are fine)** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md). *(Residual sub-pixel offset = BUG-4.)*

**BUG-4 · MultiplEYE: residual small text-vs-image mismatch** — `Status: Backlog`

Follow-up to **BUG-3** (now `Pending approval`). After the BUG-3 fixes (real
`FONT_SIZE`/`FONT` threaded through, line-pitch-based `scale_text_to_boxes`,
script-aware width cap) the MultiplEYE true-to-scale word text lines up *much*
better, but a **small** residual offset between the rendered text layer and the
stimulus image remains — the labels are close but not pixel-exact on top of the
image words. Likely the leftover slack noted in BUG-3's root cause (2): the
nominal-vs-inked glyph size + anchor difference between how PIL drew the image
glyphs (top-left in a glyph-tight cell) and how Plotly centers/rasterizes the
label in the box, and/or remaining font-metric differences between the CJK
fallback font and the exact stimulus font. Quantify the residual (by how much,
and whether it's a constant shift vs. per-line/per-word drift) before fixing.
Code anchors: `_word_label_font_px` / `scale_text_to_boxes` / `_line_pitch`
([`plots.py`](scanpath_studio/plots.py:339)), MultiplEYE font stamping
(`datasets._multipleye_font_config` / `_multipleye_font_css`), and the font snap
in `app.render_sidebar_canvas_controls`. Related: **BUG-3**, **VIZ-4**, **PRE-6**.

**BUG-5 · Upload crashes on Streamlit Community Cloud (works locally)** — `Status: Pending approval (changes addressed 2026-07-03)`

> **User input (2026-07-03):** the **Cloud log shows nothing** (no Python
> traceback) and the crash was on **OneStop repeated reading**. Empty log + a large
> upload ⇒ almost certainly a **memory (OOM) kill** — Streamlit Cloud kills the
> process on RAM exhaustion without a traceback. **Chosen fix: (a)** add a
> pre-upload **size/row guard** + a clear "too large for the hosted app — run
> locally" warning (wizard flow in [`wizard.py`](scanpath_studio/wizard.py) /
> `app.render_sidebar_data_source`). Repro data supplied at
> `data/OneStop/public/repeated` — **size it first** to set the guard threshold.

Uploading a dataset through the Upload / Add-dataset wizard works on a local
`streamlit run` but **crashes on the deployed Streamlit Community Cloud app**.
Repro + capture the actual traceback from the Cloud logs first — the local-vs-deployed
split points at an environment difference rather than wizard logic: likely the
Cloud upload-size limit (`server.maxUploadSize`), a memory cap on large
CSV/Parquet, a missing/locked writable temp dir, or a dependency/version skew
between local and the Cloud image. Code anchors: the wizard flow in
[`wizard.py`](scanpath_studio/wizard.py) and the upload source handling in
`app.render_sidebar_data_source` ([`app.py`](scanpath_studio/app.py)); deployment
config in `streamlit_app.py` / any `.streamlit/config.toml`. Confirm whether it's
size-, memory-, or import-related before fixing.

**BUG-6 · Accent color differs: blue locally vs. red on the deployed app** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Fixed 2026-07-03 (awaiting sign-off).** Was (reopened): the deployed Cloud app is now blue, but running
> **`python -m scanpath_studio` from the repo root** (`/Users/shubi/Projects/scanpath_studio`)
> still shows **red**. Root cause: the pinned theme lives in
> **`app/.streamlit/config.toml`**, and Streamlit only reads `.streamlit/config.toml`
> relative to the **launch CWD** — so launching from the parent of `app/` (or any
> other dir) misses it and falls back to the default red. Fix so the theme applies
> regardless of CWD: either move/duplicate the config to the repo root, or set the
> theme via `st.set_page_config(theme=…)` / injected CSS in `app.py` so it's not
> CWD-dependent. (The `tour.py` red-fallback fix already landed.)

**Resolved (2026-07-03) — superseded by the reopen above.** The repo pins an
explicit theme in
[`.streamlit/config.toml`](.streamlit/config.toml) (`[theme] primaryColor =
#1f77b4` light / `#5aa9e6` dark), so both environments now match — the user
confirmed the **deployed Cloud app renders blue**. The one leftover inconsistency
was fixed: `tour.py`'s spotlight accent fell back to Streamlit's default red
(`#ff4b4b`) when the runtime didn't expose `theme.primaryColor`; it now falls back
to the brand blue `#1f77b4` so the tour matches the pinned theme in every
environment.

_Original diagnosis below (kept for context):_


The app's accent/primary color renders **blue when run locally** (`streamlit
run`) but **red on the deployed Streamlit Community Cloud version** (e.g. the
selected data-source radio and the filter chips show red online). The theme
should be consistent across environments. Likely cause: a theme `primaryColor`
mismatch between a local `~/.streamlit/config.toml` (or a personal theme) and
what the deployed app actually uses — the repo may not pin a theme, so local
picks up a user/default theme while Cloud falls back to its own default. Fix by
pinning an explicit theme in the repo (`.streamlit/config.toml` `[theme]
primaryColor = …`, or via `st.set_page_config` / injected CSS) so both
environments match; decide the intended accent. Code anchors: any
`.streamlit/config.toml`, `streamlit_app.py`, page config in
[`app.py`](scanpath_studio/app.py), and injected CSS in
[`styles.py`](scanpath_studio/styles.py). Related: **BUG-5** (also
local-vs-deployed).

_Next item: `BUG-7`._

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

**ENG-8 · Resolve / promote the "Generations (WIP)" tab** — `Status: Pending approval (changes addressed 2026-07-03)`

> **✅ Implemented 2026-07-03 (awaiting sign-off).** Was requested (first cut reviewed):
> 1. **Rename "Generations".** It needn't be model generations — it's any set of
>    scanpaths of the same text (e.g. repeated readings), so give it a more general
>    name. **"Comparisons"** is a good name for the tab itself.
> 2. **Unnest Line assignment.** Move **Line assignment** back out to its own
>    top-level subtab — so **Comparisons has no subtabs** (it's just the renamed
>    Generations view); Line assignment sits beside it in the subtab bar.
> 3. **Drop the Fixation-index range slider** from the Comparisons view — it's
>    redundant with the fixation-index control already in the main rail's Fixations
>    section.
> 4. **Drop the "Stimulus & questions" panel** shown inside Generations — there's
>    already a dedicated **Stimulus & questions** subtab.

**Implemented (2026-07-03).** Finished + relocated, per the user's spec:
- **New "🔬 Comparisons" subtab** in the Scanpath view (where "📐 Line assignment"
  was), holding two nested subtabs — **Generations** and **📐 Line assignment**.
  Both use the **main scanpath selection**; neither renders its own trial picker.
  Generations is **removed from Corpus Analysis** (now Per text · Per reader ·
  Groups); `render_corpus_analysis_tab` lost its `combos` param.
- **Generations is now data-driven, not synthetic.** Dropped the trial picker (uses
  the main selection) and the **🎲 Regenerate** button. Added a **Generation
  column** selectbox: the distinct values of that column — over the **same text**
  as the selected trial — are the generations, scored against the selected reading.
  New pure helpers `_generation_column_options` (ranks model/condition-like names,
  then reader/trial ids; excludes coordinates + per-fixation ids; skips
  unhashable/JSON columns) + `_collect_generations` (scopes to the trial's text via
  the canonical `text_id`/`unique_text_id`/`paragraph_id` priority, excludes the
  selected trial, groups by the column, caps the grid at 24 with a "showing N of M"
  caption). The existing similarity machinery (`compute_similarity_table` /
  `nld_by_*` / convergence plots) is reused unchanged; the table's column reads
  **Generation**.
- **Dead code removed:** the synthetic `_cached_model_scanpaths` + its
  `model_scanpaths` import (the `model_scanpaths.py` module is now unused by the
  app — its tests still pass; candidate for a later delete). `_SELECTION_PREFIXES`
  dropped `"multi"` (no second picker).

Tests: `tests/test_multiple_comparison_ui.py` (`_generation_column_options` /
`_collect_generations` — text scoping incl. real `text_id` + `paragraph_id`
fallback, exclusions, unhashable guard); `tests/test_apptest.py` (Generations
renders real generations from the bundled demo). An adversarial review pass caught
a real **HIGH**: the first cut scoped on `paragraph_id`, which normalized OneStop
fixations don't carry (they use `text_id`), so generations mixed across texts —
now fixed to the canonical text-column priority; plus three LOW robustness fixes
(within-trial ids excluded, `nunique()` TypeError on list columns guarded, grid
iframe keys made collision-proof).

_Original ask:_ finish it or hide it (`model_scanpaths.py` / `similarity.py`).

### UX / robustness

_ENG-9 (surface auto-detected columns) · ENG-10 (animation-export errors when
Chrome is missing) signed off & archived — see
[`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md)._

**ENG-11 · Version saved plot-config JSON + migration path** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**ENG-12 · Document the true-to-scale text rendering model** — `Status: Done (signed off 2026-07-03)` → moved to [`IMPROVEMENTS_ARCHIVE.md`](IMPROVEMENTS_ARCHIVE.md).

**ENG-13 · Document the new analysis sections once built** — `Status: Backlog`

Add to `docs/` after AN-* land.

**ENG-14 · Replace the provisional/TBD author list with the real co-authors** — `Status: Pending approval (changes addressed 2026-07-03)`

> **Confirmed by the user (2026-07-03):** the list + **order** below is correct,
> **all authors appear in every place** (CITATION / README / constants / app), and
> the affiliations are:
> - **DiLi Lab is at UZH (University of Zurich).**
> - **David Reiche also has a University of Potsdam affiliation** (two affiliations).
>
> **Final author order** (apply everywhere, in sync):
> 1. **Omer Shubi** — LACC Lab, Technion
> 2. **Keren Gruteke Klein** — LACC Lab, Technion
> 3. **Ella Lion** — LACC Lab, Technion
> 4. **Deborah Jacobi** — DiLi Lab, University of Zurich (UZH)
> 5. **David Reiche** — DiLi Lab, University of Zurich (UZH); University of Potsdam
> 6. **Lena Jäger** — DiLi Lab, University of Zurich (UZH)
> 7. **Yevgeni Berzak** — (as currently in `CITATION.cff`)
>
> *(Still to double-check while editing: Berzak's affiliation string, and that the
> in-prep paper's author list matches this set + order.)*

The author/citation metadata is still provisional. Add the confirmed co-authors
in place of the `TBD` / "and others" placeholders:
- **Ella Lion** — LACC Lab, Technion (our lab).
- **Deborah Jacobi**, **David Reiche**, **Lena Jäger** — DiLi Lab (Lena Jäger's
  Digital Linguistics group).

Update every surface that carries the author list (keep them in sync):
- [`CITATION.cff`](CITATION.cff:10) — the `authors:` block (currently Shubi /
  Gruteke Klein / Berzak with a "provisional" note at line 20); add the new
  `given-names` / `family-names` / `affiliation` entries and drop the note once
  final.
- [`README.md`](README.md:19) — "Omer Shubi, Keren Gruteke Klein, and others
  (TBD) — LACC Lab, Technion."
- [`scanpath_studio/constants.py`](scanpath_studio/constants.py:106) —
  `CITATION["authors"]` (`"Omer Shubi, LACC Lab (Technion)"`), surfaced in-app.
- [`scanpath_studio/app.py`](scanpath_studio/app.py:263) — the "… and TBD at the
  LaCC Lab" About text.

**The paper and app author lists must match** — keep the in-prep paper's authors
(the "citation TBD" note at [`README.md`](README.md:145)) and the software author
list above as the same set, in the same order.

Confirm exact name spelling/diacritics (Jäger), affiliation wording, and author
order with the user before editing.

---

> When any view, measure, severity, or path here lands, update `AGENTS.md`,
> `scanpath_studio/CLAUDE.md`, `CHANGELOG.md`, and the `docs/` site in the same
> change (project convention: keep docs in sync with code).
