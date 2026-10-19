---
title: "Scanpath replay"
description: "An animated replay of a reading, fixation by fixation in reading order, exportable as GIF or MP4, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Replay

Replay a reading in fixation order. Press **Play** above the text to start this
example, **Pause** to stop, or drag the time slider to inspect a moment. The
example shows forty fixations at twice the recorded speed.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("replay"))
```

=== "In the app"

    1. Load your data and select a participant and trial in Scanpath.
    2. Turn on Animate. To replay just part of the reading, choose a fixation range in Filters & highlights ▾ → Fixations → Index range.
    3. Choose a playback speed in Animate ▾ and press Play. Use Pause or the time slider to inspect the reading; save a replay from Export → Current figure.

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
