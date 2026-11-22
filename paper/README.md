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

The interface figures are the one set that cannot be rendered headlessly — they
are screenshots of the application itself. `paper_ui_screenshots.py` drives a
real browser over a running server, so they are reproducible all the same:

```bash
uv run streamlit run streamlit_app.py --server.port 8599   # in one shell
PAPER_FIGURES_DIR=../overleaf/figures \
    uv run --with playwright python paper/paper_ui_screenshots.py
```

It needs Playwright's Chromium (`playwright install chromium`, or point
`PAPER_CHROME` at another Chrome binary) and talks to `PAPER_APP_URL`
(default `http://localhost:8599`). Never overwrite `fig_interface` or a
`fig_ui_*` figure from one of the headless scripts.

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
