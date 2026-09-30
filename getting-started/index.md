# Getting started

## 1. Choose how to run it

Open the [live demo](https://scanpath-studio.streamlit.app). Use only public or non-sensitive data on the hosted service.

```
pip install scanpath-studio
scanpath-studio
```

Requires Python 3.11–3.14 and opens the app at <http://localhost:8501>.

Download the build for your operating system — [macOS (Apple silicon)](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-macos-arm64.dmg) · [Windows](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-windows-x86_64.zip) · [Linux](https://github.com/lacclab/scanpath-studio/releases/latest/download/ScanpathStudio-linux-x86_64.tar.gz) — and launch Scanpath Studio. On macOS that is a `.dmg` you drag to Applications; on Windows and Linux an archive you unpack. See the [desktop notes](https://lacclab.github.io/scanpath-studio/desktop/index.md) for the first-launch steps.

## 2. Make the first plot

1. Keep **Bundled Demo** as the data source.
1. Keep the default participant and trial.
1. Use the layer controls beside the plot to show or hide text, fixations, saccades, bounding boxes, and the heatmap.
1. Turn on **Animate** to replay the trial.
1. Open **Export → Current figure** and download HTML. HTML needs nothing else, nor do a still figure's PNG and SVG; PDF, GIF and MP4 need Chrome, Chromium or Edge.

Next, pick a [tutorial](https://lacclab.github.io/scanpath-studio/tutorials/index.md).

## 3. Load your data

Click **+** beside **Select Dataset**, choose **Import files**, upload your fixation and words/IA tables, check the proposed column mapping, answer **Recording setup**, then select **✅ Add dataset**. See [Loading public and own data](https://lacclab.github.io/scanpath-studio/guides/loading-data/index.md) for accepted formats, manual mapping, and common checks. **🗂️ Data → ➕ Add dataset** opens the same wizard.

## Author a scanpath without files

Choose **+ → Create manually** beside **Select Dataset** when you want to sketch a trial from text instead of uploading tables. Enter the stimulus, inspect the generated word boxes, then edit the scanpath in either place:

- click empty canvas space to add a fixation;
- drag a fixation to change its X/Y coordinate;
- select and delete a fixation on the canvas; or
- edit the event table directly.

The editor starts with one centred fixation per word. X/Y is the authoritative location; **Target word** is optional metadata for reading measures, so a fixation may sit between or outside words. Enter a **Dataset name** and choose **Save dataset** to add it to the dataset list and open its regular visualization. **Cancel** returns to the previous dataset without adding one.

For a ready-made example, choose **Synthetic sample** in the dataset picker: a manually authored six-word example that opens like any other dataset. To change its text, fixation positions, or timing, open it from the list on the 🗂️ **Data** page and choose **Edit dataset**; its draft is separate from your own scanpath. You can also start a scanpath from \*\*🗂️ Data →

- Add dataset → Create manually\*\*.

## Run from source

To run from a source checkout, see the [contributor guide](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md).
