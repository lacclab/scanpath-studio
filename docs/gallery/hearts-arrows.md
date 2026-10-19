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

    1. Load your word and fixation tables and select a participant and trial in Scanpath. You can also try the example <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a> with a 450 × 300 canvas.
    2. In **Fixations → Marker**, choose **Heart**, set the color to `#d12d72`, size range to **18–30**, and opacity to **0.85**. Under **Snap**, choose **To line**. Turn off **Fixation index**.
    3. In **Saccades**, set **Shape** to **Arc**. Under **Line**, use `#4f46a5` and width **2.5**. Turn on **Direction arrows** with size **12**.
    4. In **Figure & canvas**, hide the duration size key and set the Illustration label to “Illustration · hand-drawn”. Keep text highlighting off.

    Save the look under **My designs** to apply it to your own data.

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
