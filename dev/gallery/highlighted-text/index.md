# Highlighted text

Highlight a selected text span alongside its fixations.

1. Load a Words table with a true/false column that marks the words to highlight, and your Fixations table. Open the dataset in the **Scanpath View** and pick a trial in **Select trial**.
1. In **Stimulus** ▾, tick **Highlight words** and choose that column.
1. Under **Style**, keep **Mark text** and pick the highlight color in the box beside it. To show only the highlighted text and the fixations, turn off **Saccades**.

[Open the demo](https://scanpath-studio-dev.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_273 -t l37_273_2_1_1_Ele --screen Paragraph \
  --highlight-column is_in_aspan --critical-span-style mark-text \
  --no-saccades -o highlighted-text.html
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
    screen="Paragraph",
    highlight_column="is_in_aspan",
    critical_span_style="Mark text",
    show_saccades=False,
)

sps.save_figure(fig, "highlighted-text.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/dev/gallery/index.md)
