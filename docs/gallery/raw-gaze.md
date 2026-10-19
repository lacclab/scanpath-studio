---
title: "Raw gaze"
description: "Raw eye-tracker gaze samples drawn under translucent fixations over the text, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Raw gaze

Gaze samples under translucent fixations. The bundled demo's gaze samples are synthetic.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("raw-gaze"))
```

=== "In the app"

    1. Load a Raw gaze table with your Fixations and Words tables. Open the dataset in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. Turn on :material/grain: **Raw gaze** and turn off :material/arrow_outward: **Saccades**.
    3. In :material/blur_on: **Fixations** ▾ → **Marker** → **Opacity**, set 0.35 so the samples show through.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_2_2_Adv_r0 \
      --sample-raw-gaze --fixation-opacity 0.35 --no-saccades \
      --highlight-column '' \
      -o raw-gaze.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("raw-gaze"))
    ```

[← All examples](../gallery.md)
