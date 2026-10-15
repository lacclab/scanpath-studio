# Export every trial

The same view across many trials — for a supplement, or as a consistent image set for downstream processing.

## 1. Set the view once

Choose the view as for [one figure](https://lacclab.github.io/scanpath-studio/tutorials/exporting-figures/export-one-figure/#1-choose-the-view); every trial in the batch is drawn with it.

## 2. Build the bundle

In **Export → Export bundle**:

1. choose this trial, the active filtered pool, or the whole dataset;
1. select figure and table formats;
1. preview the filename pattern;
1. start the export and inspect one file before using the batch.

For post-production, enable separable layers so text, boxes, fixations, saccades, heatmap, and stimulus image can be stacked in a vector editor.

\[!\[

\](../../../assets/workflows/export-bundle_poster.webp)\](../../../assets/workflows/export-bundle.mp4)

*Adding PNG and the fixation and word-measure tables, then building a zip of all 24 trials (fast-forwarded) and downloading it.*

## 3. Keep provenance

Keep `plot_config.json` with the batch. The bundle's `README.md` records the package version and which trials it was built from, and `index.csv` lists every file with its participant, trial and screen, and any that failed. Record the dataset version and the trial filters you used in the caption or analysis log — the export does not store them.

**Done:** the exported files share one visual configuration and can be recreated. For scripted runs, see [Automation](https://lacclab.github.io/scanpath-studio/automation/index.md).
