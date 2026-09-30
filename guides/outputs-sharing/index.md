# Outputs and sharing

## Export results

Open the **Export** subtab in the Scanpath view.

- **Current figure** exports the visible static or animated figure.
- **Export bundle** packages figures, tables, and configuration metadata for this trial, a filtered subset, or the whole dataset. Its **Also include → Separable layers** toggle adds aligned text, boxes, fixations, saccades, heatmap, and image layers as separate files for editing, and **Tabular data → Full measure family** adds saccades, sentence measures, trial and reader summaries, character grids, cleaning QA and `run_config.json` — per trial and concatenated under `aggregate/`. **Tabular data → Raw gaze** writes each exported trial's gaze samples as recorded, as `raw_gaze.csv` (or `.parquet`) beside its other tables; a trial with no samples gets none. The bundle's figures draw the samples whenever the 🔵 **Raw gaze** layer is on. **Also include → Annotations (JSON)** adds `annotations.json`: the favorites, tags and notes on the exported trials, which 🗂️ Data → Annotations can import.

With a [participant metadata](https://lacclab.github.io/scanpath-studio/data-format/#participant-metadata) table attached, the bundle also carries `metadata/participants.*`, and **Participant fields to include** chooses which of its columns go in. Every field is selected by default; clearing one drops it, and clearing them all leaves the table out entirely.

HTML is interactive and needs no local browser engine. PNG, SVG, PDF, GIF, and MP4 use Chrome/Chromium through Kaleido. See [Export troubleshooting](https://lacclab.github.io/scanpath-studio/export-troubleshooting/index.md) if those formats fail.

## Share a view

The **Share** subtab has three ways to pass the figure on — **Link**, **Code** and **File**. **Link** is a deep link containing the selected data source and visualization settings; **Refresh & Copy** rebuilds the URL from the current trial and settings and places it on the clipboard in one step. **Code** is the code that reproduces the figure, in Python or as a CLI command. **File** is a settings file, described below.

A link never contains an uploaded or public dataset's fixation or word tables. Built-in data can be reopened from the URL; a recipient of an uploaded-data link must load the same dataset. The one exception is **✏️ Author a scanpath**: there the text and every hand-placed fixation *are* the dataset, so its link carries them.

The link carries every figure setting, including the recording setup and Compare's per-scanpath styles; settings left at the dataset's defaults are omitted to keep it short. Public corpora travel by name, not data: the recipient needs the same corpus set up; otherwise the link leaves the data source unchanged.

## Back up and restore work

Each kind of work has its own file, downloaded where it is edited:

- **🔗 Share → File** — the figure's settings and trial. *Restore settings* re-applies one; settings that don't fit the loaded data are listed and skipped.
- **🗂️ Data → Annotations** — a dataset's favorites, tags and notes, with *Export* and *Import*. Inspect them before sharing: notes may contain participant-related information.
- **✏️ Edit dataset → Save setup** — a dataset's column mapping and recording setup, restored when you add the same kind of data again.
- **🎨 My designs → Export** — your saved figure designs, imported on another computer with *Import*.

None of these files contains uploaded dataset rows; load the same data before restoring them. That differs from the recovery cache, which keeps dataset tables and working state on the current computer and restores them after a refresh or restart — see **Saved on this computer** at the foot of the 🗂️ Data page.

For repeatable scripted output, use [Automation](https://lacclab.github.io/scanpath-studio/automation/index.md).
