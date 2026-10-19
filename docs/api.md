---
description: "Python API and figure options: load eye-tracking data, plot and save figures, with defaults and matching CLI flags."
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
builders also take the [figure options](#figure-options) as keywords.

## At a glance

```python exec="true"
from docs_support import api_index

print(api_index())
```

## Column names

Columns keep the names your files give them. The bundled demo's Words table
calls its word ID column `IA_ID` and its total fixation duration
`IA_DWELL_TIME`, and every function and option takes those names. A column
Scanpath Studio made keeps its internal name.
`load_scanpath_data(..., names="canonical")` gives the internal names, which are
the same for every dataset. On the bundled demo, the first steps print this
(run when the docs are built):

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

## Load the bundled demo and public datasets

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.api.load_sample_raw_gaze

::: scanpath_studio.datasets.load_potec

::: scanpath_studio.datasets.load_onestop

## Draw a scanpath

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

Set layers, colors, sizes and legends with keyword arguments to `plot_scanpath`,
`animate_scanpath` or `compare_scanpaths`. The tables below list each option's
default and matching CLI `render` flag, under the section names of the app's
:material/tune: **Plot controls**. A description ends by naming the builders an
option is limited to, if any.

For options with a fixed set of values, case, spaces, `-` and `_` are ignored;
other values raise a `ValueError`. A `--no-…` flag turns off an option that is
on by default.

`figure_options()` returns the defaults in code; `figure_options(choices=True)`
also lists the accepted values.

::: scanpath_studio.api.figure_options

```python exec="true" idprefix=""
from docs_support import figure_options_reference

print(figure_options_reference(heading="###"))
```

## Reproduce a figure in code

The app's :material/share: **Share** tab → **Code** shows the Python or CLI
code that rebuilds the figure on screen. Paste it into a notebook or a terminal
to get the same figure. `figure_code` writes the same code without the app, and
`render --print-code` prints it for a `render` command you already have.

```python exec="true" source="above" result="python" session="api"
print(
    sps.figure_code(
        participant="l7_1090",
        trial="l7_1090_2_1_1_Ele",
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
