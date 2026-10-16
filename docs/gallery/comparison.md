---
title: "Two readers"
description: "Two participants' scanpaths over the same text on one canvas, to compare eye movements between readers, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Two readers

Two readings of one text on the same canvas.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("comparison"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
    2. Turn on Compare. In Trial B, select participant `l7_1090`, trial `l7_1090_2_1_1_Ele_r0`.
    3. In Compare ▾, choose Overlay. In Filters & highlights ▾, set both fixation ranges to 1–50.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --compare-with l7_1090:l7_1090_2_1_1_Ele_r0 --fix-index-range 1:50 --compare-legend \
      -o comparison.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("comparison"))
    ```

[← All examples](../gallery.md)
