---
title: "Fixations by line"
description: "Fixations colored by the nearest line of text, a quick check of vertical alignment in eye-tracking-while-reading data, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Fixations by line

Color each fixation by its text line.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("text-lines"))
```

=== "In the app"

    1. Load your data and select a participant and trial in Scanpath.
    2. Open Fixations ▾ → Marker → Color and choose Text line.
    3. Keep Saccades and Stimulus on. The colors follow the word-box lines.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
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
