# Manuscript scripts

Every figure and every number in the Scanpath Studio manuscript is produced by a
script in this directory, so an archived release of the software is enough to
reproduce them. Each script drives the package's own public API — the same
pipeline the app uses — rather than a private analysis path.

## Running

Run from the repository root so the package and its environment resolve:

```bash
cd app && uv run python paper/paper_figs.py
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
| `paper_fig_potec.py` | `fig_potec` | PoTeC under `data/PoTeC` (`download=True` on first use) |
| `paper_fig_drift.py` | `fig_drift` | PoTeC under `data/PoTeC` |
| `paper_fig_multipleye.py` | `fig_multipleye` | MultiplEYE ZH pilot under `data/MultiplEYE_ZH_CH_Zurich_1_2025` |
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

- `paper_stats.py` runs the measure validation twice, under both word-boundary
  conventions — see its module docstring, and `measures.word_box_bounds`.
- Figures are rendered through Kaleido, which needs a Chrome/Chromium binary
  (`plotly_get_chrome -y` once, locally).
