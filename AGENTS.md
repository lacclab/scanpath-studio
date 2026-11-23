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
│  ├─ ui_mode.py         the Scanpath view's Essentials | Full mode: how it is seeded (`?ui=`, cookie),
│  │                     the header switch, the CSS that hides the other mode's containers, ＋ More lists
│  ├─ tabs.py            the views' panels: Scanpath (plot + rail + subtabs), Corpus Analysis, the Data page
│  ├─ corpus_overview.py the Corpus Analysis landing view and its links into text, participant and group analyses
│  ├─ controls.py        the Scanpath rail, the column-mapping UI and the trial filters
│  ├─ metadata_editor.py the participant, trial and text metadata controls shared by the wizard and Data Management
│  ├─ upload_ui.py       shared file-read error messages for the upload controls
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
│  ├─ datasets.py        public-corpus loaders: PoTeC, OneStop; the experimental MultiplEYE reader
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
   ├─ citation.py        the citation in every format (BibTeX, APA, RIS, CSL-JSON, a figure credit),
   │                     the public corpora's own, and `corpus_for` (the dataset → its corpus)
   ├─ file_citation.py   writes the citation into each exported file's metadata, editing bytes in place
   ├─ cite_button.py     the Cite popover under every figure, replay and bundle download
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
- **Text Word IDs.** A Word/IA ID column that holds text and not one number
  (`w1`, `Hello_3`) is read as keys (`data.read_word_ids`): the text goes to
  `word_key` (`constants.WORD_KEY`, shown and exported under the column's own
  name), and `word_id` stays numeric for every consumer — on the words, each
  key's position in its text (and screen), 1, 2, … in the row order of the
  reading that lists the most of the text's keys, one number for every reader
  (`data._number_word_keys`); on the fixations, the number of the word with
  exactly that key in the same trial (`data.match_text_word_ids`, in
  `harmonize_frames`). A column with any
  number in it is read as numbers, and its other cells as blanks.
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
a Word ID — used exactly as given, a blank staying blank; a text Word ID is
looked up by its exact text in its trial's words, and a text ID is never
matched to a number, nor a number to a text ID. Only when it has
none does `measures.assign_fixations_to_words` derive it from geometry:
box containment, else `word_id = NaN` (no snapping to a nearby word). That
assignment feeds the reading measures. The "out-of-text" flag uses the recorded
coordinates and actual box containment, independently of the mapped Word ID
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
- Corpus Analysis's *Per sentence* subtab;
- the MultiplEYE session-set format (`multipleye_format_enabled`): the
  wizard's *Dataset format* choice, `datasets.load_multipleye` and
  `render --multipleye`. A dataset already added that way still opens.

Hidden, not broken: the code and its tests stay, CLI flags still parse (they
are only hidden from `--help`), and the docs site does not describe them.

## Build / Lint / Test

```bash
# Run everything through uv: it resolves CI's toolchain (pandas 3, the ruff
# pinned in the `lint` extra). A bare `pytest` / `ruff` / `python` on PATH can
# be another interpreter with another pandas and an older ruff, and pass code
# CI rejects. (`pip install -e ".[test,lint]"` in a venv is the non-uv route.)

# Run the app — bind to loopback: the recovery cache and local folder access
# are off on a server other machines can reach, and a bare `streamlit run`
# listens on every interface.
uv run streamlit run streamlit_app.py --server.address 127.0.0.1
uv run scanpath-studio                       # binds 127.0.0.1 itself

# Tests
uv run --extra test pytest -n auto                   # the full suite, as CI runs it
uv run --extra test pytest tests/test_measures.py    # one file
uv run --extra test pytest --cov                     # coverage; floor in pyproject.toml
uv run --extra test python scripts/verify_change.py  # see a change work (/verify)

# Lint — the `lint` extra, never `test`'s ruff
uv run --extra lint ruff check .
uv run --extra lint ruff format .

# Regenerate bundled sample data (needs the full OneStop CSVs, or --source-dir)
uv run python -m scanpath_studio.update_sample_data

# Standalone desktop bundle (needs `pip install . pyinstaller` — non-editable)
# Output: dist/ScanpathStudio.app on macOS, dist/ScanpathStudio/ elsewhere.
pyinstaller --clean --noconfirm desktop/scanpath_studio.spec
python desktop/smoke_test.py     # signature + selfcheck + server-boot smoke test

# Docs site (MkDocs Material; API autodoc via mkdocstrings from docstrings)
uv run --extra docs mkdocs serve           # local preview
uv run --extra docs mkdocs build --strict  # CI gate; don't add -q, it hides the warnings --strict fails on
sh scripts/refresh_docs_media.sh           # re-capture every screenshot, GIF and video of the app
```

User-facing docs live in `docs/` and publish to
<https://lacclab.github.io/scanpath-studio/>. The Python API reference is
generated from the `api.py` docstrings, so keep those current. The gallery,
printed example output, CLI and figure-option references, and the Cite page are
generated at build time by `exec="true"` fences calling
`scripts/docs_support.py` — see CONTRIBUTING.md → *Docs site*.

CI (GitHub Actions) runs pytest on Python 3.11–3.15, ruff lint + format checks,
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
  widgets — the preferred way to test app behavior. `tests/conftest.py` pins
  every `AppTest.from_file` to `?ui=full` (a test sets
  `at.query_params["ui"]` itself to open Essentials); an `AppTest.from_function`
  app seeds no mode, so `ui_mode.current_mode()` there is Essentials.
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

One line per rule. [`REVIEW.md`](REVIEW.md) holds the checklist form — the
diff that triggers each, the check, and the bug it came from — and a test named
here fails when its rule is broken.

**State and the wire format**

- **Widget keys, URL params and settings keys are a wire format.** Deep-link
  presets are applied before widgets render (`app.py`); renaming one breaks
  links and files already in users' hands (`tests/test_session_key_contract.py`).
  A settings-file shape change bumps `session_keys.PLOT_CONFIG_SCHEMA_VERSION`
  and registers a migration in `url_state._PLOT_CONFIG_MIGRATIONS`.
- **`persist_state="session"` on every persisted widget**, or a control that
  renders only sometimes remounts at its default
  (`tests/test_widget_value_sync.py`).
- **Write a widget key inside a popover with `controls.write_through`** — the
  browser keeps echoing the value it last showed.
- **Never pass `value=` / `index=` to a gated (disabled) widget**; disabling
  must not rewrite what a link or saved file carries.
- **Anything drawn only sometimes above a view goes in a container drawn every
  run.** Streamlit matches elements by position, so one more or fewer above
  `sps_view` redraws the whole view. `st.dialog`, a bare `st.toast` and
  `@st.fragment` are safe; a bare `st.warning`, `st.markdown` or iframe is not.
- **Essentials and Full draw the same widgets.** Essentials is `SIMPLE` /
  `simple_only` in code, Full is `ADVANCED` / `advanced_only`. Mode-only UI
  goes in a `ui_mode.advanced_only(host, name)` (or `simple_only`) container,
  one per item, hidden by `ui_mode.mode_css`; never skip rendering a widget by
  mode. The subtab list is the one structural difference. `?ui=` is read on a
  session's first run; Share never writes it.
- **Never give `st.select_slider` a single option** — the browser throws and
  blanks the tab, invisibly to AppTest.
- **Code changes not showing? Restart the server** (CONTRIBUTING → *If a code
  change doesn't show up*).

**Data**

- **Carry `column_names` through every rewrite of `_datasets[name]`**, and show
  column names through the map. The API's frames use the dataset's own names;
  package code reading them passes `names="canonical"`.
- **A trial filter decides readings, never rows of one table** — see *Trial
  annotations & filtering*.
- **One trial pool, the union, on every surface**: a trial is listed when any
  table has it, and a table that lacks it draws as an empty layer
  (`data.trial_pool`; `utils.combo_source` in the app).
- **Raw gaze can be a dataset's only table**; nothing derives fixations from
  samples, and the Raw gaze layer then turns on by default.
- **Column auto-detection** (`data.pick_column`) ignores case and separators
  and one trailing unit block (`Fixation Duration [ms]` == `fixation_duration`),
  so `*_CANDIDATES` lists hold only distinct conventions. A whole-token match
  (`AOI_LEFT`) is taken only when exactly one column survives it.
- **`*` on a mapping field means exactly "validation blocks without it."**
  Without X/Y, fixations whose Word IDs name no word of their trial are refused
  (`harmonize_frames` → `UnplacedFixationsError`).
- **pandas joins NaN to NaN** in `merge` and `Series.map(dict)`: drop missing
  keys before any lookup keyed on a word id.
- **Repeated readings** get `_r2` on `trial_id` (ranked on `TRIAL_INDEX`) unless
  the Trial ID maps to several columns, which builds a composite id
  (`data.compose_id`). Any mapping beats a literal `unique_trial_id` column.
- **A built-in dataset's recording setup is an override, never an edit of the
  corpus** (`constants.DATASET_SETUP_OVERRIDES_KEY`); a share link elides it
  against the source's screen.
- **Every fingerprint is exact** — a frame hashed in full or named by its source
  (`data.stamp_source` / `adopt_source`, `frame_cache`, `assign_derived`), never
  sampled. A new large per-rerun frame needs one, or it is hashed every run.
- The bundled `raw_gaze.{csv,parquet}` is **synthesized** from one bundled
  trial's fixations and must stay keyed to a trial in them.

**Figures**

- **Spatial plots go through `tabs._render_true_scale_chart`, never
  `st.plotly_chart`**, which pins the width to the column but keeps the layout
  height and so mis-scales the px-sized word labels. The embed draws the
  figure's HTML at its exact pixel size and CSS-scales it. plotly.js comes from
  the app's own server (`html_embed.plotlyjs_script`); HTML downloads take
  `export.html_plotlyjs(...)`.
- **The replay player owns the clock.** Plotly's frame queue rounds frames up
  to display ticks, so `make_scanpath_animation` stamps each frame's reading
  time on `fig.layout.meta` and every HTML surface passes
  `plots.animation_player_post_script(fig)`. Pages carry the frames packed
  (`plots.replay_page`: frame 0 whole, then deltas); the figure keeps its own.
- **Transport controls never shrink the plot.** The figure keeps Plotly's
  controls in a top band it grows by (`plots._CONTROLS_MARGIN_PX`; GIF/MP4
  strip it). HTML pages hide them, take the band back (`plots.replay_page_box`)
  and draw a `REPLAY_TOOLBAR_PX` row above the figure instead. A legend above
  the plot grows the figure past the band, never into it.
- **Set layout shapes in one assignment** (`fig.layout.shapes = …`); each
  `add_shape` re-validates every shape (`tests/test_smoke.py` counts them).
- **A new top-level trace** in `make_scanpath_figure` goes in
  `plots._trace_layer`, or separable-layer export files it under fixations.
- **Every exported file carries the citation** — `export._figure_renderer`,
  `file_citation.stamp_html` / `stamp_file`, `animation_export`, and the bytes
  `tabs._render_save_plot_button` hands its component. A new writer stamps its
  output too; only the toolbar camera's PNG can't.
- **Kaleido** (PNG/SVG/PDF, GIF/MP4) needs Chrome (`plotly_get_chrome -y`;
  `packages.txt` on Streamlit Cloud), and its warm server is a process-wide
  singleton: hold `animation_export.KALEIDO_LOCK`. The on-screen PNG/SVG is
  saved in the browser; HTML needs no browser.
- Bulk export iterates *all* filtered trials — narrow the filter first.

**Loading and performance**

- **A new slow step gets a `loading.card`, not `st.spinner`**, with
  `progress.report()` from inside its loop. Under a *gated* card it reports at
  the start of its work on a miss, or the card shows late or never. Never create
  a Streamlit element inside a cached function.
- **Keep the plot stage's order**: notes before the figure go to
  `plot_notes_slot`, never into `tour_grp_plot` ahead of the figure.

**Compare**

- **Scanpath B's id is namespaced only in the throwaway compare frames**
  (`utils.qualify_for_compare`), since two corpora can share a
  `(participant_id, trial_id)`; everything user-facing goes through
  `utils.unqualify_for_export`.
- **Overlay and co-animation across datasets need equal canvases**
  (`experimental_setup.setups_comparable`): the app falls back to side by side,
  the API raises `IncomparableScreensError`, the CLI exits.
- **Filter helpers are prefix-scoped**: B's use `cmp`, and
  `controls.FILTER_PREFIXES` keeps clearing A's from wiping B's.

## Which viz settings apply in which render path

The rail is one control set feeding three builders (static, Animate, Compare,
and the co-animation). Which setting each one honours — and so which controls
`controls._mode_gate` greys out — is the table in
[`RENDER_PATHS.md`](RENDER_PATHS.md). Read it before adding or changing a figure
option, and update it in the same PR.

## Releasing

Run `/release`: it rolls the `changelog.d/` fragments into `CHANGELOG.md`,
re-captures the app's media when the UI changed, bumps `__release__` in
`scanpath_studio/__init__.py` and `version` + `date-released` in `CITATION.cff`
together (`tests/test_citation.py` enforces parity), lands the bump through a
PR, and tags the merge commit `v<version>`, which publishes to PyPI and builds
the desktop bundles.
