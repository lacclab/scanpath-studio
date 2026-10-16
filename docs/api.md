---
description: "Python API reference for Scanpath Studio: load eye-tracking data, list trials, plot scanpaths, heatmaps and replays, and save figures from a script or notebook."
---

# Python API

The public API follows one pipeline:

```text
load data → list trials → plot → save
```

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, participant="p1", trial="t3")
sps.save_figure(fig, "scanpath.html")
```

Every function on this page is importable from `scanpath_studio`. The figure
builders also take any of the [figure options](figure-options.md) as a keyword.

## At a glance

```python exec="true"
from docs_support import api_index

print(api_index())
```

## Column names

Columns keep the names your files give them. The demo's word table calls its
word id `IA_ID` and its total fixation duration `IA_DWELL_TIME`, and every
function and option takes those names. A column Scanpath Studio made keeps its
internal name. `load_scanpath_data(..., names="canonical")` gives the internal
names, which are the same for every dataset. On the bundled demo, the first
steps print this (run when the docs are built):

```python exec="true" source="above" result="text" session="api"
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
print(sps.list_trials(words, fixations).head(3))

columns = ["IA_ID", "IA_LABEL", "IA_FIRST_FIXATION_DURATION", "IA_DWELL_TIME"]
print(words[columns].head(3))
```

## Load your data

::: scanpath_studio.api.load_scanpath_data

::: scanpath_studio.api.ScanpathData

::: scanpath_studio.api.propose_schema

::: scanpath_studio.api.attach_stimulus_images

::: scanpath_studio.api.load_raw_gaze

::: scanpath_studio.api.load_participant_metadata

::: scanpath_studio.api.load_trial_metadata

::: scanpath_studio.api.load_text_metadata

## Load the demo and public corpora

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.api.load_sample_raw_gaze

::: scanpath_studio.datasets.load_potec

::: scanpath_studio.datasets.load_onestop

## Author a scanpath

::: scanpath_studio.api.build_authored_scanpath

::: scanpath_studio.api.load_authored_scanpath

## Inspect

::: scanpath_studio.api.list_trials

::: scanpath_studio.api.list_parts

::: scanpath_studio.api.check_data_health

## Plot

::: scanpath_studio.api.plot_scanpath

::: scanpath_studio.api.animate_scanpath

::: scanpath_studio.api.compare_scanpaths

::: scanpath_studio.api.render_parent_trial

::: scanpath_studio.api.plot_corpus_figure

## Figure options

`plot_scanpath`, `animate_scanpath` and `compare_scanpaths` take the
[figure options](figure-options.md) as keywords: every layer, color, size and
legend setting, with the default it renders with and the `render` flag that
sets it. `figure_options()` returns the same defaults in code.

::: scanpath_studio.api.figure_options

## Reproduce a figure in code

The app's :material/share: **Share** subtab shows the API or CLI code that rebuilds the figure
currently on screen — paste it into a notebook or terminal to get the same
figure. `figure_code` is the headless
form of that block, and `render --print-code` prints it for an invocation you
already have.

```python exec="true" source="above" result="python" session="api"
print(
    sps.figure_code(
        participant="l7_1090",
        trial="l7_1090_2_1_1_Ele_r0",
        show_heatmap=True,
        color_by="duration_ms",
    )
)
```

::: scanpath_studio.api.figure_code

## Save

::: scanpath_studio.api.save_figure

::: scanpath_studio.api.save_figure_layers

## Recovery cache

::: scanpath_studio.api.cache_status

::: scanpath_studio.api.clear_cache

## Version and updates

::: scanpath_studio.api.version_info

::: scanpath_studio.api.check_for_updates

## See also

- [Export and share](guides/exporting/index.md): the
  [batch pattern](guides/exporting/index.md#batch-pattern) for many trials, and
  [GIF/MP4 replays](guides/exporting/index.md#replays-as-gif-or-mp4).
- [CLI reference](cli.md): the same figures from the command line.
