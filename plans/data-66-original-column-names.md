# DATA-66 — Show the dataset's own column names, everywhere

*Design spec, 2026-10-02. Status: draft for review.*

## Request

Beta testers find it very confusing that the app shows column names that differ
from the ones they uploaded (`total_fixation_duration_ms` where they uploaded
`IA_DWELL_TIME`), and that features the app computes are mixed in with their own
fields with no separation (the *Sort trials by* picker lists both, prettified the
same way). The user's direction (2026-10-02): the app's goal is not to normalize
datasets but to make it easy for researchers to work with their data — so the
user's own names appear **on screen, in exports, and from the API / CLI**
(options a + b + c), the canonical names become an implementation detail, and
computed features are visibly separate. Edge cases can take a second iteration;
be thorough about where updates are needed.

## What exists today (inventory summary)

The full inventory is in the appendix. The headline facts:

1. **Normalization rebuilds every table under canonical names and keeps no
   record of where each came from.** The schema (`{field: source column}`) is
   used and dropped; `api.load_scanpath_data` returns frames only; no
   `df.attrs`; the optional-field registries (`WORD_OPTIONAL_FIELDS`,
   `FIX_OPTIONAL_FIELDS`) rename `IA_DWELL_TIME → total_fixation_duration_ms`,
   `EYE_USED → eye`, `reread → pass_index` … and record nothing.
2. **The only durable record is broken.** Stored uploads keep `schemas` with
   source names, but ✏️ Edit dataset → Save (`tabs._apply_remap`) overwrites
   them with a canonical→canonical identity mapping. Built-ins keep the mapping
   only in live session state (`_active_column_mapping`, `col_map_*`).
3. **Fourteen label dictionaries and eight humanizers, which disagree.**
   `CHIP_FIELD_LABELS`, `_FILTER_FIELD_LABELS`, `_GROUP_COL_LABELS`,
   `_STIMULUS_FIELD_LABELS`, `_HOVER_MEASURE_LABELS`, `MEASURES[*].label`, …;
   humanizers alternate `.capitalize()` / `.title()` / bare `replace("_", " ")`.
   The same column is "Correct" on a chip and "Is correct" in the chip picker,
   "Pp age" in the sort menu and "Age" on the chip.
4. **Wire formats carry canonical names as values** — the Share link
   (`color_by`, `x_field`, hover fields, `highlight_column`, `heatmap_metric` as
   a *closed* choice), the saved config, saved designs, the recovery cache, CLI
   flags, export path/title patterns (`{participant_id}`). Readers heal unknown
   names by dropping them silently.
5. **Where users meet canonical names**, by reach: the Data page's Fixations /
   AOIs / Raw gaze tables (`tabs._render_raw_table`); the rail pickers (colour-by,
   hover fields, highlight, axis fields); the add wizard's *Extra fields to keep*
   (shows the canonical destination for every detected field — before anything
   has been normalized); ✏️ Edit dataset's mapping editor (offers the
   *normalized* frame's columns as if they were the user's); trial-sort, chips,
   filters; figure text (categorical legends `saccade_type: forward`, colorbar
   titles "Total Fixation Duration Ms"); exported files and their README data
   dictionary; API frames; `render --list-trials`.

## Approaches considered

**A. Rename the frames to source names at normalization** (canonical names
gone). Rejected: every module reads canonical columns (measures, plots,
aggregation, alignment — hundreds of call sites); two datasets would name the
same field differently, so cross-dataset compare, saved designs and share links
lose their meaning; and several renames are many-to-one or one-to-two.

**B. Keep canonical frames internally; translate at every boundary** through one
per-dataset *column-name map* (recommended). Inside the app nothing changes;
every place a column name reaches a person — a label, a header, a file, a frame
the API hands back — asks one function for the name to show. Wire formats keep
canonical values, so nothing already in the world breaks.

**C. Display-only relabel** (option a alone). Rejected by the user: exports and
the API must speak the user's names too.

## Design (approach B)

### 1. The column-name map — one record per dataset

A new pure module, `scanpath_studio/column_names.py`, with a frozen
`ColumnNames` value:

- `source: Mapping[canonical, SourceName]` — for each canonical column the
  dataset's own name, with a `kind`:
  - `mapped` — a schema field (`duration → CURRENT_FIX_DURATION`), or a
    registry rename (`IA_DWELL_TIME`);
  - `composite` — several columns joined (`Trial ID ← participant + paragraph +
    reading`), shown as `A + B + C`;
  - `converted` — mapped, but the value changed: unit (`FPOGD`, seconds → ms) or
    edges→box (`width ← IA_RIGHT − IA_LEFT`); shown as the source plus a short
    note ("FPOGD, in ms");
  - `generated` — the app made it up because the data had none
    (`fixation_id` 1, 2, …, `timestamp_ms` as order, `line_idx = 1`,
    `text = w0…`, placeholder participants, `text_id` from the trial id);
  - `computed` — derived by the app (reading measures it filled, run/pass
    columns, `is_regression`, `progression`, angles, `right_to_left`, word-box
    centres filled into `x`/`y`, summary-table columns).
- `display(column) -> str` — the name to show; `label(column)` — the name plus,
  for converted/generated/computed, the marker.
- `to_canonical(name) -> column` — the inverse, for inputs (API keywords, CLI
  flags, typed pattern placeholders) that use the user's names.

**Built at normalization.** `normalize_words` / `normalize_fixations` /
`normalize_raw_gaze` already know every rename they make; they return the map
alongside the frame (a new `normalize_*_with_names` pair, the existing functions
unchanged for callers that do not need it), and `harmonize_frames` and the
measure/enrichment steps add their `computed` / `generated` entries.
Provenance is **per column, per dataset**; where an imported column is filled
cell by cell with computed values (`measures.py`'s `where(notna)`), the column is
`mapped` with a note "gaps filled by Scanpath Studio".

**Stored with the dataset.** A `column_names` field on the `_datasets` entry,
the built-in source's live state, `SecondaryDataset`, and the recovery-cache
manifest. (Adding a field to `_datasets` rewrites each upload's Parquet once —
acceptable, and noted in the PR.) ✏️ Edit dataset's save must carry the map
through instead of overwriting it — this fixes the identity-schema bug in
`_apply_remap` as part of the work.

**Fallback.** A frame with no map (synthetic data, authored scanpaths, old
cache entries) gets the canonical name prettified by **one** humanizer — the
existing curated labels unified into `column_names.CANONICAL_LABELS`, so the
fourteen dictionaries collapse into one.

### 2. On screen (option a)

Every place the inventory lists goes through `ColumnNames.label`:

- **Pickers** keep canonical values and gain a `format_func` (colour-by, hover
  fields, highlight, axis fields, heatmap metric, Match field, sentence measure,
  stimulus fields, group field). The wire values do not change.
- **Pickers group by provenance**: *From your data* first, then *Computed by
  Scanpath Studio*, each under a small caption (Streamlit selectboxes cannot
  nest groups, so the computed entries carry a ⚙ marker and sort last; the
  trial-sort menu's computed stats move under their own heading in its
  popover).
- **Tables** (`_render_raw_table`, summaries, per-sentence, part catalogue,
  metadata) rename their headers on the way to `st.dataframe` with
  `column_config` labels, keeping the frame canonical.
- **The add wizard** shows the source name in *Extra fields to keep*; ✏️ Edit
  dataset's mapping editor offers the **source** columns (from the stored map),
  not the normalized frame's.
- **Figure text** (legend names, colorbar and axis titles, hover labels) takes
  labels from `FigureSettings.column_labels` — a mapping built by the caller, so
  the builders stay pure. This also fixes "Total Fixation Duration Ms", the
  double "Ms: N ms" hover unit and the AN-9 trend's "X" axis.
- **Captions and help** that name canonical columns (`joined on participant_id`,
  the uploader help, "canonical fields") say the user's names or plain words.

### 3. Exports (option b)

`export._write_table` and `analyze`'s writer rename columns to `display` names
on the way out (one choke point each). The bundle's README data dictionary lists
**both**: the column as written, what it means, and where it came from (yours /
converted / computed). A `columns.json` beside the tables records the full map,
so a script can recover canonical names. Path / title / caption patterns accept
either name (`{CURRENT_FIX_DURATION}` or `{duration_ms}`), translated with
`to_canonical` at render time.

### 4. API and CLI (option c)

- `load_scanpath_data` returns frames whose columns are the user's names by
  default; `names="canonical"` asks for the internal names, for code that
  works across datasets (the house rule is no back-compat shims, so this is a
  real option, not a legacy mode). The map does **not** ride on `df.attrs`,
  which pandas drops on most operations; the loaders return a `ScanpathData`
  value carrying `words`, `fixations` and `column_names`. Whether it still
  unpacks as `words, fixations = …` is an open question below.
- Every API function that takes a column name (`color_by=`, `highlight_column=`,
  hover fields, `x_field=`) accepts either name via `to_canonical`; frames
  passed back in with source names are translated on entry.
- CLI `--color-by` / `--highlight-column` / hover / axis flags accept either
  name; `--list-trials` prints source names; `analyze` writes source names.
- `code_snippet` keeps emitting canonical values, which are valid on every
  dataset and are what the API checks against (see the open questions).

### 5. What does not change

Share links, saved configs, saved designs and the recovery cache keep canonical
values, so every link and file already in the world keeps working; a link
carrying a source name is translated on read. The canonical names stay the
internal contract and the cross-dataset vocabulary (Compare, saved designs).

## Phasing

One issue, several PRs, each shippable:

1. **The map** — `column_names.py`, built at normalization, stored per dataset,
   survives Edit-dataset save, recovery cache. Tests: every rename kind.
2. **On screen** — pickers, tables, wizard, editor, chips, filters, sort,
   figure text, captions; unify the labellers.
3. **Exports** — file headers, README dictionary, `columns.json`, patterns.
4. **API + CLI** — `ScanpathData`, `names=`, either-name inputs, CLI flags,
   docs.

## Open questions (second iteration)

- Many-to-one registry renames (`EYE_USED` / `EYE_TRACKED` → `eye`): show
  whichever the dataset had — the map records the one that matched.
- One-to-two (`IA_SECOND_RUN_DWELL_TIME` → `second_pass_duration_ms` and its
  alias `higher_pass_fixation_duration_ms`): drop the alias from user-facing
  output, or show both pointing at one source?
- Loader-invented names (PoTeC's `x`/`y`, OneStop's `unique_paragraph_id`,
  MultiplEYE's `left`/`top`, the wizard's `file_part_N`): `generated`, or the
  loader declares the publisher's name.
- Two datasets in Compare whose source names differ: label by A's names, B's in
  its own panel?
- Should *Export* offer "canonical names" as an option for users who already
  have scripts?
- The Share → Code snippet: canonical values always, or the user's names when
  the snippet loads with an explicit schema (more readable, but tied to that
  dataset)?
- `ScanpathData`: keep two-value unpacking (`words, fixations = load(...)`,
  with the map as an attribute), or break it and return three values?

## Testing

Unit tests per rename kind in `column_names`; AppTest checks that the Data
page, rail pickers and wizard show the uploaded names for a dataset with
EyeLink headers; export round-trip (`columns.json` → canonical); API either-name
inputs; a wire-format test that an old link with canonical values still lands.
Estimated blast radius: 25–35 test files assert canonical names in user-visible
output and will move with the phases that change them.

## Side bugs found by the inventory

To file separately: the AN-9 trend axis titled "X"; double unit in the hover
fallback; "Participant Id"; trial-sort `TRIAL_INDEX` / `trial_index` label
collision; stale help in `wizard.py` naming a removed toggle; `analyze` writes
`image_path` with the full local path; `code_snippet`'s file source drops
`word_schema` / `fix_schema`; `computations.py` register entries that disagree
with the code (`assign.runs`, `agg.normalize`).

## Appendix — the inventory

Collected 2026-10-02 by reading the code at `af991bd2`; line numbers are
from that commit and will drift. Terse by design: this is the checklist the
phases work through.

### Normalization, exports, API, CLI, figure text


#### Core fact
- normalize_words/normalize_fixations build a NEW frame; schema is not kept anywhere (no df.attrs). api.load_scanpath_data returns only (words, fixations); schema discarded. load_raw_gaze same.
- Renames happen in 3 places: schema keys (participant/trial/x/duration...), optional-field registries WORD_/FIX_OPTIONAL_FIELDS (IA_DWELL_TIME->total_fixation_duration_ms, Reduced_POS->reduced_pos, NEXT_SAC_AMPLITUDE->next_saccade_amplitude_deg, EYE_USED->eye, reread->pass_index, blink->is_blink), READING_MEASURE_FIELDS (measure_* key -> canonical).
- Existing seam: data.categorize_columns returns detected_optional {source,dest,category}; drop_internal_columns at export/analyze/Data page tables; data.user_columns for pickers (per scanpath_studio/CLAUDE.md, verify).

#### Exports (export.py)
- _write_table (622-632) single choke point for bundle tables (calls strip_local_paths(drop_internal_columns(df))). analyze write loop cli.py:3217-3219 (no strip_local_paths -> image_path full path leak: separate bug?).
- bulk_export takes no schema; side channels settings dict + _session_*_metadata helpers (1683-1724).
- README.md data dictionary hardcodes canonical names (1799-1860).
- plot_config.json / run_config.json store column-valued settings (color_by, x_field, heatmap_metric, hover fields).
- pair_export adds 'dataset','scanpath' columns.
- Path/title/caption patterns use {participant_id}/{trial_id}/{text_id} + every combo column as placeholders; 'Fields' popover lists them (436-450, 1159-1206). _settings_summary caption writes "colour by {color_by}".
- metadata pickers already show field.label.
- animation_export, export_status: no column names.
- bulk_export not called by api/cli despite comments.

#### API (api.py)
- propose_schema exposes mapping. load_* return canonical frames. compute_word_metrics/trial_summary/reader_summary/preprocess_data/analysis_tables return computed columns. list_trials/list_parts canonical id cols. render_parent_trial layout.meta keys.
- Column-valued options: color_by, highlight_column validated (_check_column_options 1445-1491, against canonical cols); word_hover_fields, fixation_hover_fields, word_hover_measure, x_field, y_field, word_heatmap_col, heatmap_metric not validated.
- CANONICAL_FIGURE_DEFAULTS: heatmap_metric="duration_ms", word_hover_fields=[text,word_id,line_idx,total_fixation_duration_ms], fixation_hover_fields=[order_in_trial,duration_ms,word_id]; highlight_column default is_in_aspan; word_hover_measure total_fixation_duration_ms.
- plot_corpus_figure: tidy CSV, hardcoded word_id/diff/lo/hi.
- compare: qualify_for_compare, align_compare_columns.

#### CLI (cli.py)
- --word-schema/--fix-schema JSON; --color-by, --highlight-column, --heatmap-metric choices=[duration_ms,counts], --word-hover-fields, --fixation-hover-fields, --word-hover-measure, --word-heatmap-col, --x-field/--y-field, --image-pattern placeholders, --list-trials/--list-parts print canonical columns; analyze writes analysis_tables CSVs + run_config.json.

#### code_snippet.py
- Emits column-valued kwargs/flags literally; trials[trials['participant_id']==...]; files source DROPS word_schema/fix_schema (separate bug: --word-schema --print-code recipe loses mapping).
- Must stay canonical-consistent with what api validates.

#### Trial sort (utils.py)
- trial_sort_keys label->Series; computed _TRIAL_SORT_STATS (301-307) "Fixations (n)", "Reading time (s)", ...; discovered cols labelled col.replace('_',' ').capitalize() (L652); _TRIAL_SORT_PREFERRED_COLS / _EXCLUDED_COLS hardcode canonical+raw names. No schema parameter.

#### Wire format
- Session/URL keys with canonical column VALUES: global_color_by, global_heatmap_metric, global_highlight_column, global_word_hover_measure, global_x_field/global_y_field, filter_meta_<name> etc, trial_chip_fields. Pinned by tests/test_session_key_contract.py.

#### Edge cases
- composite ids (list mapping); edge->box (width = right-left: two sources); synthesized (text w0, line_idx=1, fixation_id, timestamp_ms cumcount, participant placeholders, text_id from trial id); unit conversion (FPOGD seconds -> duration_ms); mixed source/computed (saccade_amplitude, IA measures vs computed, x/y filled from word centres); unique_paragraph_id precedence.
- computations.py (VAL-5) register has imported-vs-computed precedence; aggregation.MEASURES curated labels.

#### Still missing
- plots.py hover templates / colorbar / axis titles; on-screen tables (Data Inspection, stats); chips; computed columns list (measures/preprocessing/aggregation); UI pickers beyond sort; tests blast radius; metadata key-column naming.

#### Figure text (plots.py etc.)
- No label map in FigureSettings; column-valued fields pass raw canonical names.
- Existing label dicts: plots._HOVER_MEASURE_LABELS (P:1346), plots._hover_label aliases (P:1355-1367, fallback .replace('_',' ').title(); adds ' ms' for *_ms -> double unit "Ms: N ms"), aggregation.MEASURES (Measure.label/unit/axis_label, A:85-220), aggregation.LINGUISTIC_FEATURES (A:223), tabs._GROUP_COL_LABELS/_pretty_col (T:7682), tabs._STIMULUS_FIELD_LABELS/_humanize_field (T:2742), controls.CHIP_FIELD_LABELS (T:4956).
- RAW name in figure: categorical legend f"{color_by}: {cat}" P:2491 + anim P:4304; legacy word hover label P:1433; make_trend_figure hover x_col P:6083; export._settings_summary "colour by {color_by}" E:258.
- PRETTIFIED: colorbar titles P:2377, P:4050, P:4912; _hover_label fallback (4 builder paths); non-spatial axis titles from x_field/y_field P:2571; trend x-axis P:6093 (BUG: shows "X" from T:8972); word-matrix heatmap title/axis P:6283/6285 ("Participant Id"); AN-9 trend title T:8974.
- Curated: heatmap colorbars, corpus builders via MEASURES labels, CLI corpus user labels.
- Bugs: AN-9 trend axis "X"; double unit; "Participant Id"; four labelling methods.

### Screens, pickers, computed columns, tests


#### On-screen tables (raw canonical headers)
- tabs._render_trials_with_open_button (trial_summary_table cols), reader summary 8941/9237, group trials 9242, per-sentence 8431, alignment sensitivity 9754, **_render_raw_table 10305 (Data page Fixations/AOIs/Raw gaze — biggest)**, _render_raw_metadata_tab 10347 (metadata.py renames user's id col to participant_id/trial_id/text_id at metadata 1137/530/846), part_catalog 12976, derived tables 13083 (experimental), app authoring geometry 6977.
- Curated models to copy: annotations frame rename (annotations 1000), authoring data_editor column_config (app 7011), stimuli table (tabs 10372), readonly mapping grid (tabs 10651).

#### Captions naming canonical
- tabs 7562 dropped_metric; 9003 first_fix_x; 10078 gen_col; 10502/10507 "joined on participant_id/text_id"; 10848 uploader help "participant_id column"; 12250, 12667 "canonical fields"; app 3980 raw-gaze uploader help; app 8421 image filename pattern; app 612-640 filter diagnosis .capitalize (disagrees with popover .title); controls 6458 axes help; wizard 1021 source_file; **wizard 1324 stale text (toggle removed)**.
- data.py messages: validate_*_schema, normalization_issues, trial_identity_warning, StimulusJoin.describe, mapping_failure_problem.

#### Pickers (31 sites). Wire-format value pickers (store canonical; relabel with format_func only):
- controls: color-by 5243 (color_field_options 3180), fixation hover 5518, word hover 6060, highlight 5884, heatmap metric 6165 (["duration_ms","counts"]), X/Y axis 6473; global_word_hover_measure legacy no widget.
- UI-only: trial sort (utils 606-653; stores LABEL; BUG: TRIAL_INDEX & trial_index both "Trial index", overwrite), Compare sort tabs 2477, chip picker controls 7026 (labels differ from chip table labeller tabs 4956), trial filters (controls 7948/8025 label _FILTER_FIELD_LABELS else .title), metadata filters (field_label; original names), stimulus fields tabs 2968/3000, Match field tabs 10039, measure pickers (curated MEASURES labels), features (LINGUISTIC_FEATURES), group field _pretty_col tabs 7682, sentence measure 8393 raw, per-reader X axis 8962 pretty.
- **Mapping seam**: column_mapping_ui (controls 2612) options are ORIGINAL source names pre-normalization; col_map_* store source col.
- **Edit dataset remap editor (tabs 12083-12226)** runs column_mapping_ui over NORMALIZED frames -> options canonical; and **_apply_remap writes new_schemas[table]=schema mapping field->CANONICAL col (tabs 11714) -> original names LOST after first save.** Critical for DATA-66.
- Read-only mapping grid (tabs 10651) for built-ins uses _active_column_mapping (field->source); label dicts lack measure keys/screen fields.
- **wizard keep picker 1556-1653 shows d['dest'] canonical for detected optional fields** -> most direct.
- Export pattern vocabulary {participant_id} etc (export 232-433, controls 3556) — wire format.

#### Labellers: 14 dicts + 8 humanizers with different rules (listed in subagent report). Unify into one display-name function.

#### Computed columns (full list)
- normalize: participant/trial/text ids (+ synthesized placeholders), text 'w{id}', line_idx=1, edge->box, timestamp cumcount, fixation_id cumcount, order_in_trial, order_in_screen, screen_index first-appearance, right_to_left, _aoi_trial_id, fill x/y from word centres, word_id offset -1.
- measures.compute_per_word_measures: first_fixation_ms, first_pass_gaze_duration_ms, regression_path_duration_ms, total_fixation_duration_ms, n_fixations, skip_flag, regression_in_flag, regression_out_flag, first_fix_x/y, initial_landing_position/distance, number_of_regressions_in, second_pass_duration_ms, single_fixation_duration_ms, gaze_duration_ms alias. **Imported wins CELL BY CELL** (measures 1006: where(notna)) -> a column can mix provenance; CLAUDE.md says column by column (overstated).
- enrich_fixations: saccade_amplitude (cell-wise), angle_incoming/outgoing, progression, is_regression (always overwritten). materialize_runs: run, linerun, word_runid, word_run, word_run_fix, nrun, reread (recomputed, overwrites incoming reread).
- preprocessing: excluded, excluded_reason, is_blink, blink_before/after, original_duration_ms, sentence tables, saccade table, character grid, cleaning report.
- alignment.correct: y snapped, y_original, y_correction, alignment_agreement.
- aggregation trial/reader summary tables; regression_in_rate falls back to regression_rate.
- No COMPUTED_COLUMNS set exists. computations.py register output is free text, partly inaccurate (assign.runs lists pass_index; reread "kept" but recomputed; agg.normalize NaN vs code 0).

#### Tests blast radius
- Display-only relabel: ~8-12 files. Canonical rename: ~25-35 files, 150-250 assertions + wire-format break.
- Wire-format column-name VALUES: SHARE_VALUE_PARAMS (session_keys 416-449): color_by, heatmap_metric, highlight_column, x_field, y_field, word_hover_measure, word_hover_fields, fixation_hover_fields — not pinned by contract test; test_app.py 283-333 catches color_by.

#### Side bugs found (candidates for separate issues)
- AN-9 per-reader trend x-axis titled "X" / hover "x:" (plots 6083/6093, tabs 8972).
- Double unit "… Ms: N ms" in _hover_label fallback.
- "Participant Id" .title().
- trial_sort_keys TRIAL_INDEX/trial_index label collision.
- wizard 1324 stale help text.
- analyze doesn't strip_local_paths (image_path full path leak) cli 3218.
- code_snippet files source drops word_schema/fix_schema (render --word-schema --print-code recipe loses mapping).
- Edit-dataset save loses original source names in stored schemas (tabs 11714).
- computations.py register inaccuracies.

### Wire formats and where the mapping lives


#### Wire values naming columns: ALL canonical (only col_map_* hold source names)
- URL _SHARE_VALUE_PARAMS (url_state 355-401): color_by, heatmap_metric (CLOSED choice ("duration_ms","counts") url_state 1192 — a source name would be REJECTED), highlight_column, x_field/y_field, word_hover_measure (URL-only, legacy), word_hover_fields/fixation_hover_fields; title/caption_pattern placeholders {canonical}.
- Heal on read: controls._seed_viz_state _drop_stale / _drop_stale_multi (controls 3287) silently drop unknown names.
- Saved config (PLOT_CONFIG_SCHEMA=4): tabs._build_studio_config 3482-3766 / url_state._restore_plot_config 1634-2321: axes.x/y, coloring.color_by, heatmap_metric, text.*_hover_fields, labels patterns, highlighting.highlight_column.
- Setup JSON (wizard._wizard_setup_config 1841): column_mapping col_map_* -> SOURCE names; keep_and_filter wizard_keep_by_table SOURCE, wizard_filter_by CANONICAL dest.
- Saved designs (controls 1485, 1750) store global_* values; recovery cache persists PLOT_CONFIG_STATE_KEYS + col_map_* (persistence 382-389).
- Decision: KEEP WIRE VALUES CANONICAL; relabel at render (format_func). Canonical = cross-dataset contract (tabs._CROSS_DATASET_SAFE_METRICS 3900). Patterns: accept source-name placeholders by translating at render.
- Sort labels (single_trial_sort, single_compare_order) store prettified LABELS, UI-only.

#### Mapping storage
- Live: app._stash_active_mapping (3009-3020) -> session "_active_column_mapping"[table] = {schema_key: source col}; built-ins only per-run + col_map_* keys.
- Stored uploads: _datasets[name]["schemas"] (wizard 3898-3902, after filename-derive, before char aggregation). **tabs._apply_remap (11718/11806) overwrites with canonical identity schema** -> source names lost; mixed if a raw table added on same screen (11763).
- MultiplEYE upload schemas are loader-built names.
- Authored/manual & synthetic: no schemas (synthetic frames already canonical).
- persistence._manifest_for (326-396): every non-frame _datasets field is cache identity -> adding a field rewrites every upload's Parquet once.
- compare_source.SecondaryDataset has NO schema field.
- api.load_scanpath_data discards schema; df.attrs unused for provenance (only SOURCE_TOKEN_ATTR, popped). pandas drops attrs on many ops -> attrs is fragile.
- Optional registry renames not recorded; many-to-one (EYE_USED/EYE_TRACKED->eye, blink/blink_flag/BLINK->is_blink) and one-to-two (IA_SECOND_RUN_DWELL_TIME -> second_pass_duration_ms + higher_pass_fixation_duration_ms; IA_REGRESSION_IN_COUNT -> number_of_regressions_in + regression_in_count).
- Loader-invented "source" names: PoTeC x/y/text_id/line; OneStop unique_paragraph_id/unique_trial_id/part/screen_index; MultiplEYE left/top/right/bottom/trial_id/genre; wizard file_part_N.
- Existing helpers: tabs._column_mapping_rows (10631, joins composite with " + "), _render_readonly_mapping_grid, tabs._WORD/_FIX/_RAW_GAZE_REMAP_CANON (10684-10716: schema key -> canonical col). Compose with source schema = canonical->source for core fields.
