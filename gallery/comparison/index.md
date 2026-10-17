# Two readers

Two complete readings of a shorter text, labeled Reader A and Reader B.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_2_4_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
1. Turn on Compare. In Trial B, select participant `l7_1090`, trial `l7_1090_2_2_4_Ele_r0`.
1. In Compare ▾, choose Overlay and set Label A / Label B to Reader A / Reader B. Leave both fixation ranges unrestricted.
1. In Figure & canvas, choose Crop to data with a 50 px margin. Under Legends, place the comparison legend above the plot and hide the duration size key.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_2_4_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_2_4_Ele_r0 --compare-legend --label-a "Reader A" --label-b "Reader B" \
  --legend compare=top-center-outside,side-by-side,24 --no-duration-size-legend \
  --crop-to-data --crop-margin 50 \
  --highlight-column '' \
  -o comparison.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_2_4_Ele_r0"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_1090", "l7_1090_2_2_4_Ele_r0"),
    highlight_column=None,
    labels=("Reader A", "Reader B"),
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
