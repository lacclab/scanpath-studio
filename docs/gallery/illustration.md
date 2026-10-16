---
hide:
  - navigation
  - toc
---

# Reading schematic

Snapped fixations and arced saccades; an illustration of the reading.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("illustration"))
```

=== "In the app"

    1. Select the bundled demo in Scanpath, then participant `l37_1129` and trial `l37_1129_2_1_1_Ele_r0`. Start with Reset visualization.
    2. In Filters & highlights ▾ → Fixations → Index range, choose 124–139.
    3. In Fixations ▾ → Snap, turn on To line. In Saccades ▾ → Shape, choose Arc.
    4. Keep the Illustration label: these positions and arcs are schematic.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    ```bash
    scanpath-studio render --sample \
      -p l37_1129 -t l37_1129_2_1_1_Ele_r0 \
      --snap-fixations --saccade-arcs --fix-index-range 124:139 \
      -o illustration.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("illustration"))
    ```

[← All examples](../gallery.md)
