---
description: "Analyze an eye-tracking reading corpus: compare participants on one text, compare groups or conditions, and follow a reading measure over time."
---

# Analyze a corpus

<div class="grid cards" markdown>

- :material-text-box-search-outline:{ .lg .middle } **[Analyze one text](analyze-one-text.md)**

    Compare word-by-word measures across participants.

- :material-chart-box:{ .lg .middle } **[Compare groups or conditions](compare-groups.md)**

    Inspect group means and differences.

- :material-chart-timeline-variant:{ .lg .middle } **[See progression over time](progression-over-time.md)**

    Inspect trends within or across trials.

</div>

## Before you start

Open a dataset and set the trial filters for your question. Word-level views
need [reading measures in the Words table](../../guides/loading-data/index.md#reading-measures);
the bundled demo includes them. To compare participants on one text, their
trials of that text must share one text ID.

## Keep the result

**⬇ Download this table (CSV)** saves the values. **⬇ Download the recipe
(JSON)** saves the dataset name, the trial filters, the analysis choices and the
counts. The recipe names the dataset but holds none of its data, so keep the
source data to reproduce the result.

To draw a summary with Python or the CLI, see
[Plot a summary in code](../../guides/corpus-workspace/index.md#plot-a-summary-in-code).
