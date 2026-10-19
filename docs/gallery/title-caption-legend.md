---
title: "Title, caption & legend"
description: "Add a title and caption to a scanpath figure and place its legends around the plot, with app, CLI and Python instructions."
hide:
  - navigation
  - toc
---

# Title, caption & legend

A figure ready for a slide or a paper. It has a title above the plot, a caption
below it, the **Saccade types** legend down the right side and the
**Fixation sizes** legend below the plot.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("title-caption-legend"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/arrow_outward: **Saccades** ▾ → **Line** → **Color**, choose **By type**.
    3. In :material/aspect_ratio: **Figure & canvas** ▾ → **Title & labels**, tick **Title** and **Caption**. Enter a title for your reading and a caption that explains the markers and colors. Set each one's **Size**, here 34 px and 20 px.
    4. Under **Legends**, set **Saccade types** to **Right, outside** and **Fixation sizes** to **Bottom right, outside**, both with text size 18.
    5. Under **Screen & framing**, tick **Frame** → **Crop to data**. Untick **Margin** → **Auto** and enter 60 px.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --saccade-color-by-type \
      --title "One participant, one article" --title-size 34 \
      --caption "Marker size: fixation duration. Line color: saccade type." --caption-size 20 \
      --legend saccades=right-outside,,18 --legend size-key=bottom-right-outside,,18 \
      --crop-to-data --crop-margin 60 \
      --highlight-column '' \
      -o title-caption-legend.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("title-caption-legend"))
    ```

[← All examples](../gallery.md)
