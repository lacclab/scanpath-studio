# Getting started

This page gets you from installation to one exported scanpath. It uses the
bundled sample, so no data preparation is required.

## 1. Choose how to run it { #install }

=== "Try online"

    Open the [live demo](https://scanpath-studio.streamlit.app). Use only public
    or non-sensitive data on the hosted service.

=== "Install with pip"

    ```bash
    pip install scanpath-studio
    scanpath-studio
    ```

    Requires Python 3.11–3.14 and opens the app at
    <http://localhost:8501>.

=== "Desktop app"

    Download the archive for your operating system from the
    [latest release](https://github.com/lacclab/scanpath-studio/releases/latest),
    unpack it, and launch Scanpath Studio. See the [desktop notes](desktop.md)
    if your OS blocks the unsigned build.

## 2. Make the first plot

1. Keep **Bundled demo** as the data source.
2. Keep the default participant and trial.
3. Use the layer controls beside the plot to show or hide text, fixations,
   saccades, word boxes, and the heatmap.
4. Turn on **Animate** to replay the trial.
5. Open **Export**, choose **This trial**, and download HTML. HTML works without
   extra software; PNG, SVG, PDF, GIF, and MP4 require Chrome/Chromium.

That is the default workflow. You can now follow a tutorial for
[data collection](tutorials/data-collection.md),
[data filtering](tutorials/data-filtering.md),
[figure export](tutorials/exporting-figures.md), or
[corpus analysis](tutorials/corpus-analysis.md).

## 3. Load your data

Select **➕ Add data** and work down the setup wizard:

1. name the dataset and enter the experiment's monitor size;
2. upload a words/IA table and a fixations table;
3. check the proposed participant, trial, text, position, and duration columns;
4. select **Add dataset**.

See [Loading public and own data](guides/loading-data.md) for accepted formats,
manual mapping, and common checks.

## Author a scanpath without files

Choose **Author a scanpath** as the data source when you want to sketch a trial
from text instead of uploading tables. Enter the stimulus, inspect the generated
word boxes, then edit the scanpath in either place:

- click empty canvas space to add a fixation;
- drag a fixation to change its X/Y coordinate;
- select and delete a fixation on the canvas; or
- edit the event table directly.

The editor starts with one centred fixation per word. X/Y is the authoritative
location; **Target word** is optional metadata for reading measures, so a
fixation may sit between or outside words. Download the authoring JSON to reopen
the same layout later, render it with `scanpath-studio render --authoring`, or
load it with `scanpath_studio.load_authored_scanpath`.

## Static export setup

If HTML exports but static images do not, install the browser used by Plotly:

```bash
plotly_get_chrome -y
```

More fixes are in [Export troubleshooting](export-troubleshooting.md).

## Run from source

Contributors can install the repository directly:

```bash
git clone https://github.com/lacclab/scanpath-studio.git
cd scanpath-studio
pip install -e ".[test,docs]"
streamlit run streamlit_app.py
```

Development commands belong in the
[contributor guide](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md),
not in the user workflow.
