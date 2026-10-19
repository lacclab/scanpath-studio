---
title: "Redacted text"
description: "Hide the stimulus text behind a block over each word's letters, keeping the layout of the text, with app, CLI and Python instructions."
hide:
  - navigation
  - toc
---

# Redacted text

Show where the text was without showing what it said. Each word is drawn as a
rounded block over its letters, and the hovers hide the words too.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("redacted-text"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. In :material/article: **Stimulus** ▾ → **Text**, tick **Redact**. The blocks take the text color.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --redact-text --highlight-column '' \
      -o redacted-text.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("redacted-text"))
    ```

[← All examples](../gallery.md)
