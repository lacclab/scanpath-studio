# Raw gaze

Samples under translucent fixations. The demo samples are synthetic.

1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_2_2_Adv_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
1. Turn on Raw gaze and turn off Saccades.
1. In Fixations ▾ → Marker → Opacity, choose 0.35 so the samples show through.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

```
scanpath-studio render --sample \
  -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
  --sample-raw-gaze --fixation-opacity 0.35 --no-saccades \
  --highlight-column '' \
  -o raw-gaze.html
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
pid, tid = "l37_1129", "l37_1129_2_1_1_Ele_r0"
raw_gaze = sps.load_sample_raw_gaze()
fig = sps.plot_scanpath(
    words,
    fixations,
    "l37_1129",
    "l37_1129_2_2_2_Adv_r0",
    raw_gaze=raw_gaze,
    highlight_column=None,
    fixation_opacity=0.35,
    show_saccades=False,
)

sps.save_figure(fig, "raw-gaze.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
