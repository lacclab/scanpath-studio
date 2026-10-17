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

    1. Select the bundled demo, participant `l37_1129`, trial `l37_1129_2_1_1_Ele_r0`. Reset visualization.
    2. In Stimulus → Highlight words, turn on Show and choose `is_in_aspan` as the word column.
    3. Turn off Saccades. The orange words mark the trial’s answer span.

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
