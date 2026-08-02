# Agent guide (headless use)

This page is written for a coding agent — or any script — that has to **use**
Scanpath Studio without a browser: load an eye-tracking-while-reading dataset,
render a figure, pull per-word reading measures. (`AGENTS.md` in the repository
root is the opposite document: how to *develop* this codebase.)

Everything the app draws is reachable from two places:

| Surface | Entry point | Reference |
|---------|-------------|-----------|
| Python | `scanpath_studio.api`, re-exported at the package root | [Python API](api.md) |
| Shell | `scanpath-studio render` | [CLI reference](cli.md) |

Both go through the same `data → measures → plots` pipeline as the Streamlit
app, so a figure rendered here is the figure the app shows.

## The 30-second version

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()          # bundled OneStop demo
pid, tid = sps.list_trials(words, fixations).iloc[0]
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
sps.save_figure(fig, "scanpath.html")              # .png/.svg/.pdf need Chrome
```

`canvas_size` is the monitor the stimulus was shown on. Pass it whenever you
know it — without it the canvas is *estimated* from the data extents and the
scanpath no longer sits at its true on-screen position.

## Two tables in, one figure out

Scanpath Studio works on a pair of tables — **word interest areas** (one row per
word per trial, with its bounding box) and **fixations** (one row per fixation).
`load_scanpath_data` maps whatever your columns are called onto these canonical
names; everything downstream assumes them.

**Words / IA** — after `load_scanpath_data`:

| Column | Meaning |
|--------|---------|
| `participant_id` | Reader id (string). Optional in the source: a stimulus-level word table with no reader column is broadcast across the readers found in the fixations. |
| `trial_id` | One reading of one text by one reader. **Required.** (`unique_trial_id` rides along when the source ships one.) |
| `text_id` | Which text/passage the row belongs to (plus `unique_text_id` when the source has a corpus-wide id). |
| `word_id` | Word index within the trial. **Required** — it is the join key to fixations. |
| `text` | The word itself (what gets drawn in the boxes). |
| `x`, `y`, `width`, `height` | Word bounding box in screen px, origin top-left. **Required** (or supply `left`/`right`/`top`/`bottom`, which are converted). |
| `line_idx` | Source line number, when the export has one. Often constant — the plots derive visual lines from box `y` instead. |

Pre-aggregated EyeLink IA measures (`IA_FIRST_FIXATION_DURATION` → `first_fixation_ms`, …)
and linguistic features (`gpt2_surprisal`, `wordfreq_frequency`, `universal_pos`, …)
are carried through under their canonical / original names when present.

**Fixations** — after `load_scanpath_data`:

| Column | Meaning |
|--------|---------|
| `participant_id` | Reader id. Optional in the source (a dataset without one becomes a single anonymous reader). |
| `trial_id` | Must match the words table. **Required.** |
| `text_id` | Text/passage id, when present. |
| `x`, `y` | Fixation location in screen px. **Required unless** `word_id` is given — AOI-sequence data is placed at word-box centers. |
| `duration_ms` | Fixation duration. **Required.** |
| `timestamp_ms` | Fixation onset. Falls back to the row's position within the trial (0, 1, 2, …) when the source has no timestamp — it drives the ordering, so rows must already be in reading order in that case. |
| `word_id` | Source word/AOI assignment, carried through when the export has one — otherwise `NaN`. Nothing recomputes it at load time; the assignment (box containment, then nearest word center within 50 px) happens inside `compute_word_metrics` and the plots that need it. |
| `order_in_trial` | 1-based fixation index, added during normalization. |
| `fixation_id` | Always present — mapped from the source when it has one, otherwise synthesized as a per-trial running index (1, 2, 3, …). |
| `saccade_type`, `saccade_amplitude`, `eye`, `pass_index` | Passed through when the source has them. |

Column matching is case- and separator-insensitive: `IA_LEFT`, `ia_left` and
`Ia Left` are the same name. See [Data format](data-format.md) for the full
candidate lists per convention (EyeLink, Gazepoint, MultiplEYE, snake_case).

## The minimum a figure needs

Boxes, ids, durations. Nothing else — no participant column, no timestamps, no
measures:

```python
import pandas as pd
import scanpath_studio as sps

words = pd.DataFrame(
    {
        "trial_id": ["t1"] * 4,
        "word_id": [1, 2, 3, 4],
        "text": ["The", "cat", "sat", "down"],
        "x": [100, 200, 300, 400],
        "y": [100, 100, 100, 100],
        "width": [80, 80, 80, 90],
        "height": [40, 40, 40, 40],
    }
)
fixations = pd.DataFrame(
    {
        "trial_id": ["t1"] * 3,
        "x": [130.0, 320.0, 240.0],
        "y": [118.0, 122.0, 115.0],
        "duration_ms": [210, 180, 260],
    }
)

words, fixations = sps.load_scanpath_data(words, fixations)
fig = sps.plot_scanpath(words, fixations, canvas_size=(800, 300))
sps.save_figure(fig, "minimal.html")
```

With one trial in the frames, `participant` / `trial` can be omitted — more than
one and an underspecified call raises rather than guessing (see
[Errors](#errors-and-what-they-mean)). Neither table had a participant column
here, so both frames come back under one synthetic reader: `list_trials` returns
`participant_id="(all)"`, `trial_id="t1"`.

## Loading real data

```python
words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
words, fixations = sps.load_scanpath_data("ia/*.csv", "fix/*.tsv")     # globs
words, fixations = sps.load_scanpath_data(words=ia_df, fixations=fix_df)
words, fixations = sps.load_scanpath_data(fixations="fix.parquet")     # one table
```

- Accepts DataFrames, paths, glob patterns, or lists of paths
  (`.csv` / `.tsv` / `.parquet` / `.feather`). Multi-file datasets are
  concatenated and each row keeps its file stem in `source_file` — useful when
  the participant or text id only exists in the filename.
- Either table may be omitted. The missing side comes back as an empty canonical
  frame and the corresponding layer is simply not drawn.
- Ready-made public corpora have their own loaders:
  `sps.load_potec(dir)`, `sps.load_onestop(dir)`, `sps.load_multipleye(dir)` —
  they return the same normalized pair. See [OneStop](onestop.md) and
  [MultiplEYE](multipleye.md).

### When auto-detection can't find a column

The `ValueError` names the canonical field, the column names that were tried,
and the columns your table actually has. In full, for a words table whose
columns are `subject, para, word, start_x`:

```text
Words/IA schema problems: missing Trial ID; missing Word/IA ID; need either (x, y, width, height) or (left, right, top, bottom)
Could not infer these canonical fields from the words/IA table:
  - Trial ID (word_schema key 'trial'): no column matched. Looked for: unique_trial_id, trial_id, unique_paragraph_id, paragraph_id, text_id, trial, trial_index
  - Word/IA ID (word_schema key 'word_id'): no column matched. Looked for: word_id, IA_ID, ia_index, word_index, aoi, word_idx, char_idx
  - Word box (word_schema keys): need either (x, y, width, height) or (left, right, top, bottom) — (x, y, width, height) is missing x, y, width, height; (left, right, top, bottom) is missing right, top, bottom.
      Looked for → x: x, left, top_left_x | y: y, top, top_left_y | width: width | height: height | right: IA_RIGHT, right, end_x | top: IA_TOP, top, start_y, top_left_y | bottom: IA_BOTTOM, bottom, end_y
Fields that did resolve: text='word', left='start_x'
Columns present in the words/IA table (4): subject, para, word, start_x
Matching ignores case and separators (IA_LEFT == ia_left == 'Ia Left') and takes the first candidate that matches.
To override auto-detection pass the full mapping, e.g. word_schema={'trial': '<column>', 'word_id': '<column>', 'left': 'start_x', 'right': '<column>', 'top': '<column>', 'bottom': '<column>'} — api.propose_schema(df, 'words') returns what was detected.
```

Repair it by starting from what *was* detected and filling the gaps — an
explicit schema replaces auto-detection wholesale, so it has to be complete:

```python
from scanpath_studio import api

schema = api.propose_schema("ia.csv", "words")   # {field: column or None}
schema["trial"] = "para"
schema["word_id"] = "aoi_number"
words, fixations = sps.load_scanpath_data("ia.csv", "fix.csv", word_schema=schema)
```

`propose_schema(table, kind)` takes `kind="words"`, `"fixations"` or
`"raw_gaze"`.

## Choosing a trial

```python
combos = sps.list_trials(words, fixations)     # DataFrame[participant_id, trial_id]
```

`plot_scanpath` / `animate_scanpath` take `participant` and `trial` positionally
after the frames. Both are optional **only** when the frames hold exactly one
combo; an ambiguous selection raises instead of silently picking one. Filter the
frames yourself for anything else — they are plain DataFrames:

```python
one_reader = combos[combos["participant_id"] == "l37_1129"]
```

## Rendering

```python
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
anim = sps.animate_scanpath(words, fixations, pid, tid, playback_speed=4.0)

sps.save_figure(fig, "out.html")     # interactive, no browser needed
sps.save_figure(fig, "out.png")      # .png/.svg/.pdf via Kaleido → needs Chrome
sps.save_figure_layers(fig, "layers/", fmt="svg")   # one file per layer
```

- **HTML never needs Chrome.** PNG/SVG/PDF go through Kaleido, which drives a
  Chrome/Chromium binary: run `plotly_get_chrome -y` once, or fall back to HTML.
  Details in [Export & troubleshooting](export-troubleshooting.md).
- `save_figure_layers` writes one registered file per visible layer (word boxes /
  fixations / saccades / heatmap / labels / stimulus image / frame) at identical
  size and axis ranges — for assembling a figure in Illustrator / Inkscape.
- A saved animation autoplays at `playback_speed`; pass `autoplay=False` for one
  that opens paused. GIF/MP4 need
  `scanpath_studio.animation_export.export_animation` (Kaleido + Chrome).

Two per-trial transforms are keywords rather than figure options, because they
change *which fixations are drawn* rather than how:

```python
fig = sps.plot_scanpath(
    words, fixations, pid, tid,
    fix_index_range=(1, 40),     # only fixations 1–40 (1-based, both inclusive)
    drift_correction="warp",     # any of alignment.ALGORITHMS
    drift_connectors=True,       # faint original → corrected line per fixation
)
```

- `fix_index_range` is the app's fixation-index window; `animate_scanpath`
  accepts it too, and replays only that stretch. A window that lands outside the
  trial raises rather than drawing an empty scanpath.
- `drift_correction` snaps each fixation to its assigned text line and colours by
  line, exactly like the app's *Drift correction* control. Windowing is applied
  first, then the correction — the app's order.

## Every figure option

`plot_scanpath` forwards any extra keyword to the figure builder; an unknown one
raises a `TypeError` naming the closest valid options. The authoritative list is
`api.figure_options()` (`"animation"` for the replay's subset):

```python
from scanpath_studio import api

api.figure_options()                    # {option: default} for plot_scanpath
api.figure_options("animation")         # …for animate_scanpath
```

The defaults below are what a bare `plot_scanpath(words, fixations, pid, tid)`
renders. **Anim** marks the options `animate_scanpath` also accepts (the
animation has no heatmap and no arced/typed saccades; it adds `words_b`,
`fixations_b`, `label_a`, `label_b`, `show_legend` for a two-scanpath overlay,
plus replay-only knobs — `figure_options("animation")` is the full list).

### Layers

| Option | Default | Anim |
|--------|---------|------|
| `show_words` | `True` | yes |
| `show_word_labels` | `True` | yes |
| `show_fixations` | `True` | no |
| `show_order` | `True` | yes |
| `show_saccades` | `True` | yes |
| `show_heatmap` | `True` | no |
| `show_raw_gaze` | `False` | no |
| `show_connectors` | `False` | no |
| `connector_y` | `None` | no |

### Fixations

| Option | Default | Anim |
|--------|---------|------|
| `color_by` | `'(uniform)'` | yes |
| `color_by_line` | `False` | yes |
| `fixation_color` | `'#1f77b4'` | yes |
| `fixation_colorscale` | `'Blues'` | yes |
| `fixation_color_range` | `None` | yes |
| `fixation_symbol` | `'circle'` | yes |
| `fixation_opacity` | `0.7` | yes |
| `hollow_fixations` | `False` | yes |
| `marker_size_range` | `(8, 24)` | yes |
| `fixation_snap_to_word` | `False` | no |
| `fixation_flags` | `None` | yes |
| `order_font_size` | `10` | yes |
| `order_font_color` | `'#111111'` | yes |

`color_by` is a *fixation column name* (`"duration_ms"`, `"pass_index"`, …) or
the sentinel `"(uniform)"` for one flat colour; a name the frame doesn't have
falls back to uniform. Colouring by text line is the separate `color_by_line=True`
flag (the lines are inferred from word-box geometry), which overrides `color_by`.
Marker size already encodes duration, which is why hue is unmapped by default.

`fixation_flags` marks or drops suspicious fixations (display only — reading
measures and exports are untouched). One entry per category, each with a mode of
`"Off"` / `"Highlight"` / `"Discard"`:

```python
flags = {
    "short": {"mode": "Highlight", "threshold_ms": 80.0,
              "symbol": "triangle-up-open", "color": "#ff7f0e"},
    "long": {"mode": "Off", "threshold_ms": 800.0,
             "symbol": "square-open", "color": "#9467bd"},
    "oob": {"mode": "Discard", "symbol": "x", "color": "#d62728"},  # out of text
}
fig = sps.plot_scanpath(words, fixations, pid, tid, fixation_flags=flags)
```

`show_connectors` / `connector_y` are the raw form of the drift connectors; use
`drift_correction=` + `drift_connectors=True` instead unless you are snapping the
fixations yourself.

### Saccades

| Option | Default | Anim |
|--------|---------|------|
| `saccade_color` | `'#6f42c1'` | yes |
| `saccade_style` | `'solid'` | yes |
| `saccade_width` | `2.0` | yes |
| `saccade_color_mode` | `'Uniform'` | no |
| `saccade_class_colors` | `None` | no |
| `saccade_type_legend` | `True` | no |
| `saccade_render_mode` | `'Straight'` | no |
| `show_saccade_arrows` | `False` | yes |

`saccade_color_mode` is `"Uniform"`, `"Forward / regression"` (the two-way fold)
or `"By type"` (forward / skip / refixation / return sweep / regression, each a
legended sub-trace, classified at render time);
`saccade_class_colors={"regression": "#000", …}` overrides individual class
colours. `saccade_render_mode="Arc"` draws the linear-reading schematic.

### Heatmap

| Option | Default | Anim |
|--------|---------|------|
| `heatmap_style` | `'Word boxes'` | no |
| `heatmap_metric` | `'duration_ms'` | no |
| `heatmap_norm` | `'Linear'` | no |
| `heatmap_colorscale` | `'Blues'` | no |
| `heatmap_range` | `None` | no |
| `word_heatmap_col` | `None` | no |
| `word_heatmap_title` | `None` | no |

`heatmap_style` is `"Word boxes"`, `"Interpolated"` or `"Density"`;
`heatmap_metric="counts"` weights by fixation count instead of dwell time;
`heatmap_norm="Log"` compresses heavy-tailed dwell times.

### Text & words

| Option | Default | Anim |
|--------|---------|------|
| `text_color` | `'#343a40'` | yes |
| `highlight_column` | `'is_in_aspan'` | yes |
| `highlight_text_color` | `'#C8097C'` | yes |
| `critical_span_style` | `'Mark text'` | no |
| `span_border_color` | `'#000000'` | no |
| `line_spacing` | `3.0` | yes |
| `scale_text_to_boxes` | `True` | yes |
| `word_hover_measure` | `'total_fixation_duration_ms'` | yes |

`highlight_column` is a boolean words column (OneStop's critical span by
default); it is ignored when the column isn't there.

### Canvas & background

| Option | Default | Anim |
|--------|---------|------|
| `background_color` | `'#ffffff'` | yes |
| `fit_to_monitor` | `True` | yes |
| `x_field` | `'x'` | no |
| `y_field` | `'y'` | no |
| `background_image` | `None` | yes |
| `background_image_size` | `None` | yes |
| `background_image_origin` | `None` | yes |
| `background_image_opacity` | `1.0` | yes |

`fit_to_monitor=True` frames the whole `canvas_size`; `False` crops to the data.
`background_image` places a stimulus screenshot under the scanpath at data
coordinates — see [Rendering](rendering.md).

### Colorbars

| Option | Default | Anim |
|--------|---------|------|
| `show_colorbars` | `False` | yes |
| `colorbar_orientation` | `'Vertical'` | yes |
| `colorbar_tickangle` | `0` | yes |
| `colorbar_tickfont_size` | `12` | yes |

`palette=` is a shorthand that sets a whole group of the colours above at once —
`"Default"`, `"Colourblind-safe"`, `"Print / greyscale"` or `"High contrast"`
(`constants.PALETTES`). Anything you pass explicitly still wins over it, and an
unknown name raises rather than silently falling back.

!!! note "Headless defaults vs. the app's first screen"
    `CANONICAL_FIGURE_DEFAULTS` turns **every layer on** — word boxes, heatmap
    and fixation indices included — while the app opens on the core scanpath
    only, so a new user sees a legible picture. That is the only intended
    difference: every other default (marker opacity, index-label size, monitor
    framing, colours) is the app's.

## Reading measures

```python
metrics = sps.compute_word_metrics(words, fixations)
```

One row per `(participant_id, trial_id, word_id)` with `first_fixation_ms`
(FFD), `first_pass_gaze_duration_ms` (FPRT), `regression_path_duration_ms`
(RPD / go-past), `total_fixation_duration_ms` (TFD), `n_fixations`, `skip_flag`,
`regression_in_flag`, `regression_out_flag`. Pre-aggregated columns already in
the words table (EyeLink IA exports) win; the rest are computed from the
fixations and word boxes.

## The same thing from the shell

```bash
scanpath-studio render --sample --list-trials
scanpath-studio render --sample -o scanpath.html
scanpath-studio render --words 'ia/*.csv' --fixations 'fix/*.csv' \
    -p l37_1129 -t l37_1129_2_1_1_Ele_r0 --canvas 2560x1440 -o figure.png
scanpath-studio render --sample --animate --playback-speed 4 -o replay.html
```

Flags carry the API's option names: layers are `--no-words` / `--no-labels` /
`--no-fixations` / `--no-order` / `--no-saccades` / `--no-heatmap`, plus
`--color-by`, `--heatmap-metric`, `--heatmap-norm`, `--palette`, `--canvas WxH`,
`--separable-layers`. Drift correction is on the CLI too:
`--drift-correction ALGORITHM` (any of the ten names) and
`--drift-connectors`. So are the public corpora — `--potec DIR`,
`--onestop DIR` (+ `--onestop-regime` / `--onestop-part` /
`--onestop-variant`), `--source multipleye --export DIR` — plus styling and
output controls (`--fixation-symbol`, `--saccade-arcs`, `--snap-fixations`,
`--saccade-color-by-type` / `-by-direction`, the `--stimulus-image*` family,
`--width` / `--height` / `--scale`, `--anim-grid-step-ms` /
`--anim-max-frames`, `--no-autoplay`). Without `-p` / `-t` it renders the
first available trial instead of raising. Most `plot_scanpath` keywords have
a flag; check `scanpath-studio render --help` (or the
[CLI reference](cli.md)) before assuming one doesn't.

## Errors and what they mean

| Message starts with | Cause | Fix |
|---------------------|-------|-----|
| `Words/IA schema problems:` / `Fixations schema problems:` | A canonical field could not be inferred (or is missing from the schema you passed). | Read the bullets — they name the field, its schema key and the candidates tried. Pass `word_schema=` / `fix_schema=` built from `api.propose_schema`. |
| `Words/IA schema maps N column names the … table doesn't have` | A schema you passed names a column that isn't in the table. | The message lists each bad key and the closest real column names. |
| `fix_index_range=(a, b) selects no fixations` | The window is outside the trial. | The message gives the trial's fixation count and index range. |
| `words must be the normalized pandas DataFrame` | A path/string was passed where a frame belongs. | Run it through `load_scanpath_data` first. |
| `words frame is not normalized:` | A raw table (or a renamed frame) reached a plotting function. | Same — the frames the loader returns are the only accepted input. |
| `Ambiguous selection: N trials match` | `participant` / `trial` left out with several combos loaded. | Pass both; `list_trials` shows what exists. |
| `No trial matches participant=…` | Unknown id. | The message lists available ids and the closest spellings. |
| `plot_scanpath() got an unexpected keyword argument` | Misspelled or unsupported option. | The message suggests the nearest names; `api.figure_options()` is the full list. |
| `Options not supported by the animation:` | A static-only option (heatmap, arcs, saccade types) passed to `animate_scanpath`. | Drop it, or render the static figure. |
| `Static .png export failed:` | Kaleido has no Chrome. | `plotly_get_chrome -y`, or save `.html`. |
| `Fixations … have no usable coordinates` | AOI-sequence fixations with no matching word boxes. | Supply the words table whose `word_id`s match. |

## Recipes

**Render every trial of a corpus**

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
for pid, tid in sps.list_trials(words, fixations).itertuples(index=False):
    fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
    sps.save_figure(fig, f"{pid}__{tid}.html")
```

For a zip of figures **and** tables across many trials, use the bulk exporter
(`scanpath_studio.export.bulk_export` with an `ExportOptions`) instead of
looping by hand.

**A print-ready, layer-separated figure**

```python
fig = sps.plot_scanpath(
    words, fixations, pid, tid,
    canvas_size=(2560, 1440),
    palette="Print / greyscale",
    show_heatmap=False,
    show_order=False,
)
paths = sps.save_figure_layers(fig, "fig1_layers", fmt="pdf")   # {layer: Path}
```

**Compare drift-correction algorithms**

```python
from scanpath_studio.alignment import ALGORITHMS

for method in ALGORITHMS:
    fig = sps.plot_scanpath(
        words, fixations, pid, tid, show_heatmap=False, drift_correction=method
    )
    sps.save_figure(fig, f"aligned_{method}.html")
```

## What the API doesn't cover

Several things the app can do have no `api.py` entry point. They are still
reachable through the internal modules — on the same normalized frames, but
without the API layer's conveniences: no trial resolution, no
`CANONICAL_FIGURE_DEFAULTS`, and canvas/font settings you must pass yourself.
Besides the three shown below, two more are worth knowing about:

- **Scanpath similarity** (`scanpath_studio.similarity`) — the Comparisons
  tab's scoring surface: `compute_similarity_table`,
  `normalized_levenshtein`, `aoi_sequence`, `nld_by_fixation_index`,
  `nld_by_time`.
- **Corpus-level aggregation** (`scanpath_studio.aggregation`) — the
  `MEASURES` registry and the per-reader/cohort profile, rate, and
  group-comparison helpers behind the Corpus Analysis view; see
  [Corpus analysis](corpus-analysis.md).

There is also no entry point that *normalizes* a raw-gaze table
(`propose_schema(df, "raw_gaze")` gives you the schema, but
`data.normalize_raw_gaze` is its only consumer); a normalized raw-gaze frame
can then be passed to `plot_scanpath(raw_gaze=…)`, which filters it to the
trial and switches the layer on.

**Two-scanpath comparison** (the app's Compare mode). Takes the whole frames and
two `(participant_id, trial_id)` tuples, not per-trial frames:

```python
from scanpath_studio import plots

fig = plots.make_comparison_figure(
    words, fixations,
    ("l37_1129", "l37_1129_2_1_1_Ele_r0"),      # trial A
    ("l7_1090", "l7_1090_2_1_1_Ele_r0"),        # trial B
    canvas_width=2560, canvas_height=1440,
    font_family="Arial", base_font_size=16,
    layout="overlay",                            # or "side_by_side" / "stacked"
    trial_labels=("A", "B"), show_legend=True,
)
```

`animate_scanpath` *does* overlay a second reading itself, via `words_b=` /
`fixations_b=` / `label_a=` / `label_b=` / `show_legend=`.

**GIF / MP4 of a replay** — returns bytes, keyword-only, and needs an explicit
per-frame duration (Kaleido + Chrome; ffmpeg rides along with `imageio-ffmpeg`):

```python
from pathlib import Path

from scanpath_studio.animation_export import export_animation
from scanpath_studio.plots import animation_autoplay_frame_duration

anim = sps.animate_scanpath(words, fixations, pid, tid, playback_speed=4.0)
clip = export_animation(
    anim,
    fmt="mp4",                                                  # or "gif"
    frame_duration_ms=animation_autoplay_frame_duration(anim),  # keeps the speed
)
Path("replay.mp4").write_bytes(clip)
```

**Bulk export** (many trials → one zip of figures and tables):
`export.bulk_export(combos, words, fixations, …)` with an `export.ExportOptions`.

## Ground rules

- **Normalized frames only.** Every function past `load_scanpath_data` expects
  its output; raw tables are rejected with a message saying so.
- **Nothing is inferred silently.** An unknown trial, an ambiguous selection or
  a misspelled option raises with the available alternatives listed. Read the
  message rather than guessing a second time.
- **AOIs come from the data.** Word boxes are never computed — only the
  fixation → word assignment is (box containment, then nearest word center
  within 50 px, else unassigned).
- **`import scanpath_studio` is cheap**; pandas/plotly/streamlit load on the
  first API call. Budget a few seconds for it.
- **Kaleido/Chrome is the only external requirement**, and only for static image
  output. HTML always works.
