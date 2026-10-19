---
title: "Across the experiment"
description: "Follow reading time across one participant’s recorded trial order, with app and Python instructions."
hide:
  - navigation
  - toc
---

# Across the experiment

Mean total fixation duration per word across one participant’s trials in the
bundled demo. Each point is one trial. The bundled demo holds only part of the
session.

```python exec="true" html="true"
from gallery_examples import gallery_figure

print(gallery_figure("across-experiment"))
```

=== "In the app"

    1. Open your data in the :material/bar_chart: **Corpus Analysis** view, on the **Per participant** tab.
    2. Choose a participant, and in **View** choose **Per-trial trend**.
    3. Choose a reading measure your data provides, and **Mean** in **Aggregate**. The horizontal axis is the trial order from the data’s `trial_index` or `TRIAL_INDEX` column. Without one, the app orders the trials by fixation time, or as listed.

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
