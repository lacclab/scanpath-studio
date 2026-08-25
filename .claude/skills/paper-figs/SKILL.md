---
name: paper-figs
description: Regenerate the manuscript figures/stats from paper/*.py and sync them into the Overleaf tree (../overleaf/figures), then optionally recompile the manuscript to verify nothing broke.
disable-model-invocation: true
---

# Paper figures — regenerate and sync

Every figure and number in the manuscript is produced by a script in
`paper/`, driving the package's own public API. Argument (optional): which
figures/scripts to regenerate (e.g. `drift`, `all`, `stats`); default is the
no-external-data set (`paper_figs.py` + `paper_fig_architecture.py`).

Run from the repository root (`app/`).

## Script → output map

| Script | Output | Data needed |
| --- | --- | --- |
| `paper_figs.py` | `fig_scanpath`, `fig_comparison`, `fig_replay` | bundled demo (none) |
| `paper_fig_architecture.py` | `fig1_architecture.pdf` | none |
| `paper_fig_potec.py` | `fig_potec` | PoTeC under `data/PoTeC` (`download=True` first use) |
| `paper_fig_drift.py` | `fig_drift` | PoTeC under `data/PoTeC` |
| `paper_fig_multipleye.py` | `fig_multipleye` | MultiplEYE ZH pilot under `data/MultiplEYE_ZH_CH_Zurich_1_2025` |
| `paper_fig_corpus.py` | `fig_corpus` | full OneStop under `data/OneStop` (`datasets.download_onestop`) |
| `paper_stats.py` | case-study descriptives + measure validation | bundled demo (none) |
| `paper_timings.py` | runtime table | bundled demo + PoTeC |
| `paper_ui_screenshots.py` | `fig_interface`, `fig_ui_*` | a **running app** — see step 6 |

`fig_interface` and the `fig_ui_*` figures are screenshots of the running app.
They come only from `paper_ui_screenshots.py` (step 6) — never overwrite one
from a headless script.

## Steps

1. Check required data exists under `data/` for the requested scripts; if a
   dataset is missing, say which script needs it and how it downloads, and
   skip that script rather than triggering a large download unasked.
2. Render straight into the manuscript tree:
   `PAPER_FIGURES_DIR=../overleaf/figures uv run python paper/<script>.py`
   (without the env var, outputs land in `paper/figures/`).
   Kaleido needs a Chrome/Chromium binary — if rendering fails with a Chrome
   error, run `uv run plotly_get_chrome -y` once and retry.
3. For `paper_stats.py` / `paper_timings.py`, capture the printed numbers and
   report them; if the manuscript (`../overleaf/sn-article.tex`) hardcodes
   values that changed, list the mismatches — don't silently edit the .tex
   unless asked.
4. Verify: `git -C ../overleaf status` (if it's a repo) or list
   `../overleaf/figures` timestamps to confirm which figures changed.
5. Optional (if requested or figures changed): recompile the manuscript with
   `latexmk -pdf sn-article.tex` in `../overleaf/` and report any errors.
6. **Interface figures** (only when asked for them, or for `all`): these need
   the app up. Start it — `uv run streamlit run streamlit_app.py --server.port
   8599`, or the `scanpath` entry in `.claude/launch.json` — then run
   `PAPER_FIGURES_DIR=../overleaf/figures uv run --with playwright python
   paper/paper_ui_screenshots.py`. Playwright's Chromium must be installed
   (`playwright install chromium`, or set `PAPER_CHROME`). The script leaves
   the app on the Data page with nothing half-set-up; open the captures and
   look at them before reporting, since a mid-rerun capture fails silently as a
   blank or half-drawn panel.
