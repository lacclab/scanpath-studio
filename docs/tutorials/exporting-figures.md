# Tutorial: export figures

Use this workflow for a publication figure, presentation, supplement, or a
consistent image set for downstream processing.

## 1. Select the view

Choose the participant and trial. Keep only layers that answer the question:

- **Fixations + saccades + text** for a conventional scanpath;
- **Heatmap + text** for spatial concentration;
- **Compare** for two readings of the same text;
- **Animate** for a talk or supplement.

Set the experimental monitor size correctly before adjusting marker sizes or
fonts; it defines the figure's coordinate system.

## 2. Make one clean figure

Use the visualization controls to set colors, opacity, labels, and saccade
style. Prefer the defaults unless a change carries information. Check the whole
canvas for clipped marks, unreadable text, and an unnecessary legend.

Open **Export → This trial** and choose:

| Need | Format |
| --- | --- |
| editable vector | SVG or PDF |
| image for slides/web | PNG |
| interactive inspection | HTML |
| replay | HTML, GIF, or MP4 |

Static image and video formats require Chrome/Chromium; HTML does not.

## 3. Export a batch when needed

In **Export → Multiple trials**:

1. choose the active filtered pool or the whole dataset;
2. select figure and table formats;
3. preview the filename pattern;
4. start the export and inspect one file before using the batch.

For post-production, enable separable layers so text, boxes, fixations,
saccades, heatmap, and stimulus image can be stacked in a vector editor.

## 4. Keep provenance

Save `plot_config.json` with the batch, and download the **💾 Save & restore**
configuration for a single figure. Record the package version, dataset version,
participant/trial identity, and any filtering or drift-correction choice in the
caption or analysis log.

**Done:** the exported files share one visual configuration and can be recreated.
For scripted runs, see [Automation & reference](../automation.md).
