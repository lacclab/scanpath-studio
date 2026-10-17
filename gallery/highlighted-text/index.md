# Highlighted text

Highlight a selected text span alongside its fixations.

1. Select the bundled demo, participant `l37_1129`, trial `l37_1129_2_1_1_Ele_r0`. Reset visualization.
1. In Stimulus → Highlight words, turn on Show and choose `is_in_aspan` as the word column.
1. Turn off Saccades. The orange words mark the trial’s answer span.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --highlight-column is_in_aspan --critical-span-style mark-text \
  --no-saccades -o highlighted-text.html
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
    highlight_column="is_in_aspan",
    critical_span_style="Mark text",
    show_saccades=False,
)

sps.save_figure(fig, "highlighted-text.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
