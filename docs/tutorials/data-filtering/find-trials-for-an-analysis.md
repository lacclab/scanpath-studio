---
description: "Find eye-tracking trials with particular fixation patterns — short or long fixations, fixations outside the text, or blinks — and tag them for an analysis."
---

# Find the trials an analysis needs

Locate trials containing particular fixation patterns.

These steps use the **Full** mode: switch to it in the top bar of the
:material/route: **Scanpath** view, or add `ui=full` to the app's
address ([Essentials and Full](../../guides/scanpath-visualization/index.md#essentials-and-full)).

1. Open :material/filter_list: **Filters & highlights** ▾ → **Fixations**.
2. Set the **Mode** of the category you need to **Highlight**:

    - **Short** or **Long**, with a duration threshold in **ms**
    - **Outside the text**, for fixations in no word box
    - **Near a blink**, if your data has a blink column

3. Step through the trials. In :material/edit_note: **Annotations**, tag those
   that meet your analysis criteria, for example `include`.
4. Open the filter (:material/filter_alt:) beside **Select trial**. Under
   **By trial annotation**, add `include` to **With any of these tags**.
5. [Check and export the selection](index.md#every-task-ends-the-same-way).
