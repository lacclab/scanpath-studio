---
title: "Saccade types"
description: "Saccades colored by type — forward movements, skips, refixations, return sweeps and regressions — over the text, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Saccade types

Forward movements, skips, refixations, return sweeps and regressions.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("saccade-types"))
```

=== "In the app"

    1. Load your data and select a participant and trial in Scanpath.
    2. Open Saccades ▾ → Line → Color and choose By type.
    3. To match this view, hide the on-figure type legend under Figure & canvas → Legends. The color key is shown below this example.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --saccade-color-by-type --no-saccade-type-legend \
      --highlight-column '' \
      -o saccade-types.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("saccade-types"))
    ```

[← All examples](../gallery.md)
