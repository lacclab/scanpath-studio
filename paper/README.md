# Manuscript scripts

These scripts rebuild the case-study figures, descriptive statistics and runtime
table using the package's figure builders and analysis functions. Use the
software revision and data from the manuscript revision you are reproducing.
Runtime measurements also depend on the machine.

## Running

Run from the repository root so the package and its environment resolve:

```bash
uv run python paper/paper_figs.py
```

Rendered figures land in `paper/figures/`. To write straight into a manuscript
tree instead, set `PAPER_FIGURES_DIR`:

```bash
PAPER_FIGURES_DIR=../overleaf/figures uv run python paper/paper_figs.py
```

## What each script produces

| Script | Output | Data needed |
| --- | --- | --- |
| `paper_figs.py` | `fig_scanpath`, `fig_comparison`, `fig_replay` | bundled demo (none) |
| `paper_fig_architecture.py` | `fig1_architecture.pdf` | none |
| `paper_fig_potec.py` | `fig_potec` | a local PoTeC copy under `data/PoTeC` |
| `paper_fig_drift.py` | `fig_drift` | PoTeC under `data/PoTeC` |
| `paper_fig_corpus.py` | `fig_corpus` | full OneStop under `data/OneStop` (`datasets.download_onestop`) |
| `paper_stats.py` | case-study descriptives + the measure validation | bundled demo (none) |
| `paper_timings.py` | the runtime table | bundled demo, plus PoTeC for the long-trial row |
| `paper_ui_screenshots.py` | `fig_interface`, `fig_ui_*` | a **running app** to point a browser at (see below) |

The corpus scripts look for their inputs relative to the working directory.
From the repository root, put the PoTeC checkout at `data/PoTeC/` and the two
ordinary-reading reports at these paths. Existing data directories can be
linked into place.

```text
data/OneStop/ia_Paragraph_ordinary.csv.zip
data/OneStop/fixations_Paragraph_ordinary.csv.zip
```

Run `uv run python paper/paper_fig_corpus.py` to check the OneStop figure.
The ordinary reports select passage `1_0_1_Adv` with 60 readers and 128 words.
The figure omits words 1 and 128 and shows 24 readers in panel A. Panel C
calculates each word's rate over readers with a recorded value for that flag.
The PNG includes the software and dataset citations.

For the interface screenshots, start the app in one terminal.

```bash
uv run streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8599
```

In another terminal, run the screenshot driver. It opens the running app in
headless Chromium.

```bash
PAPER_FIGURES_DIR=../overleaf/figures \
    uv run --with playwright python paper/paper_ui_screenshots.py
```

Install Playwright's browser with `uv run --with playwright playwright install chromium`,
or set `PAPER_CHROME` to an existing Chrome binary. Set `PAPER_APP_URL` to
capture another running instance. The default is `http://localhost:8599`.
The filenames `fig_interface` and `fig_ui_*` are reserved for screenshots.

## Notes

- Run `SCANPATH_EXPERIMENTAL=1 uv run python paper/paper_stats.py` for the
  experimental reading measures. The validation reassigns fixations from the
  recorded word rectangles and compares the resulting measures with the
  EyeLink IA report. The current bundled files contain 2,614 word rows, 3,209
  fixations and 24 readings. The script prints how many words enter each
  comparison.
- The architecture PDF uses Matplotlib. Run
  `uv run --with matplotlib python paper/paper_fig_architecture.py`.
- The PoTeC and drift figures read the same local corpus. The drift figure
  applies the experimental Warp line-assignment algorithm to reader 0's
  reading of text b0.
- Figures are rendered through Kaleido, which needs a Chrome/Chromium binary
  (`plotly_get_chrome -y` once, locally).

For a small reproducible study with synthetic data, a tagged exclusion, a manuscript panel and a checked cohort CSV, see the [coauthor example](../scanpath_studio/sample_data/coauthor/README.md).
