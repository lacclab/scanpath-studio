---
title: "Saccade types"
description: "Saccades colored by type — forward movements, skips, refixations, return sweeps and regressions — over the text, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Saccade types

Forward movements, skips, refixations, return sweeps and regressions.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("saccade-types"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/arrow_outward: **Saccades** ▾ → **Line** → **Color**, choose **By type**.
    3. To match this example, open :material/aspect_ratio: **Figure & canvas** ▾ → **Legends** and untick **Show** for **Saccade types**. This page shows the color key below the figure.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --saccade-color-by-type --no-saccade-type-legend \
      --highlight-column '' \
      -o saccade-types.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("saccade-types"))
    ```

[← All examples](../gallery.md)
