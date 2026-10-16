# Word-box heatmap

Fixation time within each word’s bounding box.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight → Show.
1. Turn on Heatmap. In Heatmap ▾, choose Word boxes and weight by fixation duration.
1. Turn off Fixations and Saccades; keep Stimulus on.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --heatmap --heatmap-style word-boxes --no-fixations --no-saccades \
  --highlight-column '' \
  -o word-boxes.html
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
    highlight_column=None,
    show_heatmap=True,
    heatmap_style="Word boxes",
    show_fixations=False,
    show_saccades=False,
)

sps.save_figure(fig, "word-boxes.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
