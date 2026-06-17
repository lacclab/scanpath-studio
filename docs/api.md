# Python API

Everything the app draws is available headless through the package's public
functions. They follow one pipeline:

```text
load_scanpath_data / load_sample_data / load_potec   →   (words, fixations)
        list_trials            →  which (participant, trial) combos exist
        compute_word_metrics   →  per-word reading measures (FFD/FPRT/RPD/TFD …)
        plot_scanpath          →  a static Plotly figure
        animate_scanpath       →  an animated replay figure
        save_figure            →  .html / .png / .svg / .pdf on disk
```

All names are importable straight from the package root:

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, "p1", "t3", show_heatmap=False)
sps.save_figure(fig, "scanpath.png")
```

!!! note "Lazy imports"
    `import scanpath_studio` stays cheap — pandas / plotly / streamlit are only
    pulled in on the first API call (the package re-exports `api.py` /
    `datasets.py` lazily). The first call therefore pays a one-time import cost.

## Loading data

::: scanpath_studio.api.load_scanpath_data

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.datasets.load_potec

## Inspecting & measuring

::: scanpath_studio.api.list_trials

::: scanpath_studio.api.compute_word_metrics

## Plotting

Any keyword accepted by the underlying figure builder can be passed through
`plot_scanpath` / `animate_scanpath` (e.g. `show_heatmap=False`,
`color_by="pass_index"`, `saccade_color="#444"`, `hollow_fixations=True`,
`x_field="order_in_trial"`).

::: scanpath_studio.api.plot_scanpath

::: scanpath_studio.api.animate_scanpath

## Saving

::: scanpath_studio.api.save_figure

For rasterized animation (GIF / MP4) use the animation exporter:

```python
from scanpath_studio.animation_export import export_animation

anim = sps.animate_scanpath(words, fixations, "p1", "t3")
export_animation(anim, "replay.mp4")   # or replay.gif — needs Kaleido + Chrome
```

See [Export & troubleshooting](export-troubleshooting.md) for the Chrome /
ffmpeg requirements.
