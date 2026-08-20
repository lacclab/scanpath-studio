# Outputs and sharing

Scanpath Studio separates exported results from ways to reproduce a view.

## Export results

Open the **Export** subtab in the Scanpath view.

- **Current figure** exports the visible static or animated figure.
- **Export bundle** packages figures, tables, and configuration metadata for
  this trial, a filtered subset, or the whole dataset.
- **Separable layers** writes aligned text, boxes, fixations, saccades, heatmap,
  and image layers for editing.

With a [participant metadata](../data-format.md#participant-metadata) table
attached, the bundle also carries `metadata/participants.*`, and **Participant
fields to include** chooses which of its columns go in. Every field is selected
by default; clearing one drops it, and clearing them all leaves the table out
entirely. Reader attributes are the most re-identifying thing an export can
carry, so decide this per bundle — full detail for a collaborator, a group label
for a public repository.

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
visualization settings. **Refresh & Copy** rebuilds the URL from the current
trial and settings and places it on the clipboard in one step.

A link never contains the fixation or word tables. Built-in data can be reopened
from the URL; a recipient of an uploaded-data link must load the same dataset.

Public corpora travel too: the link names the corpus (`?source=corpus&corpus=…`)
rather than its data. For a harmonised benchmark corpus the recipient needs their
own prepared bundle containing it — the Share panel says which corpus the link
names, and opening a link for a corpus that isn't available leaves the data
source where it was instead of switching to a different one.

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
