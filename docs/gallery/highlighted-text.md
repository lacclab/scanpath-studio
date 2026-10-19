---
title: "Highlighted text"
description: "Highlight an answer or critical span on the reading stimulus, with app, CLI and Python instructions."
hide:
  - navigation
  - toc
---

# Highlighted text

Highlight a selected text span alongside its fixations.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("highlighted-text"))
```

=== "In the app"

    1. Load a Words table with a true/false column that marks the words to highlight, and your Fixations table. Open the dataset in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/article: **Stimulus** ▾, tick **Highlight words** and choose that column.
    3. Under **Style**, keep **Mark text** and pick the highlight color in the box beside it. To show only the highlighted text and the fixations, turn off :material/arrow_outward: **Saccades**.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --highlight-column is_in_aspan --critical-span-style mark-text \
      --no-saccades -o highlighted-text.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("highlighted-text"))
    ```

[← All examples](../gallery.md)
