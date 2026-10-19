---
title: "Fixations by line"
description: "Fixations colored by the nearest line of text, a quick check of vertical alignment in eye-tracking-while-reading data, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Fixations by line

Fixations colored by their nearest text line.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("text-lines"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/blur_on: **Fixations** ▾ → **Marker** → **Color**, choose **Text line (computed)**.
    3. Keep **Saccades** and **Stimulus** on. Each fixation takes the color of the nearest line of word boxes.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele \
      --color-by-line \
      --highlight-column '' \
      -o text-lines.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("text-lines"))
    ```

[← All examples](../gallery.md)
