# Reading schematic

A hand-drawn two-line text, with fixations snapped to its lines and arced saccades.

1. Download the [words](https://lacclab.github.io/scanpath-studio/gallery/illustration/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/illustration/fixations.csv), then choose + → Import files in the app.
1. Add the two tables as a dataset. Select its only trial and Reset visualization.
1. In Fixations → Snap, choose To line and show the reading order. In Saccades → Shape, choose Arc.
1. In Figure & canvas, use a 450 × 340 canvas and hide the duration size key. Set the Illustration label text to “Illustration · hand-drawn”.

[Open the demo](https://scanpath-studio.streamlit.app) · [All controls](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/controls/index.md)

Download the example [words](https://lacclab.github.io/scanpath-studio/gallery/illustration/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/illustration/fixations.csv) into the same folder.

```
scanpath-studio render --words words.csv --fixations fixations.csv \
  -p synthetic -t synthetic_2line_demo \
  --canvas 450x340 --snap-fixations --saccade-arcs --fixation-index \
  --illustration-text "Illustration · hand-drawn" --no-duration-size-legend \
  --highlight-column '' -o illustration.html
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
    canvas_size=(450, 340),
    fixation_snap_to_line=True,
    saccade_render_mode="Arc",
    illustration_text="Illustration · hand-drawn",
    show_order=True,
    duration_size_legend=False,
)

sps.save_figure(fig, "illustration.html")
```

[← All examples](https://lacclab.github.io/scanpath-studio/gallery/index.md)
