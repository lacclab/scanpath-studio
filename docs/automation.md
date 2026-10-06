# Automation

Use the app for exploration, the CLI for one repeatable render, and Python for
loops or analysis pipelines.

## CLI: one figure

```bash
scanpath-studio render --sample --list-trials
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o scanpath.html
```

Replace `--sample` with `--words ia.csv --fixations fixations.csv`. The
[CLI reference](cli.md) has the common combinations and, at its end, every flag.

## Python: one pipeline

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
trials = sps.list_trials(words, fixations)  # (participant, trial), your names
pid, tid = trials.iloc[0]

fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    canvas_size=(2560, 1440),  # the monitor the stimulus was shown on
)
sps.save_figure(fig, "scanpath.html")
```

The [Python API](api.md) lists the public functions and parameters.

## From the app to a script

Tune the figure in the app, open :material/share: **Share → Code**,
and copy the snippet (Python or CLI); it writes only the options that differ
from the defaults. For a dataset you added in the app, the snippet loads your
files with the column mapping you set up (`word_schema` / `fix_schema`, or
`--word-schema` / `--fix-schema`), and only the tables the dataset has; the
file paths are placeholders to replace. A step the loader cannot repeat, such
as joining character boxes into words or columns made from the file names, is
named in a note beside the snippet. The same recipe is available without the
app:

```bash
# translate a render invocation you already have into Python
scanpath-studio render --sample --no-heatmap --print-code python -o out.png
```

From Python, `sps.figure_code(...)` returns the same snippet — see
[Reproduce a figure in code](api.md#reproduce-a-figure-in-code).

## Batch pattern

```python
from pathlib import Path
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
out = Path("figures")
out.mkdir(exist_ok=True)

for pid, tid in sps.list_trials(words, fixations).itertuples(index=False):
    fig = sps.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        canvas_size=(2560, 1440),  # the monitor the stimulus was shown on
    )
    sps.save_figure(fig, out / f"{pid}_{tid}.html")
```

HTML needs nothing else. PNG, SVG and PDF need Chrome, Chromium or Edge
installed; with none, run `plotly_get_chrome -y` once, or save HTML.

## Replays as GIF or MP4

```python
from pathlib import Path

import scanpath_studio as sps
from scanpath_studio.animation_export import export_animation

words, fixations = sps.load_sample_data()
anim = sps.animate_scanpath(words, fixations, "l37_1129", "l37_1129_2_1_1_Ele_r0")
Path("replay.mp4").write_bytes(export_animation(anim, fmt="mp4"))  # or "gif"
```

This also needs Chrome, Chromium or Edge; ffmpeg comes with the package. The
CLI's `--animate` writes interactive HTML only.
