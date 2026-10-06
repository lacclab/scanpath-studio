# Python API

The public API follows one pipeline:

```
load data → list trials → plot or measure → save
```

```
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, participant="p1", trial="t3")
sps.save_figure(fig, "scanpath.html")
```

All functions below are importable from `scanpath_studio`. The [figure options](#figure-options) table lists every figure keyword.

Columns keep the names your files give them. The demo's word table calls its word id `IA_ID` and its total fixation duration `IA_DWELL_TIME`, and every function and option takes those names. A column Scanpath Studio made keeps its internal name. `load_scanpath_data(..., names="canonical")` gives the internal names, which are the same for every dataset. On the bundled demo, the first steps print this (run when the docs are built):

```
words, fixations = sps.load_sample_data()
print(sps.list_trials(words, fixations).head(3))

columns = ["IA_ID", "IA_LABEL", "IA_FIRST_FIXATION_DURATION", "IA_DWELL_TIME"]
print(words[columns].head(3))
```

```
  participant_id        unique_trial_id
0       l37_1129  l37_1129_2_1_1_Ele_r0
1       l37_1129  l37_1129_2_1_2_Ele_r0
2       l37_1129  l37_1129_2_1_3_Adv_r0
   IA_ID  IA_LABEL  IA_FIRST_FIXATION_DURATION  IA_DWELL_TIME
0      0    Robert                          32            387
1      1  Myslajek                         170            785
2      2     stops                         290           1330
```

## Load

### scanpath_studio.api.load_scanpath_data

```
load_scanpath_data(words: TablesLike | None = None, fixations: TablesLike | None = None, *, word_schema: dict | None = None, fix_schema: dict | None = None, trial_parts_manifest: dict | None = None, image_root: str | Path | None = None, image_pattern: str = '{text_id}.png', keep_columns: Iterable[str] | None = None, names: str = NAMES_SOURCE) -> ScanpathData
```

Load and normalize a words/IA table and/or a fixations table.

The columns keep the names your files give them: `CURRENT_FIX_DURATION`, not `duration_ms`. A column Scanpath Studio built, converted, computed or changed keeps its internal name, and `data.column_names` (a ScanpathData) records what every column was called. Every API function takes these frames, and every column option (`color_by=`, hover fields …) takes either name. `names="canonical"` returns the internal names instead — the same for every dataset, for code that works across them.

`words` / `fixations` may be DataFrames, paths to `.csv` / `.tsv` / `.txt` / `.tab` / `.parquet` / `.feather` / `.xlsx` / `.xls` files (or a `.zip` of them), glob patterns, or lists of paths — multi-file datasets (one file per participant and/or text) are concatenated, with each file's stem kept in a `source_file` column. Column schemas are auto-detected (EyeLink, Gazepoint, Tobii, SMI, Pupil Labs, and snake_case names); pass `word_schema` / `fix_schema` mappings (field → column name; see propose_schema) to override detection.

`trial_parts_manifest` accepts a nested parent-trial/parts definition for datasets whose source tables identify screens through arbitrary selector columns; explicit `screen_id` / `screen_index` columns can instead be mapped directly in each schema. Either table may be omitted for datasets that ship only one report: the missing side comes back as an empty canonical frame and the plots simply skip that layer. Words without a participant column (stimulus-level AoIs) are copied onto every reading in the fixations — each reading matched by its trial id, else the trial id it had before a repeat's `_r2` suffix, else its `text_id` (trial ids that embed the reader), with a `data.StimulusJoinWarning` (a `UserWarning`) when some readings match none — and fixations without x/y but with a word/AoI ID are placed at word-box centers. Columns named in `data.INTERNAL_COLUMNS` are the pipeline's bookkeeping (`data.drop_internal_columns` removes them).

Normalization keeps the mapped fields and the recognised optional ones (eye, EyeLink's interest-area measures, linguistic features …) and drops the rest. `keep_columns` names further columns of your own to carry through under their own names — a pupil size, a detection confidence — from whichever table has them, so a figure can colour, hover or plot by them (the app's *Keep columns*; `render --keep-columns` on the command line).

Returns the normalized `(words, fixations)` frames the plotting functions expect. Raises `ValueError` if a required field can't be found — the message names the canonical field, the column names auto-detection looked for, and the columns the table actually has — and `data.StimulusJoinError` (a `ValueError`) when a stimulus-level words table shares neither a trial id nor a `text_id` with any reading (or, multipart, with every screen a reading has fixations on).

### scanpath_studio.api.ScanpathData

Bases: `tuple`

What load_scanpath_data returns: the `(words, fixations)` frames — so `words, fixations = load_scanpath_data(…)` unpacks it — plus `column_names`, the dataset's own name for every canonical column, per table (`{"words": ColumnNames, "fixations": ColumnNames}`).

With `names="source"` (the default) the frames' columns are the dataset's own names and each frame carries its map, so any API function takes it — sliced, filtered or merged — and the names it writes are yours. With `names="canonical"` they are the internal names, the same for every dataset.

### scanpath_studio.api.load_sample_data

```
load_sample_data(*, names: str = NAMES_SOURCE) -> ScanpathData
```

Return the bundled OneStop demo, normalized and ready to plot: two readers, twelve paragraphs each, every one of them with fixations. Under the demo's own column names; `names="canonical"` for the internal ones (see load_scanpath_data).

### scanpath_studio.api.load_raw_gaze

```
load_raw_gaze(table: TablesLike, *, raw_gaze_schema: dict | None = None, names: str = NAMES_SOURCE) -> DataFrame
```

Load and normalize a raw (sample-level) gaze table for `raw_gaze=`.

The third table plot_scanpath can draw, under the fixations: one row per eye-tracker sample, with a participant, a trial, `x` / `y` and usually a timestamp. `table` is a DataFrame, path, glob or list of paths, like load_scanpath_data's, and the columns are auto-detected the same way; pass `raw_gaze_schema` (field → column, see `api.propose_schema(table, "raw_gaze")`) to override the detection. `plot_scanpath` keeps only the plotted trial's (and screen's) samples, so one table can serve a whole corpus::

```
raw_gaze = sps.load_raw_gaze("gaze_samples.csv")
fig = sps.plot_scanpath(words, fixations, "p1", "t3", raw_gaze=raw_gaze)
```

Under the table's own column names, like `load_scanpath_data`'s; `names="canonical"` for the internal ones.

### scanpath_studio.api.load_sample_raw_gaze

```
load_sample_raw_gaze(*, names: str = NAMES_SOURCE) -> DataFrame
```

The bundled demo's raw gaze, normalized — what the app overlays on it.

OneStop ships no sample-level gaze, so this is **synthesized** from one of the demo's real trials and covers that trial alone.

### scanpath_studio.api.load_participant_metadata

```
load_participant_metadata(table: TablesLike, *, id_column: str | None = None, participants: DataFrame | list | None = None)
```

Load a participant-level metadata table.

`table` is a DataFrame or a path/glob to a CSV/TSV/Parquet/Excel file with **one row per reader**: an id column plus anything known about them (`native_language`, `age`, a comprehension score). `id_column` defaults to the first recognised spelling (`participant_id`, `subject`, `RECORDING_SESSION_LABEL`, …).

Pass `participants` — a normalized frame or a list of ids — to have the join validated against the data you actually loaded; the returned object's `.report` then names the readers missing from either side.

Returns a `ParticipantMetadata`: the cleaned frame, a field registry (name, label, grain, dtype, missingness), and the join report. Nothing is broadcast onto the words/fixations frames — use `scanpath_studio.metadata.project` to attach chosen columns to a per-trial frame, or `.values_for(pid)` for one reader.

> > > words, fixations = load_sample_data() meta = load_participant_metadata( ... "readers.csv", participants=fixations ... ) # doctest: +SKIP meta.names # doctest: +SKIP ('native_language', 'age')

### scanpath_studio.api.load_trial_metadata

```
load_trial_metadata(table: TablesLike, *, id_column: str | None = None, participant_column: str | None = None, trials: DataFrame | None = None)
```

Load a trial-level metadata table.

The sibling of load_participant_metadata, one grain down: `table` has **one row per reading** — a trial-id column plus anything known about that reading (a list name, a condition, a per-trial comprehension score).

**The key is yours to state, and it changes what the table means.** Keyed by trial id alone, a row describes a *text*, and every reader's reading of it inherits that row; pass `participant_column` to key by reader **and** trial, so a row describes one *reading*. Nothing in a file says which world a corpus is in, so this is never inferred — unlike `id_column`, which defaults to the first recognised spelling (`trial_id`, `item_id`, `TRIAL_INDEX`, …).

Pass `trials` — a normalized fixations/words frame, or any frame with `participant_id` + `trial_id` — to have the join validated against the data you actually loaded; the returned `.report` then names the trials missing from either side.

Returns a `TrialMetadata`: the cleaned frame, a field registry, and the join report. As with the participant table, nothing is broadcast onto the words/fixations frames.

> > > words, fixations = load_sample_data() meta = load_trial_metadata( ... "readings.csv", trials=fixations ... ) # doctest: +SKIP meta.names # doctest: +SKIP ('list_name', 'comprehension_score')

### scanpath_studio.api.load_text_metadata

```
load_text_metadata(table: TablesLike, *, id_column: str | list[str] | None = None, texts: DataFrame | list | None = None)
```

Load a text-level metadata table — the third grain.

`table` has **one row per text** — a text-id column plus anything known about that text (genre, difficulty, a stimulus-level comprehension score). Flat grain, like load_participant_metadata: never keyed by reader, since a text is a stimulus rather than something one reader owns. `id_column` defaults to the first recognised spelling (`text_id`, `paragraph_id`, `stimulus_id`, …) and may be several columns to build a composite id, the same way the uploaded data's own Text ID mapping does.

Pass `texts` — a normalized fixations/words frame, or any iterable of text ids — to have the join validated against the data you actually loaded; the returned `.report` then names the texts missing from either side.

Returns a `TextMetadata`: the cleaned frame, a field registry, and the join report. As with the other two grains, nothing is broadcast onto the words/fixations frames.

> > > words, fixations = load_sample_data() meta = load_text_metadata( ... "texts.csv", texts=words ... ) # doctest: +SKIP meta.names # doctest: +SKIP ('genre', 'difficulty')

### scanpath_studio.api.propose_schema

```
propose_schema(table: TablesLike, kind: str = 'words') -> dict
```

Auto-detected column mapping for a **raw** (un-normalized) table.

`kind` is `"words"`, `"fixations"` or `"raw_gaze"`. Returns `{canonical field: source column or None}` — the same mapping load_scanpath_data infers internally, so it's the place to start when detection got a field wrong or couldn't find one: edit the dict and pass it back as `word_schema=` / `fix_schema=`::

```
from scanpath_studio import api

schema = api.propose_schema("ia.csv", "words")
schema["trial"] = "TRIAL_LABEL"
words, fixations = api.load_scanpath_data("ia.csv", "fix.csv",
                                          word_schema=schema)
```

`table` is a DataFrame, path, glob or list of paths, like the loader's.

### scanpath_studio.api.build_authored_scanpath

```
build_authored_scanpath(text: str, events: DataFrame | None = None, **layout_options) -> tuple[DataFrame, DataFrame]
```

Build normalized word/fixation frames from hand-authored reading events.

When `events` is omitted, one centered fixation per laid-out word is used. `layout_options` are forwarded to `authoring.layout_text`.

### scanpath_studio.api.load_authored_scanpath

```
load_authored_scanpath(source: str | Path) -> tuple[DataFrame, DataFrame]
```

Load a scanpath-author JSON file (or its text) as normalized word/fixation frames.

### scanpath_studio.datasets.load_potec

```
load_potec(root, *, readers: Iterable | None = None, texts: Iterable[str] | None = None, download: bool = False, names: str = 'source') -> tuple[DataFrame, DataFrame]
```

Load PoTeC as normalized `(words, fixations)` frames, ready to plot.

Under PoTeC's own column names; `names="canonical"` for the internal ones (see `api.load_scanpath_data`).

`root` is a clone of the PoTeC repo (with the eye-tracking data downloaded) or any folder; with `download=True` the needed files are fetched into it on first use (~45 MB). Narrow the load with `readers` (e.g. `[0, 1]`) and/or `texts` (e.g. `["b0", "p3"]`) — the full corpus is 75 readers × 12 texts = 900 trials.

Participants are PoTeC reader ids (as strings); a trial is one reader's reading of one text, `<reader>_<text>` (`"0_b0"`), and `text_id` is the text (`b0`–`b5` biology, `p0`–`p5` physics)::

```
import scanpath_studio as sps

words, fixations = sps.load_potec("data/PoTeC", readers=[0], texts=["b0"])
fig = sps.plot_scanpath(
    words, fixations, "0", "0_b0", canvas_size=(1680, 1050)
)
```

The PoTeC monitor was 1680×1050 (DELL P2210, 60 Hz); pass that as `canvas_size` to plot_scanpath for true-to-scale rendering.

### scanpath_studio.datasets.load_onestop

```
load_onestop(root, *, regime: str = 'ordinary', parts: Iterable[str] | None = None, variant: str = 'public', download: bool = False, names: str = 'source') -> tuple[DataFrame, DataFrame]
```

Load OneStop as normalized `(words, fixations)` frames, ready to plot.

Under OneStop's own column names; `names="canonical"` for the internal ones (see `api.load_scanpath_data`).

`root` is a folder holding (or to download into, public variant only) the OneStop reports. Narrow the load with `regime` (`ordinary` / `information_seeking` / `repeated` / `information_seeking_repeated`), `parts` (any subset of `Title / Question_Preview / Paragraph / Questions / Answers / QA / Feedback` — default Paragraph), and `variant` (`public` OSF release or `lacclab` local export). The public OSF reports are large; pass `download=True` to fetch the chosen regime + parts into `root` on first use::

```
import scanpath_studio as sps

words, fixations = sps.load_onestop(
    "data/OneStop", regime="ordinary", parts=["Paragraph"], download=True
)
pid, tid = sps.list_trials(words, fixations).iloc[0]  # one reading
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
```

OneStop's presentation monitor was 2560×1440 (Dell U2715H) — the citation lives in `scanpath_studio.eyegenbench_geometry.DISPLAY_SPECS`'s `"onestop"` entry (Berzak et al. 2025, Methods → Apparatus); pass that as `canvas_size` to plot_scanpath for true-to-scale rendering. The reports already match the bundled demo's schema, so this reuses the generic auto-detect → normalize path (no OneStop-specific column mapping).

## Inspect

### scanpath_studio.api.list_trials

```
list_trials(words: DataFrame | None = None, fixations: DataFrame | None = None, *, raw_gaze: DataFrame | None = None) -> DataFrame
```

Plottable `(participant_id, trial_id)` combos.

Combos present in both frames when both are loaded; for single-report datasets (words-only or fixations-only), combos from whichever frame has data. `raw_gaze` (a frame from load_raw_gaze) adds the trials that only its samples cover — every trial, for a dataset recorded as raw gaze alone (pass `None` for `words` and `fixations` then). The id columns take the names the frames carry.

### scanpath_studio.api.list_parts

```
list_parts(words: DataFrame | None, fixations: DataFrame | None, participant: str | None = None, trial: str | None = None, *, raw_gaze: DataFrame | None = None) -> DataFrame
```

Ordered screens in multipart data, optionally narrowed to one parent.

Single-screen data returns an empty table. A trial recorded as raw gaze alone takes its screens from `raw_gaze` (its `screen_id`), decided per trial — so a samples-only trial keeps its screens in a dataset whose other trials have fixations.

### scanpath_studio.api.check_data_health

```
check_data_health(words: DataFrame | None = None, fixations: DataFrame | None = None, raw_gaze: DataFrame | None = None) -> DataFrame
```

Values that loaded as numbers but cannot be right — the Data page's *Data checks*.

Checks the normalized tables (from load_scanpath_data / load_raw_gaze) for fixations lasting 0 ms or less or with an infinite duration or onset, fixations and raw-gaze samples whose position is missing or infinite, word boxes with no area or no finite position, and per-screen screen sizes that are not finite and positive. One row per check that found anything: `table`, `check`, `problem`, the `columns` it read (in the names the frames carry), `rows` of `of_rows`, the `trials` they fall in, a `breakdown` by kind, `severity` (`"note"` for raw-gaze gaps, which blinks and track loss make ordinary), `what_happens` to those rows in the app, and a few `examples`. An empty frame means every check passed. Nothing is changed or dropped::

```
words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
print(sps.check_data_health(words, fixations))
```

## Plot

### scanpath_studio.api.plot_scanpath

```
plot_scanpath(words: DataFrame | None = None, fixations: DataFrame | None = None, participant: str | None = None, trial: str | None = None, *, screen: str | None = None, canvas_size: tuple[int, int] | None = None, base_font_size: int = 16, font_family: str = FONT_FAMILY, raw_gaze: DataFrame | None = None, drift_correction: str | None = None, drift_connectors: bool = False, fix_index_range: tuple[int, int] | None = None, illustration: bool = False, illustration_label: str = 'auto', title: str = '', caption: str = '', column_names: dict | None = None, **figure_overrides) -> Figure
```

Build the canonical scanpath figure for one trial.

`words` / `fixations` are normalized frames from load_scanpath_data. `participant` / `trial` may be omitted when the frames contain exactly one combo. `canvas_size` is the monitor size in px; by default it is estimated from the data extents — pass the real monitor resolution (e.g. `(2560, 1440)` for OneStop) to keep coordinates true to scale. For a multipart trial, `screen` selects one child screen; omitting it selects the first recorded screen and never concatenates coordinate spaces. `raw_gaze` is a frame from load_raw_gaze, filtered to the selected trial and drawn as recorded. It can be the only table: for a dataset recorded as raw gaze alone pass `None` for `words` and `fixations` (`plot_scanpath(raw_gaze=samples, trial=…)`) — the trial is looked up in the samples, the canvas is estimated from their extent, and the figure is the samples alone. Nothing is derived from them: no fixations are detected, so the fixation, saccade and heatmap layers stay empty.

`drift_correction` / `drift_connectors` are experimental: without `SCANPATH_EXPERIMENTAL=1` any `drift_correction` other than `None` / `"off"` raises `ValueError`.

`fix_index_range=(start, end)` draws only fixations `start` through `end` (1-based, both inclusive) of the trial — the headless form of the app's fixation-index window.

`title` / `caption` stamp a title/caption band onto the figure without shrinking the plot area, exactly like the rail's *Title* / *Caption* rows — literal text here, not the rail's `{trial_id}`-style pattern, since the caller already knows which trial this is.

Remaining keywords override the app's defaults and are forwarded to `plots.make_scanpath_figure` (e.g. `show_heatmap=False`, `color_by="pass_index"`, `x_field="order_in_trial"`); an unknown keyword raises a `TypeError` naming the closest valid options, and figure_options lists them all with their defaults. A `color_by` / `highlight_column` naming a column the trial's table doesn't have raises a `ValueError` naming the closest ones, rather than drawing without it.

Frames under the dataset's own column names (what `load_scanpath_data` returns by default) are read through the map they carry, and an option naming a column takes either name. `column_names` is that map for frames loaded with `names="canonical"` (`data.column_names`): the options then take the dataset's names too, and the figure's text uses them.

### scanpath_studio.api.animate_scanpath

```
animate_scanpath(words: DataFrame | None = None, fixations: DataFrame | None = None, participant: str | None = None, trial: str | None = None, *, screen: str | None = None, screen_b: str | None = None, canvas_size: tuple[int, int] | None = None, base_font_size: int = 16, font_family: str = FONT_FAMILY, playback_speed: float = 1.0, autoplay: bool = True, fix_index_range: tuple[int, int] | None = None, fix_index_range_b: tuple[int, int] | None = None, illustration_label: str = 'auto', title: str = '', caption: str = '', column_names: dict | None = None, trial_b: tuple[str, str] | None = None, dataset_b: str | None = None, setup: SetupSnapshot | None = None, setup_b: SetupSnapshot | None = None, **animation_overrides) -> Figure
```

Build the animated scanpath replay for one trial.

Same trial selection, canvas and column-name semantics as plot_scanpath (`column_names` included), and `screen` selection for multipart trials. The replay takes the reading time divided by `playback_speed`: save it as interactive HTML with save_figure, whose page keeps that clock itself, or rasterize it to GIF/MP4 with `animation_export.export_animation`, which lasts as long. (`fig.show()` plays it on Plotly's own frame queue, which runs slow.) `fix_index_range=(start, end)` replays only that window of the trial's fixations (1-based, inclusive), like plot_scanpath.

With `autoplay` (default `True`) the saved interactive HTML auto-starts the replay on load *at `playback_speed`* — save_figure honors the marker the builder stamps on the figure. Pass `autoplay=False` to save a figure that opens paused (press ▶ Play to run it). Autoplay only affects the interactive HTML; a GIF/MP4 always plays from its first frame.

When `playback_speed` is not `1`, the automatic Illustration label says the replay timing was changed. `illustration_label` accepts `"auto"`, `"show"`, or `"hide"` like plot_scanpath.

In a co-animation `fix_index_range` windows A only (the app's rule — A's slider never cuts B), `fix_index_range_b` windows B, and `fixation_flags_b` gives B flags of its own (`None`: A's `fixation_flags`, or the `fixation_flags` of `style_b` when it names some).

`style_a` / `style_b` style the two scanpaths of a co-animation as they style compare_scanpaths' — the same keys (`fix_color`, `marker_size_range`, `opacity`, `hollow`, `saccade_color`, `saccade_style`, `saccade_width`), resolved the same way, so the replay and the static comparison draw each reading alike. The replay has no saccade-class filter, so a style naming `saccade_classes` raises `ValueError`. A lone replay ignores both.

`trial_b=(participant, trial)` co-animates a second reading on the same clock, like the app's Animate + Compare. It is looked up in `words_b` / `fixations_b` when given, else in `words` / `fixations` — the way compare_scanpaths takes it. Without `trial_b`, `words_b` / `fixations_b` must hold one trial; B frames holding several raise `ValueError` rather than drawing them all. A multipart B is drawn at `screen_b` — looked up in B's own trial — or at its first recorded screen without it, as A is with `screen`.

**Two datasets.** Both readings are drawn in A's coordinates, so a co-animation is an overlay, and a reading from another dataset has to share A's screen. Name that dataset with `dataset_b` (or give its `setup_b`) and the pair is checked the way `compare_scanpaths` checks an overlay: two different canvases raise `IncomparableScreensError`, a `ValueError`, rather than draw. `setup` / `setup_b` are `experimental_setup.SetupSnapshot` values; a side without one is read off its data — the extent of that one trial, which rarely spans the whole screen, so state both when you know them — and `canvas_size` covers A when you only have a resolution. `dataset_b` also prefixes B's participant ids with the dataset's name, as `compare_scanpaths` does, so a hover says whose reader it is. `words_b` / `fixations_b` passed without either are taken to be from A's dataset, as `render` passes them for `--compare-with` alone, and are not checked: two readings of one corpus can span different extents, and inferring a canvas from each would refuse pairs that shared a screen.

The animation builder accepts a subset of the static figure's options (`show_words`, `show_word_labels`, `show_saccades`, `show_order`, styling, and second-scanpath overlays) — see `figure_options("animation")`; an unsupported key raises a `ValueError` naming the valid ones. The shared options default to the same values as plot_scanpath (`CANONICAL_FIGURE_DEFAULTS`), so the replay matches the static figure. `palette=` works here too; the colours it implies that the animation doesn't support are dropped rather than raising, since the caller named a look, not those individual keys.

`title` / `caption` — same as plot_scanpath.

The replay is made of fixations, so a trial without any — one recorded as raw gaze alone, or a words-only one — raises `ValueError` rather than returning an empty replay, and `raw_gaze=` is refused: the replay draws no raw-gaze layer, and nothing detects fixations from samples. Draw samples with plot_scanpath`(raw_gaze=…)`.

### scanpath_studio.api.compare_scanpaths

```
compare_scanpaths(words: DataFrame, fixations: DataFrame, trial_a: tuple[str, str], trial_b: tuple[str, str], *, screen: str | None = None, screen_b: str | None = None, words_b: DataFrame | None = None, fixations_b: DataFrame | None = None, dataset_b: str = 'Dataset B', raw_gaze: DataFrame | None = None, raw_gaze_b: DataFrame | None = None, layout: str = 'overlay', compare_stimulus: str = 'both', setup: SetupSnapshot | None = None, setup_b: SetupSnapshot | None = None, canvas_size: tuple[int, int] | None = None, labels: tuple[str, str] | None = None, style_a: dict | None = None, style_b: dict | None = None, base_font_size: int = 16, font_family: str = FONT_FAMILY, fix_index_range: tuple[int, int] | None = None, fix_index_range_b: tuple[int, int] | None = None, drift_correction: str | None = None, title: str = '', caption: str = '', column_names: dict | None = None, **figure_overrides) -> Figure
```

Build a two-scanpath comparison figure.

The headless form of the app's **Compare** mode. `trial_a` / `trial_b` are `(participant, trial)` pairs; `layout` is `"overlay"`, `"side_by_side"` (`"side-by-side"` also accepted) or `"stacked"`.

**Multipart trials.** Each scanpath is one screen, never a whole multipart trial: every screen is its own coordinate space, so pooling them would draw saccades across page boundaries. `screen` picks A's screen and `screen_b` B's, independently — B's is looked up in B's own frames, so it may be a later page or another dataset's. Either one left out is that trial's first recorded screen, as in plot_scanpath; `list_parts()` lists them. A screen named for a single-screen trial, or one the trial does not have, raises `ValueError`.

**Two datasets.** Pass `words_b` / `fixations_b` to draw B from a *different* corpus. Two corpora can hold the same `(participant_id, trial_id)` and the builder slices by exactly that pair, so B's participant ids are namespaced with `dataset_b` inside the throwaway merged frames — without it one reading would silently render as two. The frames you pass in are never modified, and nothing in the returned figure's data depends on the namespace beyond the trace labels.

**The overlay gate.** Across datasets an overlay needs both canvases to be the same size; otherwise this raises `ValueError` (the app falls back to side by side). One dataset can hold screens of different sizes too, so a same-dataset pair is refused the same way when the two selected screens carry different canvases (`canvas_width` / `canvas_height` columns) or `setup_b` states another screen. Pass `layout="side_by_side"` or `"stacked"` to compare readings from different screens; each panel is then drawn to its own. Nothing is rescaled.

`setup` / `setup_b` are `experimental_setup.SetupSnapshot` values — what the gate reads. `canvas_size` covers A when you only have a resolution; omit both and the canvas is read off the data.

**Stimulus images.** `background_image` is A's page. A split layout draws B's panel over `background_image_b` (with `background_image_size_b` / `background_image_origin_b`) and over nothing without it — never A's, since sharing a dataset says nothing about sharing a page.

`compare_stimulus` picks whose word boxes and text an **overlay** draws — `"both"` (default), `"a"` or `"b"`. Two datasets' AOIs coincide only when the text is identical. Split layouts ignore it; each panel owns its own stimulus.

**Per-scanpath style.** `style_a` / `style_b` restyle one scanpath: `fix_color`, `marker_size_range`, `opacity`, `hollow`, `saccade_color`, `saccade_style`, `saccade_width`, `box_color` — the outline of that reading's word boxes, its `fix_color` when left out — `box_fill_color`, their fill, `word_box_fill_color` when left out — and `raw_gaze_color`, that reading's raw-gaze samples, its `fix_color` when left out. These three are this figure's only: the co-animation draws one set of boxes, in `word_box_color` / `word_box_fill_color`, and no raw gaze, and ignores them.

**Filters, per scanpath.** `fixation_flags` and `saccade_classes` filter both scanpaths, as they filter plot_scanpath's one; the same two keys in `style_a` / `style_b` give that scanpath its own, overriding them — e.g. `style_b={"fixation_flags": {"short": {"mode": "Discard", "threshold_ms": 80}}, "saccade_classes": ["regression"]}`. The app's Compare mode draws A under the rail's filters and B under B's own. `fix_index_range` windows both scanpaths; `fix_index_range_b` gives B a window of its own (the app's B slider).

**Raw gaze.** `raw_gaze` is a frame from load_raw_gaze; each reading's samples are drawn under its scanpath, in that scanpath's colour (`raw_gaze_marker_size` / `raw_gaze_opacity` style them). It serves both readings of a same-dataset comparison; across datasets it is A's, and `raw_gaze_b` is B's. Passing either turns the layer on; `show_raw_gaze=False` keeps it off.

Remaining keywords are forwarded to `plots.make_comparison_figure` (e.g. `show_words=False`, `color_by="duration_ms"`); an unknown one raises `TypeError` naming the closest valid options; `figure_options("comparison")` lists the accepted keywords. Column names follow plot_scanpath's rule: A's names (or `column_names`) name the options and the figure's text, and either dataset's frames may come under their own names.

### scanpath_studio.api.render_parent_trial

```
render_parent_trial(words: DataFrame, fixations: DataFrame, participant: str | None = None, trial: str | None = None, *, animate: bool = False, transition_mode: str = 'instant', **options) -> dict[str, Figure]
```

Render every screen of one logical trial without stitching coordinates.

The ordered mapping is keyed by `screen_id`. Each value is the same figure returned by plot_scanpath or animate_scanpath; callers can save them into deterministic per-screen files. `transition_mode` is `"instant"` or `"recorded"`. For animated output, each figure's `layout.meta['transition_after_ms']` records the delay before the next screen (zero for instant mode, or the observed parent-clock gap). No visual saccade is ever drawn across the boundary.

### scanpath_studio.api.plot_corpus_figure

```
plot_corpus_figure(data: DataFrame, *, kind: str, measure_label: str = 'Value', series_col: str = 'series', value_col: str = 'value', colors: tuple[str, ...] | None = None, canvas_width: int = 1000, base_font_size: int = 14, font_family: str = FONT_FAMILY) -> Figure
```

Headless corpus profile/distribution/difference plot with shared colours.

`profile` expects `word_id` plus `value_col` (and optional `lo` / `hi`); `distribution` expects `value_col`; `difference` expects `word_id` and `diff`. When `series_col` is present, it defines the overlaid profile/distribution series. A table missing a column its `kind` reads raises `ValueError` naming it and the columns present.

## Reproduce a figure in code

The app's **Share** subtab shows the API or CLI code that rebuilds the figure currently on screen — paste it into a notebook or terminal to get the same figure. `figure_code` is the headless form of that block, and `render --print-code` prints it for an invocation you already have.

```
print(
    sps.figure_code(
        participant="l7_1090",
        trial="l7_1090_2_1_1_Ele_r0",
        show_heatmap=False,
        color_by="duration_ms",
    )
)
```

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()

fig = sps.plot_scanpath(
    words,
    fixations,
    participant='l7_1090',
    trial='l7_1090_2_1_1_Ele_r0',
    canvas_size=(2560, 1440),
    color_by='duration_ms',
    show_heatmap=False,
)

sps.save_figure(fig, 'scanpath.png')
```

### scanpath_studio.api.figure_code

```
figure_code(*, kind: str = 'static', source: str = 'demo', source_options: dict | None = None, participant: str = '', trial: str = '', screen: str | None = None, compare: tuple[str, str] | None = None, compare_screen: str | None = None, compare_layout: str = 'overlay', compare_stimulus: str = 'both', compare_dataset: str = '', compare_canvas: tuple[int, int] | None = None, compare_labels: tuple[str, str] | None = None, canvas_size: tuple[int, int] | None = None, base_font_size: int = 16, font_family: str = FONT_FAMILY, title: str = '', caption: str = '', fix_index_range: tuple[int, int] | None = None, illustration_label: str = 'auto', drift_correction: str | None = None, drift_connectors: bool = False, playback_speed: float = 1.0, autoplay: bool = True, flavor: str = 'python', explicit: bool = False, output: str | None = None, **figure_overrides) -> str
```

The API or CLI code that reproduces a figure.

The headless twin of the app's 🔗 Share → *Reproduce this figure in code* block: give it the same arguments you would give plot_scanpath (`kind="static"`), animate_scanpath (`"animation"`) or compare_scanpaths (`"comparison"`) and it returns the snippet that rebuilds that figure, rather than the figure::

```
print(sps.figure_code(participant="l7_1090", trial="l7_1090_2_1_1_Ele_r0",
                      show_heatmap=False, flavor="cli"))
```

`source` names how the data is loaded — `"demo"`, `"synthetic"`, `"files"`, `"potec"`, `"onestop"`, `"multipleye"`, `"benchmark"`, `"author"`, or `"unknown"` for data a snippet can't name — with `source_options` carrying that loader's arguments (`{"root": …}`, `{"words": [...], "fixations": [...]}`, and so on). With `show_raw_gaze=True` the raw-gaze table is read too: the demo's own, or the path(s) given as `source_options["raw_gaze"]` (plus an optional `"raw_gaze_schema"`) — load_raw_gaze in the Python form, `--raw-gaze` in the CLI one. `source="raw_gaze"` is a dataset recorded as raw gaze alone: the samples at `source_options["raw_gaze"]` are the data, and `plot_scanpath` is handed `None` for the words and fixations.

`screen` / `compare_screen` are A's and B's screens of a multipart trial (`screen=` / `screen_b=`, `--screen` / `--compare-screen`).

`compare_dataset` names the corpus scanpath B was loaded from when it is a *second* one. B's participant id belongs to that corpus rather than the one the snippet loads, so both forms then load B's own tables and name B in them — `words_b=` / `fixations_b=` / `dataset_b=`, and `--compare-words` / `--compare-fixations` beside `--compare-with` — from the placeholder paths `B_WORDS` / `B_FIXATIONS`, which you point at its files. `compare_canvas` is B's screen, `(width, height)`, when you know it: written as `setup_b=` and `--compare-canvas`, which a co-animation across datasets needs.

`compare_labels` is the pair you would pass compare_scanpaths as `labels=` — the two trace labels, when they are not the composed defaults. Both forms carry them: `labels=` in the Python snippet, `--label-a` / `--label-b` in the CLI one.

With `participant` / `trial` left empty the snippet renders the first available trial, as `render` does. `canvas_size` defaults to the screen `render` assumes for the source (the demo's 2560×1440, PoTeC's 1680×1050, …), so both flavours draw the same figure; `output` defaults to `scanpath.html` for an animation — `render --animate` writes only HTML — and to a PNG otherwise.

Only the options that differ from figure_options are written, so the snippet stays readable; `explicit=True` emits every option at its current value. `flavor` is `"python"`, `"cli"`, or `"both"` (the two separated by a blank line). Anything neither form can reproduce — a raw-gaze table with no path to name, an uploaded stimulus image, B's rows from a second corpus — follows as `# Note:` comments, matching the ⚠️ captions the app shows and the `Note:` lines `render --print-code` writes to stderr. See `code_snippet.ReproductionCode` for the structured form.

### scanpath_studio.api.figure_options

```
figure_options(kind: str = 'static') -> dict
```

Every figure keyword a builder accepts → the default it renders with.

`kind="static"` covers plot_scanpath, `kind="animation"` animate_scanpath (whose builder supports a subset), and `kind="comparison"` compare_scanpaths. The values are the *effective* defaults — `CANONICAL_FIGURE_DEFAULTS` where it sets one, the builder's default otherwise — so a scripted caller can diff its intended settings against what it would get::

```
{k: v for k, v in sps.figure_options().items() if k.startswith("show_")}
```

## Figure options

Every keyword the figure builders take, with the default it renders with, the `render` flag that sets it on the command line, and which builders accept it: `plot` is `plot_scanpath`, `animate` is `animate_scanpath`, `compare` is `compare_scanpaths`.

| Option                            | Default                                        | `render` flag                                             | Accepted by      |
| --------------------------------- | ---------------------------------------------- | --------------------------------------------------------- | ---------------- |
| `anim_grid_step_ms`               | `None`                                         | `--anim-grid-step-ms`                                     | animate          |
| `anim_max_frames`                 | `None`                                         | `--anim-max-frames`                                       | animate          |
| `background_color`                | `'#ffffff'`                                    | `--background-color`                                      | all three        |
| `background_image`                | `None`                                         | `--stimulus-image`                                        | all three        |
| `background_image_b`              | `None`                                         | `--stimulus-image-b`                                      | compare          |
| `background_image_opacity`        | `1.0`                                          | `--stimulus-image-opacity`                                | all three        |
| `background_image_origin`         | `None`                                         | `--stimulus-image-origin`                                 | all three        |
| `background_image_origin_b`       | `None`                                         | `--stimulus-image-origin-b`                               | compare          |
| `background_image_size`           | `None`                                         | `--stimulus-image-size`                                   | all three        |
| `background_image_size_b`         | `None`                                         | `--stimulus-image-size-b`                                 | compare          |
| `color_by`                        | `'(uniform)'`                                  | `--color-by`                                              | all three        |
| `color_by_line`                   | `False`                                        | `--color-by-line`                                         | all three        |
| `compare_stimulus`                | `'both'`                                       | `--compare-stimulus`                                      | animate          |
| `connector_y`                     | `None`                                         | —                                                         | plot, compare    |
| `coordinate_grid_spacing`         | `None`                                         | `--coordinate-grid-spacing`                               | all three        |
| `critical_span_style`             | `'Mark text'`                                  | `--critical-span-style`                                   | plot, compare    |
| `duration_size_legend`            | `True`                                         | `--no-duration-size-legend`                               | all three        |
| `fit_to_monitor`                  | `True`                                         | `--no-full-monitor`                                       | all three        |
| `fixation_color`                  | `'#0072B2'`                                    | `--fixation-color`                                        | all three        |
| `fixation_color_range`            | `None`                                         | `--fixation-color-range`                                  | all three        |
| `fixation_colorbar_orientation`   | `'Vertical'`                                   | `--fixation-colorbar-orientation`                         | all three        |
| `fixation_colorbar_tickangle`     | `0`                                            | `--fixation-colorbar-tickangle`                           | all three        |
| `fixation_colorbar_tickfont_size` | `12`                                           | `--fixation-colorbar-tickfont-size`                       | all three        |
| `fixation_colorscale`             | `'Blues'`                                      | `--fixation-colorscale`                                   | all three        |
| `fixation_flags`                  | `None`                                         | `--fixation-flag`                                         | all three        |
| `fixation_flags_b`                | `None`                                         | `--compare-fixation-flag`                                 | animate          |
| `fixation_hover_fields`           | `['order_in_trial', 'duration_ms', 'word_id']` | `--fixation-hover-fields`                                 | all three        |
| `fixation_opacity`                | `0.7`                                          | `--fixation-opacity`                                      | all three        |
| `fixation_snap_to_word`           | `False`                                        | `--snap-fixations`                                        | plot, compare    |
| `fixation_symbol`                 | `'circle'`                                     | `--fixation-symbol`                                       | all three        |
| `fixations_b`                     | `None`                                         | —                                                         | animate          |
| `heatmap_colorbar_orientation`    | `'Vertical'`                                   | `--heatmap-colorbar-orientation`                          | all three        |
| `heatmap_colorbar_tickangle`      | `0`                                            | `--heatmap-colorbar-tickangle`                            | all three        |
| `heatmap_colorbar_tickfont_size`  | `12`                                           | `--heatmap-colorbar-tickfont-size`                        | all three        |
| `heatmap_colorscale`              | `'Blues'`                                      | `--heatmap-colorscale`                                    | plot, compare    |
| `heatmap_metric`                  | `'duration_ms'`                                | `--heatmap-metric`                                        | plot, compare    |
| `heatmap_norm`                    | `'Linear'`                                     | `--heatmap-norm`                                          | plot, compare    |
| `heatmap_range`                   | `None`                                         | `--heatmap-range`                                         | plot, compare    |
| `heatmap_sigma_px`                | `None`                                         | `--heatmap-sigma`                                         | plot, compare    |
| `heatmap_style`                   | `'Word boxes'`                                 | `--heatmap-style`                                         | plot, compare    |
| `highlight_column`                | `'is_in_aspan'`                                | `--highlight-column`                                      | all three        |
| `highlight_text_color`            | `'#D55E00'`                                    | `--highlight-text-color`                                  | all three        |
| `hollow_fixations`                | `False`                                        | `--hollow-fixations`                                      | all three        |
| `illustration_reasons`            | `None`                                         | —                                                         | plot, compare    |
| `illustration_text`               | `''`                                           | `--illustration-text`                                     | all three        |
| `label_a`                         | `'Scanpath A'`                                 | `--label-a`                                               | animate          |
| `label_b`                         | `'Scanpath B'`                                 | `--label-b`                                               | animate          |
| `line_spacing`                    | `3.0`                                          | `--line-spacing`                                          | all three        |
| `marker_duration_range`           | `(50, 600)`                                    | `--marker-duration-range`                                 | all three        |
| `marker_size_range`               | `(8, 24)`                                      | `--marker-size-range`                                     | all three        |
| `marker_size_scale`               | `'sqrt'`                                       | `--marker-size-scale`                                     | all three        |
| `order_font_color`                | `'#111111'`                                    | `--order-font-color`                                      | all three        |
| `order_font_size`                 | `10`                                           | `--order-font-size`                                       | all three        |
| `raw_gaze_color`                  | `'#888888'`                                    | `--raw-gaze-color`                                        | all three        |
| `raw_gaze_marker_size`            | `4.0`                                          | `--raw-gaze-marker-size`                                  | all three        |
| `raw_gaze_opacity`                | `0.6`                                          | `--raw-gaze-opacity`                                      | all three        |
| `saccade_class_colors`            | `None`                                         | `--saccade-type-color`                                    | plot, compare    |
| `saccade_classes`                 | `list` (see `figure_options()`)                | `--saccade-classes`                                       | plot, compare    |
| `saccade_color`                   | `'#CC79A7'`                                    | `--saccade-color`                                         | all three        |
| `saccade_color_mode`              | `'Uniform'`                                    | `--saccade-color-by-type`, `--saccade-color-by-direction` | plot, compare    |
| `saccade_render_mode`             | `'Straight'`                                   | `--saccade-arcs`                                          | plot, compare    |
| `saccade_style`                   | `'solid'`                                      | `--saccade-style`                                         | all three        |
| `saccade_type_legend`             | `True`                                         | `--no-saccade-type-legend`                                | plot, compare    |
| `saccade_width`                   | `2.0`                                          | `--saccade-width`                                         | all three        |
| `scale_text_to_boxes`             | `True`                                         | `--no-scale-text-to-boxes`                                | all three        |
| `show_connectors`                 | `False`                                        | —                                                         | plot, compare    |
| `show_coordinate_grid`            | `False`                                        | `--coordinate-grid`                                       | all three        |
| `show_fixation_colorbar`          | `True`                                         | `--no-fixation-colorbar`                                  | all three        |
| `show_fixations`                  | `True`                                         | `--no-fixations`                                          | plot, compare    |
| `show_heatmap`                    | `True`                                         | `--no-heatmap`                                            | plot, compare    |
| `show_heatmap_colorbar`           | `True`                                         | `--no-heatmap-colorbar`                                   | all three        |
| `show_legend`                     | `False`                                        | `--compare-legend`                                        | animate, compare |
| `show_order`                      | `True`                                         | `--no-order`                                              | all three        |
| `show_raw_gaze`                   | `False`                                        | —                                                         | plot, compare    |
| `show_saccade_arrows`             | `False`                                        | `--saccade-arrows`                                        | all three        |
| `show_saccades`                   | `True`                                         | `--no-saccades`                                           | all three        |
| `show_word_labels`                | `True`                                         | `--no-labels`                                             | all three        |
| `show_words`                      | `True`                                         | `--no-words`                                              | all three        |
| `span_border_color`               | `'#000000'`                                    | `--span-border-color`                                     | plot, compare    |
| `style_a`                         | `None`                                         | `--style-a`                                               | animate, compare |
| `style_b`                         | `None`                                         | `--style-b`                                               | animate, compare |
| `text_color`                      | `'#000000'`                                    | `--text-color`                                            | all three        |
| `word_box_color`                  | `'#6c757d'`                                    | `--word-box-color`                                        | all three        |
| `word_box_fill_color`             | `'#646464'`                                    | `--word-box-fill-color`                                   | all three        |
| `word_box_fill_opacity`           | `0.05`                                         | `--word-box-fill-opacity`                                 | all three        |
| `word_box_line_opacity`           | `1.0`                                          | `--word-box-line-opacity`                                 | all three        |
| `word_heatmap_col`                | `None`                                         | `--word-heatmap-col`                                      | plot, compare    |
| `word_heatmap_title`              | `None`                                         | `--word-heatmap-title`                                    | plot, compare    |
| `word_hover_fields`               | `list` (see `figure_options()`)                | `--word-hover-fields`                                     | all three        |
| `word_hover_measure`              | `'total_fixation_duration_ms'`                 | `--word-hover-measure`                                    | all three        |
| `words_b`                         | `None`                                         | —                                                         | animate          |
| `x_field`                         | `'x'`                                          | `--x-field`                                               | plot, compare    |
| `y_field`                         | `'y'`                                          | `--y-field`                                               | plot, compare    |

## Save

### scanpath_studio.api.save_figure

```
save_figure(fig: Figure, path: str | Path, *, scale: int = 2, width: int | None = None, height: int | None = None) -> Path
```

Save a figure by extension: `.html` (interactive, browser-free) or `.png`/`.svg`/`.pdf` (static via Kaleido — needs a Chrome/Chromium; run `plotly_get_chrome -y` once if missing). `width` / `height` set the raster output size in px (overriding the figure's intrinsic layout size); both ignored for `.html`. Returns the written path.

### scanpath_studio.api.save_figure_layers

```
save_figure_layers(fig: Figure, directory: str | Path, *, fmt: str = 'svg', scale: int = 2, width: int | None = None, height: int | None = None) -> dict
```

Split a scanpath figure into its layers and save one file per layer.

Writes `<directory>/<layer>.<fmt>` for each *visible* layer (word boxes / fixations / saccades / heatmap / labels / stimulus image / frame) and returns `{layer: Path}`. Each layer is the full figure with only that layer's elements and a transparent background, at the same size and axis ranges — so the files register perfectly when stacked in Illustrator / Inkscape. `fmt` is any save_figure extension without the dot (`svg` / `pdf` are vector and best for editing; `png` / `html` also work). `scale` / `width` / `height` are forwarded to save_figure.

## Recovery cache

### scanpath_studio.api.cache_status

```
cache_status() -> dict
```

Describe the on-device recovery cache a local app run keeps.

The app stores completed uploaded datasets, column mappings, view settings and annotations under the user's cache directory so a refresh or restart resumes where it left off — on localhost/desktop only, never on a hosted deployment. This reports that store without launching the app: `enabled`, `directory`, `datasets` (name + per-frame row counts), `rows`, `annotations`, `settings`, `bytes`, `saved_at`, plus `exists` / `readable` for a missing or unreadable manifest, `damaged` (name + reason) for a stored dataset whose entry or files are broken — the app restores the others and keeps that one in the cache rather than dropping it — and `damaged_metadata`, the reason the stored metadata tables would not restore (`""` when they would). Delete it with clear_cache; the same information is in the app's 🗂️ Data Management → *Saved on this computer* section and in `scanpath-studio cache`.

### scanpath_studio.api.clear_cache

```
clear_cache() -> dict
```

Delete the on-device recovery cache and return its status afterwards.

Removes only the files this app wrote (`manifest.json` and the dataset Parquet files); anything else in the folder is left alone. A *running* local app writes its session back out at the end of its next change — start it with `scanpath-studio run --no-persist` or `SCANPATH_STUDIO_PERSIST=0` to stop that.

For a batch loop, see [Automation](https://lacclab.github.io/scanpath-studio/automation/#batch-pattern). GIF and MP4 export uses `scanpath_studio.animation_export.export_animation` and requires Kaleido plus Chrome/Chromium.
