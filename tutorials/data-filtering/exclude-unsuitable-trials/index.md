# Exclude unsuitable trials

Mark the trials that should not be analysed — poorly calibrated, skimming, or not reading at all — and leave them out of the pool without deleting them.

## 1. Review each trial

Inspect the default scanpath, and turn on **Animate** when timing helps: skimming shows as long jumps and few fixations, poor calibration as fixations shifted off the lines. Open **Filters & highlights → Fixations** in the plot rail and **Highlight** out-of-bounds fixations; highlighting keeps the whole trial visible.

## 2. Tag the decision

In **Annotations**, apply a consistent tag vocabulary — for example `exclude`, `poor-calibration` or `skimming` — and add a brief reason.

\[!\[

\](../../../assets/workflows/favorites_poster.webp)\](../../../assets/workflows/favorites.mp4)

*Starring a trial and tagging it, starring another, then showing only the starred ones.*

## 3. Leave the tagged trials out

First save the full record ( **Data Management → Annotations → Export**). Then, in the filter funnel under **By trial annotation**, put `exclude` in **Excluding tags** — not in **With any of these tags**, which would keep only the rejected trials. The pool is now the trials you kept.

On a dataset with several screens per trial, a tag on a single screen does not hide its trial; find those on **Data Management → Annotations**.

**Then:** [check and export the pool](https://lacclab.github.io/scanpath-studio/tutorials/data-filtering/#every-task-ends-the-same-way).
