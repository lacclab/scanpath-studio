---
title: "Across the experiment"
description: "Follow reading time across one participant’s recorded trial order, with app and Python instructions."
hide:
  - navigation
  - toc
---

# Across the experiment

Mean total fixation duration per word across the demo reader’s recorded trials.
Each point summarizes one trial; this is the bundled subset of the session.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("across-experiment"))
```

=== "In the app"

    1. Select the bundled demo and open Corpus Analysis → Per participant.
    2. Choose `l37_1129`, Total fixation duration and Mean aggregation.
    3. Open Per-trial trend. The horizontal axis uses the dataset’s `trial_index`.

    [Follow the progression tutorial](../tutorials/corpus-analysis/progression-over-time.md)

=== "CLI"

    The corpus CLI does not offer trial-order trends. Download the
    <a href="across-experiment.py" download>Python recipe</a> and run:

    ```bash
    python across-experiment.py
    ```

=== "Python"

    This uses the app’s aggregation and trend builder.

    ```python exec="true"
    from gallery_examples import gallery_python

    print(gallery_python("across-experiment"))
    ```

[← All examples](../gallery.md)
