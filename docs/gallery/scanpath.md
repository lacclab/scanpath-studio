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

    1. Load your data and select a participant and trial in Scanpath.
    2. Choose the Scanpath design preset, with Fixations, Saccades and Stimulus on.
    3. Use Export → Current figure to save it.

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
