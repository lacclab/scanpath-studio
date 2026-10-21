---
description: "Select eye-tracking participants by metadata such as native language, age or group, by attaching a participant metadata table to the dataset."
---

# Select participants by a field

Select participants using metadata such as native language, age or group.

These steps use the **Advanced** mode: switch to it in the top bar of the
:material/route: **Scanpath** view, or add `ui=advanced` to the app's
address ([Simple and Advanced](../../guides/scanpath-visualization/index.md#simple-and-advanced)).

1. Attach a participant metadata table, with one row per participant and a
   participant ID column. When you add a dataset, use **Metadata** →
   **Participants**. For a loaded dataset, use :material/database: **Data
   Management** → :material/edit: **Edit dataset** → **Data tables & column
   mapping**.
2. Open the filter (:material/filter_alt:) beside **Select trial** and find
   **By participant**.
3. Choose a field and the values or range to keep.
4. Check the remaining participant IDs and
   [export the selection](index.md#every-task-ends-the-same-way).

To also apply trial-level quality criteria, follow
[Exclude unsuitable trials](exclude-unsuitable-trials.md).
