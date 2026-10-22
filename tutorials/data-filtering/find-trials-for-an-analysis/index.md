# Find the trials an analysis needs

Locate trials containing particular fixation patterns.

These steps use the **Full** mode: switch to it in the top bar of the **Scanpath** view, or add `ui=full` to the app's address ([Essentials and Full](https://lacclab.github.io/scanpath-studio/guides/scanpath-visualization/#essentials-and-full)).

1. Open **Filters & highlights** ▾ → **Fixations**.

1. Set the **Mode** of the category you need to **Highlight**:

   - **Short** or **Long**, with a duration threshold in **ms**
   - **Outside the text**, for fixations in no word box
   - **Near a blink**, if your data has a blink column

1. Step through the trials. In **Annotations**, tag those that meet your analysis criteria, for example `include`.

1. Open the filter () beside **Select trial**. Under **By trial annotation**, add `include` to **With any of these tags**.

1. [Check and export the selection](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/#every-task-ends-the-same-way).
