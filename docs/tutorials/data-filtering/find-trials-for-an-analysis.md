---
description: "Find eye-tracking trials with particular fixation patterns — short, long, out-of-bounds fixations or blinks — and tag them for an analysis."
---

# Find the trials an analysis needs

Locate trials containing particular fixation patterns.

1. Open Plot controls → Filters & highlights → Fixations.
2. Set the relevant category to Highlight:

    - Short or Long, with a duration threshold in milliseconds
    - Out of bounds, for fixations outside every word box
    - Blink, if your data includes a blink column

3. Step through the trials. In Annotations, tag those that meet your analysis
   criteria, for example `include`.
4. Open the filter button beside Select trial. Under By trial annotation,
   enter `include` in With any of these tags.
5. [Check and export the selection](index.md#every-task-ends-the-same-way).
