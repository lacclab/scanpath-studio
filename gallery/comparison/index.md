# Two participants

Two complete readings of a shorter text, labeled Participant A and Participant B.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. Turn on **Compare**. In **Trial B**, choose another participant's reading of the same text.
1. In **Compare** ▾, set **View** to **Overlay**, and name the two readings in **Label A** and **Label B**. To compare the complete readings, keep the **Index range** of both scanpaths at the full range, under **Filters & highlights** ▾ → **Fixations · A** and **Fixations · B**.
1. In **Figure & canvas** ▾ → **Screen & framing**, tick **Frame** → **Crop to data**. Untick **Margin** → **Auto** and enter 50 px.
1. Under **Legends**, set **Compare (A/B)** to **Top center, outside** and **Side by side**, with text size 24. Untick **Show** for **Fixation sizes**.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_2_4_Ele \
  --compare-with l7_1090:l7_1090_2_2_4_Ele --compare-legend --label-a "Participant A" --label-b "Participant B" \
  --legend compare=top-center-outside,side-by-side,24 --no-duration-size-legend \
  --crop-to-data --crop-margin 50 \
  --highlight-column '' \
  -o comparison.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_2_4_Ele"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_1090", "l7_1090_2_2_4_Ele"),
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

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
