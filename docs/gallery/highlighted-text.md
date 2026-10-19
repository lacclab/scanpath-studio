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

    1. Load a word table with a true/false column marking the words you want to highlight, along with your fixations. Select a participant and trial in Scanpath.
    2. In Stimulus → Highlight words, turn on Show and choose that word column.
    3. Choose a highlight color. Turn off Saccades if you want to show just the highlighted text and fixations.

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
