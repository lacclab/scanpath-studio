---
title: "Scanpath plot"
description: "A scanpath plot of a reading: fixations and saccades drawn over the text at its on-screen position, with the Python and CLI code that makes it."
hide:
  - navigation
  - toc
---

# Scanpath

Fixations and saccades over the text.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("scanpath"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In **Design presets**, click :material/timeline: **Scanpath**. It turns on **Fixations**, **Saccades** and **Stimulus**.
    3. Save the figure from :material/file_export: **Export** → **Current figure**.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --highlight-column '' \
      -o scanpath.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("scanpath"))
    ```

[← All examples](../gallery.md)
