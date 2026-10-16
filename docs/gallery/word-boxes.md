---
title: "Word-box heatmap"
description: "An eye-tracking heatmap of where fixation time concentrates on the text, with the app controls and the Python and CLI code that make it."
hide:
  - navigation
  - toc
---

# Word-box heatmap

Fixation time within each word’s bounding box.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("word-boxes"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight → Show.
    2. Turn on Heatmap. In Heatmap ▾, choose Word boxes and weight by fixation duration.
    3. Turn off Fixations and Saccades; keep Stimulus on.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --heatmap --heatmap-style word-boxes --no-fixations --no-saccades \
      --highlight-column '' \
      -o word-boxes.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("word-boxes"))
    ```

[← All examples](../gallery.md)
