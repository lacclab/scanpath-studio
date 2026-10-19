# Fixations by line

Fixations colored by their nearest text line.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Fixations** ▾ → **Marker** → **Color**, choose **Text line (computed)**.
1. Keep **Saccades** and **Stimulus** on. Each fixation takes the color of the nearest line of word boxes.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele \
  --color-by-line \
  --highlight-column '' \
  -o text-lines.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
fig = sps.plot_scanpath(words, fixations, pid, tid, color_by_line=True)

sps.save_figure(fig, "text-lines.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
