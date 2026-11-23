# Heatmap

Where fixation time concentrates.

1. Open your data in the **Scanpath View** and pick a trial in **Select trial**.
1. Turn on **Heatmap**. In **Heatmap** ▾ → **Style**, choose **Smoothed**. Keep **Color** → **By** at **Duration (ms)**.
1. Turn off **Fixations** and **Saccades**, and keep **Stimulus** on.

[Open the demo](https://scanpath-studio-dev.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_273 -t l37_273_2_1_1_Ele \
  --heatmap --heatmap-style smoothed --no-fixations --no-saccades \
  --highlight-column '' \
  -o heatmap.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_273", "l37_273_2_1_1_Ele"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    show_heatmap=True,
    heatmap_style="Smoothed",
    show_fixations=False,
    show_saccades=False,
)

sps.save_figure(fig, "heatmap.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/dev/gallery/index.md)
