# CLI reference

The package installs a single console command, `scanpath-studio`, with two
modes: **launch the app** (default) and **`render`** a trial to a file headless.

```bash
scanpath-studio --version
scanpath-studio --help
```

## Launch the app

```bash
scanpath-studio                 # launch the Streamlit app (default)
scanpath-studio run             # explicit; same as above
scanpath-studio --server.port 8600   # unknown flags forward to `streamlit run`
```

No-args / `run` / unrecognized flags start the app via `streamlit run`
(default port 8501); extra flags are forwarded to Streamlit for backward
compatibility.

## `render` — headless figures

Render one trial's scanpath to a file without launching the app. **HTML** output
is interactive and browser-free; **PNG / SVG / PDF** go through Kaleido and need
a Chrome/Chromium binary (`plotly_get_chrome -y`).

```bash
scanpath-studio render --sample --list-trials              # what's available
scanpath-studio render --sample -o scanpath.html           # interactive HTML
scanpath-studio render --words ia.csv --fixations fix.csv -p p1 -t t3 -o figure.png
scanpath-studio render --sample --animate -o replay.html   # animated replay (HTML)
```

### Input

| Flag | Description |
|------|-------------|
| `--sample` | Use the bundled 3-participant OneStop demo. |
| `--words PATH [PATH …]` | Words / IA table(s) (`csv`/`tsv`/`parquet`/`feather`). Multiple paths or a quoted glob concatenate multi-file datasets. |
| `--fixations PATH [PATH …]` | Fixations table(s); same multi-file rules (e.g. one file per participant). |
| `--potec DIR` | Load the [PoTeC](https://github.com/DiLi-Lab/PoTeC) corpus from `DIR`, downloading (~45 MB) on first use. 75 readers with sparse ids within `0–105` (`--list-trials` shows them), texts `b0–b5` / `p0–p5`. |

### Selection & output

| Flag | Description |
|------|-------------|
| `-p, --participant ID` | Participant id (default: first available). |
| `-t, --trial ID` | Trial id (default: first for the participant). |
| `--list-trials` | Print the available `(participant, trial)` combos and exit. |
| `-o, --output PATH` | Output file; format from extension (`.html`/`.png`/`.svg`/`.pdf`). |
| `--animate` | Render the animated replay instead of the static figure (HTML only). |

### Visualization (defaults match the app)

| Flag | Description |
|------|-------------|
| `--no-words` | Hide word bounding boxes. |
| `--no-labels` | Hide the reading text. |
| `--no-fixations` | Hide fixation markers. |
| `--no-order` | Hide fixation-index labels. |
| `--no-saccades` | Hide saccade lines. |
| `--no-heatmap` | Hide the heatmap overlay. |
| `--saccade-arrows` | Draw saccade direction arrowheads. |
| `--saccade-color-by-type` | Colour each saccade by its reading type (forward / skip / refixation / return sweep / regression). |
| `--saccade-type-color CLASS=COLOR` | Override one reading-type colour, e.g. `regression=#000000` (repeatable; implies `--saccade-color-by-type`). |
| `--no-saccade-type-legend` | With `--saccade-color-by-type`: hide the saccade-type colour key (the coloured lines still draw). |
| `--saccade-arcs` | Draw saccades as upward arcs (the linear-reading diagram) instead of straight connectors. |
| `--snap-fixations` | Snap each fixation above the word it lands on instead of its raw gaze point. |
| `--color-by FIELD` | Fixation color field (default: `duration_ms`). |
| `--heatmap-metric {duration_ms,counts}` | Heatmap weighting (default: `duration_ms`). |
| `--heatmap-norm {linear,log}` | Heatmap colour scaling (default: `linear`); `log` compresses heavy-tailed dwell times. |
| `--canvas WxH` | Monitor size in px, e.g. `2560x1440` (default: estimated from data; the bundled sample uses `2560x1440`). |
| `--font-size PX` | Base figure font size (default: 16). |
| `--font-family NAME` | Word-label font (default: `monospace`). |
| `--playback-speed X` | Animation speed multiplier for `--animate` (default: 1.0 = real time). |
| `--no-autoplay` | With `--animate`: save the replay paused (default: it autoplays on load at the playback speed). |
| `--stimulus-image PATH` | Draw an image (PNG/JPG) as the stimulus background under the scanpath. Works with `--animate`. |
| `--stimulus-image-size WxH` | Stimulus-image size in px (default: the PNG's own size, else the canvas). |
| `--stimulus-image-origin X,Y` | Top-left of the stimulus image in monitor px (default: `0,0`). |
| `--stimulus-image-opacity O` | Stimulus-image opacity 0.1–1.0 (default: 1.0); lower it to dim a busy image. |
| `--separable-layers` | Also write the figure split into one file per layer in `<output>_layers/` (static `.svg`/`.pdf`/`.png` output). |

!!! tip
    GIF / MP4 export isn't a `render` flag — `--animate` writes interactive HTML.
    For rasterized animation use the Python API
    (`animation_export.export_animation`); see [Export & troubleshooting](export-troubleshooting.md).
