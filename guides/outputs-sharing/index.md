# Outputs and sharing

## Export results

Open the **Export** subtab in the Scanpath view.

- **Current figure** exports the visible static or animated figure.
- **Export bundle** packages figures, tables, and configuration metadata for this trial, a filtered subset, or the whole dataset. Its **Also include → Separable layers** toggle adds aligned text, boxes, fixations, saccades, heatmap, and image layers as separate files for editing, and **Tabular data → Full measure family** adds saccades, sentence measures, trial and reader summaries, character grids, cleaning QA and `run_config.json` — per trial and concatenated under `aggregate/`.

With a [participant metadata](https://lacclab.github.io/scanpath-studio/data-format/#participant-metadata) table attached, the bundle also carries `metadata/participants.*`, and **Participant fields to include** chooses which of its columns go in. Every field is selected by default; clearing one drops it, and clearing them all leaves the table out entirely.

HTML is interactive and needs no local browser engine. PNG, SVG, PDF, GIF, and MP4 use Chrome/Chromium through Kaleido. See [Export troubleshooting](https://lacclab.github.io/scanpath-studio/export-troubleshooting/index.md) if those formats fail.

## Share a view

The **Share** subtab creates a deep link containing the selected data source and visualization settings. **Refresh & Copy** rebuilds the URL from the current trial and settings and places it on the clipboard in one step. Below it, the code that reproduces the figure, in Python or as a CLI command.

A link never contains an uploaded or public dataset's fixation or word tables. Built-in data can be reopened from the URL; a recipient of an uploaded-data link must load the same dataset. The one exception is **✏️ Author a scanpath**: there the text and every hand-placed fixation *are* the dataset, so its link carries them.

The link carries every figure setting, including the recording setup and Compare's per-scanpath styles; settings left at the dataset's defaults are omitted to keep it short. Public corpora travel by name, not data: the recipient needs the same corpus set up; otherwise the link leaves the data source unchanged.

## Back up and restore work

**Session → JSON backup** downloads the view, mapping, metadata attachments and annotations. It is portable, but it does **not** contain uploaded dataset rows; load the same data before restoring it. Inspect annotations before sharing because notes may contain participant-related information.

This differs from **Automatic recovery**, which keeps dataset tables and working state on the current computer and restores them after a refresh or restart.

For repeatable scripted output, use [Automation](https://lacclab.github.io/scanpath-studio/automation/index.md).
