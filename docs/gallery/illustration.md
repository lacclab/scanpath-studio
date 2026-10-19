---
title: "Reading schematic"
description: "A schematic of a reading for papers and talks: fixations snapped to words and saccades drawn as arcs, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Reading schematic

A hand-drawn two-line text, with one fixation per word in reading order:
The → cat → sat → on → the → mat. Fixations sit on the lines and saccades are arcs.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("illustration"))
```

=== "In the app"

    1. Load your Words and Fixations tables, or the example <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a>. For the example, set **Recording setup** → **Screen** to **I know it**, 450 × 340 px.
    2. Open the dataset in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    3. In :material/blur_on: **Fixations** ▾, tick **Snap** → **To line** and **Fixation index** → **Show**. In :material/arrow_outward: **Saccades** ▾ → **Shape**, choose **Arc**.
    4. In :material/aspect_ratio: **Figure & canvas** ▾ → **Legends**, untick **Show** for **Fixation sizes**. Under **Title & labels** → **Illustration**, enter “Illustration · hand-drawn” in **Text**.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    Download the example <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a> into the same folder.

    ```bash
    scanpath-studio render --words words.csv --fixations fixations.csv \
      -p synthetic -t synthetic_2line_demo \
      --canvas 450x340 --snap-fixations --saccade-arcs --fixation-index \
      --illustration-text "Illustration · hand-drawn" --no-duration-size-legend \
      --highlight-column '' -o illustration.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("illustration"))
    ```

[← All examples](../gallery.md)
