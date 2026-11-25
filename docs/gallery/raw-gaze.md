---
title: "Raw gaze"
description: "Raw eye-tracker gaze samples drawn under translucent fixations over the text, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Raw gaze

EyeLink gaze samples recorded at 1,000 Hz under translucent fixation markers.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("raw-gaze"))
```

=== "In the app"

    1. Open the bundled demo in the :material/route: **Scanpath View**. In **Select trial**, choose `l37_273` and `2_2_2_Adv`, and set **Screen** to **Paragraph**.
    2. Turn on :material/grain: **Raw gaze** and turn off :material/arrow_outward: **Saccades**.
    3. In :material/blur_on: **Fixations** → **Opacity**, set 0.35 so the samples show through.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_273 -t l37_273_2_2_2_Adv --screen Paragraph \
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
