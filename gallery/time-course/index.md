# Time course

Horizontal gaze position against fixation onset time.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
1. Open Figure & canvas ▾ → Axes.
1. Set X to Time (ms) and Y to the fixation X position. This plots fixation onset against horizontal position.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --x-field timestamp_ms --y-field x \
  -o time-course.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.plot_scanpath(
    words, fixations, pid, tid, x_field="timestamp_ms", y_field="x"
)

sps.save_figure(fig, "time-course.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
