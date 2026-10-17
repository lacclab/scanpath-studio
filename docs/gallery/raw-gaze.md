---
title: "Raw gaze"
description: "Raw eye-tracker gaze samples drawn under translucent fixations over the text, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Raw gaze

Samples under translucent fixations. The demo samples are synthetic.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("raw-gaze"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_2_2_Adv_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
    2. Turn on Raw gaze and turn off Saccades.
    3. In Fixations ▾ → Marker → Opacity, choose 0.35 so the samples show through.

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
