# Automation

Use the app for exploration, the CLI for one repeatable render, and Python for loops or analysis pipelines.

## CLI: one figure

```
scanpath-studio render --sample --list-trials
scanpath-studio render --sample -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o scanpath.html
```

Replace `--sample` with `--words ia.csv --fixations fixations.csv`. The [CLI reference](https://lacclab.github.io/scanpath-studio/cli/index.md) has the common combinations and, at its end, every flag.

## Python: one pipeline

```
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
trials = sps.list_trials(words, fixations)
pid, tid = trials.iloc[0][["participant_id", "trial_id"]]

fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    canvas_size=(2560, 1440),  # the monitor the stimulus was shown on
)
sps.save_figure(fig, "scanpath.html")

metrics = sps.compute_word_metrics(words, fixations)
metrics.to_csv("word_measures.csv", index=False)
```

The [Python API](https://lacclab.github.io/scanpath-studio/api/index.md) lists the public functions and parameters.

## From the app to a script

Tune the figure in the app, open 🔗 **Share → Reproduce this figure in code**, and copy the snippet (Python or CLI); it writes only the options that differ from the defaults. The same recipe is available without the app:

```
# translate a render invocation you already have into Python
scanpath-studio render --sample --no-heatmap --print-code python -o out.png
```

From Python, `sps.figure_code(...)` returns the same snippet — see [Reproduce a figure in code](https://lacclab.github.io/scanpath-studio/api/#reproduce-a-figure-in-code).

## Batch pattern

```
from pathlib import Path
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
out = Path("figures")
out.mkdir(exist_ok=True)

for row in sps.list_trials(words, fixations).itertuples():
    fig = sps.plot_scanpath(
        words,
        fixations,
        row.participant_id,
        row.trial_id,
        canvas_size=(2560, 1440),  # the monitor the stimulus was shown on
    )
    sps.save_figure(fig, out / f"{row.participant_id}_{row.trial_id}.html")
```

HTML needs nothing else; PNG, SVG and PDF need Chrome/Chromium (see [Export troubleshooting](https://lacclab.github.io/scanpath-studio/export-troubleshooting/index.md)).
