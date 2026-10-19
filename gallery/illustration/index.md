# Reading schematic

A hand-drawn two-line text, with one fixation per word in reading order: The → cat → sat → on → the → mat. Fixations sit on the lines and saccades are arcs.

1. Load your Words and Fixations tables, or the example [words](https://lacclab.github.io/scanpath-studio/gallery/illustration/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/illustration/fixations.csv). For the example, set **Recording setup** → **Screen** to **I know it**, 450 × 340 px.
1. Open the dataset in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Fixations** ▾, tick **Snap** → **To line** and **Fixation index** → **Show**. In **Saccades** ▾ → **Shape**, choose **Arc**.
1. In **Figure & canvas** ▾ → **Legends**, untick **Show** for **Fixation sizes**. Under **Title & labels** → **Illustration**, enter “Illustration · hand-drawn” in **Text**.

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

from scanpath_studio.synthetic import make_synthetic_words

words = make_synthetic_words()
fixations = words[["participant_id", "trial_id", "text_id", "word_id"]].copy()
fixations["x"] = words["x"] + words["width"] / 2
fixations["y"] = words["y"] + words["height"] / 2
fixations["duration_ms"] = [100, 150, 120, 200, 90, 110]
fixations["timestamp_ms"] = (
    fixations["duration_ms"].cumsum() - fixations["duration_ms"]
)
fixations["order_in_trial"] = range(1, len(fixations) + 1)
fixations["pass_index"] = 1
pid, tid = "synthetic", "synthetic_2line_demo"
fig = sps.plot_scanpath(
    words,
    fixations,
    pid,
    tid,
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
