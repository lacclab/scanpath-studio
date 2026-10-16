# Two readers

Two readings of one text on the same canvas.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
1. Turn on Compare. In Trial B, select participant `l7_1090`, trial `l7_1090_2_1_1_Ele_r0`.
1. In Compare ▾, choose Overlay. In Filters & highlights ▾, set both fixation ranges to 1–50.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --fix-index-range 1:50 --compare-legend \
  -o comparison.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.compare_scanpaths(
    words,
    fixations,
    (pid, tid),
    ("l7_1090", "l7_1090_2_1_1_Ele_r0"),
    fix_index_range=(1, 50),
    show_legend=True,
)

sps.save_figure(fig, "comparison.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
