---
title: "Gaze time course"
description: "Horizontal gaze position against fixation onset time for one reading, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Time course

Horizontal gaze position against fixation onset time.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("time-course"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
    2. Open Figure & canvas ▾ → Axes.
    3. Set X to Time (ms) and Y to the fixation X position. This plots fixation onset against horizontal position.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --x-field timestamp_ms --y-field x \
      -o time-course.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("time-course"))
    ```

[← All examples](../gallery.md)
