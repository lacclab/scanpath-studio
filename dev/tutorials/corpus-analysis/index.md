# Analyze a corpus

- **[Analyze one text](https://lacclab.github.io/scanpath-studio/dev/tutorials/corpus-analysis/analyze-one-text/index.md)**

  Compare word-by-word measures across participants.

- **[Compare groups or conditions](https://lacclab.github.io/scanpath-studio/dev/tutorials/corpus-analysis/compare-groups/index.md)**

  Inspect group means and differences.

- **[Track changes over time](https://lacclab.github.io/scanpath-studio/dev/tutorials/corpus-analysis/progression-over-time/index.md)**

  Inspect trends within or across trials.

## Before you start

Open a dataset and set the trial filters for your question. Word-level views need [reading measures in the Words table](https://lacclab.github.io/scanpath-studio/dev/guides/loading-data/#reading-measures); the bundled demo includes them. To compare participants on one text, their trials of that text must share one text ID.

Choose **Texts** to compare passages or **Participants** to compare readers. Select a dot to see its mean, range and how many readings contributed. **Open word profile** shows where in a text the values change. **Open participant profile** compares one reader’s word values with the others.

## Keep the result

Open **Table and downloads** under a text or participant comparison. In a detailed analysis that produces a table, use **Download results**. The CSV saves the values. **Download recipe (JSON)** saves the dataset name, the trial filters, the analysis choices and the counts. Keep the source data alongside the recipe so you can reproduce the result.

To draw a summary with Python or the CLI, see [Plot a summary in code](https://lacclab.github.io/scanpath-studio/dev/guides/corpus-workspace/#plot-a-summary-in-code).
