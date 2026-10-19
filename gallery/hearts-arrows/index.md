# Fully customizable

Make a figure for a talk or teaching: pink hearts for fixations, purple arrows for the eye’s movements. This hand-drawn illustration follows The → cat → sat → on → the → mat, with one fixation per word.

1. Load your Words and Fixations tables, or the example [words](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/words.csv) and [fixations](https://lacclab.github.io/scanpath-studio/gallery/hearts-arrows/fixations.csv). For the example, set **Recording setup** → **Screen** to **I know it**, 450 × 300 px. Open the dataset in the **Scanpath** view and pick a trial in **Select trial**.
1. In **Fixations** ▾ → **Marker**, set **Shape** to **♥ Heart**. Keep **Color** at **One color** and set its box to `#d12d72`. Set **Size** to **18–30** and **Opacity** to **0.85**. Tick **Snap** → **To line**, and leave **Fixation index** → **Show** unticked.
1. In **Saccades** ▾, set **Shape** to **Arc**. Under **Line**, keep **Color** at **One color** with `#4f46a5`, and set **Width** to **2.5**. Tick **Direction arrows** and set **Arrow size** to **12**.
1. In **Figure & canvas** ▾ → **Legends**, untick **Show** for **Fixation sizes**. Under **Title & labels** → **Illustration**, enter “Illustration · hand-drawn” in **Text**. Leave **Stimulus** ▾ → **Highlight words** unticked.

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
