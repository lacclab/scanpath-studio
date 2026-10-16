---
title: "Reading schematic"
description: "A schematic of a reading for papers and talks: fixations snapped to words and saccades drawn as arcs, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Reading schematic

A hand-drawn two-line text, with fixations snapped to its lines and arced saccades.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("illustration"))
```

=== "In the app"

    1. Download the <a href="words.csv" download>words</a> and <a href="fixations.csv" download>fixations</a>, then choose + → Import files in the app.
    2. Add the two tables as a dataset, with Recording setup → Screen → I know it set to 450 × 340. Select its only trial and Reset visualization.
    3. In Fixations → Snap, choose To line and show the reading order. In Saccades → Shape, choose Arc.
    4. In Figure & canvas, hide the duration size key and set the Illustration label text to “Illustration · hand-drawn”.

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
