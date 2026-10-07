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

All functions below are importable from `scanpath_studio`. The
[figure options](#figure-options) table lists every figure keyword.

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

## Load

::: scanpath_studio.api.load_scanpath_data

::: scanpath_studio.api.ScanpathData

::: scanpath_studio.api.load_sample_data

::: scanpath_studio.api.load_raw_gaze

::: scanpath_studio.api.load_sample_raw_gaze

::: scanpath_studio.api.load_participant_metadata

::: scanpath_studio.api.load_trial_metadata

::: scanpath_studio.api.load_text_metadata

::: scanpath_studio.api.propose_schema

::: scanpath_studio.api.build_authored_scanpath

::: scanpath_studio.api.load_authored_scanpath

::: scanpath_studio.datasets.load_potec

::: scanpath_studio.datasets.load_onestop

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

::: scanpath_studio.api.figure_options

## Figure options

Every keyword the figure builders take, with the default it renders with, the
values it takes when there is a fixed set (any case, and `-` or `_` for a
space, so the CLI's `"log"` and `"mark-border"` work; anything else raises a
`ValueError`), the `render` flag that sets it on the command line, and which
builders accept it:
`plot` is `plot_scanpath`, `animate` is `animate_scanpath`, `compare` is
`compare_scanpaths`.

```python exec="true"
from docs_support import figure_options_table

print(figure_options_table())
```

## Save

::: scanpath_studio.api.save_figure

::: scanpath_studio.api.save_figure_layers

## Recovery cache

::: scanpath_studio.api.cache_status

::: scanpath_studio.api.clear_cache

## Version and updates

::: scanpath_studio.api.version_info

::: scanpath_studio.api.check_for_updates

For a batch loop, see [Automation](automation.md#batch-pattern). GIF and MP4
export uses
`scanpath_studio.animation_export.export_animation` and requires Kaleido plus
Chrome, Chromium or Edge.
