# Figure options

Every keyword the figure builders take: the default it renders with, the
`render` flag that sets it on the command line, and what it does. The sections
follow the app's plot rail.

```python
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
fig = sps.plot_scanpath(
    words,
    fixations,
    "l7_1090",
    "l7_1090_2_1_1_Ele_r0",
    show_heatmap=True,  # any option below, as a keyword
    heatmap_norm="log",
    fixation_color="#D55E00",
)
```

- **Builders.** [`plot_scanpath`][scanpath_studio.api.plot_scanpath],
  [`animate_scanpath`][scanpath_studio.api.animate_scanpath] and
  [`compare_scanpaths`][scanpath_studio.api.compare_scanpaths] take every
  option, unless its description ends by naming the builders that do
  (*Plot and compare only.*). A keyword a builder does not take raises a
  `TypeError` that names the closest valid ones.
- **Fixed values.** An option with a fixed set of values lists them. Case,
  spaces, `-` and `_` are ignored, so the CLI's `log` and `mark-border` work;
  any other value raises a `ValueError`.
- **Descriptions** are the `render` flag's own help. A `--no-…` flag describes
  an option that is on by default.
- **In code**, [`figure_options()`][scanpath_studio.api.figure_options]
  returns the same defaults, and `figure_options(choices=True)` adds the values.

```python exec="true" idprefix=""
from docs_support import figure_options_reference

print(figure_options_reference())
```
