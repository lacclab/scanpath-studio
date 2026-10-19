# AGENTS.md — Scanpath Studio

A map of the codebase for AI coding agents (Claude, Copilot, Codex, …) and for
the people working alongside them: the modules, the data pipeline, the
conventions, and the gotchas that are not obvious from reading one file.
Workflow rules (commits, changelog, tracking work) are in [`CLAUDE.md`](CLAUDE.md);
contributor setup is in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Project

Interactive Streamlit workbench for **eye-tracking-while-reading** scanpath
visualization, for reading-research and NLP audiences. It ships as the PyPI
package `scanpath-studio`, as standalone desktop bundles (`desktop/`), and as a
hosted demo on Streamlit Community Cloud (`streamlit_app.py` at the repo root).

Demo corpus: 2 participants × 2 articles × {Adv, Ele} from **OneStop Eye
Movements** (Berzak, Malmaud, Shubi, Meiri, Lion, Levy, *Scientific Data* 2025;
[doi:10.1038/s41597-025-06272-2](https://doi.org/10.1038/s41597-025-06272-2)),
shipped under `scanpath_studio/sample_data/` as CSV and Parquet. Linguistic
features (`gpt2_surprisal`, `wordfreq_frequency`, `subtlex_frequency`,
`universal_pos`, `ptb_pos`, `dependency_relation`, …) are preserved.

## Architecture

Every entry script — `streamlit_app.py` (Cloud, tests) and
`scanpath_studio/streamlit_entry.py` (what `scanpath-studio run` and the desktop
app launch) — calls `crash_report.run_app`, which imports and runs `app.main`
inside `crash_report.guarded`, so an uncaught error shows a "this is a bug —
report it" note above the traceback. Every `@st.dialog` / `@st.fragment` also
carries `@guarded()`, since Streamlit calls one directly when it reruns on its
own (a test enforces it).

```text
scanpath_studio/
├─ App shell
│  ├─ app.py             entry point: page config, the data-source registry and loaders (`prepare_data`,
│  │                     `_normalize_pair`), trial filters, view dispatch, and the 🗂️ Data Management page
│  │                     (📂 Available datasets, ✏️ Edit dataset, *Saved on this computer*)
│  ├─ menu.py            the header: Streamlit's `st.navigation(position="top")` with three views
│  │                     (🗺️ Scanpath · 📊 Corpus Analysis · 🗂️ Data Management) and ❓ Help's action
│  │                     entries, which arm a dialog and bounce back to the current view
│  ├─ tabs.py            the views' panels: Scanpath (plot + rail + subtabs), Corpus Analysis, the Data page
│  ├─ controls.py        the Scanpath rail, the column-mapping UI and the trial filters
│  ├─ fields.py          the `label | field` row primitive shared by the rail, the wizard and the subtabs
│  ├─ wizard.py          the ➕ Add-dataset wizard (and dataset naming, rename, removal)
│  ├─ wizard_shell.py    the wizard's part registry (`STEPS`) and ✏️ Edit dataset's (`EDITOR_STEPS`)
│  ├─ dataset_table.py   the pure row model behind 📂 Available datasets
│  ├─ url_state.py       deep links, 🔗 Share (Link · Code · File), settings-file save/restore + migrations
│  ├─ session_keys.py    the session keys / URL params that are a wire format, as constants
│  ├─ plot_config.py     the settings-file serializer shared by Share and the export bundle
│  ├─ tour.py            welcome tour, task tutorials and the setup guide
│  ├─ loading.py         loading cards (revealed by a timer thread) with Cancel
│  ├─ progress.py        a Streamlit-free progress + cancel hook for loaders and builders
│  ├─ constants.py       palette, defaults, `ICONS`, citation metadata, experimental-feature gates
│  ├─ styles.py          injected CSS
│  ├─ html_embed.py      same-origin HTML iframes; plotly.js served from the app's own server
│  ├─ debug_log.py       in-app log + state inspector (❓ Help → About → Debug)
│  ├─ crash_report.py    the "report this bug" note around every run
│  ├─ wizard_watch.py    the wizard's browser guards: the lost-connection notice and the leave prompt
│  └─ easter_egg.py, color_picker_commit.py, save_dialog.py, truncation_tooltip.py
│                        browser-only helpers installed into the parent document
├─ Data
│  ├─ data.py            schema inference, normalization, filtering, the stimulus join, fingerprints
│  ├─ column_names.py    the dataset's own column names behind the canonical ones
│  ├─ multipart.py       trials recorded over several screens
│  ├─ metadata.py        participant / trial / text metadata tables (never broadcast onto frames)
│  ├─ annotations.py     favorites / tags / notes, one store per dataset
│  ├─ datasets.py        public-corpus loaders: PoTeC, OneStop
│  ├─ compare_source.py  Compare's second dataset (scanpath B): widget-free readiness + loading
│  ├─ experimental_setup.py
│  │                     display-geometry conversions + `SetupSnapshot` with per-group provenance
│  ├─ persistence.py     the on-device recovery cache (loopback / desktop only)
│  ├─ data_health.py     the Data page's *Data checks*
│  ├─ synthetic.py       the hand-built ground-truth trial and the example import pair
│  └─ update_sample_data.py, onestop_shard.py
│                        maintainer scripts: regenerate the bundled demo; shard full OneStop
├─ Measures & analysis
│  ├─ measures.py        reading measures, fixation→word assignment, word-box geometry accessors
│  ├─ aggregation.py     pure corpus-level aggregation for Corpus Analysis (`MEASURES` registry)
│  ├─ analysis_recipe.py the JSON recipe downloaded beside each Corpus Analysis table
│  ├─ computations.py    the register of every computation shown to users (formula, units, precedence)
│  ├─ preprocessing.py   soft exclusion / merge pipeline and derived tables (experimental)
│  ├─ alignment.py       line assignment: a port of Carr et al.'s algorithms (experimental)
│  ├─ similarity.py      scanpath similarity (NLD) for Comparisons (experimental)
│  ├─ model_scanpaths.py synthetic scanpaths over a text; `_ordered_word_rows` is used by alignment
│  └─ illustration.py    which views must carry the automatic *Illustration* label
├─ Figures & export
│  ├─ plots.py           `FigureSettings` (the render contract) + every Plotly builder + layer split
│  ├─ code_snippet.py    the Python / CLI code that reproduces the figure on screen
│  ├─ export.py          bulk export (figures + tables, per trial or combined)
│  ├─ animation_export.py GIF / MP4 from the replay (warm Kaleido + Pillow / imageio-ffmpeg)
│  ├─ export_status.py   shared export stages and byte signatures
│  └─ authoring.py, authoring_component.py
│                        the manually authored scanpath ("Create manually") and its canvas
└─ Headless & distribution
   ├─ api.py             the public Python API (`load_scanpath_data`, `plot_scanpath`, `animate_scanpath`,
   │                     `compare_scanpaths`, `save_figure`, `figure_code`, …)
   ├─ cli.py             `scanpath-studio`: `run`, `render`, `corpus`, `check`, `cache`, `version`, `analyze`
   ├─ __init__.py        `__release__`, the lazy `__version__`, and lazy re-exports of `api.py`
   ├─ citation.py        the BibTeX / APA entries shown in About and on the docs' Cite page
   ├─ build_info.py      which build this is (release, git checkout, desktop stamp, VCS install)
   ├─ updates.py         *Check for updates* against the latest GitHub release (on request only)
   └─ desktop_update.py  the desktop app's own *Update & restart*
```

`sample_data/` holds the bundled demo; `desktop/` the PyInstaller launcher, spec
and smoke tests; `paper/` the scripts that make the manuscript's figures;
`scripts/` docs, release and recording helpers.

### Pipeline

```text
uploaded/sample table(s) → infer_*_schema → normalize_* → canonical columns
                       → select_trials / filter_trials → build_combo_options → view renderers
                       → make_*_figure / export / Corpus Analysis aggregations
```

### Canonical columns

After `normalize_words` / `normalize_fixations`:

- **Words**: `participant_id`, `trial_id`, `text_id` (`unique_*` variants kept
  when present), `word_id`, `text`, `line_idx`, `x`, `y`, `width`, `height`.
  Plus EyeLink IA columns (`IA_*` renamed to `first_fixation_ms`, etc.) and
  linguistic features when shipped.
- **Multipart words** additionally carry `screen_id`, positive 1-based
  `screen_index`, and optional per-screen `canvas_width` / `canvas_height`.
- **Fixations**: `participant_id`, `trial_id`, `text_id`, `x`, `y`,
  `duration_ms`, `timestamp_ms`, `fixation_id` (synthesized per trial when
  absent), `word_id`, `pass_index`, `saccade_type`, `saccade_amplitude`
  (pixels), `eye`, `order_in_trial`, and — when the export carries EyeLink's
  degree-valued amplitudes — `next_saccade_amplitude_deg` /
  `prev_saccade_amplitude_deg`, kept distinct from the pixel amplitude.
- **Multipart fixations** keep those parent-global clock/index columns and add
  `screen_id`, `screen_index`, optional `screen_timestamp_ms`,
  `screen_fixation_id`, and per-screen canvas metadata. Scientific grouping
  uses `(participant_id, trial_id, screen_id)`; coordinate spaces are never
  connected across screens.
- `data.INTERNAL_COLUMNS` (`_aoi_trial_id`, `_base_trial_id`,
  `_stimulus_words`, …) stay in the frames and the recovery cache and are
  dropped by `data.drop_internal_columns` wherever data leaves the app (export,
  `analyze`, the Data page's tables, the editor's field options).

### Reading measures

`measures.py` computes, per (participant, trial, word): `first_fixation_ms`
(FFD), `first_pass_gaze_duration_ms` (FPRT), `regression_path_duration_ms`
(RPD / go-past), `total_fixation_duration_ms` (TFD), `n_fixations`,
`skip_flag`, `regression_in_flag`, `regression_out_flag`, `first_fix_x/y`, plus
landing position/distance, regression-in count, second-pass duration and
single-fixation duration. Every definition follows EyeLink's `IA_*` meaning;
pre-computed IA values on the words table win column by column over computed
ones. Fixations are enriched with `saccade_amplitude`, `progression`,
`is_regression`, incoming/outgoing angles, and run/pass columns.

**Corpus Analysis shows only the measures the dataset brought**, mapped as
optional Words-table fields (`data.READING_MEASURE_FIELDS`, schema keys
`measure_*`, auto-detected from EyeLink `IA_*` names). Without one it shows a
notice and greys its sections. The measures the app computes itself are off by
default — see *Experimental features*.

### Areas of interest (AOIs)

AOIs are **not computed** — they are the data's own word bounding boxes, given
as `(x, y, width, height)` or EyeLink's `(IA_LEFT, IA_RIGHT, IA_TOP, IA_BOTTOM)`
(converted by `normalize_words`), and used **exactly as given**:
`measures.word_box_bounds` is the one accessor and returns `x .. x + width`
unmodified. On a tiling corpus such as the OneStop demo each box carries the
space after its word, and a fixation there belongs to that word, as in EyeLink's
report. Every containment test goes through `measures.word_box_contains`, which
is half-open (`x0 <= x < x1`), so a point on an edge two boxes share belongs to
the box that starts there. Positions *inside* a word go through
`word_char_advance` / `word_glyph_span`.

The **fixation→word assignment** is the data's own when the fixation table maps
a Word ID — used exactly as given, a blank staying blank. Only when it has
none does `measures.assign_fixations_to_words` derive it from geometry:
box containment, else `word_id = NaN` (no snapping to a nearby word). That
assignment feeds the reading measures and the "out-of-text" flag
(`measures.fixation_in_text_mask`); "color by line" derives visual lines from
word-box `y` clustering (`measures.cluster_word_lines`) because `line_idx` is
often a constant in IA exports.

### Metadata tables

Optional **separate** tables — one row per participant, per trial, or per text
— attached on the 🗂️ Data page or headlessly (`api.load_participant_metadata`
and siblings, `render --participant-metadata`). Their columns behave like fields
in the data: trial filters (`filter_meta_*`, `filter_trialmeta_*`,
`filter_textmeta_*` keys), chips, sorting, Data Inspection, and `metadata/*` in
the export bundle.

**Never broadcast a metadata table onto the word/fixation frames.** A
participant-grain constraint becomes a set of reader ids for the existing
participant filter (`metadata.participants_matching`), and the only join is
`metadata.project` onto the small per-trial `combos` frame in `app.main`.
Duplicate rows that *disagree* are dropped and reported, never resolved by
taking the first. The tables belong to a dataset: the session keys hold the
selected dataset's, and `metadata.activate_dataset` swaps them when the
selection changes.

### Trial annotations & filtering

`annotations.py` keeps favorites / tags / notes keyed by
`(participant_id, trial_id)` (or with `screen_id`), **one store per dataset**,
swapped by `annotations.activate_dataset` like the metadata tables. Import it as
`import scanpath_studio.annotations as …` — `from scanpath_studio import
annotations` can bind the package's `from __future__ import annotations`
feature instead. Export / import is on 🗂️ Data → Annotations, and the Export
bundle can carry the same `annotations.json`.

`controls.render_trial_filters` (read back via `controls.read_trial_filters`)
and `data.filter_trials` / `data.filter_to_keys` narrow the trial pool by
condition and annotation state before `build_combo_options`. A condition is
decided **per reading** `(participant_id, trial_id)` from whichever table
carries its column and applied to every table, raw gaze included
(`data.select_trials` → `TrialSelection`); a reading two tables disagree on is
left out and reported, never decided for one table.

### Experimental features

Some finished-but-unvalidated or unfinished features are off unless
`SCANPATH_EXPERIMENTAL=1` is set (gates in `constants.py`, read at call time):

- drift correction / line assignment (`alignment.py`) and its 📐 Line
  assignment subtab;
- NLD similarity scoring in Comparisons (`similarity.py`);
- the preprocessing panel and the Data page's derived analysis tables
  (`preprocessing.py`);
- the reading measures the app computes itself (`computed_measures_enabled`):
  without the flag `api.compute_word_metrics` / `trial_summary` /
  `reader_summary` / `preprocess_data` / `analysis_tables` raise, `analyze` is
  refused, the export bundle offers no measure family, and Corpus Analysis drops
  the views computed from fixations; the computation register marks these
  entries `computations.EXPERIMENTAL_IDS`;
- Corpus Analysis's *Per sentence* subtab.

Hidden, not broken: the code and its tests stay, CLI flags still parse (they
are only hidden from `--help`), and the docs site does not describe them.

## Build / Lint / Test

```bash
# Install in editable mode — the test + lint extras give CI's toolchain
# (pandas 3, ruff pinned in `lint`); a bare `pytest`/`ruff` on PATH may be
# another interpreter and another version.
pip install -e ".[test,lint]"                # or: uv sync --extra test --extra lint

# Run the app — bind to loopback: the recovery cache and local folder access
# are off on a server other machines can reach, and a bare `streamlit run`
# listens on every interface.
streamlit run streamlit_app.py --server.address 127.0.0.1
uv run streamlit run streamlit_app.py --server.address 127.0.0.1
scanpath-studio                              # binds 127.0.0.1 itself

# Tests (in that environment — e.g. prefix with `uv run --extra test`)
pytest -n auto                      # the full suite (CI runs it this way)
pytest tests/test_measures.py       # one file
pytest --cov                        # coverage; config + floor in pyproject.toml

# Lint
ruff check .
ruff check --select I --fix .
ruff format .

# Regenerate bundled sample data (needs the full OneStop CSVs, or --source-dir)
python -m scanpath_studio.update_sample_data

# Standalone desktop bundle (needs `pip install . pyinstaller` — non-editable)
# Output: dist/ScanpathStudio.app on macOS, dist/ScanpathStudio/ elsewhere.
pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
python desktop/smoke_test.py     # signature + selfcheck + server-boot smoke test

# Docs site (MkDocs Material; API autodoc via mkdocstrings from docstrings)
pip install -e ".[docs]"
mkdocs serve                 # local preview
mkdocs build --strict        # CI gate on every PR and on deploy
uv run --with playwright python scripts/capture_docs_screenshots.py  # re-capture app screenshots
```

User-facing docs live in `docs/` and publish to
<https://lacclab.github.io/scanpath-studio/>. The Python API reference is
generated from the `api.py` docstrings, so keep those current. The gallery,
printed example output, CLI and figure-option references, and the Cite page are
generated at build time by `exec="true"` fences calling
`scripts/docs_support.py` — see CONTRIBUTING.md → *Docs site*.

CI (GitHub Actions) runs pytest on Python 3.11–3.14, ruff lint + format checks,
`mkdocs build --strict`, and one `pytest --cov` leg that fails below
`[tool.coverage.report] fail_under` in `pyproject.toml`. The HTML coverage
report and the README badge are published with the docs site for each release
tag.

## Code style

- `from __future__ import annotations` at the top of every Python file.
- snake_case functions/variables, PascalCase classes, UPPER_SNAKE_CASE
  constants. Files: snake_case.py.
- Sorted imports via ruff (`--select I`). stdlib → third-party → local.
- Use `pd.DataFrame` and `np.ndarray` as type hints directly.
- Add return type hints to public functions.
- Streamlit: `@st.cache_data` for expensive loaders, with every DataFrame
  parameter underscore-prefixed and identity passed as an explicit
  `data.frame_fingerprint(df)` key. Use `st.warning` (not `st.toast`) for
  per-rerender warnings.
- Plotting: y-axis inverted (`y_range = [max, min]`) for screen coordinates.
  Word boxes + the word-level heatmap use `layout.shapes`. Saccades are a SINGLE
  trace with `None` separators (never one trace per saccade).
- Centralized palette / sizing in `constants.py`. Marker sizes come from
  `plots._compute_marker_sizes` so single-trial and comparison figures render
  identically.
- Icons drawn as chrome (labels, `icon=`, headings, alerts) come from
  `constants.ICONS` — Material Symbols, keyed by concept; inside raw HTML use
  `constants.icon_html`. Never a literal emoji or `:material/…:` there
  (`tests/test_icons.py`). Prose — help text, tour bodies, docstrings, `cli.py`
  — keeps its emoji ("the 🗂️ **Data** page"). The docs site names an app icon
  with the label's own shortcode, `:material/database: **Data**`, which
  `scripts/mkdocs_hooks.py` draws in the font Streamlit ships.
- Comments describe the code as it is now — what it does and why. No issue
  numbers, dates or history; those belong in commits and PRs.

## Testing patterns

- `tests/conftest.py` exposes `sample_words_df`, `sample_raw_gaze_df`,
  `normalized_words_df`, `normalized_fixations_df`, `synthetic_words_df`,
  `synthetic_fixations_df`.
- `tests/synthetic_data.py` is a fully specified 6-word / 2-line trial with
  hand-traced `EXPECTED` values (incl. a regression and one out-of-text
  fixation); `tests/test_synthetic.py` asserts every measure and geometry
  helper exactly. It is shared with `scanpath_studio/synthetic.py`.
- `tests/test_smoke.py` exercises the full pipeline (load → infer → normalize
  → plot) against the bundled sample, including a check that saccades collapse
  to a single trace.
- `tests/test_apptest.py` and many more files boot the whole app headless with
  `streamlit.testing.v1.AppTest.from_file("streamlit_app.py")` and drive
  widgets — the preferred way to test app behavior.
- Contract tests: `tests/test_session_key_contract.py` pins the wire-format
  keys, `tests/test_citation.py` the version parity, `tests/test_computations.py`
  the computation register against the code.

## Adding a new column convention

Update the candidate lists in `data.py` (e.g. `WORD_X_CANDIDATES`,
`FIX_DURATION_CANDIDATES`). `pick_column` walks the list and picks the first
existing column. Optional passthrough columns (e.g. `saccade_amplitude`, IA
measures) go through the `WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS` tuple
tables instead, applied by `_apply_optional_fields` during normalization.

## Adding a new reading measure

1. Compute it in `measures.compute_per_word_measures` per trial.
2. Add it to `WORD_OPTIONAL_FIELDS` in `data.py` if it can come pre-computed
   from EyeLink IA columns.
3. Add a `computations.py` register entry — its formula, unit, grouping keys,
   missing behaviour and precedence. A `MEASURES` entry with no register row
   fails `tests/test_computations.py`.
4. Surface it in `controls.color_field_options` (if useful for coloring) and
   register it in `aggregation.MEASURES` (surfaced via
   `aggregation.available_measures`, which feeds the measure pickers).
5. Add a test under `tests/test_measures.py`.

## Adding a new figure type

1. Add a `make_*_figure` function in `plots.py` using the helpers
   `_compute_axis_ranges`, `_compute_marker_sizes`, `_saccade_segments`,
   `_add_word_label_trace`.
2. Wire it into a view in `tabs.py` (spatial figures through
   `tabs._render_true_scale_chart`, never `st.plotly_chart`).
3. Add a smoke test in `tests/test_smoke.py` that builds the figure against
   the bundled sample.

## Exposing a feature on every surface

Scanpath Studio has four parallel entry points. A user-facing feature (a new
toggle, option, or parameter) is only "done" when it reaches **all** of them:

1. **Visual UI** — the Streamlit control (`controls.py` widget + a `global_*` /
   `single_*` / `filter_*` session key, read by `_collect_viz_settings`).
2. **Deep link / Share** — the URL contract in `url_state.py`:
   `_URL_PRESETS` + `_apply_url_preset` (read) and the inverse
   `_build_share_query` (write), plus `_URL_BOUNDED` if it needs clamping, and
   the settings file if it is a plot setting.
3. **CLI** — a `render` flag in `cli.py` (follow the per-layer `--no-*` pattern).
4. **Headless API** — a parameter on the relevant `api.py` builder
   (`plot_scanpath` / `animate_scanpath` / `compare_scanpaths`) plus a default in
   `CANONICAL_FIGURE_DEFAULTS`, so headless output matches the app.

Every figure option also needs a `render` flag and a `code_snippet` emitter:
`tests/test_render_every_option.py` sets each option off its default and fails
on one the Share → Code snippet cannot reproduce.

## Gotchas

**State and the wire format**

- URL deep-link presets are applied before widgets render (`app.py`); renaming
  a `global_*` / `single_*` / `filter_*` widget key, a URL param or a settings
  key breaks links and saved files already in the world.
  `tests/test_session_key_contract.py` pins them. Changing the settings file's
  shape means bumping `session_keys.PLOT_CONFIG_SCHEMA_VERSION` and registering
  a migration in `url_state._PLOT_CONFIG_MIGRATIONS`.
- **`persist_state="session"` on every persisted widget.** A control that
  renders only sometimes loses its key at the end of a run in which it did not
  render, and remounts at its proto default. Every widget on a `global_*` /
  `single_*` / `cmp{idx}_*` / wire-format key passes `persist_state="session"`;
  `tests/test_widget_value_sync.py` fails if one doesn't.
- **A programmatic write to a widget inside a popover can be undone by the
  browser**, which keeps echoing the value the widget last showed. Write such
  keys with `controls.write_through(key, value)`.
- **Never pass `value=` / `index=` to a gated (disabled) widget** — disabling
  must not rewrite the stored value a deep link or saved file carries.
- **Anything drawn only sometimes above a view goes inside a container drawn
  every run.** Streamlit matches a rerun's elements to the last run's by
  position, so one element more or fewer above `sps_view` shifts the whole view
  and redraws it from nothing. `st.dialog`, a bare `st.toast` and
  `@st.fragment` are safe; a bare `st.warning`, `st.markdown` or iframe is not.
- **Never give `st.select_slider` a single option** — the browser slider throws
  and blanks the tab (invisible to AppTest). Guard any new slider, as the trial
  picker does.
- **Code changes not showing? Restart the server.** Streamlit doesn't reload
  imported modules on rerun, and `st.cache_data` doesn't hash
  transitively-called helpers.

**Data**

- **A dataset's column-name map must survive every rewrite of its entry.**
  `column_names.ColumnNames` records what each canonical column was called in
  the user's files; anything that rewrites `_datasets[name]` carries
  `column_names` along, and showing a column name goes through the map. The
  API's frames are under the dataset's own names; package code that reads them
  itself passes `names="canonical"`.
- **A trial filter decides readings, never rows of one table** — see *Trial
  annotations & filtering*.
- **One trial pool, the union, on every surface.** A trial is listed when any
  table has it (words, fixations, raw gaze); a table that lacks it draws as an
  empty layer. `data.trial_pool` is the rule (`api.list_trials`, `render
  --list-trials`) and `utils.combo_source` the app's form of it.
- **Raw gaze can be a dataset's only table.** Nothing derives fixations from
  samples; the 🔵 Raw gaze layer turns on by default for such a dataset.
- Schema auto-detection (`data.pick_column`) matches candidate names case- and
  separator-insensitively and drops one trailing unit block
  (`Fixation Duration [ms]` == `fixation_duration`), so the `*_CANDIDATES`
  lists hold only distinct conventions. A second pass accepts a whole-token
  match (`AOI_LEFT`, `LEFT_px`) only when exactly one column survives it;
  ambiguity falls through to manual mapping.
- `*` on a mapping field means exactly "validation blocks without it". A Word/IA
  ID is read as a number, so one that holds no numbers is no location.
- **pandas joins NaN to NaN** — in `merge` and in `Series.map` over a dict — so
  any lookup keyed on a word id drops missing keys first.
- Repeated readings of a trial get a `_r2` suffix on `trial_id` (ranked on
  `TRIAL_INDEX`) unless the Trial ID is mapped to several columns, which builds
  a composite id with `data.compose_id` (escaping `_` and `\`). Any mapping is
  authoritative over a literal `unique_trial_id` column.
- **A built-in dataset's recording setup is an override, never an edit of the
  corpus** (`constants.DATASET_SETUP_OVERRIDES_KEY`). A share link elides the
  setup against the *source's* screen, since a recipient has no override.
- Every fingerprint is exact: a frame is hashed in full or named by where it
  came from (`data.stamp_source` / `adopt_source`, `frame_cache`,
  `assign_derived`), never sampled. A new large frame made every rerun needs
  one of these, or it is hashed each run.
- The bundled `raw_gaze.{csv,parquet}` is **synthesized** from one real
  bundled trial's fixations (OneStop ships no sample-level gaze); it must stay
  keyed to a trial present in the bundled fixations.

**Figures**

- **Don't render the spatial plots with `st.plotly_chart`.** It pins the chart
  width to the column while keeping the layout height, which mis-scales the
  px-sized word labels. The single / animation / comparison plots go through
  `tabs._render_true_scale_chart`, which embeds the figure's HTML at its exact
  pixel size and CSS-scales it to the column. plotly.js loads from the app's own
  server (`html_embed.plotlyjs_script`), never a CDN; HTML *downloads* take
  `export.html_plotlyjs(...)`.
- **The replay player owns the clock.** Plotly's own frame queue rounds every
  frame up to whole display ticks, so `make_scanpath_animation` stamps each
  frame's reading time on `fig.layout.meta` and every HTML surface passes
  `plots.animation_player_post_script(fig)`. Pages carry the frames packed
  (`plots.replay_page`: frame 0 whole, then per-frame deltas); the figure itself
  keeps its frames. Both are pinned by tests that run the JS under node.
- **Animation transport controls must not shrink the plot**: they sit above it
  in a top band the figure grows by (`plots._CONTROLS_MARGIN_PX`), so the
  equal-aspect plot keeps the static figure's box size.
- **Layout shapes go on a figure in one assignment** (`fig.layout.shapes =
  …`): Plotly re-validates every existing shape on each `add_shape`.
  `tests/test_smoke.py` counts the constructions.
- **A new top-level trace** in `make_scanpath_figure` whose name isn't a
  fixation variant must be added to `plots._trace_layer`, or separable-layer
  export files it under fixations.
- Static image export (PNG/SVG/PDF) and the GIF/MP4 replay go through Kaleido,
  which needs Chrome (`plotly_get_chrome -y` locally; `packages.txt` installs
  `chromium` on Streamlit Cloud). The current figure's PNG/SVG is saved in the
  browser from the plot on screen; HTML is the browser-free fallback. Kaleido's
  warm server is a process-wide singleton: hold `animation_export.KALEIDO_LOCK`
  around any use of it.
- Bulk export iterates *all* filtered trials — narrow the filter first on a
  large corpus.

**Loading and performance**

- **A new slow step gets a loading card, not `st.spinner`.** Wrap it in
  `loading.card(slot, …)` and report counts through `progress.report()` from
  inside its loop. A build under a *gated* card (the dataset pipeline,
  Compare's B, the Corpus measures) must report at the start of its work on a
  miss, or the card shows late or never. Never create a Streamlit element inside
  a cached function.
- **Keep the plot stage's order**: notes that come before the figure go to
  `plot_notes_slot`, never into `tour_grp_plot` ahead of the figure.

**Compare**

- Scanpath B can come from a second dataset (`compare_source.py`). Two corpora
  can hold the same `(participant_id, trial_id)`, so B's `participant_id` is
  namespaced with the dataset name **only in the throwaway compare frames**
  (`utils.qualify_for_compare`); everything user-facing carries the corpus' own
  id (`utils.unqualify_for_export`).
- An overlay or co-animation across datasets needs equal canvases
  (`experimental_setup.setups_comparable`); the app resolves to side by side,
  the API raises `IncomparableScreensError`, the CLI exits.
- Filter helpers are prefix-scoped: B's filters use the `cmp` prefix, and
  `controls.FILTER_PREFIXES` keeps a clear-sweep of A's from wiping B's.

## Which viz settings apply in which render path

The scanpath rail (`controls.render_plot_controls`) is **one** control set
feeding **three** figure builders, picked by the rail's Animate / Compare
toggles (`single_animate` / `single_compare_toggle`, rendered in `tabs.py`
before `render_plot_controls`):

| mode | builder | thread |
| --- | --- | --- |
| neither toggle | `plots.make_scanpath_figure` | `tabs._build_figure_settings` → `_cached_scanpath_figure` |
| **Animate** | `plots.make_scanpath_animation` | `tabs._build_and_render_animation` |
| **Compare** | `plots.make_comparison_figure` (split layouts: `_make_split_comparison_figure`) | `tabs._render_comparison_figure` |
| **Animate + Compare** | `make_scanpath_animation(fixations_b=…)` — the co-animation | same as Animate |

A setting is honoured (✅) only where the builder takes the parameter **and**
`tabs.py` passes it; everything else renders disabled with a reason via
`controls._mode_gate`. Keep this table in sync when a builder gains or loses a
parameter.

| setting (`viz_settings` name) | static | animation | compare | notes |
| --- | :---: | :---: | :---: | --- |
| `show_words`, `show_labels`, `show_saccades`, `show_order`, `order_font_size` | ✅ | ✅ | ✅ | |
| `word_box_*` (colour, line / fill opacity) | ✅ | ✅ | fill only | Compare outlines each reading's boxes in its own `cmp{idx}_box_color` (its scanpath colour by default) |
| `show_fix` | ✅ | ❌ | ✅ | The replay *is* the fixation trail |
| `show_saccade_arrows`, `saccade_arrow_size`, `saccade_opacity` | ✅ | ✅ | ✅ | One figure-wide value in Compare |
| `legend_layout` | ✅ | ✅ (not saccades) | ✅ (not saccades) | `plots.apply_legend_layout`; one `legend_<kind>=SPOT[,ARR][,SIZE]` link param per moved legend, `render --legend` |
| `order_font_color`, `fixation_color`, `marker_size_range`, `fixation_opacity`, `hollow_fixations`, `saccade_color` / `_style` / `_width` | ✅ | ✅ (single only) | ❌ | Compare and the co-animation use the per-scanpath `cmp{idx}_*` styles |
| `color_by`, `fixation_colorscale`, `fixation_color_range` | ✅ | ✅ | ✅ | Compare colours the fill and makes the scanpath colour the outline; a range is present only when explicit (absent = scale to the data, A+B together) |
| `fixation_symbol` | ✅ | ✅ | ✅ | Glyph shapes (♥) are drawn as text by `plots._glyph_scatter_traces` in every builder |
| `marker_size_scale`, `marker_duration_range`, `duration_size_legend` | ✅ | ✅ | ✅ | One duration scale; the size key draws in Compare only while A and B share a px range |
| `fix_index_range` | ✅ | ✅ | ✅ | Sliced in `tabs._slice_fix_range`; Compare's B has its own window (`single_compare_fix_range`) |
| `fixation_flags` (short / long / out-of-bounds) | ✅ | ✅ | ✅ | Compare applies each scanpath's own (B: `cmp1_fixclass_*`) |
| `illustration_label` / `illustration_text` | ✅ | ✅ | ❌ | `compare_scanpaths` takes no label; the app stamps it itself |
| drift correction (`align_algorithm`) | ✅ | ✅ | ✅ | Experimental; `tabs._drift_corrected` runs once above the mode split; "Off" returns the same frame object |
| drift connectors (`align_connectors`) | ✅ | ❌ | ❌ | Only the static figure has the original→corrected layer |
| `fixation_snap_to_line` / `_position`, Arc saccades | ✅ | ❌ | ❌ | The linear-reading schematic |
| saccade colour by type, `saccade_classes` | ✅ | ❌ | classes only | Reading-class colouring is static-only; Compare filters classes per scanpath |
| heatmap (`show_heatmap`, metric / norm / colour scale / range / opacity) | ✅ | ❌ | ✅ | Compare is always word boxes (`heatmap_style` static-only), on a scale shared by A and B |
| raw gaze (`show_raw_gaze`, size / opacity) | ✅ | ❌ | ✅ | Compare draws each reading's samples in its scanpath's colour |
| stimulus image (`background_image*`, opacity / offset / scale) | ✅ | ✅ | ✅ | Split layouts get one image per panel |
| `highlight_column`, `highlight_text_color`, `text_color` | ✅ | ✅ | ✅ | Only *Mark text* reaches all three; *Mark border* (`span_border_color`) is static-only |
| `redact_text` | ✅ | ✅ | ✅ | `plots.redact_word_text` masks the words at each builder's entry; the blocks take the text / highlight colour |
| `word_hover_measure` | ✅ | ✅ | ❌ | |
| colour bars (`{fixation,heatmap}_colorbar_*`) | ✅ | ✅ fixation only | ✅ | Through `plots._colorbar_dict` |
| `x_field` / `y_field` | ✅ | ❌ | ❌ | Animation and comparison always plot spatial `x` / `y` |
| `fit_to_monitor`, `crop_margin`, coordinate grid + font size, title / caption styling, `background_color`, `show_plot_frame` / `plot_frame_color` | ✅ | ✅ | ✅ | |
| `fixation_outline_width` / `_color` | ✅ | ✅ | ✅ | |
| `show_compare_legend`, `compare_stimulus` | ❌ | ✅ (co-animation) | ✅ | Widgets in `tabs.py` (⚙ Compare options) |
| `anim_autoplay`, replay grid step / max frames, `playback_speed` | ❌ | ✅ | ❌ | Widgets in `tabs.py` (⚙ Playback) |
| `canvas_b`, `background_image_b*` | ❌ | ❌ | ✅ (split only) | B's own screen and page; `None` = same as A |

The canvas / font controls (`app.render_canvas_controls`: line spacing,
scale-to-boxes, base font, canvas size, text colour) reach all three builders.
`app.seed_canvas_state` seeds their keys before any view renders, so the
rail-less Corpus view resolves the same geometry.

## Where the work is tracked

[GitHub Issues](https://github.com/lacclab/scanpath-studio/issues), arranged on
the [Scanpath Studio board](https://github.com/orgs/lacclab/projects/5). The
conventions — `#N` citations, when an issue is needed, the board's Status and
Priority, the approval gate — are in `CLAUDE.md` → *Tracking work*.

## Releasing

1. `python scripts/changelog_fragments.py release <version>` writes the
   `changelog.d/` fragments into a `CHANGELOG.md` section and deletes them.
2. Bump `__release__` in `scanpath_studio/__init__.py` — the single source of
   truth for the release number; `pyproject.toml` reads it dynamically.
3. Bump `version` + `date-released` in `CITATION.cff` to match
   (`tests/test_citation.py` enforces version parity). On the first release of
   a new year, bump `constants.CITATION["year"]` too — the in-app and docs
   citation's year, which the same test holds to `date-released`.
4. Commit on a branch and land it through a PR — `main` is protected. Once it
   has merged, tag the merge commit on `main` with `v<version>` and push the
   tag (`publish.yml` refuses a tag that does not match `__release__`).
5. The `Publish to PyPI` workflow builds the wheel + sdist and publishes via
   PyPI Trusted Publishing.
6. The `Desktop builds` workflow (`.github/workflows/desktop.yml`) builds the
   per-OS desktop bundles (`desktop/`) and attaches them to the GitHub release.
   The macOS leg also signs, notarizes and staples a `.app` + `.dmg` when the
   Apple secrets are configured (`desktop/SIGNING.md`); without them it still
   builds, unsigned.
