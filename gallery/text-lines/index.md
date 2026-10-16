# Fixations by line

Color each fixation by its text line.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight → Show.
1. Open Fixations ▾ → Marker → Color and choose Line.
1. Keep Saccades and Stimulus on. The colors follow the word-box lines.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --color-by-line \
  --highlight-column '' \
  -o text-lines.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.plot_scanpath(
    words, fixations, pid, tid, color_by_line=True, highlight_column=None
)

sps.save_figure(fig, "text-lines.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
