---
description: "Filter eye-tracking data for analysis: exclude unsuitable trials, select participants by metadata, and find the trials with particular fixation patterns."
---

# Filter data

<div class="grid cards" markdown>

- :material-close-octagon-outline:{ .lg .middle } **[Exclude unsuitable trials](exclude-unsuitable-trials.md)**

    Leave tagged trials out.

- :material-account-filter-outline:{ .lg .middle } **[Select participants by a field](select-participants.md)**

    Use participant metadata.

- :material-magnify-scan:{ .lg .middle } **[Find the trials an analysis needs](find-trials-for-an-analysis.md)**

    Select trials after inspecting fixations.

</div>

## Before you start

Open a dataset in Scanpath. The filter button beside Select trial selects
whole trials. Plot controls → Filters & highlights changes which fixations
and saccades the figure draws.

## Check and export the selection { #every-task-ends-the-same-way }

1. Check the remaining trial and participant counts and inspect a few trials.
2. Follow [Export every trial](../exporting-figures/export-every-trial.md),
   choosing the active filtered pool. The bundle's `index.csv` lists its files
   and trial IDs.
3. Keep a full decision record with
   [Data Management → Annotations → Export](../data-collection/check-a-session.md#5-save-the-review).
   Bundle annotations cover only the exported trials.
