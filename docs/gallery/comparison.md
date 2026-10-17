---
title: "Two readers"
description: "Two participants' scanpaths over the same text on one canvas, to compare eye movements between readers, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Two readers

Two complete readings of a shorter text, labeled Reader A and Reader B.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("comparison"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_2_4_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
    2. Turn on Compare. In Trial B, select participant `l7_1090`, trial `l7_1090_2_2_4_Ele_r0`.
    3. In Compare ▾, choose Overlay and set Label A / Label B to Reader A / Reader B. Leave both fixation ranges unrestricted.
    4. In Figure & canvas, choose Crop to data with a 50 px margin. Under Legends, place the comparison legend above the plot and hide the duration size key.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_2_4_Ele_r0 \
      --compare-with l7_1090:l7_1090_2_2_4_Ele_r0 --compare-legend --label-a "Reader A" --label-b "Reader B" \
      --legend compare=top-center-outside,side-by-side,24 --no-duration-size-legend \
      --crop-to-data --crop-margin 50 \
      --highlight-column '' \
      -o comparison.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("comparison"))
    ```

[← All examples](../gallery.md)
