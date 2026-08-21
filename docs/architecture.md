# Architecture

For contributors. The full architectural map lives in
[`AGENTS.md`](https://github.com/lacclab/scanpath-studio/blob/main/AGENTS.md) at
the repo root (kept current as the code changes); this is the short version.

## Modules

| Module | Responsibility |
|--------|----------------|
| `app.py` | Streamlit entry point: page config, data load, filtering, and dispatch to the three top-level views (Scanpath Visualization · Corpus Analysis · Data), plus the 💾 Session dialog. |
| `menu.py` | The top navigation and the menu slots that replaced the sidebar — `render_nav` draws Streamlit's native top nav, and 💾 Session and the ❓ Help entries open dialogs over the current view. Nothing in the app writes to `st.sidebar`. |
| `url_state.py` | Deep links + plot-config save/restore (versioned schema + migrations) + the Share link, split out of `app.py`. |
| `wizard.py` | The Upload / Add-dataset guided setup flow. |
| `tabs.py` | View renderers: Scanpath Visualization (Annotations / Stimulus & Context / Comparisons / Export / Share subtabs; Line assignment only under `SCANPATH_EXPERIMENTAL=1`), Corpus Analysis (Per text · Per sentence · Per reader · Groups subtabs — the question-oriented analysis sections), and the Data page's inspection and metadata panels. |
| `controls.py` | Visualization controls (rendered into the Scanpath tab's right-hand rail), column-mapping UI, trial-filter panel. |
| `data.py` | Schema inference, normalization, filtering, sample/OneStop loaders, trial-index derivation. |
| `multipart.py` | Ordered child-screen identity, validation, manifest assignment, screen catalogues, and per-screen canvas metadata. |
| `measures.py` | Canonical reading measures (FFD/FPRT/RPD/TFD, regressions) + geometry helpers. |
| `plots.py` | Plotly figure builders (scanpath, animation, comparison, trends, histograms, heatmaps). |
| `authoring.py` / `authoring_component.py` | Deterministic text/word geometry, stable fixation-event reducers and JSON migration; bidirectional click/drag canvas for the Streamlit authoring source. |
| `aggregation.py` | Pure corpus-level aggregation helpers for the Corpus Analysis sections (measure registry, per-reader/cohort word profiles, distributions, group masks, difference + effect-size). |
| `export.py` | Configurable bulk export (PNG/SVG/JSON/CSV/Parquet/mega-table). |
| `animation_export.py` | Rasterize an animated figure to GIF/MP4. |
| `export_status.py` | Shared honest export stages, validated real-unit progress, and deterministic static-result signatures. |
| `api.py` | Headless public API (re-exported lazily from the package root). |
| `cli.py` | Console entry point (`run` / `render`). |
| `tour.py` | First-visit/setup guides plus the registry and progress for task-oriented in-app tutorials. |
| `annotations.py` | Parent-trial and optional screen-scoped favorites / tags / notes (session state + JSON). |
| `persistence.py` | On-device recovery cache for a local/desktop session (datasets, mappings, settings, annotations), inspected and cleared from the 💾 Session dialog's 🗄️ Automatic recovery block, `scanpath-studio cache`, and `api.cache_status`. |
| `alignment.py` | Vertical drift correction: native port of the ten Carr et al. (2021) line-assignment algorithms. Gated off by default (PRE-21). |
| `datasets.py` | Ready-made loaders for public corpora (OneStop, PoTeC, MultiplEYE) and for the thirty-one [harmonised benchmark corpora](benchmark-corpora.md), each its own data source. |
| `metadata.py` | Keyed participant-metadata tables: a validated frame + field registry, joined only onto the per-trial combos and turned into reader ids for the participant filter — never broadcast onto words or fixations. |
| `computations.py` | The computation register behind [Computations & methodology](computations.md): one entry per user-visible derived value, and the generator for that page. |
| `compare_source.py` | The second dataset compare mode can draw scanpath B from: a widget-free readiness gate + loader, so a comparison can cross corpora without the picker having to render a corpus' folder/download controls. |

The standalone desktop build (launcher, PyInstaller spec, smoke test, CI
matrix) lives outside the package in
[`desktop/`](https://github.com/lacclab/scanpath-studio/tree/main/desktop) —
see the [Desktop app](desktop.md) page and the
[ENG-15 ADR](https://github.com/lacclab/scanpath-studio/blob/main/plans/eng-15-desktop-app.md).

## Pipeline

```text
uploaded / sample table(s)
    → infer_*_schema → normalize_*           (canonical columns)
    → normalize/validate screen identity     (multipart data only)
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
