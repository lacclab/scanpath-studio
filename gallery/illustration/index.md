# Reading schematic

Snapped fixations and arced saccades; an illustration of the reading.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
1. In Filters & highlights ▾ → Fixations → Index range, choose 124–139.
1. In Fixations ▾ → Snap, turn on To line. In Saccades ▾ → Shape, choose Arc.
1. Keep the Illustration label: these positions and arcs are schematic.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --snap-fixations --saccade-arcs --fix-index-range 124:139 \
  -o illustration.html
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
    fixation_snap_to_line=True,
    saccade_render_mode="Arc",
    fix_index_range=(124, 139),
)

sps.save_figure(fig, "illustration.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
