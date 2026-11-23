# Raw gaze

EyeLink gaze samples recorded at 1,000 Hz under translucent fixation markers.

1. Open the bundled demo in the **Scanpath** view. In **Select trial**, choose `l37_273` and `2_2_2_Adv`.
1. Turn on **Raw gaze** and turn off **Saccades**.
1. In **Fixations** → **Opacity**, set 0.35 so the samples show through.

[Open the demo](https://scanpath-studio-dev.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/dev/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_273 -t l37_273_2_2_2_Adv \
  --sample-raw-gaze --fixation-opacity 0.35 --no-saccades \
  --highlight-column '' \
  -o raw-gaze.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_273", "l37_273_2_2_2_Adv"
raw_gaze = sps.load_sample_raw_gaze()
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    raw_gaze=raw_gaze,
    fixation_opacity=0.35,
    show_saccades=False,
)

sps.save_figure(fig, "raw-gaze.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/dev/gallery/index.md)
