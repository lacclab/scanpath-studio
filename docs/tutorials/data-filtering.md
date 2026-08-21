# Tutorial: filter data

This workflow finds trials unsuitable for an analysis or publication and leaves
an auditable retained pool.

## 1. Narrow the trial pool

Load the dataset, then open the **filter funnel** on the control line above the
plot: it holds **Narrow by** (text and participant) together with the condition
and annotation filters. Start with broad dataset fields such as participant,
condition, correctness, or repeated-reading status. Use the ⇅ trial-ordering
popover to surface unusually short or long trials.

Avoid applying many filters at once: add one, check the remaining count, then
continue. If the pool becomes empty, use the adjacent clear action to identify
which filter removed it.

## 2. Review candidate trials

For each candidate, inspect the default scanpath and turn on **Animate** only
when timing helps. Open **🧹 Filter → 👁️ Fixations** in the plot rail and mark:

- out-of-bounds points;
- fixations below or above your duration thresholds;
- a specific fixation-index range when only part of the trial matters.

These controls change the visualization. They do not rewrite the uploaded table
or silently change the reading measures.

## 3. Annotate the decision

In **Annotations**, apply a consistent tag vocabulary—for example `exclude`,
`review`, `poor-calibration`, or `skimming`—and add a brief reason. Star trials
that are useful examples or approved for a figure.

Return to the trial filters and filter by favorites or tags. This turns the
review decisions into the active pool without deleting the source data.

## 4. Verify the retained pool

Check at least one trial from each participant or condition. Then open the
🗂️ **Data** page and confirm the remaining participant, text, trial,
fixation, and word counts are plausible.

## 5. Export the record

Use **Export → Export bundle** for the active filtered pool. Include the tidy
tables and `plot_config.json`; export figures only if they are part of the
analysis record. Download a **Session → JSON backup** as the human review record.

**Done:** the original data remains intact, the retained pool is reproducible,
and each manual decision has a reason.
