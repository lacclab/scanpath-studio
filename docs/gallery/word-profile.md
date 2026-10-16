---
title: "Word profile"
description: "Mean total fixation duration per word across readers, with a standard-deviation band, from eye-tracking-while-reading data."
hide:
  - navigation
  - toc
---

# Word profile

Mean total fixation duration across readers, with a standard-deviation band.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("word-profile"))
```

=== "In the app"

    1. Select the bundled demo and clear any trial filters.
    2. Open Corpus Analysis → Per text. Choose text `2_1_1_Ele` and Total fixation duration.
    3. Choose Cohort profile, Mean aggregation and SD spread.
    4. Download this table (CSV) saves the values.

    [Open the demo](https://scanpath-studio.streamlit.app) · [All controls](../guides/scanpath-visualization/controls.md)

=== "CLI"

    <a href="word-profile.csv" download>Download the example table</a> first.

    ```bash
    scanpath-studio corpus --input word-profile.csv --kind profile \
      --measure-label "Total fixation duration (ms)" -o word-profile.html
    ```

=== "Python"

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("word-profile"))
    ```

[← All examples](../gallery.md)
