# Outputs and sharing

Scanpath Studio separates exported results from ways to reproduce a view.

## Export results

Open the **Export** subtab in the Scanpath view.

- **This trial** exports the current static or animated figure.
- **Multiple trials** applies one configuration to the filtered pool or whole
  dataset and can include figures, tables, and configuration metadata.
- **Separable layers** writes aligned text, boxes, fixations, saccades, heatmap,
  and image layers for editing.

Every app export reports its current stage immediately. Frame and trial totals
appear only when the exporter has real countable units; Chrome startup, one
static rasterization, encoding, compression, and zip finalization use an honest
indeterminate state. Ready downloads persist across reruns, while any
output-affecting change invalidates the previous static result.

HTML is interactive and needs no local browser engine. PNG, SVG, PDF, GIF, and
MP4 use Chrome/Chromium through Kaleido. See
[Export troubleshooting](../export-troubleshooting.md) if those formats fail.

## Share a view

The **Share** subtab creates a deep link containing the selected data source and
visualization settings. Choose whether the URL includes participant + trial,
trial only, or settings only.

A link never contains the fixation or word tables. Built-in data can be reopened
from the URL; a recipient of an uploaded-data link must load the same dataset.

## Save and restore work

**💾 Save & restore** downloads a JSON configuration containing the view,
mapping, and annotations. Use it to continue work, attach a reproducible bug
report, or preserve a manual review. Inspect annotations before sharing because
notes may contain participant-related information.

## Keep an output reproducible

For a figure or batch, retain:

- the source dataset/version and participant/trial selection;
- the Scanpath Studio version;
- the saved configuration or batch `plot_config.json`;
- any trial filtering, fixation filtering, or drift correction applied.

For repeatable scripted output, use [Automation & reference](../automation.md).
