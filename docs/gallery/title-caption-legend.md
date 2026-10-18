---
title: "Title, caption & legend"
description: "Add a title and caption to a scanpath figure and place its legends around the plot, with app, CLI and Python instructions."
hide:
  - navigation
  - toc
---

# Title, caption & legend

A figure ready for a slide or a paper: a title above the plot, a caption
below it, the saccade-type legend down the right side and the fixation-size
key under the plot.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("title-caption-legend"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
    2. Open Saccades ▾ → Line → Color and choose By type.
    3. In Figure & canvas ▾ → Title & labels, turn on Title and type `One reader, one article`, size 34. Turn on Caption and type `Marker size: fixation duration. Line color: saccade type.`, size 20.
    4. Under Legends, place Saccade types at Right, outside, and Fixation sizes at Bottom right, outside, both with text size 18.
    5. Choose Crop to data with a 60 px margin.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --saccade-color-by-type \
      --title "One reader, one article" --title-size 34 \
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
