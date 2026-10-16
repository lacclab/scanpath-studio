# Replay

The first forty fixations, replayed at twice the recorded speed.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight → Show.
1. Turn on Animate. In Filters & highlights ▾ → Fixations → Index range, choose 1–40.
1. Set speed to ×2 in Animate ▾ and press Play; save a replay from Export → Current figure.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
  --animate --fix-index-range 1:40 --playback-speed 2 \
  --highlight-column '' \
  -o replay.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
fig = sps.animate_scanpath(
    words,
    fixations,
    pid,
    tid,
    fix_index_range=(1, 40),
    highlight_column=None,
    playback_speed=2.0,
)

sps.save_figure(fig, "replay.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
