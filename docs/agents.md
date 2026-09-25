# Agent guide (headless use)

This page is written for a coding agent — or any script — that has to **use**
Scanpath Studio without a browser: load an eye-tracking-while-reading dataset,
render a figure, pull per-word reading measures. (`AGENTS.md` in the repository
root is the opposite document: how to *develop* this codebase.) A plain-text map
of the whole site is at [`/llms.txt`](https://lacclab.github.io/scanpath-studio/llms.txt).

Everything the app draws is reachable from two places:

| Surface | Entry point | Reference |
|---------|-------------|-----------|
| Python | `scanpath_studio.api`, re-exported at the package root | [Python API](api.md) |
| Shell | `scanpath-studio render` | [CLI reference](cli.md) |

Both go through the same `data → measures → plots` pipeline as the Streamlit
app, so with the same settings a figure rendered here matches the app's.
Headless use (the API or `render`) never writes the app's on-device recovery
cache.

## The 30-second version

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()  # bundled OneStop demo
pid, tid = sps.list_trials(words, fixations).iloc[0]
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
sps.save_figure(fig, "scanpath.html")  # .png/.svg/.pdf need Chrome
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
| `trial_id` | Trial id; with `participant_id` it names one reading. **Required.** |
| `screen_id`, `screen_index` | Optional child screen and 1-based order inside a multipart logical trial. Map in both reports. |
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
| `screen_id`, `screen_index` | Optional child screen and 1-based order; scientific operations never join across it. |
| `text_id` | Text/passage id, when present. |
| `x`, `y` | Fixation location in screen px. **Required unless** `word_id` is given — AOI-sequence data is placed at word-box centers. |
| `duration_ms` | Fixation duration. **Required.** |
| `timestamp_ms` | Fixation onset. Falls back to the row's position within the trial (0, 1, 2, …) when the source has no timestamp — it drives the ordering, so rows must already be in reading order in that case. |
| `screen_timestamp_ms`, `screen_fixation_id` | Optional local clock/id that resets per screen; retained alongside the parent-global columns. |
| `word_id` | Source word/AOI assignment, carried through when the export has one — otherwise `NaN`. The loader only shifts ids numbered from 1 onto 0-based word boxes; the assignment (box containment, then nearest word center within 50 px) happens inside `compute_word_metrics` and the plots that need it. |
| `order_in_trial` | 1-based fixation index, added during normalization. |
| `fixation_id` | Always present — mapped from the source when it has one, otherwise synthesized as a per-trial running index (1, 2, 3, …). |
| `saccade_type`, `saccade_amplitude`, `eye`, `pass_index` | Passed through when the source has them. |

Column matching is case- and separator-insensitive: `IA_LEFT`, `ia_left` and
`Ia Left` are the same name.

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
words, fixations = sps.load_scanpath_data("ia/*.csv", "fix/*.tsv")  # globs
words, fixations = sps.load_scanpath_data(words=ia_df, fixations=fix_df)
words, fixations = sps.load_scanpath_data(fixations="fix.parquet")  # one table
```

Ready-made public corpora have their own loaders — `sps.load_potec(dir)` and
`sps.load_onestop(dir)` — which return the same normalized pair. See
[OneStop](onestop.md).

A raw-gaze table is loaded with `load_raw_gaze(path_or_frame)` (columns
auto-detected; `raw_gaze_schema=` overrides), or `load_sample_raw_gaze()` for
the demo's. Passing it as `plot_scanpath(raw_gaze=…)` filters it to the trial
and switches the layer on.

For a multipart parent, inspect `sps.list_parts(words, fixations, pid, tid)`,
pass `screen="…"` to `plot_scanpath` / `animate_scanpath`, or call
`sps.render_parent_trial(...)` for an ordered mapping of per-screen figures.
Data without explicit screen columns can use `trial_parts_manifest=`; see
[Data format](data-format.md#multipart-logical-trials).

### When auto-detection can't find a column

The `ValueError` names the canonical field, the column names that were tried,
and the columns your table actually has. In full, for a words table whose
columns are `subject, para, word, start_x`:

```text
Words/IA schema problems: missing Trial ID; missing Word/IA ID; need either (x, y, width, height) or (left, right, top, bottom)
Could not infer these canonical fields from the words/IA table:
  - Trial ID (word_schema key 'trial'): no column matched. Looked for: unique_trial_id, trial_id, unique_paragraph_id, paragraph_id, text_id, trial, trial_index, trial_number, presented_stimulus_name, media_name, stimulus
  - Word/IA ID (word_schema key 'word_id'): no column matched. Looked for: word_id, IA_ID, ia_index, word_index, aoi, word_idx, char_idx
  - Word box (word_schema keys): need either (x, y, width, height) or (left, right, top, bottom) — (x, y, width, height) is missing x, y, width, height; (left, right, top, bottom) is missing right, top, bottom.
      Looked for → x: x, left, top_left_x | y: y, top, top_left_y | width: width | height: height | right: IA_RIGHT, right, end_x | top: IA_TOP, top, start_y, top_left_y | bottom: IA_BOTTOM, bottom, end_y
Fields that did resolve: text='word', left='start_x'
Columns present in the words/IA table (4): subject, para, word, start_x
Matching ignores case and separators (IA_LEFT == ia_left == 'Ia Left') and takes the first candidate that matches.
To override auto-detection pass the full mapping, e.g. word_schema={'trial': '<column>', 'word_id': '<column>', 'left': 'start_x', 'right': '<column>', 'top': '<column>', 'bottom': '<column>'} — api.propose_schema(df, 'words') returns what was detected.
```

Pass the complete mapping the message's last line suggests — an explicit schema
replaces auto-detection wholesale — or start from
`api.propose_schema(table, "words")` and fill the gaps.

## Rendering

```python
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
anim = sps.animate_scanpath(words, fixations, pid, tid, playback_speed=4.0)
pair = sps.compare_scanpaths(words, fixations, (pid, tid), (pid_b, tid_b))

sps.save_figure(fig, "out.html")  # interactive, no browser needed
sps.save_figure(fig, "out.png")  # .png/.svg/.pdf via Kaleido → needs Chrome
sps.save_figure_layers(fig, "layers/", fmt="svg")  # one file per layer
```

**HTML never needs Chrome.** PNG/SVG/PDF go through Kaleido, which drives a
Chrome/Chromium binary: run `plotly_get_chrome -y` once, or fall back to HTML.
Details in [Export troubleshooting](export-troubleshooting.md).

## Figure options

Every figure keyword, its default, its `render` flag and the builders that
accept it: the [figure options table](api.md#figure-options), or
`api.figure_options(kind)` at runtime. The option *values* below are the ones
neither reference spells out.

`color_by` is a *fixation column name* (`"duration_ms"`, `"pass_index"`, …) or
the sentinel `"(uniform)"` for one flat colour; a name the frame doesn't have
raises a `ValueError` naming the closest columns (see
[Errors](#errors-and-what-they-mean)). Colouring by text line is the separate
`color_by_line=True` (the lines are inferred from word-box geometry), which
overrides `color_by`.

`fixation_flags` marks or drops suspicious fixations (display only — reading
measures and exports are untouched). One entry per category, each with a mode of
`"Off"` / `"Highlight"` / `"Discard"`:

```python
flags = {
    "short": {
        "mode": "Highlight",
        "threshold_ms": 80.0,
        "symbol": "triangle-up-open",
        "color": "#ff7f0e",
    },
    "long": {
        "mode": "Off",
        "threshold_ms": 800.0,
        "symbol": "square-open",
        "color": "#9467bd",
    },
    "oob": {"mode": "Discard", "symbol": "x", "color": "#d62728"},  # out of text
}
fig = sps.plot_scanpath(words, fixations, pid, tid, fixation_flags=flags)
```

`saccade_color_mode` is `"Uniform"`, `"Forward / regression"` (the two-way fold)
or `"By type"` (forward / skip / refixation / return sweep / regression, each a
legended sub-trace, classified at render time);
`saccade_class_colors={"regression": "#000", …}` overrides individual class
colours. `saccade_classes` is the same split used as a **filter** rather than as
hue — `saccade_classes=["regression"]` draws a regressions-only figure (the
hidden classes lose their direction arrows too), and it composes with any
colour mode; naming every class is a no-op. `saccade_render_mode="Arc"` draws
the linear-reading schematic.

`heatmap_style` is `"Word boxes"`, `"Interpolated"` or `"Duration mass"`;
`heatmap_metric="counts"` weights by fixation count instead of dwell time;
`heatmap_norm="Log"` compresses heavy-tailed dwell times. Duration mass spreads
dwell over nearby characters; `duration_mass_sigma_chars` controls its Gaussian.

`fixation_color_range` and `heatmap_range` are `(min, max)` pairs in the
metric's own units. Left at `None` each trial is scaled to its own values, and
a comparison shares one scale across A and B. Pass a range to put every trial on
the same scale.

`highlight_column` is a boolean words column (OneStop's critical span by
default); the default is skipped when absent, a column you name must exist.

`fit_to_monitor=True` frames the whole `canvas_size`; `False` crops to the data.
`show_coordinate_grid=True` overlays zero-anchored monitor-pixel coordinates;
`coordinate_grid_spacing=None` selects a readable 1/2/5×10ⁿ interval, while a
positive number pins the major interval in pixels. `background_image` places a
stimulus screenshot under the scanpath at data coordinates.

`palette=` is a shorthand that sets a whole group of colours at once —
`"Default (colourblind-safe)"`, `"Print / greyscale"` or `"High contrast"`
(`constants.PALETTES`). Anything you pass explicitly still wins over it, and an
unknown name raises rather than silently falling back.

!!! note "Headless defaults vs. the app's first screen"
    `plot_scanpath` draws word boxes, the heatmap and fixation indices by
    default, while the app opens on the core scanpath only. Every other default
    (marker opacity, index-label size, monitor framing, colours) is the app's.

## Reading measures

```python
metrics = sps.compute_word_metrics(words, fixations)
```

One row per `(participant_id, trial_id, word_id)` with `first_fixation_ms`
(FFD), `first_pass_gaze_duration_ms` (FPRT), `regression_path_duration_ms`
(RPD / go-past), `total_fixation_duration_ms` (TFD), `n_fixations`, `skip_flag`,
`regression_in_flag`, `regression_out_flag`. Pre-aggregated columns already in
the words table (EyeLink IA exports) win; the rest are computed from the
fixations and word boxes. Every definition is in
[Computations & methodology](computations.md).

## The same thing from the shell

```bash
scanpath-studio render --sample --list-trials
scanpath-studio render --sample -o scanpath.html
scanpath-studio render --words 'ia/*.csv' --fixations 'fix/*.csv' \
    -p l37_1129 -t l37_1129_2_1_1_Ele_r0 --canvas 2560x1440 -o figure.png
scanpath-studio render --sample --animate --playback-speed 4 -o replay.html
```

Without `-p` / `-t`, `render` draws the first available trial instead of
raising. Every flag is in the [CLI reference](cli.md).

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
| `color_by='…' (--color-by on the CLI) names no column` (or `highlight_column=`, words) | The option's *value* is a column the data doesn't have. | The message names the closest columns and lists them all; `color_by` also takes `'(uniform)'`; colour by line with `color_by_line=True`. |
| `Options not supported by the animation:` | A static-only option (heatmap, arcs, saccade types) passed to `animate_scanpath`. | Drop it, or render the static figure. |
| `Static .png export failed:` | Kaleido has no Chrome. | `plotly_get_chrome -y`, or save `.html`. |
| `Fixations … have no usable coordinates` | AOI-sequence fixations with no matching word boxes. | Supply the words table whose `word_id`s match. |

## GIF / MP4 of a replay

There is no `api.py` entry point for animated GIF or MP4. Use
`animation_export.export_animation`, which returns bytes, is keyword-only, and
needs an explicit per-frame duration (Kaleido + Chrome; ffmpeg rides along with
`imageio-ffmpeg`):

```python
from pathlib import Path

from scanpath_studio.animation_export import export_animation
from scanpath_studio.plots import animation_autoplay_frame_duration

anim = sps.animate_scanpath(words, fixations, pid, tid, playback_speed=4.0)
clip = export_animation(
    anim,
    fmt="mp4",  # or "gif"
    frame_duration_ms=animation_autoplay_frame_duration(anim),  # keeps the speed
)
Path("replay.mp4").write_bytes(clip)
```

## Ground rules

- **Errors name the alternatives.** An unknown trial, an ambiguous selection or
  a misspelled option raises with the valid values listed; read the message
  rather than guessing again.
- **AOIs come from the data.** Word boxes are never computed — only the
  fixation → word assignment is (box containment, then nearest word center
  within 50 px, else unassigned).
