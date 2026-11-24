# Two participants

Two complete readings of a shorter text, labeled Participant A and Participant B.

1. Open your data in the **Scanpath View** and pick a trial in **Select trial**.
1. Turn on **Compare**. In **Trial B**, choose another participant's reading of the same text.
1. In **Compare settings**, set **Layout** to **Overlay** and name the two readings under **Reading labels**. To compare the complete readings, keep the **Index range** of both scanpaths at the full range, under **Filters & highlights** ▾ → **Reading A** and **Reading B**.
1. In **Figure** → **Screen & framing**, tick **Crop to data**. Under **Margins and border color**, untick the automatic margin and enter 50 px.
1. Under **Legends** → **Legend position and style**, set **Compare (A/B)** to **Top center, outside** and **Side by side**, with text size 24.

[Open the demo](https://scanpath-studio-dev.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_273 -t l37_273_2_2_4_Ele --screen Paragraph \
  --compare-with l7_183:l7_183_2_2_4_Ele --compare-screen Paragraph \
  --compare-legend --label-a "Participant A" --label-b "Participant B" \
  --legend compare=top-center-outside,side-by-side,24 \
  --crop-to-data --crop-margin 50 \
  --highlight-column '' \
  -o comparison.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_273", "l37_273_2_2_4_Ele"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_183", "l7_183_2_2_4_Ele"),
    screen="Paragraph",
    screen_b="Paragraph",
    labels=("Participant A", "Participant B"),
    fit_to_monitor=False,
    crop_margin=50,
    show_legend=True,
    duration_size_legend=False,
    legend_layout={
        "compare": {
            "position": "top-center-outside",
            "arrangement": "side-by-side",
            "size": 24,
        }
    },
)

sps.save_figure(fig, "comparison.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/dev/gallery/index.md)
