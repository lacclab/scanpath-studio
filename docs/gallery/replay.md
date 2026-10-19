---
title: "Scanpath replay"
description: "An animated replay of a reading, fixation by fixation in reading order, exportable as GIF or MP4, with Python and CLI code."
hide:
  - navigation
  - toc
---

# Replay

Replay a reading in fixation order. Press **▶ Play** above the text to start
this example, **⏸ Pause** to stop, or drag the time slider to inspect a moment.
The example shows the first forty fixations at twice the recorded speed.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("replay"))
```

=== "In the app"

    1. Open your data in the :material/route: **Scanpath** view and pick a trial in **Select trial**.
    2. Turn on :material/movie: **Animate**. To replay part of the reading, set :material/filter_list: **Filters & highlights** ▾ → **Fixations** → **Index range**, here 1 to 40.
    3. In **Animate** ▾ → **Replay** → **Speed**, choose **×2**, then press **▶ Play** above the plot. Use **⏸ Pause** or the time slider to inspect the reading.
    4. Save the replay from :material/file_export: **Export** → **Current figure**.

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
