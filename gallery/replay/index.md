# Replay

Replay a reading in fixation order. Press **▶ Play** above the text to start this example, **⏸ Pause** to stop, or drag the time slider to inspect a moment. The example shows the first forty fixations at twice the recorded speed.

1. Open your data in the **Scanpath** view and pick a trial in **Select trial**.
1. Turn on **Animate**. To replay part of the reading, set **Filters & highlights** ▾ → **Fixations** → **Index range**, here 1 to 40.
1. In **Animate** ▾ → **Replay** → **Speed**, choose **×2**, then press **▶ Play** above the plot. Use **⏸ Pause** or the time slider to inspect the reading.
1. Save the replay from **Export** → **Current figure**.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele \
  --animate --fix-index-range 1:40 --playback-speed 2 \
  --highlight-column '' \
  -o replay.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele"
fig = sps.animate_scanpath(
    words,
    fixations,
    pid,
    tid,
    fix_index_range=(1, 40),
    playback_speed=2.0,
)

sps.save_figure(fig, "replay.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
