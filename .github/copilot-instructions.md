# Copilot Instructions — Scanpath Visualization

## Big Picture
This repo’s primary product is a Streamlit workbench packaged as `scanpath_visualization_app/`. It visualizes eye-tracking scanpaths over text (word boxes + fixations + saccades + heatmaps + comparisons). Legacy/experiments live under `other_vis/`.

## Architecture & Data Flow (core path)
- Entry/UI: `scanpath_visualization_app/app.py` (tabs, uploads, trial selection, filtering, calls plotting)
- Data handling: `scanpath_visualization_app/data.py` (schema inference + normalization + filtering + metrics)
- Plotting: `scanpath_visualization_app/plots.py` (Plotly figure builders)
- Controls/defaults: `scanpath_visualization_app/controls.py`, `scanpath_visualization_app/constants.py`

Pipeline: uploaded CSVs → `infer_*_schema()` → `normalize_*()` to canonical columns → filters/metrics → `make_*_figure()` → Streamlit render.

## Input Formats & Normalization
- The Streamlit app currently accepts **CSV** uploads (“Words/IA csv” + “Fixations csv”) and ships demo CSVs in `scanpath_visualization_app/sample_data/`.
- Canonical columns used by plotting:
	- Words: `participant_id`, `trial_id`, `paragraph_id`, `word_id`, `text`, `line_idx`, `x`, `y`, `width`, `height`
	- Fixations: `participant_id`, `trial_id`, `paragraph_id`, `x`, `y`, `duration_ms`, `timestamp_ms` (+ optional `word_id`, `pass_index`, `saccade_type`, `eye`, `noise_flag`)
	- Raw gaze (optional overlay): normalized by `infer_raw_gaze_schema()` / `normalize_raw_gaze()`.

## Column Auto-Detection Convention
Schema inference uses `pick_column(df, candidates)` with **priority-ordered candidate lists**. When adding support for new upstream names, update the relevant `infer_*_schema` candidate lists in `scanpath_visualization_app/data.py`.

## Plot/Coordinate Conventions
- Screen coordinates: Plotly y-axis is inverted (`y_range = [max, min]`) in `make_scanpath_figure()`.
- Word boxes and word-level heatmap overlays are implemented with Plotly `layout.shapes` (see `build_word_boxes()` and heatmap shape generation).

## Running & Dev Workflows
- Use the existing conda env `scanpath-visualization` (prefer `mamba activate scanpath-visualization` if available).
- Run app (dev): `streamlit run scanpath_visualization_app/app.py`
- Run app (packaged): `python -m scanpath_visualization_app` (see `scanpath_visualization_app/__main__.py`) or the console script `scanpath-visualization`.
- Fast dev setup (if you have uv): `uv sync` then `uv run streamlit run scanpath_visualization_app/app.py`.
- Tests: `conda run -n scanpath-visualization pytest` (see `tests/README.md`). Streamlit calls are mocked in tests, so test utilities rather than full UI runtime.
- Lint/format: use the same conda env and keep legacy `other_vis/` excluded: `conda run -n scanpath-visualization ruff check --fix --exclude other_vis .`, then `conda run -n scanpath-visualization ruff check --select I --fix --exclude other_vis .`, then `conda run -n scanpath-visualization ruff format --exclude other_vis .`.

## Import Mode Gotcha
`app.py` supports both package imports (`from .data import ...`) and a fallback “direct run” path tweak for `streamlit run .../app.py`. Keep this pattern intact when refactoring imports.
