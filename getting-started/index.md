# Getting started

## 1. Choose how to run it

Open the [live demo](https://scanpath-studio.streamlit.app). Use only public or non-sensitive data on the hosted service.

```
pip install scanpath-studio
scanpath-studio
```

Requires Python 3.11–3.14 and opens the app at <http://localhost:8501>.

Download the archive for your operating system — [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip) · [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.tar.gz) · [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz) — unpack it, and launch Scanpath Studio. See the [desktop notes](https://lacclab.github.io/scanpath-studio/desktop/index.md) if your OS blocks the unsigned build.

## 2. Make the first plot

1. Keep **Bundled Demo** as the data source.
1. Keep the default participant and trial.
1. Use the layer controls beside the plot to show or hide text, fixations, saccades, bounding boxes, and the heatmap.
1. Turn on **Animate** to replay the trial.
1. Open **Export → Current figure** and download HTML. HTML needs no Chrome; PNG, SVG, PDF, GIF and MP4 do.

Next, pick a [tutorial](https://lacclab.github.io/scanpath-studio/tutorials/index.md).

## 3. Load your data

Open 🗂️ **Data**, select **➕ Add dataset**, upload your fixation and words/IA tables, check the proposed column mapping, answer **Recording setup**, then select **✅ Add dataset**. See [Loading public and own data](https://lacclab.github.io/scanpath-studio/guides/loading-data/index.md) for accepted formats, manual mapping, and common checks.

## Author a scanpath without files

Choose **✏️ Author a scanpath** as the data source when you want to sketch a trial from text instead of uploading tables. Enter the stimulus, inspect the generated word boxes, then edit the scanpath in either place:

- click empty canvas space to add a fixation;
- drag a fixation to change its X/Y coordinate;
- select and delete a fixation on the canvas; or
- edit the event table directly.

The editor starts with one centred fixation per word. X/Y is the authoritative location; **Target word** is optional metadata for reading measures, so a fixation may sit between or outside words. **💾 Save authoring file** saves the layout as JSON to reopen later, render it with `scanpath-studio render --authoring`, or load it with `scanpath_studio.load_authored_scanpath`.

## Run from source

To run from a source checkout, see the [contributor guide](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md).
