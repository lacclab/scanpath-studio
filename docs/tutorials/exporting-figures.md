# Tutorial: export figures

Use this workflow for a publication figure, presentation, supplement, or a
consistent image set for downstream processing.

## 1. Select the view

Choose the participant and trial. Keep only layers that answer the question:

- **Fixations + saccades + text** for a conventional scanpath;
- **Heatmap + text** for spatial concentration;
- **Compare** for two trials of the same text;
- **Animate** for a talk or supplement.

Set the monitor size first, under :material/database: **Data Management → Edit
dataset → Recording setup**; it defines the figure's coordinate system.

## 2. Make one clean figure

Check the whole canvas for clipped marks, unreadable text, and an unnecessary
legend. When several figures must share identical grid marks, set a manual
interval under **:material/aspect_ratio: Figure & canvas → :material/grid_on: Axes & grid → Grid** (untick **Auto**).

Open **Export → Current figure** and choose:

| Need | Format |
| --- | --- |
| editable vector | SVG or PDF |
| image for slides/web | PNG |
| interactive inspection | HTML |
| replay | HTML, GIF, or MP4 |

PNG and SVG are saved by your browser from the figure on screen, and HTML
needs nothing either (it loads Plotly from the internet when opened, or tick
**Self-contained HTML** for a larger file that opens offline); PDF, GIF
and MP4 need Chrome, Chromium or Edge. For print, give the PNG a **Width**
(mm or in) and a **DPI**: 180 mm at 600 dpi is 4,252 px wide, and
**Share → Code** writes the same size. Without a width, the plot's own camera
button saves the same PNG.

## 3. Export a batch when needed

In **Export → Export bundle**:

1. choose this trial, the active filtered pool, or the whole dataset;
2. select figure and table formats;
3. preview the filename pattern;
4. start the export and inspect one file before using the batch.

For post-production, enable separable layers so text, boxes, fixations,
saccades, heatmap, and stimulus image can be stacked in a vector editor.

## 4. Keep provenance

Keep `plot_config.json` with the batch (or a **:material/share: Share → File** settings file
for a single figure). The bundle's `README.md` records the package version and
which trials it was built from, and `index.csv` lists every file with its
participant, trial and screen, and any that failed. Record the dataset version and
the trial filters you used in the caption or analysis log — the export does not
store them.

**Done:** the exported files share one visual configuration and can be recreated.
For scripted runs, see [Automation](../automation.md).
