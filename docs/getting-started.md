# Getting started

## Install

=== "pip"

    ```bash
    pip install scanpath-studio
    scanpath-studio          # launches the app in your browser
    ```

=== "conda"

    ```bash
    conda create -n scanpath python=3.12 -y
    conda activate scanpath
    pip install scanpath-studio
    scanpath-studio
    ```

=== "from source"

    ```bash
    git clone https://github.com/lacclab/scanpath-studio.git
    cd scanpath-studio
    pip install -e ".[test]"   # add ,docs for the docs site
    streamlit run streamlit_app.py
    ```

Tested on **Python 3.11–3.14** (CI runs the suite on all four). The fresh-install
path above — `conda create` → `pip install -e ".[test]"` → `pytest` — is verified
to pass end to end on current dependency releases.

### Desktop app (no Python needed)

Standalone builds for **Windows / macOS / Linux** are attached to each
[GitHub release](https://github.com/lacclab/scanpath-studio/releases): download
the archive for your OS, unpack it, and double-click **ScanpathStudio** — it
starts a local server and opens the app in your browser. Everything runs on
your machine; no data leaves it.

!!! note "Unsigned builds"
    The builds are not code-signed yet, so macOS Gatekeeper / Windows
    SmartScreen will warn on first launch (macOS: right-click → *Open*).
    PNG/SVG/PDF and GIF/MP4 export still need a Chrome/Chromium on the machine,
    like the pip install; HTML export works without one.

!!! tip "Static image export needs a browser"
    Interactive **HTML** export is browser-free. **PNG / SVG / PDF** (and GIF /
    MP4 animation) go through [Kaleido](https://github.com/plotly/Kaleido), which
    needs a Chrome/Chromium binary — run `plotly_get_chrome -y` once. See
    [Export & troubleshooting](export-troubleshooting.md).

## Launch the app

Any of these open the Streamlit app (default at <http://localhost:8501>):

```bash
scanpath-studio                       # console entry point
python -m scanpath_studio             # module form
streamlit run streamlit_app.py        # from a source checkout
```

A 3-participant [OneStop](https://github.com/lacclab/OneStop-Eye-Movements) demo
is preloaded, so the app works with zero setup. Switch to **➕ Add data** to
upload your own tables — see [Data format](data-format.md).

## Your first figure (Python)

```python
import scanpath_studio as sps

# Load + normalize (paths, globs, or DataFrames; either table optional)
words, fixations = sps.load_sample_data()      # or load_scanpath_data("ia.csv", "fix.csv")

# What's available?
combos = sps.list_trials(words, fixations)
pid, tid = combos.iloc[0][["participant_id", "trial_id"]]

# Build + save the scanpath (every layer toggle is a kwarg)
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
sps.save_figure(fig, "scanpath.html")          # .html / .png / .svg / .pdf

# Per-word reading measures (FFD / FPRT / RPD / TFD, skips, regressions)
measures = sps.compute_word_metrics(words, fixations)
```

See the full [Python API](api.md) and the [CLI reference](cli.md) for the
headless equivalents.

## Run the tests

```bash
pip install -e ".[test]"
pytest                       # full suite
pytest tests/test_measures.py
ruff check --exclude other_vis .
```
