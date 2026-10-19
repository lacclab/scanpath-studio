---
title: "Gaze heatmap"
description: "An eye-tracking heatmap of where fixation time concentrates on the text, with the app controls and the Python and CLI code that make it."
hide:
  - navigation
  - toc
---

# Heatmap

Where fixation time concentrates.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("heatmap"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. Turn on :material/local_fire_department: **Heatmap**. In **Heatmap** ▾ → **Style**, choose **Smoothed**. Keep **Color** → **By** at **Duration (ms)**.
    3. Turn off :material/blur_on: **Fixations** and :material/arrow_outward: **Saccades**, and keep :material/article: **Stimulus** on.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --heatmap --heatmap-style smoothed --no-fixations --no-saccades \
      --highlight-column '' \
      -o heatmap.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("heatmap"))
    ```

[← All examples](../gallery.md)
