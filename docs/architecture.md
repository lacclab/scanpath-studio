# Architecture

For contributors. The full architectural map lives in
[`AGENTS.md`](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md) at
the repo root (kept current as the code changes); this is the short version.

## Modules

| Module | Responsibility |
|--------|----------------|
| `app.py` | Streamlit entry point: page config, URL deep-link presets, sidebar, data load, filtering, and dispatch to the three tabs. |
| `tabs.py` | Tab renderers: Scanpath Visualization (Annotations / Stimulus & questions / Export subtabs — Export folds in the former Bulk Export tab), Corpus Analysis (Generations + Aggregated Views subtabs), Data Inspection. |
| `controls.py` | Visualization controls (rendered into the Scanpath tab's right-hand rail), column-mapping UI, trial-filter panel. |
| `data.py` | Schema inference, normalization, filtering, sample/OneStop loaders, trial-index derivation. |
| `measures.py` | Canonical reading measures (FFD/FPRT/RPD/TFD, regressions) + geometry helpers. |
| `plots.py` | matplotlib figure builders (scanpath, animation, comparison, trends, histograms, heatmaps). |
| `mpl_render.py` | matplotlib rendering helpers: render DPI, px↔point conversions, color/colorscale/dash parsing, exact-pixel figure scaffolding. |
| `aggregation.py` | Pure corpus-level aggregation helpers for the Aggregated Views subtab. |
| `export.py` | Configurable bulk export (PNG/SVG/JSON/CSV/Parquet/mega-table). |
| `animation_export.py` | Rasterize an animated figure to GIF/MP4. |
| `api.py` | Headless public API (re-exported lazily from the package root). |
| `cli.py` | Console entry point (`run` / `render`). |
| `tour.py` | First-visit welcome tour + the dataset-setup guide card. |
| `annotations.py` | Per-trial favorites / tags / notes (session state + JSON). |

## Pipeline

```text
uploaded / sample table(s)
    → infer_*_schema → normalize_*           (canonical columns)
    → filter_data → build_combo_options      (trial pool)
    → make_*_figure / compute_word_metrics / bulk_export
```

## Develop

```bash
pip install -e ".[test]"     # add ,docs for the docs site
pytest
ruff check --exclude other_vis .
ruff format --exclude other_vis .

# Serve these docs locally
pip install -e ".[docs]"
mkdocs serve
```

See [`CONTRIBUTING.md`](https://github.com/lacclab/scanpath-studio/blob/main/CONTRIBUTING.md)
and [`AGENTS.md`](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md)
for the detailed conventions, testing patterns, and gotchas.
