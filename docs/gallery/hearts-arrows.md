---
title: "Fully customizable"
description: "Customize a scanpath with heart-shaped fixations, curved saccades and direction arrows, with app, CLI and Python instructions."
hide:
  - navigation
  - toc
---

# Fully customizable

Make a figure for a talk or teaching: pink hearts for fixations, purple arrows
for the eye’s movements. This hand-drawn illustration follows
The → cat → sat → on → the → mat, with one fixation per word.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("hearts-arrows"))
```

=== "In the app"

    1. Load your Words and Fixations tables, or the example <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a>. For the example, set **Recording setup** → **Screen** to **I know it**, 450 × 300 px. Open the dataset in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/blur_on: **Fixations** ▾ → **Marker**, set **Shape** to **♥ Heart**. Keep **Color** at **One color** and set its box to `#d12d72`. Set **Size** to **18–30** and **Opacity** to **0.85**. Tick **Snap** → **To line**, and leave **Fixation index** → **Show** unticked.
    3. In :material/arrow_outward: **Saccades** ▾, set **Shape** to **Arc**. Under **Line**, keep **Color** at **One color** with `#4f46a5`, and set **Width** to **2.5**. Tick **Direction arrows** and set **Arrow size** to **12**.
    4. In :material/aspect_ratio: **Figure & canvas** ▾ → **Legends**, untick **Show** for **Fixation sizes**. Under **Title & labels** → **Illustration**, enter “Illustration · hand-drawn” in **Text**. Leave :material/article: **Stimulus** ▾ → **Highlight words** unticked.

    Save the look under :material/palette: **My designs** to apply it to your own data.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    Download the example <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a> into the same folder.

    ```bash
    scanpath-studio render --words words.csv --fixations fixations.csv \
      -p synthetic -t synthetic_2line_demo --canvas 450x300 \
      --fixation-symbol heart --fixation-color '#d12d72' \
      --marker-size-range 18 30 --fixation-opacity 0.85 --snap-fixations \
      --saccade-arcs --saccade-arrows --saccade-color '#4f46a5' \
      --saccade-width 2.5 --saccade-arrow-size 12 \
      --no-fixation-index --no-duration-size-legend --highlight-column '' \
      --illustration-text "Illustration · hand-drawn" -o hearts-arrows.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("hearts-arrows"))
    ```

[← All examples](../gallery.md)
