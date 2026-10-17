---
title: "Scanpath replay"
description: "An animated replay of a reading, fixation by fixation in reading order, exportable as GIF or MP4, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Replay

The first forty fixations, replayed at twice the recorded speed.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("replay"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization, turn off Stimulus → Highlight words → Show.
    2. Turn on Animate. In Filters & highlights ▾ → Fixations → Index range, choose 1–40.
    3. Set speed to ×2 in Animate ▾ and press Play; save a replay from Export → Current figure.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --animate --fix-index-range 1:40 --playback-speed 2 \
      --highlight-column '' \
      -o replay.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("replay"))
    ```

[← All examples](../gallery.md)
