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

::: scanpath_studio.api.build_authored_scanpath

::: scanpath_studio.api.load_authored_scanpath

::: scanpath_studio.datasets.load_potec

## Inspect and measure

::: scanpath_studio.api.list_trials

::: scanpath_studio.api.list_parts

::: scanpath_studio.api.compute_word_metrics

::: scanpath_studio.api.preprocess_data

::: scanpath_studio.api.analysis_tables

::: scanpath_studio.api.trial_summary

::: scanpath_studio.api.reader_summary

::: scanpath_studio.api.alignment_sensitivity

## Plot

::: scanpath_studio.api.plot_scanpath

::: scanpath_studio.api.animate_scanpath

::: scanpath_studio.api.compare_scanpaths

::: scanpath_studio.api.render_parent_trial

::: scanpath_studio.api.plot_corpus_figure

## Save

::: scanpath_studio.api.save_figure

::: scanpath_studio.api.save_figure_layers

## Recovery cache

The app caches a local session on the machine it runs on (see
[Privacy](privacy.md#what-happens-to-a-file-you-upload)). These inspect and
remove that store from a script; `scanpath-studio cache` is the CLI equivalent.

::: scanpath_studio.api.cache_status

::: scanpath_studio.api.clear_cache

For a batch loop and surface choice, start at
[Automation & reference](automation.md). GIF and MP4 export uses
`scanpath_studio.animation_export.export_animation` and requires Kaleido plus
Chrome/Chromium.
