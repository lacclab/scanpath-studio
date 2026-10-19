---
title: "Word-box heatmap"
description: "An eye-tracking heatmap of the fixation time in each word box, with the app controls and the Python and CLI code that make it."
hide:
  - navigation
  - toc
---

# Word-box heatmap

Fixation time within each word box.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("word-boxes"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. Turn on :material/local_fire_department: **Heatmap**. In **Heatmap** ▾ → **Style**, choose **Word boxes**. Keep **Color** → **By** at **Duration (ms)**.
    3. Turn off :material/blur_on: **Fixations** and :material/arrow_outward: **Saccades**, and keep :material/article: **Stimulus** on.

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
