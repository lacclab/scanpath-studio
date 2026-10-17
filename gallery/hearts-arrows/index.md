# Hearts & arrows

Make a figure for a talk or teaching: pink hearts for fixations, purple arrows for the eye’s movements. This short, hand-drawn example is an illustration.

1. Download the [words](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/fixations.csv). Choose + → Import files and add both tables. In Recording setup, choose Screen → I know it and enter 450 × 300. Add the dataset, then select the only trial and Reset visualization.
1. In **Fixations → Marker**, choose **Heart**, set the color to `#d12d72`, size range to **18–30**, and opacity to **0.85**. Under **Snap**, choose **To line**. Turn off **Fixation index**.
1. In **Saccades**, set **Shape** to **Arc**. Under **Line**, use `#4f46a5` and width **2.5**. Turn on **Direction arrows** with size **12**.
1. In **Figure & canvas**, hide the duration size key and set the Illustration label to “Illustration · hand-drawn”. Keep text highlighting off.

Save the look under **My designs** to apply it to your own data.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

Download the example [words](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/fixations.csv) into the same folder.

```
scanpath-studio render --words words.csv --fixations fixations.csv \
  -p synthetic -t synthetic_2line_demo --canvas 450x300 \
  --fixation-symbol heart --fixation-color '#d12d72' \
  --marker-size-range 18 30 --fixation-opacity 0.85 --snap-fixations \
  --saccade-arcs --saccade-arrows --saccade-color '#4f46a5' \
  --saccade-width 2.5 --saccade-arrow-size 12 \
  --no-fixation-index --no-duration-size-legend --highlight-column '' \
  --illustration-text "Illustration · hand-drawn" -o hearts-arrows.html
```

```
import scanpath_studio as sps

from scanpath_studio.measures import fixation_in_text_mask
from scanpath_studio.synthetic import load_synthetic_data

words, fixations = load_synthetic_data()
fixations = fixations[fixation_in_text_mask(fixations, words)].copy()
pid, tid = "synthetic", "synthetic_2line_demo"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
    highlight_column=None,
    canvas_size=(450, 300),
    fixation_symbol="heart",
    fixation_color="#d12d72",
    marker_size_range=(18, 30),
    fixation_opacity=0.85,
    fixation_snap_to_line=True,
    saccade_render_mode="Arc",
    show_saccade_arrows=True,
    saccade_color="#4f46a5",
    saccade_width=2.5,
    saccade_arrow_size=12,
    show_order=False,
    duration_size_legend=False,
    illustration_text="Illustration · hand-drawn",
)

sps.save_figure(fig, "hearts-arrows.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
