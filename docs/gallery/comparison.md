---
title: "Two participants"
description: "Two participants' scanpaths over the same text on one canvas, to compare their eye movements, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Two participants

Two complete readings of a shorter text, labeled Participant A and Participant B.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("comparison"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. Turn on :material/compare: **Compare**. In **Trial B**, choose another participant's reading of the same text.
    3. In **Compare** ▾, set **View** to **Overlay**, and name the two readings in **Label A** and **Label B**. To compare the complete readings, keep the **Index range** of both scanpaths at the full range, under :material/filter_list: **Filters & highlights** ▾ → **Fixations · A** and **Fixations · B**.
    4. In :material/aspect_ratio: **Figure & canvas** ▾ → **Screen & framing**, tick **Frame** → **Crop to data**. Untick **Margin** → **Auto** and enter 50 px.
    5. Under **Legends**, set **Compare (A/B)** to **Top center, outside** and **Side by side**, with text size 24. Untick **Show** for **Fixation sizes**.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_2_4_Ele_r0 \
      --compare-with l7_1090:l7_1090_2_2_4_Ele_r0 --compare-legend --label-a "Participant A" --label-b "Participant B" \
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
