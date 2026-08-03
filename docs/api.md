# Python API

The public API follows one pipeline:

```text
load data → list trials → plot or measure → save
```

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, participant_id="p1", trial_id="t3")
sps.save_figure(fig, "scanpath.html")
```

All functions below are importable from `scanpath_studio`. Plotting functions
accept the same canonical visualization keywords, so a script can reproduce the
app's default view and change only the needed layers.

## Load

::: scanpath_studio.api.load_scanpath_data

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.datasets.load_potec

## Inspect and measure

::: scanpath_studio.api.list_trials

::: scanpath_studio.api.compute_word_metrics

## Plot

::: scanpath_studio.api.plot_scanpath

::: scanpath_studio.api.animate_scanpath

## Save

::: scanpath_studio.api.save_figure

::: scanpath_studio.api.save_figure_layers

For a batch loop and surface choice, start at
[Automation & reference](automation.md). GIF and MP4 export uses
`scanpath_studio.animation_export.export_animation` and requires Kaleido plus
Chrome/Chromium.
