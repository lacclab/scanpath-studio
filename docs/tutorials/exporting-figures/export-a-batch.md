# Export a batch

In **Export → Export bundle**:

1. choose this trial, the active filtered pool, or the whole dataset;
2. select figure and table formats;
3. preview the filename pattern;
4. start the export and inspect one file before using the batch.

For post-production, enable separable layers so text, boxes, fixations,
saccades, heatmap, and stimulus image can be stacked in a vector editor.

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/export-bundle_poster.webp" data-autoplay
       aria-label="Exporting every trial's figures and tables as one zip">
  <source src="../../../assets/workflows/export-bundle.mp4" type="video/mp4">
</video>

*Adding PNG and the fixation and word-measure tables, then building a zip of all 24 trials (fast-forwarded) and downloading it.*

## Keep provenance

Keep `plot_config.json` with the batch (or a **:material/share: Share → File**
settings file for a single figure). The bundle's `README.md` records the package
version and which trials it was built from, and `index.csv` lists every file with
its participant, trial and screen, and any that failed. Record the dataset
version and the trial filters you used in the caption or analysis log — the
export does not store them.

**Done:** the exported files share one visual configuration and can be
recreated. For scripted runs, see [Automation](../../automation.md).
