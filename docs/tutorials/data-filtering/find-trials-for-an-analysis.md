# Find the trials an analysis needs

Some analyses need particular trials: ones with very short or very long
fixations, fixations out of bounds, or many blinks.

## 1. Make them stand out

Open **:material/filter_list: Filters & highlights → :material/blur_on:
Fixations** in the plot rail and **Highlight** the category you are after:
**Short** or **Long** (each with its own threshold in ms), **Out of bounds**
(fixations in no word box), or **Blink** (fixations at or next to a blink — it
needs a blink column in your data).

## 2. Bring them to the top

Use the ⇅ trial-ordering popover beside the trial picker to sort the trials,
for example by reading time to surface unusually short or long ones, and step
through them with ◀ ▶.

## 3. Mark them

Tag the trials the analysis needs in **Annotations**, then keep only them: in
the filter funnel under **By trial annotation**, put the tag in **With any of
these tags**.

**Then:** [check and export the pool](index.md#every-task-ends-the-same-way).
