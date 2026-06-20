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

Render one trial's scanpath to a file without launching the app. All static
formats — **HTML** (a self-contained SVG page) and **PNG / SVG / PDF** — render
natively with matplotlib, so no Chrome/Chromium is needed.

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
| `--potec DIR` | Load the [PoTeC](https://github.com/DiLi-Lab/PoTeC) corpus from `DIR`, downloading (~45 MB) on first use. Readers are `0–105`, texts `b0–b5` / `p0–p5`. |

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
| `--color-by FIELD` | Fixation color field (default: `duration_ms`). |
| `--heatmap-metric {duration_ms,counts}` | Heatmap weighting (default: `duration_ms`). |
| `--canvas WxH` | Monitor size in px, e.g. `2560x1440` (default: estimated from data; the bundled sample uses `2560x1440`). |
| `--font-size PX` | Base figure font size (default: 16). |
| `--font-family NAME` | Word-label font (default: `monospace`). |
| `--playback-speed X` | Animation speed multiplier for `--animate` (default: 1.0 = real time). |

!!! tip
    GIF / MP4 export isn't a `render` flag — `--animate` writes interactive HTML.
    For rasterized animation use the Python API
    (`animation_export.export_animation`); see [Export & troubleshooting](export-troubleshooting.md).
