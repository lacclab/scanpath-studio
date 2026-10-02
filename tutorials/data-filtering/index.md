# Tutorial: filter data

This workflow finds trials unsuitable for an analysis or publication and leaves an auditable retained pool.

## 1. Narrow the trial pool

Load the dataset, then open the **filter funnel** beside the trial picker: it holds the text and participant pickers together with the condition and annotation filters. Start with broad dataset fields such as participant, condition, correctness, or repeated-reading status. Use the ⇅ trial-ordering popover to surface unusually short or long trials.

If the pool becomes empty, the app names the filter that emptied it and offers to clear just that one.

## 2. Review candidate trials

For each candidate, inspect the default scanpath and turn on **Animate** only when timing helps. Open **Filter → Fixations** in the plot rail and set **Highlight** for:

- out-of-bounds points;
- fixations below or above your duration thresholds.

Use **Fixation index range** in the same place to show only part of the trial.

## 3. Annotate the decision

In **Annotations**, apply a consistent tag vocabulary—for example `exclude`, `review`, `poor-calibration`, or `skimming`—and add a brief reason. Star trials that are useful examples or approved for a figure.

Return to the trial filters and, under **By annotation**, put `exclude` in **Excluding tags** — not in **With any of these tags**, which would keep only the rejected trials. This turns the review decisions into the active pool without deleting the source data. Before you narrow the pool, save the full record with **Data → Annotations → Export**: it lists every trial you tagged, including the ones the filter now hides.

## 4. Verify the retained pool

Check at least one trial from each participant or condition. Then open the **Data Management** page and confirm that the participant, text, trial, fixation, and word counts under **What's in the … dataset → Stats** are plausible. Those follow the filters; the dataset table above them counts the whole dataset.

## 5. Export the record

Use **Export → Export bundle** for the active filtered pool. Include the tidy tables, `plot_config.json` and **Annotations (JSON)** — the tags and notes are the human review record; export figures only if they are part of the analysis record.

**Done:** the original data remains intact, the retained trials are in the export bundle, and each manual decision has a tag and a reason in the annotations file you exported from the Data Management page. (The bundle's `annotations.json` covers only the trials it exports.)
