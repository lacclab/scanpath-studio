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

Open a dataset in the :material/route: **Scanpath** view. The filter
(:material/filter_alt:) beside **Select trial** selects whole trials.
:material/filter_list: **Filters & highlights** in the Plot controls changes
which fixations and saccades the figure draws.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../assets/workflows/trial-filtering_poster.webp" data-autoplay
       aria-label="Narrowing the trial list by condition and participant">
  <source src="../../assets/workflows/trial-filtering.mp4" type="video/mp4">
</video>

## Check and export the selection { #every-task-ends-the-same-way }

1. Check the remaining trial and participant counts and inspect a few trials.
2. Follow [Export every trial](../exporting-figures/export-every-trial.md) and
   choose **All filtered trials**. The bundle's `index.csv` lists its files
   with their participant and trial IDs.
3. Keep a full decision record with
   [Data Management → Annotations → Export](../data-collection/check-a-session.md#5-save-the-review).
   The annotations in a bundle cover only the exported trials.
