# AGENTS.md — Scanpath Studio

Architectural map for AI agents (Claude, Copilot) modifying this code.

## Project

Interactive Streamlit workbench for **eye-tracking-while-reading** scanpath
visualization. Targeted at reading-research / NLP audiences. Distributed as the
PyPI package `scanpath-studio`; deployable to Streamlit Community
Cloud via `streamlit_app.py` at the repo root.

Demo corpus: 3 participants × 2 articles × {Adv, Ele} from **OneStop Eye
Movements** (Berzak, Malmaud, Shubi, Meiri, Lion, Levy, *Scientific Data* 2025;
[doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2);
docs at <https://lacclab.github.io/OneStop-Eye-Movements/>), shipped under
`sample_data/` as both CSV and Parquet. Linguistic features
(`gpt2_surprisal`, `wordfreq_frequency`, `subtlex_frequency`, `universal_pos`,
`ptb_pos`, `dependency_relation`, etc.) are preserved.

## Architecture

```text
scanpath_studio/
├─ app.py            entry point: page config, data load, trial filters, dispatch to tabs
├─ url_state.py      deep links + plot-config save/restore (versioned via `PLOT_CONFIG_SCHEMA` + `_migrate_plot_config` — ENG-11) + Share link, incl. the DATA-16/S3 "What the link includes" identity picker (`_SHARE_IDENTITY_MODES` → `_build_share_query(include_participant=, include_trial=)`) + the `main_nav` view helpers (`_active_view`/`_go_corpus`/`_go_scanpath`) the top nav reconciles against (split from app.py)
├─ menu.py          UX-38: the top menu bar that replaced the sidebar — `render_top_menu` reserves one popover per former sidebar group (Configure · Preprocessing · Save & restore · Recovery cache · Help · Debug) plus a main-area `notices` slot, and `render_nav` draws Streamlit's native `st.navigation(position="top")` and returns the active view. Nothing in the app writes to `st.sidebar`
├─ session_keys.py   the session-state keys / URL params that are a wire format (share links + saved configs), as constants + frozen groupings — pinned by tests/test_session_key_contract.py so a rename fails a test instead of a user's old link (ENG-6)
├─ wizard.py         the Upload / Add-dataset wizard — guided data-setup flow (split from app.py)
├─ wizard_shell.py   DATA-22: the wizard's seven-step registry, keyed-expander accordion, progress chips and navigation (no column/frame knowledge)
├─ experimental_setup.py  pure display-geometry conversions + `SetupSnapshot` — one dataset's screen/typography with a per-group `Provenance` (measured/estimated/assumed/skipped)
├─ compare_source.py  CMP-8: the *second* dataset a comparison draws scanpath B from — a widget-free readiness gate + loader (`secondary_dataset_options` / `load_secondary_dataset` → `SecondaryDataset`)
├─ tabs.py           tab implementations (Scanpath Visualization [Annotations + Stimulus & questions + Comparisons (same-text scanpaths grouped by a chosen column; NLD scoring + the Line assignment drift-correction grid are gated off by default — PRE-21) + Export subtabs — all top-level, no nesting; Export folds in single-trial + bulk export], Corpus Analysis [Per text · Per reader · Groups (one cohort, or two behind a Compare toggle) subtabs — the question-oriented analysis sections, AN-1..28], Data Inspection)
├─ aggregation.py    pure corpus-level aggregation helpers for the Corpus Analysis sections (measure registry + per-reader/cohort word profiles, word-vs-feature, rates, reader distributions/summary/landing, group masks + difference/effect-size; plus the legacy trial-index/fixation-index trends)
├─ controls.py       the Scanpath rail's plot controls (presets + palette, then collapsible 👁️ Fixations / ↗️ Saccades / 📄 Stimulus / 🔥 Overlays sections — each `toggle → ⚙️ style → 🧹 filter` — and merged 📐 Figure & canvas, itself grouped into 🖥️ Screen & geometry / 🔤 Text & fonts / 📊 Axes & grid / 🏷️ Title & labels) + column-mapping override UI + trial-filter panel
├─ data.py           schema inference, normalization, filtering (incl. condition/annotation trial filters), sample loaders
├─ multipart.py      ordered child-screen identity + validation, nested manifest assignment, per-screen extraction/catalogue/canvas helpers
├─ datasets.py       public-corpus ownership (PoTeC, MultiplEYE, OneStop), including server-bundle discovery, feeding the app + headless API. MultiplEYE models one reading of a stimulus as one trial whose `screen_id`s are the reading pages **and** the comprehension-question screens (DATA-24)
├─ measures.py       canonical reading measures (FFD, FPRT, RPD, TFD, regressions), run materialization, and geometry helpers
├─ preprocessing.py  optional soft-exclusion/merge pipeline + pass, sentence, saccade, character, RTL, QA, and sensitivity tables
├─ authoring.py      deterministic text/word layout + stable hand-authored fixation reducers and versioned JSON round-trip
├─ authoring_component.py bidirectional click/add/drag/select/delete canvas for authored events
├─ illustration.py   detects geometry-changing/synthetic views that require an Illustration disclosure
├─ alignment.py      vertical drift-correction: native port of the ten Carr et al. (2021) line-assignment algorithms (PRE-3). Not exposed by default — PRE-21 gates it (and similarity.py) behind SCANPATH_EXPERIMENTAL=1
├─ similarity.py     scanpath similarity metrics (NLD etc.) scoring the Comparisons subtab
├─ metadata.py       DATA-20 §1: keyed, entity-level metadata tables — `ParticipantMetadata` (validated frame + `MetadataField` registry + `JoinReport`), built by `build_participant_metadata`. Three narrow consumers, and the table is **never** broadcast onto words/fixations: `participants_matching` turns a participant-grain constraint into reader ids for the existing participant filter, `project` left-joins chosen columns onto a *small* frame (the per-trial `combos`), `to_payload`/`from_payload` round-trip it through save & restore
├─ computations.py   VAL-5: the computation register — 64 `Computation` entries (formula, units, grouping keys, missing behaviour, precedence, code link, tests, consumers, verification tier + status) covering everything that derives or semantically changes a user-visible value. Generates `docs/computations.md` (`python -m scanpath_studio.computations`); `tests/test_computations.py` pins it against `aggregation.MEASURES`, `alignment.ALGORITHMS` and the similarity metric so the catalogue cannot drift from the code
├─ model_scanpaths.py synthetic "model-generated" scanpaths over a real text's word boxes (Comparisons placeholder data)
├─ plots.py          `FigureSettings` is the shared render contract used by UI, API, export, scanpath, animation, and comparison builders; also owns the Plotly builders, render helpers, and separable-layer export
├─ export.py         configurable bulk-export module (PNG/SVG/JSON/CSV/Parquet/mega-table; VIZ-5 separable per-layer files via `plots.split_scanpath_layers`)
├─ animation_export.py rasterize the animated scanpath to GIF/MP4 (warm-Kaleido frame render + Pillow/imageio-ffmpeg encode)
├─ export_status.py  shared export stage/callback vocabulary + deterministic static-byte signatures
├─ tour.py           first-visit/setup guides plus the independent task-tutorial registry, navigation, availability and progress
├─ debug_log.py      in-app debug log + state inspector (logging/print only reach the server terminal)
├─ annotations.py    per-trial favorites/tags/notes (session state) + JSON import/export
├─ persistence.py    ENG-26 on-device recovery cache (localhost/desktop only): uploaded datasets as Parquet + a JSON manifest of mappings/settings/annotations, restored on the next session. ENG-30 exposed it — `cache_status`/`clear_local_state`/`set_persistence_paused` back the "🗄️ Recovery cache" menu panel (`app._render_recovery_cache_panel`), `scanpath-studio cache`, `run --no-persist`, and `api.cache_status`/`clear_cache`
├─ synthetic.py      hand-built ground-truth trial (shared by tests + the "Synthetic test trial" data source)
├─ utils.py          trial-combo construction, trial-selection UI, comparison helpers
├─ constants.py      palette, defaults, citation metadata
├─ styles.py         injected CSS
├─ api.py            headless public API (load/normalize, plot_scanpath, animate_scanpath, save_figure)
├─ cli.py            console entry: `run` launches the app, `render` builds figures headless via api.py
├─ __main__.py       `python -m scanpath_studio` → cli.main
├─ __init__.py       exposes __version__, main(), and lazy re-exports of the api.py surface
├─ onestop_shard.py  one-shot prep: shard the ~15 GB OneStop lacclab CSVs into per-pid Parquet
├─ update_sample_data.py regenerate the bundled demo subset (+ synthesized raw-gaze overlay) from the full OneStop CSVs
└─ sample_data/      bundled demo corpus (CSV + Parquet)
```

### Pipeline

```text
uploaded/sample table(s) → infer_*_schema → normalize_* → canonical columns
                       → filter_data → build_combo_options → tab renderers
                       → make_*_figure / compute_word_metrics / bulk_export
```

### Canonical columns

After `normalize_words` / `normalize_fixations`:

- **Words**: `participant_id`, `trial_id`, `text_id` (canonical name — was
  `paragraph_id`; `unique_*` variants kept when present), `word_id`, `text`,
  `line_idx`, `x`, `y`, `width`, `height`. Plus EyeLink IA columns (`IA_*`
  renamed to `first_fixation_ms`, etc.) and linguistic features when shipped.
- **Multipart words** additionally carry `screen_id`, positive 1-based
  `screen_index`, and optional per-screen `canvas_width` / `canvas_height`.
- **Fixations**: `participant_id`, `trial_id`, `text_id`, `x`, `y`,
  `duration_ms`, `timestamp_ms`, `fixation_id` (synthesized per trial when
  absent), `word_id`, `pass_index`, `saccade_type`, `saccade_amplitude`,
  `eye`, `order_in_trial`, and — when the export carries EyeLink's degree-valued amplitudes — `next_saccade_amplitude_deg` / `prev_saccade_amplitude_deg`, which BUG-25 keeps distinct from the pixel-valued `saccade_amplitude`. (`noise_flag` was removed — it silently dropped
  fixations.)
- **Multipart fixations** retain those parent-global clock/index columns and add
  `screen_id`, `screen_index`, optional `screen_timestamp_ms`,
  `screen_fixation_id`, and per-screen canvas metadata. Scientific grouping
  uses `(participant_id, trial_id, screen_id)`; never connect coordinate spaces.

### Reading measures

`measures.py` computes per (participant, trial, word):
`first_fixation_ms` (FFD), `first_pass_gaze_duration_ms` (FPRT),
`regression_path_duration_ms` (RPD / go-past), `total_fixation_duration_ms`
(TFD), `n_fixations`, `skip_flag`, `regression_in_flag`,
`regression_out_flag`, `first_fix_x/y`. Fixations are enriched with
`saccade_amplitude`, `progression`, `is_regression`, incoming/outgoing angles,
and run/pass columns. Initial landing position/distance, regression-in count,
second-pass duration, and single-fixation duration are also computed. Pre-computed IA values on
the words table take precedence over computed ones.

### Areas of interest (AOIs)

AOIs (word interest areas) are **not computed** by the app — they come directly
from the data's word bounding boxes, supplied either as `(x, y, width, height)`
or as EyeLink's `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)` (which `normalize_words`
converts to `x/y/width/height`). The only thing derived from geometry is the
**fixation→word assignment** in `measures.assign_fixations_to_words`: bounding-box
containment, then nearest word-center within 50 px
(`measures.LINE_MISREGISTRATION_PX`), else `word_id = NaN`. That
assignment feeds the reading measures and the "out-of-text" flag
(`measures.fixation_in_text_mask`); "color by line" derives visual lines from
word-box `y` clustering (`measures.cluster_word_lines`) because `line_idx` is
often a constant in IA exports.

### Participant metadata (DATA-20)

An optional **separate** table, one row per reader, attached on the 🗂️ Data page
(`tabs.render_participant_metadata_section`) or headlessly via
`api.load_participant_metadata` / `render --participant-metadata`. Its columns
behave like fields in the data — trial filters (`filter_meta_<name>` keys, so the
existing clear/mirror/Share machinery applies unchanged), chips, trial sorting,
Data Inspection, and `metadata/participants.*` in the export bundle.

**Never broadcast it onto the word/fixation frames.** A participant-grain
constraint is a participant constraint (`metadata.participants_matching` →
reader ids → the existing `participants` filter slot), and the only join is
`metadata.project` onto the per-trial `combos` frame in `app.main`. Duplicate
reader rows that *disagree* are dropped and reported, never resolved by taking
the first.

### Trial annotations & filtering

`annotations.py` keeps parent-trial and optional screen-scoped favorites / tags /
notes in session state (keyed by `(participant_id, trial_id)` or
`(participant_id, trial_id, screen_id)`), with a pure serialize/deserialize core
and JSON download/restore in the 💾 Save & restore menu panel. `controls.render_trial_filters` (read back via
`controls.read_trial_filters`) +
`data.filter_trials` / `data.filter_to_keys` narrow the trial pool by condition
(Hunting/Gathering via `question_preview`, difficulty, repeated reading,
correctness) and by annotation state (favorites / tags) before `build_combo_options`.

### Improvements tracker handoff

`tracker/data.js` is the original task catalogue. User-authored status changes and
implementation instructions live in `tracker/state.json` and override the matching
items by stable ID. When the user asks to work from the tracker, apply those
overrides first and treat each `implementationBrief` as the task-specific work
instructions; this lets the user scope work in the tracker without repeating it in
chat. Run the editable site with `python3 tracker/server.py` (or
`tracker/start.command`). The live workflow has six statuses: `Backlog`, `Planned`,
`In progress`, `On hold`, `Review`, and `Closed`; `priority` orders work within a status. Tasks
created in the UI live under `createdItems` in the same state file, and their prefix
is derived from their group.

An open item's write-up is **structured fields**, not prose with bold leads:
`request` (required) · `whatWasDone` · `whatsLeft` · `background`, each an array of
markdown lines, plus an optional `statusNote` lede and the `decisions` array.
Omit a field rather than emptying it, never repeat the section label inside the
field, and keep the status current *as you work* — see `CLAUDE.md` → *Tracking
work*. `tests/test_tracker_server.py` pins the shape; archived items keep the
legacy single `body` array and both render.

## Build / Lint / Test

```bash
# Install in editable mode
pip install -e ".[test]"

# Run app
streamlit run streamlit_app.py
uv run streamlit run streamlit_app.py

# Tests
pytest                              # run the full suite
pytest tests/test_measures.py       # one file
pytest --cov                        # coverage; config + floor in pyproject.toml

# Lint
ruff check --exclude other_vis .
ruff check --select I --fix --exclude other_vis .
ruff format --exclude other_vis .

# Regenerate bundled sample data (needs the full OneStop CSVs under sample_data/OneStop/)
python -m scanpath_studio.update_sample_data

# Standalone desktop bundle (ENG-15; needs `pip install . pyinstaller` — non-editable)
pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
python desktop/smoke_test.py     # selfcheck + server-boot smoke test

# Docs site (MkDocs Material; API autodoc via mkdocstrings from docstrings)
pip install -e ".[docs]"
mkdocs serve                 # local preview
mkdocs build --strict        # CI gate (.github/workflows/docs.yml → GitHub Pages)
```

User-facing docs live in `docs/` and publish to
<https://lacclab.github.io/scanpath-studio/>. The Python API reference is
generated from the `api.py` docstrings, so keep those current.

CI on GitHub Actions runs pytest on Python 3.11/3.12/3.13/3.14 plus ruff
lint+format checks on every pull request, and one `pytest --cov` leg that fails
below `[tool.coverage.report] fail_under` in `pyproject.toml` (ENG-37). The
browsable HTML report and the README's coverage badge are published with the
docs site on push to main — see `.github/workflows/docs.yml` → *Coverage report*
— so there is no third-party coverage service and no secret to manage. The two
one-shot data-prep scripts (`onestop_shard.py`, `update_sample_data.py`) are
omitted from the measurement: they walk corpora that cannot exist in CI.

## Code style

- `from __future__ import annotations` at the top of every Python file.
- snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE
  constants. Files: snake_case.py.
- Sorted imports via ruff (`--select I`). stdlib → third-party → local.
- Use `pd.DataFrame` and `np.ndarray` as type hints directly.
- Add return type hints to public functions.
- Streamlit: `@st.cache_data` for expensive loaders. Use `st.warning` (not
  `st.toast`) for per-rerender warnings.
- Plotting: y-axis inverted (`y_range = [max, min]`) for screen coordinates.
  Word boxes + word-level heatmap use `layout.shapes`. Sacccades are a SINGLE
  trace with `None` separators (never one-trace-per-saccade).
- Centralized palette / sizing in `constants.py`. Marker sizes come from
  `plots._compute_marker_sizes` so single-trial and comparison figures render
  identically.

## Testing patterns

- `tests/conftest.py` exposes `sample_words_df`, `sample_fixations_df`,
  `normalized_words_df`, `normalized_fixations_df`, `sample_raw_gaze_df`.
- `tests/test_measures.py` covers FFD, FPRT, RPD, TFD, skip, regressions on a
  synthetic 4-word layout.
- `tests/synthetic_data.py` is a fully-specified 6-word / 2-line trial with
  hand-traced `EXPECTED` values (incl. a regression and one out-of-text
  fixation); `tests/test_synthetic.py` asserts every measure and geometry
  helper exactly. `tests/test_annotations.py` / `tests/test_filters.py` cover
  the annotation core and trial filtering.
- `tests/test_smoke.py` exercises the full pipeline (load → infer → normalize
  → plot) against the bundled sample, including a perf regression that asserts
  saccades collapse to a single trace.
- `tests/test_apptest.py` uses `streamlit.testing.v1.AppTest` to boot the
  whole app and verify title rendering + no `st.error` calls.
- `tests/test_export.py` checks zip structure, CSV/Parquet selection, and
  progress callback behavior.

## Adding a new column convention

Update the candidate lists in `data.py` (e.g. `WORD_X_CANDIDATES`,
`FIX_DURATION_CANDIDATES`). `pick_column` walks the list and picks the
first existing column. Optional passthrough columns (e.g. `saccade_amplitude`,
IA measures) go through the `WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS`
tuple tables instead, applied by `_apply_optional_fields` during
normalization.

## Adding a new reading measure

1. Compute it in `measures.compute_per_word_measures` per trial.
2. Add it to `WORD_OPTIONAL_FIELDS` in `data.py` if it can come pre-computed
   from EyeLink IA columns.
3. Add a `computations.py` register entry (VAL-5) — its formula, unit,
   grouping keys, missing behaviour and precedence. A `MEASURES` entry with no
   register row fails `tests/test_computations.py`.
4. Surface it in `controls.color_field_options` (if useful for coloring) and
   register it in `aggregation.MEASURES` (surfaced via
   `aggregation.available_measures`, which feeds the measure pickers).
5. Add a test under `tests/test_measures.py`.

## Adding a new figure type

1. Add a `make_*_figure` function in `plots.py` using the helpers
   `_compute_axis_ranges`, `_compute_marker_sizes`, `_saccade_segments`,
   `_add_word_label_trace`.
2. Wire it into a tab via `tabs.py` with a Plotly chart call.
3. Add a smoke test in `tests/test_smoke.py` that builds the figure against
   the bundled sample.

## Exposing a feature on every surface

Scanpath Studio has four parallel entry points. A user-facing feature (a new
toggle, option, or parameter) is only "done" when it reaches **all** of them —
not just the UI:

1. **Visual UI** — the Streamlit control (`controls.py` widget + a `global_*` /
   `single_*` / `filter_*` session key, read by `_collect_viz_settings`).
2. **Deep link / Share** — wire it into the URL contract in `url_state.py`:
   `_URL_PRESETS` + `_apply_url_preset` (read) and the inverse `_build_share_query`
   (write), plus `_URL_BOUNDED` if it needs clamping. Without this the feature
   can't be linked to or restored, and the Share widget won't round-trip it.
3. **CLI** — a `render` flag in `cli.py` (follow the per-layer `--no-*` pattern).
4. **Headless API** — a parameter on the relevant `api.py` builder
   (`plot_scanpath` / `animate_scanpath`) plus a default in
   `CANONICAL_FIGURE_DEFAULTS`, so headless output matches the app.

Keep the four in sync: a feature added to the UI but missing from the deep
link / CLI / API silently can't be shared, scripted, or rendered headlessly.

## Releasing

1. Roll the `[Unreleased]` `CHANGELOG.md` notes into a `v<version>` section
   (keep them concise).
2. Bump `__version__` in `scanpath_studio/__init__.py` — the single source of
   truth; `pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic]`).
3. Bump `version` + `date-released` in `CITATION.cff` to match
   (`tests/test_citation.py` enforces version parity).
4. Commit; tag with `v<version>`; push the tag.
5. The `Publish to PyPI` GitHub Actions workflow builds the wheel + sdist and
   publishes via PyPI Trusted Publishing (requires `pypi` environment set up
   on GitHub with the project name `scanpath-studio`).
6. The `Desktop builds` workflow (`.github/workflows/desktop.yml`) builds the
   standalone per-OS desktop bundles (`desktop/` — PyInstaller launcher + spec
   + smoke test; design in `plans/eng-15-desktop-app.md`) and attaches them to
   the GitHub release for the tag.
