# Saccade types

Forward movements, skips, refixations, return sweeps and regressions.

ForwardSkipRefixationReturn sweepRegressionOther

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
1. Open Saccades ▾ → Line → Color and choose By type.
1. To match this view, hide the on-figure type legend under Figure & canvas → Legends. The color key is shown below this example.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --saccade-color-by-type --no-saccade-type-legend \
  -o saccade-types.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
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
