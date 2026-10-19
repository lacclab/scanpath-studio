---
description: "Follow an eye-tracking reading measure within trials or across a session, for one participant or a group."
---

# See progression over time

Inspect a measure within trials or across a session.

1. [Select the trials](index.md#before-you-start) and open
   :material/bar_chart: **Corpus Analysis**.
2. Choose the view for the question:

    | Scope | View |
    | --- | --- |
    | One participant across trials | **Per participant** → **Per-trial trend** |
    | Fixation duration within trials, pooled for one participant | **Per participant** → **Fixation duration over time** |
    | A group across trials | **Groups** → **Group trend** |

3. Choose a measure, and an **Aggregate** where the view offers one.
   Across-trial trends order each participant's trials by a `trial_index` or
   `TRIAL_INDEX` column. Without one, the app orders them by fixation time, or
   as listed, and this may differ from the order the trials were shown. For
   the within-trial view, set **X axis** to **Fixation order**, or to
   **Time (ms)** when the data records fixation onsets.
4. [Download the table and recipe](index.md#keep-the-result).
