# Outputs and sharing

Scanpath Studio separates exported results from ways to reproduce a view.

## Export results

Open the **Export** subtab in the Scanpath view.

- **Current figure** exports the visible static or animated figure.
- **Export bundle** packages figures, tables, and configuration metadata for
  this trial, a filtered subset, or the whole dataset. Its **Also include →
  Separable layers** toggle adds aligned text, boxes, fixations, saccades,
  heatmap, and image layers as separate files for editing.

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

A link never contains an uploaded or public dataset's fixation or word tables.
Built-in data can be reopened from the URL; a recipient of an uploaded-data link
must load the same dataset. The one exception is **✏️ Author a scanpath**: there
the text and every hand-placed fixation *are* the dataset, so its link carries
them (`author_text`, `author_events`).

The link carries every figure setting, including the recording setup and
Compare's per-scanpath styles. Those two groups are written only when they
differ from what the recipient would get anyway — a link to the demo at its own
2560×1440 monitor doesn't restate it — so a link stays short until you change
them:

| Setting | Link parameter |
| --- | --- |
| Monitor size in pixels | `canvas_width`, `canvas_height` |
| Plot font size | `base_font_size` |
| Physical width, viewing distance, display DPI | `monitor_width_mm`, `viewing_distance_mm`, `display_dpi` |
| A font given in points | `use_stimulus_font_pt`, `stimulus_font_pt` |
| Scanpath 1's styles in Compare | `cmp_a_fix_color`, `cmp_a_saccade_color`, `cmp_a_saccade_style`, `cmp_a_saccade_width`, `cmp_a_marker_size_range`, `cmp_a_opacity`, `cmp_a_hollow`, `cmp_a_label_pattern` |
| Scanpath 2's styles in Compare | the same, as `cmp_b_*` |

The monitor size of a source that declares no screen of its own (the synthetic
trial, an authored scanpath) is always written, since there is nothing to compare
it with. The Compare styles travel only with the comparison they describe
(`?compare=`). A value outside its control's range is clamped to it, and one
the control can't show at all — an unknown line style, a colour that isn't
`#rrggbb` — is dropped with a warning.

Public corpora travel too: the link names the corpus (`?source=corpus&corpus=…`)
rather than its data. For a harmonised benchmark corpus the recipient needs their
own prepared bundle containing it — the Share panel says which corpus the link
names, and opening a link for a corpus that isn't available leaves the data
source where it was instead of switching to a different one.

## Back up and restore work

**Session → JSON backup** downloads the view, mapping, metadata attachments and
annotations. It is portable, but it does **not** contain uploaded dataset rows;
load the same data before restoring it. Use it to continue work, attach a
reproducible bug report, or preserve a manual review. Inspect annotations before
sharing because notes may contain participant-related information.

This differs from **Automatic recovery**, which keeps dataset tables and working
state on the current computer and restores them after a refresh or restart.

## Keep an output reproducible

For a figure or batch, retain:

- the source dataset/version and participant/trial selection;
- the Scanpath Studio version;
- the saved configuration or batch `plot_config.json`;
- any trial filtering, fixation filtering, or drift correction applied.

For repeatable scripted output, use [Automation & reference](../automation.md).
