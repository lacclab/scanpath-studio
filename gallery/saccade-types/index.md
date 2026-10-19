# Saccade types

Forward movements, skips, refixations, return sweeps and regressions.

ForwardSkipRefixationReturn sweepRegressionOff the text

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Saccades** ▾ → **Line** → **Color**, choose **By type**.
1. To match this example, open **Figure & canvas** ▾ → **Legends** and untick **Show** for **Saccade types**. This page shows the color key below the figure.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele \
  --saccade-color-by-type --no-saccade-type-legend \
  --highlight-column '' \
  -o saccade-types.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    saccade_color_mode="By type",
    saccade_type_legend=False,
)

sps.save_figure(fig, "saccade-types.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
