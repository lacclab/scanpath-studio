# Python API

The public API follows one pipeline:

```
load data → list trials → plot → save
```

```
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
fig = sps.plot_scanpath(words, fixations, participant="p1", trial="t3")
sps.save_figure(fig, "scanpath.html")
```

Every function on this page is importable from `scanpath_studio`. The figure builders also take any of the [figure options](https://lacclab.github.io/scanpath-studio/figure-options/index.md) as a keyword.

## At a glance

| Function                             | What it does                                                                     |
| ------------------------------------ | -------------------------------------------------------------------------------- |
| **Load your data**                   |                                                                                  |
| load_scanpath_data                   | Load and normalize a words table and/or a fixations table.                       |
| ScanpathData                         | The `(words, fixations)` frames `load_scanpath_data` returns, with their names.  |
| propose_schema                       | Find the column mapping auto-detection would use for a raw table.                |
| attach_stimulus_images               | Fill `image_path` from a folder of stimulus images, on frames already loaded.    |
| load_raw_gaze                        | Load and normalize a raw, sample-level gaze table, for `raw_gaze=`.              |
| load_participant_metadata            | Load a participant-level metadata table: one row per participant.                |
| load_trial_metadata                  | Load a trial-level metadata table: one row per trial.                            |
| load_text_metadata                   | Load a text-level metadata table: one row per text.                              |
| **Load the demo and public corpora** |                                                                                  |
| load_sample_data                     | Load the bundled OneStop demo, normalized and ready to plot.                     |
| load_sample_raw_gaze                 | Load the bundled demo's raw gaze: what the app overlays on it.                   |
| load_potec                           | Load PoTeC as normalized `(words, fixations)` frames, ready to plot.             |
| load_onestop                         | Load OneStop as normalized `(words, fixations)` frames, ready to plot.           |
| **Author a scanpath**                |                                                                                  |
| build_authored_scanpath              | Build normalized word and fixation frames from hand-authored reading events.     |
| load_authored_scanpath               | Load an authoring file as normalized word and fixation frames.                   |
| **Inspect**                          |                                                                                  |
| list_trials                          | List every plottable trial: one row per participant and trial.                   |
| list_parts                           | List the ordered screens of multipart data, optionally for one trial.            |
| check_data_health                    | Find values that loaded as numbers but cannot be right: the app's *Data checks*. |
| **Plot**                             |                                                                                  |
| plot_scanpath                        | Build one trial's scanpath figure, by default in the app's Scanpath design.      |
| animate_scanpath                     | Build the animated replay of one trial's scanpath, or of two on one clock.       |
| compare_scanpaths                    | Build a figure comparing two scanpaths: the app's **Compare** mode.              |
| render_parent_trial                  | Render every screen of one multipart trial, each in its own coordinates.         |
| plot_corpus_figure                   | Plot a corpus profile, distribution or difference figure from a tidy table.      |
| **Figure options**                   |                                                                                  |
| figure_options                       | List every figure keyword a builder takes, with the default it renders with.     |
| **Reproduce a figure in code**       |                                                                                  |
| figure_code                          | Write the API or CLI code that reproduces a figure.                              |
| **Save**                             |                                                                                  |
| save_figure                          | Save a figure, in the format its file extension names.                           |
| save_figure_layers                   | Save a scanpath figure as one file per layer, for editing.                       |
| **Recovery cache**                   |                                                                                  |
| cache_status                         | Describe the recovery cache a local run keeps, without launching the app.        |
| clear_cache                          | Delete the recovery cache.                                                       |
| **Version and updates**              |                                                                                  |
| version_info                         | Say which build of Scanpath Studio this is, without using the network.           |
| check_for_updates                    | Ask GitHub whether a newer release than this build is out.                       |

## Column names

Columns keep the names your files give them. The demo's word table calls its word id `IA_ID` and its total fixation duration `IA_DWELL_TIME`, and every function and option takes those names. A column Scanpath Studio made keeps its internal name. `load_scanpath_data(..., names="canonical")` gives the internal names, which are the same for every dataset. On the bundled demo, the first steps print this (run when the docs are built):

```
import scanpath_studio as sps

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
0      0    Robert                        32.0            387
1      1  Myslajek                       170.0            785
2      2     stops                       290.0           1330
```

## Load your data

### load_scanpath_data

```
load_scanpath_data(
    words=None,
    fixations=None,
    *,
    word_schema=None,
    fix_schema=None,
    trial_parts_manifest=None,
    image_root=None,
    image_pattern=DEFAULT_STIMULUS_IMAGE_PATTERN,
    keep_columns=None,
    names=NAMES_SOURCE,
)
```

Load and normalize a words table and/or a fixations table.

Columns keep the names your files give them: `CURRENT_FIX_DURATION`, not `duration_ms`. A column Scanpath Studio built, converted, computed or changed keeps its internal name, and `data.column_names` records what every column was called. Every API function takes these frames, and every column option (`color_by=`, the hover fields …) takes either name.

Columns are auto-detected from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and snake_case names. Normalization keeps the mapped fields and the recognized optional ones (eye, EyeLink's interest-area measures, linguistic features …) and drops the rest, unless `keep_columns` names them.

- **One table is enough.** Leave out the table a dataset doesn't have: it comes back as an empty frame, and the plots skip that layer.
- **Stimulus-level words.** A words table without a participant column holds each text's word boxes once, and they are copied onto every trial in the fixations. Each trial is matched by its trial id, else the trial id it had before a repeat's `_r2` suffix, else its `text_id` (for trial ids that embed the participant). Trials that match none raise a `data.StimulusJoinWarning` (a `UserWarning`).
- **Fixations without x/y** but with a word or AOI id are placed at the centers of their word boxes.
- **Bookkeeping columns.** Columns named in `data.INTERNAL_COLUMNS` are the pipeline's own; `data.drop_internal_columns` removes them.

Parameters:

- **`words`** (`TablesLike | None`, default: `None` ) – The words (AOI) table: a DataFrame; a .csv, .tsv, .txt, .tab, .parquet, .feather, .xlsx or .xls file, or a .zip of them; a glob pattern; or a list of paths. Several files (one per participant and/or text) are concatenated, with each file's stem in a source_file column.
- **`fixations`** (`TablesLike | None`, default: `None` ) – The fixations table, in any form words takes.
- **`word_schema`** (`dict | None`, default: `None` ) – A mapping from field to column name for the words table, replacing auto-detection. Start from propose_schema.
- **`fix_schema`** (`dict | None`, default: `None` ) – The same for the fixations table.
- **`trial_parts_manifest`** (`dict | None`, default: `None` ) – A nested parent-trial/parts definition, for datasets whose tables identify screens through arbitrary selector columns. Explicit screen_id / screen_index columns can instead be mapped in each schema.
- **`image_root`** (`str | Path | None`, default: `None` ) – A local folder of stimulus images, one page per trial (or screen). Each row the pattern finds a file for gets it as its image_path; a row without one keeps the image_path it had. show_stimulus_image=True then draws the page under the figure. attach_stimulus_images does the same for frames already loaded.
- **`image_pattern`** (`str`, default: `DEFAULT_STIMULUS_IMAGE_PATTERN` ) – The file to look for under image_root, with {placeholders} naming the rows' canonical columns: "{text_id}.png", "{participant_id}/{trial_id}.png".
- **`keep_columns`** (`Iterable[str] | None`, default: `None` ) – Further columns of your own to carry through under their own names, such as a pupil size or a detection confidence, from whichever table has them, so a figure can color, hover or plot by them. The app's Extra fields to keep; render --keep-columns.
- **`names`** (`str`, default: `NAMES_SOURCE` ) – "source" keeps the dataset's column names; "canonical" returns the internal names, the same for every dataset, for code that works across datasets.

Returns:

- `ScanpathData` – The normalized (words, fixations) frames, as a ScanpathData.

Raises:

- `ValueError` – A required field can't be found. The message names the field, the column names auto-detection looked for, and the columns the table has.
- `ValueError` – image_root does not exist, or image_pattern is absolute or climbs out of it.
- `StimulusJoinError` – A stimulus-level words table shares neither a trial id nor a text_id with any trial (or, multipart, with every screen a trial has fixations on). A ValueError.
- `UnplacedFixationsError` – The fixations map no x/y and their word/AOI id column holds no numbers, so none could be placed. A ValueError.

### ScanpathData

Bases: `tuple`

The `(words, fixations)` frames `load_scanpath_data` returns, with their names.

It is a tuple, so `words, fixations = load_scanpath_data(…)` unpacks it, and `.words` / `.fixations` name the two frames. `column_names` holds the dataset's own name for every canonical column, per table: `{"words": ColumnNames, "fixations": ColumnNames}`.

With `names="source"` (the default) the frames' columns are the dataset's own names and each frame carries its map, so any API function takes it, sliced, filtered or merged, and the names it writes are yours. With `names="canonical"` they are the internal names, the same for every dataset.

### propose_schema

```
propose_schema(table, kind='words')
```

Find the column mapping auto-detection would use for a raw table.

It is the mapping load_scanpath_data infers, so it is the place to start when detection got a field wrong or could not find one: edit the dict and pass it back as `word_schema=` or `fix_schema=`.

Parameters:

- **`table`** (`TablesLike`) – A raw, not yet normalized table: a DataFrame, a path, a glob or a list of paths, as the loader takes.
- **`kind`** (`str`, default: `'words'` ) – "words", "fixations" or "raw_gaze".

Returns:

- `dict` – {canonical field: source column}, with None for a field it could not find.

Examples:

```
schema = sps.propose_schema("ia.csv", "words")
schema["trial"] = "TRIAL_LABEL"
words, fixations = sps.load_scanpath_data(
    "ia.csv", "fix.csv", word_schema=schema
)
```

### attach_stimulus_images

```
attach_stimulus_images(
    words,
    fixations,
    image_root,
    image_pattern=DEFAULT_STIMULUS_IMAGE_PATTERN,
)
```

Fill `image_path` from a folder of stimulus images, on frames already loaded.

It is load_scanpath_data's `image_root` / `image_pattern`, for frames that came from somewhere else, such as a corpus loader, which takes no folder. The rules are the same: the placeholders name the rows' canonical columns, and a row the pattern finds no file for keeps the `image_path` it had.

Parameters:

- **`words`** (`DataFrame | None`) – The words frame, or None.
- **`fixations`** (`DataFrame | None`) – The fixations frame, or None.
- **`image_root`** (`str | Path`) – The folder of stimulus images.
- **`image_pattern`** (`str`, default: `DEFAULT_STIMULUS_IMAGE_PATTERN` ) – The file to look for under image_root, as in load_scanpath_data.

Returns:

- `ScanpathData` – New (words, fixations) frames, under the names they came in. The frames passed in are not modified.

Raises:

- `ValueError` – image_root does not exist, or image_pattern is absolute or climbs out of it.

Examples:

```
words, fixations = sps.attach_stimulus_images(
    *sps.load_potec("data/PoTeC", readers=[0], texts=["b0"]),
    "pages/",
    "{text_id}.png",
)
sps.plot_scanpath(words, fixations, show_stimulus_image=True)
```

### load_raw_gaze

```
load_raw_gaze(table, *, raw_gaze_schema=None, names=NAMES_SOURCE)
```

Load and normalize a raw, sample-level gaze table, for `raw_gaze=`.

Raw gaze is the third table plot_scanpath can draw, under the fixations: one row per eye-tracker sample, with a participant, a trial, `x` / `y` and usually a timestamp. `plot_scanpath` keeps only the plotted trial's (and screen's) samples, so one table can serve a whole corpus.

Parameters:

- **`table`** (`TablesLike`) – A DataFrame, path, glob or list of paths, as load_scanpath_data takes. Columns are auto-detected the same way.
- **`raw_gaze_schema`** (`dict | None`, default: `None` ) – A mapping from field to column, replacing auto-detection. Start from propose_schema(table, "raw_gaze").
- **`names`** (`str`, default: `NAMES_SOURCE` ) – "source" keeps the table's column names; "canonical" returns the internal ones.

Returns:

- `DataFrame` – The normalized samples.

Examples:

```
raw_gaze = sps.load_raw_gaze("gaze_samples.csv")
fig = sps.plot_scanpath(words, fixations, "p1", "t3", raw_gaze=raw_gaze)
```

### load_participant_metadata

```
load_participant_metadata(table, *, id_column=None, participants=None)
```

Load a participant-level metadata table: one row per participant.

Nothing is broadcast onto the words or fixations frames. Use `scanpath_studio.metadata.project` to attach chosen columns to a per-trial frame, or `.values_for(pid)` for one participant.

Parameters:

- **`table`** (`TablesLike`) – A DataFrame, or a path or glob to a CSV, TSV, Parquet or Excel file, or a list of them, stacked into one table. It holds an id column plus anything known about each participant (native_language, age, a comprehension score).
- **`id_column`** (`str | None`, default: `None` ) – The participant-id column. Defaults to the first recognized spelling (participant_id, subject, RECORDING_SESSION_LABEL, …).
- **`participants`** (`DataFrame | list | None`, default: `None` ) – A normalized frame or a list of ids to validate the join against. The result's .report then names the participants missing from either side.

Returns:

- `ParticipantMetadata` – A ParticipantMetadata: the cleaned frame, a field registry (name, label, grain, dtype, missingness) and the join report.

Examples:

```
words, fixations = sps.load_sample_data()
meta = sps.load_participant_metadata("readers.csv", participants=fixations)
meta.names  # ('native_language', 'age')
```

### load_trial_metadata

```
load_trial_metadata(
    table, *, id_column=None, participant_column=None, trials=None
)
```

Load a trial-level metadata table: one row per trial.

The sibling of load_participant_metadata, one grain down. Nothing is broadcast onto the words or fixations frames.

**The key is yours to state, and it changes what the table means.** Keyed by trial id alone, a row describes a *text*, and every trial of it inherits that row. Keyed by participant **and** trial (`participant_column`), a row describes one *trial*. Nothing in a file says which a corpus is, so this is never inferred.

Parameters:

- **`table`** (`TablesLike`) – A DataFrame or file(s), as load_participant_metadata takes, stacked into one table. It holds a trial-id column plus anything known about each trial (a list name, a condition, a per-trial comprehension score).
- **`id_column`** (`str | None`, default: `None` ) – The trial-id column. Defaults to the first recognized spelling (trial_id, item_id, TRIAL_INDEX, …).
- **`participant_column`** (`str | None`, default: `None` ) – The participant-id column, to key each row by participant and trial. Left out, rows are keyed by trial id alone.
- **`trials`** (`DataFrame | None`, default: `None` ) – A normalized fixations or words frame, or any frame with participant_id and trial_id, to validate the join against. The result's .report then names the trials missing from either side.

Returns:

- `TrialMetadata` – A TrialMetadata: the cleaned frame, a field registry and the join report.

Examples:

```
words, fixations = sps.load_sample_data()
meta = sps.load_trial_metadata("readings.csv", trials=fixations)
meta.names  # ('list_name', 'comprehension_score')
```

### load_text_metadata

```
load_text_metadata(table, *, id_column=None, texts=None)
```

Load a text-level metadata table: one row per text.

A text is a stimulus, not something one participant owns, so the table is never keyed by participant. Nothing is broadcast onto the words or fixations frames.

Parameters:

- **`table`** (`TablesLike`) – A DataFrame or file(s), as load_participant_metadata takes, stacked into one table. It holds a text-id column plus anything known about each text (genre, difficulty, a stimulus-level comprehension score).
- **`id_column`** (`str | list[str] | None`, default: `None` ) – The text-id column, or several columns that build a composite id, as the data's own Text ID mapping can. Defaults to the first recognized spelling (text_id, paragraph_id, stimulus_id, …).
- **`texts`** (`DataFrame | list | None`, default: `None` ) – A normalized fixations or words frame, or any iterable of text ids, to validate the join against. The result's .report then names the texts missing from either side.

Returns:

- `TextMetadata` – A TextMetadata: the cleaned frame, a field registry and the join report.

Examples:

```
words, fixations = sps.load_sample_data()
meta = sps.load_text_metadata("texts.csv", texts=words)
meta.names  # ('genre', 'difficulty')
```

## Load the demo and public corpora

### load_sample_data

```
load_sample_data(*, names=NAMES_SOURCE)
```

Load the bundled OneStop demo, normalized and ready to plot.

Two participants, twelve trials each, every one with fixations. The frames carry the demo's recorded screen (OneStop's 2560×1440), so `plot_scanpath` draws them on it without a `canvas_size`, as `scanpath-studio render --sample` does.

Parameters:

- **`names`** (`str`, default: `NAMES_SOURCE` ) – "source" for the demo's own column names, "canonical" for the internal ones (see load_scanpath_data).

Returns:

- `ScanpathData` – The (words, fixations) frames, as a ScanpathData.

### load_sample_raw_gaze

```
load_sample_raw_gaze(*, names=NAMES_SOURCE)
```

Load the bundled demo's raw gaze: what the app overlays on it.

OneStop ships no sample-level gaze, so this is **synthesized** from one of the demo's real trials, and covers that trial alone.

Parameters:

- **`names`** (`str`, default: `NAMES_SOURCE` ) – "source" or "canonical", as load_sample_data takes.

Returns:

- `DataFrame` – The normalized samples.

### load_potec

```
load_potec(
    root, *, readers=None, texts=None, download=False, names="source"
)
```

Load PoTeC as normalized `(words, fixations)` frames, ready to plot.

A participant is a PoTeC reader id, as a string. A trial is one reader's reading of one text, `<reader>_<text>` (`"0_b0"`), and its `text_id` is the text: `b0`–`b5` are biology, `p0`–`p5` physics. The full corpus is 75 readers × 12 texts = 900 trials.

PoTeC's monitor was 1680×1050 (DELL P2210, 60 Hz). Pass that as `canvas_size` to plot_scanpath for true-to-scale rendering.

Parameters:

- **`root`** (`str | Path`) – A clone of the PoTeC repository with its eye-tracking data downloaded, or any folder to download into.
- **`readers`** (`Iterable | None`, default: `None` ) – Load only these readers ([0, 1]).
- **`texts`** (`Iterable[str] | None`, default: `None` ) – Load only these texts (["b0", "p3"]).
- **`download`** (`bool`, default: `False` ) – Fetch the files the load needs into root on first use, about 10 MB.
- **`names`** (`str`, default: `'source'` ) – "source" for PoTeC's own column names, "canonical" for the internal ones (see api.load_scanpath_data).

Returns:

- `tuple[DataFrame, DataFrame]` – The normalized (words, fixations) frames.

Examples:

```
import scanpath_studio as sps

words, fixations = sps.load_potec("data/PoTeC", readers=[0], texts=["b0"])
fig = sps.plot_scanpath(words, fixations, "0", "0_b0", canvas_size=(1680, 1050))
```

### load_onestop

```
load_onestop(
    root,
    *,
    regime="ordinary",
    parts=None,
    variant="public",
    download=False,
    names="source",
)
```

Load OneStop as normalized `(words, fixations)` frames, ready to plot.

OneStop's presentation monitor was 2560×1440 px (Dell U2715H; Berzak et al. 2025, Methods → Apparatus). Pass that as `canvas_size` to plot_scanpath for true-to-scale rendering. The reports already match the bundled demo's schema, so they load through the same auto-detection as any other data.

Parameters:

- **`root`** (`str | Path`) – A folder holding the OneStop reports, or (public variant only) to download them into.
- **`regime`** (`str`, default: `'ordinary'` ) – "ordinary", "information_seeking", "repeated" or "information_seeking_repeated".
- **`parts`** (`Iterable[str] | None`, default: `None` ) – Any subset of Title, Question_Preview, Paragraph, Questions, Answers, QA and Feedback. Left out, Paragraph.
- **`variant`** (`str`, default: `'public'` ) – "public" for the OSF release, "lacclab" for the lab's local export.
- **`download`** (`bool`, default: `False` ) – Fetch the chosen regime and parts into root on first use. The public reports are large.
- **`names`** (`str`, default: `'source'` ) – "source" for OneStop's own column names, "canonical" for the internal ones (see api.load_scanpath_data).

Returns:

- `tuple[DataFrame, DataFrame]` – The normalized (words, fixations) frames.

Examples:

```
import scanpath_studio as sps

words, fixations = sps.load_onestop(
    "data/OneStop", regime="ordinary", parts=["Paragraph"], download=True
)
pid, tid = sps.list_trials(words, fixations).iloc[0]  # one reading
fig = sps.plot_scanpath(words, fixations, pid, tid, canvas_size=(2560, 1440))
```

## Author a scanpath

### build_authored_scanpath

```
build_authored_scanpath(text, events=None, **layout_options)
```

Build normalized word and fixation frames from hand-authored reading events.

Parameters:

- **`text`** (`str`) – The text to lay out as word boxes. Explicit line breaks are kept.
- **`events`** (`DataFrame | None`, default: `None` ) – The fixations, one row each, with the columns the app's Author a scanpath table has (fixation_id, order_in_trial, word_id, x, y, duration_ms). Left out, each word gets one fixation at its center.
- **`**layout_options`** (`Any`, default: `{}` ) – Passed to authoring.layout_text (canvas_width, margin, character_width, word_height, line_height).

Returns:

- `tuple[DataFrame, DataFrame]` – The (words, fixations) frames, ready to plot.

### load_authored_scanpath

```
load_authored_scanpath(source)
```

Load an authoring file as normalized word and fixation frames.

Parameters:

- **`source`** (`str | Path`) – The JSON the app's Download authoring file saves: its path, or its text.

Returns:

- `tuple[DataFrame, DataFrame]` – The (words, fixations) frames, ready to plot.

## Inspect

### list_trials

```
list_trials(words=None, fixations=None, *, raw_gaze=None)
```

List every plottable trial: one row per participant and trial.

Every trial **any** table has, whether the words, the fixations or the raw gaze, appears once. The app's trial picker, `render --list-trials` and the export bundle list the same set. A trial a table lacks plots without that layer: one with words but no fixations draws its text alone, one with fixations but no words its scanpath over no word boxes.

Parameters:

- **`words`** (`DataFrame | None`, default: `None` ) – The words frame, or None when the dataset has none.
- **`fixations`** (`DataFrame | None`, default: `None` ) – The fixations frame, or None. Pass None for both for a dataset recorded as raw gaze alone.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – A frame from load_raw_gaze.

Returns:

- `DataFrame` – The participant and trial ids, sorted by participant, then trial, under the names the frames carry.

### list_parts

```
list_parts(
    words, fixations, participant=None, trial=None, *, raw_gaze=None
)
```

List the ordered screens of multipart data, optionally for one trial.

A trial recorded as raw gaze alone takes its screens from `raw_gaze` (its `screen_id`). That is decided per trial, so a samples-only trial keeps its screens in a dataset whose other trials have fixations.

Parameters:

- **`words`** (`DataFrame | None`) – The words frame, or None.
- **`fixations`** (`DataFrame | None`) – The fixations frame, or None.
- **`participant`** (`str | None`, default: `None` ) – Narrow to this participant's trials.
- **`trial`** (`str | None`, default: `None` ) – Narrow to this trial.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – A frame from load_raw_gaze.

Returns:

- `DataFrame` – One row per screen, in order; an empty table for single-screen data.

### check_data_health

```
check_data_health(words=None, fixations=None, raw_gaze=None)
```

Find values that loaded as numbers but cannot be right: the app's *Data checks*.

The checks look for fixations lasting 0 ms or less or with an infinite duration or onset, fixations and raw-gaze samples whose position is missing or infinite, word boxes with no area or no finite position, and per-screen screen sizes that are not finite and positive. Nothing is changed or dropped.

Each row of the result is one check that found something:

| Column                      | What it holds                                                         |
| --------------------------- | --------------------------------------------------------------------- |
| `table`, `check`, `problem` | Where it looked, and what it found                                    |
| `columns`                   | The columns it read, in the names the frames carry                    |
| `rows`, `of_rows`           | How many rows, of how many                                            |
| `trials`                    | The trials those rows fall in                                         |
| `breakdown`                 | The rows by kind                                                      |
| `severity`                  | `"note"` for raw-gaze gaps, which blinks and track loss make ordinary |
| `what_happens`              | What the app does with those rows                                     |
| `examples`                  | A few of them                                                         |

Parameters:

- **`words`** (`DataFrame | None`, default: `None` ) – A normalized words frame from load_scanpath_data.
- **`fixations`** (`DataFrame | None`, default: `None` ) – A normalized fixations frame.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – A normalized raw-gaze frame from load_raw_gaze.

Returns:

- `DataFrame` – The findings; an empty frame when every check passed.

Examples:

```
words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
print(sps.check_data_health(words, fixations))
```

## Plot

### plot_scanpath

```
plot_scanpath(
    words=None,
    fixations=None,
    participant=None,
    trial=None,
    *,
    screen=None,
    canvas_size=None,
    base_font_size=16,
    font_family=FONT_FAMILY,
    raw_gaze=None,
    drift_correction=None,
    drift_connectors=False,
    fix_index_range=None,
    illustration=False,
    illustration_label="auto",
    title="",
    caption="",
    column_names=None,
    **figure_overrides,
)
```

Build one trial's scanpath figure, by default in the app's Scanpath design.

Every figure option is a keyword (`show_heatmap=True`, `color_by="pass_index"`, `x_field="order_in_trial"`), and figure_options lists them with their defaults. An option naming a column takes either name: frames under the dataset's own column names, as `load_scanpath_data` returns them by default, are read through the map they carry.

Parameters:

- **`words`** (`DataFrame | None`, default: `None` ) – A normalized words frame from load_scanpath_data, or None for a dataset recorded as raw gaze alone.
- **`fixations`** (`DataFrame | None`, default: `None` ) – The normalized fixations frame, or None likewise.
- **`participant`** (`str | None`, default: `None` ) – The participant id. It may be left out when the frames hold one trial.
- **`trial`** (`str | None`, default: `None` ) – The trial id. It may be left out when the frames hold one trial.
- **`screen`** (`str | None`, default: `None` ) – The screen of a multipart trial to draw. Left out, the first recorded screen; coordinate spaces are never concatenated.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – The monitor size in px, (width, height). Estimated from the data's extent by default; pass the real resolution ((2560, 1440) for OneStop) to keep coordinates true to scale.
- **`base_font_size`** (`int`, default: `16` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – Samples from load_raw_gaze, filtered to the trial and drawn as recorded, under the fixations. It can be the only table: with words and fixations None, the trial is looked up in the samples, the canvas is estimated from their extent, and the figure is the samples alone. No fixations are detected from them, so the fixation, saccade and heatmap layers stay empty.
- **`drift_correction`** (`str | None`, default: `None` ) – Experimental. Without SCANPATH_EXPERIMENTAL=1, anything but None or "off" raises ValueError.
- **`drift_connectors`** (`bool`, default: `False` ) – Experimental, with drift_correction.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – (start, end): draw only fixations start to end of the trial, 1-based and both inclusive. The app's fixation-index window.
- **`illustration`** (`bool`, default: `False` ) – Apply the Illustration preset: fixations snapped to their lines, arced saccades, uniform colors, no heatmap or word boxes. Keywords you pass still win.
- **`illustration_label`** (`str`, default: `'auto'` ) – "auto" labels the figure an illustration when it no longer shows the data as recorded; "show" and "hide" decide it.
- **`title`** (`str`, default: `''` ) – A title band stamped onto the figure without shrinking the plot, like the app's Title & labels. Literal text, not the app's {trial_id}-style pattern, since you know which trial it is.
- **`caption`** (`str`, default: `''` ) – A caption band, likewise.
- **`column_names`** (`dict | None`, default: `None` ) – The column map for frames loaded with names="canonical" (data.column_names). The options then take the dataset's names too, and the figure's text uses them.
- **`**figure_overrides`** (`Any`, default: `{}` ) – Any figure option, in place of the app's default. Three take a word of explanation: palette= ("default", "print" or "high-contrast", or the app's names) sets a group of colors at once. A color you pass explicitly wins. show_stimulus_image=True draws the trial's own stimulus page under the scanpath, as the app's 📄 Stimulus → image does: the image_path its rows carry (from load_scanpath_data(image_root=…) or attach_stimulus_images; the demo ships its pages), at its image_x / image_y. A background_image= you pass wins. fixation_snap_to_line=True moves each fixation up or down onto its text line, keeping its x: its word's line, else the nearest. fixation_snap_position says where, in line heights from the line's middle (default −0.5, its top edge). The saccades' ends move with the markers, and it does nothing with show_fixations=False.

Returns:

- `Figure` – The Plotly figure.

Raises:

- `TypeError` – An unknown keyword. The message names the closest valid ones.
- `ValueError` – A value an enumerated option does not take, or a color_by / highlight_column naming a column the trial's table doesn't have. The message names the closest ones.

Warns:

- `UserWarning` – show_stimulus_image=True on a trial with no readable page (a PNG). The figure draws none.

### animate_scanpath

```
animate_scanpath(
    words=None,
    fixations=None,
    participant=None,
    trial=None,
    *,
    screen=None,
    screen_b=None,
    canvas_size=None,
    base_font_size=16,
    font_family=FONT_FAMILY,
    playback_speed=1.0,
    autoplay=True,
    fix_index_range=None,
    fix_index_range_b=None,
    illustration_label="auto",
    title="",
    caption="",
    column_names=None,
    trial_b=None,
    dataset_b=None,
    setup=None,
    setup_b=None,
    **animation_overrides,
)
```

Build the animated replay of one trial's scanpath, or of two on one clock.

Save it as interactive HTML with save_figure, whose page keeps the replay's clock itself, or rasterize it to GIF or MP4 with `animation_export.export_animation`, which lasts as long. `fig.show()` plays it on Plotly's own frame queue, which runs slow.

The replay takes a subset of plot_scanpath's options (`figure_options("animation")`), and the ones they share default alike, so the replay matches the static figure. The replay is made of fixations: it draws no raw gaze, and nothing detects fixations from samples.

**Two scanpaths.** `trial_b` co-animates a second trial, like the app's Animate + Compare. Both readings are drawn in A's coordinates, so a co-animation is an overlay, and a trial from another dataset has to share A's screen. Name that dataset with `dataset_b` (or give its `setup_b`), and the pair is checked the way compare_scanpaths checks an overlay. B's frames passed without either are taken to be from A's dataset, as `render` passes them for `--compare-with` alone, and are not checked: two readings of one corpus can span different extents, and inferring a canvas from each would refuse pairs that shared a screen.

Parameters:

- **`words`** (`DataFrame | None`, default: `None` ) – As in plot_scanpath.
- **`fixations`** (`DataFrame | None`, default: `None` ) – As in plot_scanpath.
- **`participant`** (`str | None`, default: `None` ) – As in plot_scanpath.
- **`trial`** (`str | None`, default: `None` ) – As in plot_scanpath.
- **`screen`** (`str | None`, default: `None` ) – A's screen of a multipart trial, as in plot_scanpath.
- **`screen_b`** (`str | None`, default: `None` ) – B's screen, looked up in B's own trial. Left out, its first recorded screen.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – A's monitor size, as in plot_scanpath.
- **`base_font_size`** (`int`, default: `16` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.
- **`playback_speed`** (`float`, default: `1.0` ) – The replay lasts the reading time divided by this. Any other value than 1 makes the automatic Illustration label say the timing was changed.
- **`autoplay`** (`bool`, default: `True` ) – Start the saved HTML's replay when it opens, at playback_speed. False saves it paused, to start with ▶ Play. A GIF or MP4 always plays from its first frame.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – (start, end): replay only that window of the trial's fixations, 1-based and inclusive. In a co-animation it windows A only, as in the app, where A's slider never cuts B.
- **`fix_index_range_b`** (`tuple[int, int] | None`, default: `None` ) – B's window, in a co-animation.
- **`illustration_label`** (`str`, default: `'auto'` ) – As in plot_scanpath.
- **`title`** (`str`, default: `''` ) – As in plot_scanpath.
- **`caption`** (`str`, default: `''` ) – As in plot_scanpath.
- **`column_names`** (`dict | None`, default: `None` ) – As in plot_scanpath.
- **`trial_b`** (`tuple[str, str] | None`, default: `None` ) – B's (participant, trial). It is looked up in words_b / fixations_b when they are given, else in words / fixations, as compare_scanpaths takes it.
- **`dataset_b`** (`str | None`, default: `None` ) – The name of B's dataset, when it is another one. The pair is then checked as an overlay, and B's participant ids are prefixed with it, so a hover says whose participant it is.
- **`setup`** (`SetupSnapshot | None`, default: `None` ) – A's experimental_setup.SetupSnapshot, the screen the overlay check reads. A side without one is read off its data: the extent of that one trial, which rarely spans the whole screen, so state both when you know them.
- **`setup_b`** (`SetupSnapshot | None`, default: `None` ) – B's.
- **`**animation_overrides`** (`Any`, default: `{}` ) – Any figure option the replay takes. Also: words_b / fixations_b: B's frames. Without trial_b they must hold one trial. style_a / style_b: each scanpath's style, with the keys compare_scanpaths takes for markers and saccades (fix_color, marker_size_range, opacity, hollow, saccade_color, saccade_style, saccade_width), so the replay and the static comparison draw each trial alike. A lone replay ignores them. fixation_flags_b: B's own fixation flags. None uses A's fixation_flags, or style_b's when it names some. show_stimulus_image=True draws the trial's own page, as in plot_scanpath. A co-animation draws one page, under the text it draws: B's when compare_stimulus="b", else A's. palette= works here too. Colors it implies that the replay doesn't take are dropped rather than raising, since you named a look, not those keys.

Returns:

- `Figure` – The animated Plotly figure.

Raises:

- `ValueError` – The trial has no fixations (one recorded as raw gaze alone, or a words-only one). Also for raw_gaze=; draw samples with plot_scanpath(raw_gaze=…).
- `ValueError` – An option the replay does not take (the message names the valid ones), a style naming saccade_classes (the replay has no saccade-class filter), or B frames holding several trials without trial_b.
- `IncomparableScreensError` – B's dataset has a different canvas from A's. A ValueError.

### compare_scanpaths

```
compare_scanpaths(
    words,
    fixations,
    trial_a,
    trial_b,
    *,
    screen=None,
    screen_b=None,
    words_b=None,
    fixations_b=None,
    dataset_b="Dataset B",
    raw_gaze=None,
    raw_gaze_b=None,
    layout="overlay",
    compare_stimulus="both",
    setup=None,
    setup_b=None,
    canvas_size=None,
    labels=None,
    style_a=None,
    style_b=None,
    base_font_size=16,
    font_family=FONT_FAMILY,
    fix_index_range=None,
    fix_index_range_b=None,
    drift_correction=None,
    title="",
    caption="",
    column_names=None,
    **figure_overrides,
)
```

Build a figure comparing two scanpaths: the app's **Compare** mode.

**Multipart trials.** Each scanpath is one screen, never a whole multipart trial: every screen is its own coordinate space, so pooling them would draw saccades across page boundaries. `list_parts()` lists the screens.

**Two datasets.** `words_b` / `fixations_b` draw B from a *different* dataset. Two datasets can hold the same `(participant_id, trial_id)`, so B's participant ids are namespaced with `dataset_b` inside the merged frames; without that, one trial would silently render as two. The frames you pass in are never modified, and only the trace labels show the namespace.

**The overlay gate.** An overlay needs both readings on screens of the same size, or it raises `ValueError` (the app falls back to side by side). That holds across datasets, and within one when the two screens carry different `canvas_width` / `canvas_height` or `setup_b` states another screen. Pass `layout="side_by_side"` or `"stacked"` to compare readings from different screens; each panel is then drawn to its own. Nothing is rescaled.

**Per-scanpath style.** `style_a` / `style_b` restyle one scanpath with these keys:

| Key                                      | What it sets                                                                                                    | Left out                                         |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `fix_color`, `saccade_color`             | The scanpath's colors                                                                                           | Its default                                      |
| `marker_size_range`, `opacity`, `hollow` | Its fixation markers                                                                                            | Its default                                      |
| `saccade_style`, `saccade_width`         | Its saccade lines                                                                                               | Its default                                      |
| `box_color`                              | The outline of that reading's word boxes                                                                        | Its `fix_color`                                  |
| `box_fill_color`                         | Their fill                                                                                                      | `word_box_fill_color`                            |
| `box_line_opacity`, `box_fill_opacity`   | Their outline's and fill's opacity, 0–1 (0 hides it)                                                            | `word_box_line_opacity`, `word_box_fill_opacity` |
| `raw_gaze_color`                         | That reading's raw-gaze samples                                                                                 | Its `fix_color`                                  |
| `heatmap_colorscale`                     | That reading's word-box heatmap color scale, on the range both share; two different scales get a color bar each | `heatmap_colorscale`                             |
| `fixation_flags`, `saccade_classes`      | That scanpath's own filters, in place of the figure's                                                           | The figure's                                     |

The box keys and `raw_gaze_color` are this figure's only: the co-animation draws one set of boxes and no raw gaze, and ignores them.

Parameters:

- **`words`** (`DataFrame`) – The words frame holding both trials, or A's when words_b is given.
- **`fixations`** (`DataFrame`) – The fixations frame, likewise.
- **`trial_a`** (`tuple[str, str]`) – A's (participant, trial).
- **`trial_b`** (`tuple[str, str]`) – B's (participant, trial).
- **`screen`** (`str | None`, default: `None` ) – A's screen of a multipart trial. Left out, its first recorded screen, as in plot_scanpath.
- **`screen_b`** (`str | None`, default: `None` ) – B's screen, looked up in B's own frames, so it may be a later page or another dataset's.
- **`words_b`** (`DataFrame | None`, default: `None` ) – B's words frame, to draw B from another dataset.
- **`fixations_b`** (`DataFrame | None`, default: `None` ) – B's fixations frame, likewise.
- **`dataset_b`** (`str`, default: `'Dataset B'` ) – The name B's participant ids are namespaced with.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – Samples from load_raw_gaze, drawn under each reading's scanpath in its color. It serves both readings of one dataset; across datasets it is A's. Passing it turns the layer on; show_raw_gaze=False keeps it off.
- **`raw_gaze_b`** (`DataFrame | None`, default: `None` ) – B's samples, across datasets.
- **`layout`** (`str`, default: `'overlay'` ) – "overlay", "side_by_side" ("side-by-side" also works) or "stacked".
- **`compare_stimulus`** (`str`, default: `'both'` ) – Whose word boxes and text an overlay draws: "both", "a" or "b". Two datasets' boxes coincide only when the text is identical. Split layouts ignore it, since each panel draws its own.
- **`setup`** (`SetupSnapshot | None`, default: `None` ) – A's experimental_setup.SetupSnapshot, the screen the overlay gate reads.
- **`setup_b`** (`SetupSnapshot | None`, default: `None` ) – B's.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – A's monitor size, when you only have a resolution. Left out with setup, the canvas is read off the data.
- **`labels`** (`tuple[str, str] | None`, default: `None` ) – The two trace labels, when not the composed defaults.
- **`style_a`** (`dict | None`, default: `None` ) – A's style, with the keys above.
- **`style_b`** (`dict | None`, default: `None` ) – B's style.
- **`base_font_size`** (`int`, default: `16` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – (start, end): draw only that window of both scanpaths' fixations.
- **`fix_index_range_b`** (`tuple[int, int] | None`, default: `None` ) – B's own window, as the app's B slider sets it.
- **`drift_correction`** (`str | None`, default: `None` ) – Experimental, as in plot_scanpath.
- **`title`** (`str`, default: `''` ) – As in plot_scanpath.
- **`caption`** (`str`, default: `''` ) – As in plot_scanpath.
- **`column_names`** (`dict | None`, default: `None` ) – As in plot_scanpath. A's names, or column_names, name the options and the figure's text; either dataset's frames may come under their own names.
- **`**figure_overrides`** (`Any`, default: `{}` ) – Any figure option a comparison takes (figure_options("comparison")). Some act per scanpath: fixation_flags and saccade_classes filter both scanpaths, unless a style gives one its own. background_image is A's page. A split layout draws B's panel over background_image_b (with background_image_size_b / background_image_origin_b), and over nothing without it, never A's, since sharing a dataset says nothing about sharing a page. show_stimulus_image=True takes each reading's own page from its rows: a split layout draws A's and B's, each in its panel, and an overlay the page of the text it draws (B's for compare_stimulus="b", else A's). An image passed explicitly wins.

Returns:

- `Figure` – The Plotly figure.

Raises:

- `ValueError` – An overlay of two different screens (see the overlay gate), or a screen / screen_b the trial does not have or that names a screen of a single-screen trial.
- `TypeError` – An unknown keyword. The message names the closest valid ones.

### render_parent_trial

```
render_parent_trial(
    words,
    fixations,
    participant=None,
    trial=None,
    *,
    animate=False,
    transition_mode="instant",
    screens=None,
    **options,
)
```

Render every screen of one multipart trial, each in its own coordinates.

No saccade is ever drawn across a screen boundary.

Parameters:

- **`words`** (`DataFrame`) – The normalized words frame.
- **`fixations`** (`DataFrame`) – The normalized fixations frame.
- **`participant`** (`str | None`, default: `None` ) – The participant id.
- **`trial`** (`str | None`, default: `None` ) – The parent trial's id.
- **`animate`** (`bool`, default: `False` ) – Build replays with animate_scanpath instead of plot_scanpath's figures.
- **`transition_mode`** (`str`, default: `'instant'` ) – "instant" or "recorded". Each animated figure's layout.meta['transition_after_ms'] records the delay before the next screen: zero for "instant", the observed parent-clock gap for "recorded".
- **`screens`** (`Sequence[str] | None`, default: `None` ) – Only these screen ids (one may be given as a string), in the trial's own order, as the app's Export → Screens does. None renders them all. Each figure's screen_index meta stays the screen's place in the trial.
- **`**options`** (`Any`, default: `{}` ) – Passed to plot_scanpath or animate_scanpath.

Returns:

- `dict[str, Figure]` – {screen_id: figure} in the trial's order, ready to save as per-screen files. A single-screen trial gives {"screen-1": figure}.

Raises:

- `ValueError` – A screen id the trial does not have, or screens for a trial with no screens to choose from.

### plot_corpus_figure

```
plot_corpus_figure(
    data,
    *,
    kind,
    measure_label="Value",
    series_col="series",
    value_col="value",
    colors=None,
    canvas_width=1000,
    base_font_size=14,
    font_family=FONT_FAMILY,
)
```

Plot a corpus profile, distribution or difference figure from a tidy table.

The headless form of Corpus Analysis's figures, in the same colors.

Parameters:

- **`data`** (`DataFrame`) – The tidy table. kind="profile" reads word_id and value_col (and optional lo / hi), "distribution" reads value_col, and "difference" reads word_id and diff.
- **`kind`** (`str`) – "profile", "distribution" or "difference".
- **`measure_label`** (`str`, default: `'Value'` ) – The measure's label, and the series' name when the table has no series_col.
- **`series_col`** (`str`, default: `'series'` ) – The column naming each overlaid profile or distribution series, when the table has it.
- **`value_col`** (`str`, default: `'value'` ) – The column holding the values.
- **`colors`** (`tuple[str, ...] | None`, default: `None` ) – The series' colors, in order. Left out, the app's palette.
- **`canvas_width`** (`int`, default: `1000` ) – The figure's width in px.
- **`base_font_size`** (`int`, default: `14` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.

Returns:

- `Figure` – The figure.

Raises:

- `ValueError` – The table lacks a column its kind reads (the message names it and the columns present), or kind is unknown.

## Figure options

`plot_scanpath`, `animate_scanpath` and `compare_scanpaths` take the [figure options](https://lacclab.github.io/scanpath-studio/figure-options/index.md) as keywords: every layer, color, size and legend setting, with the default it renders with and the `render` flag that sets it. `figure_options()` returns the same defaults in code.

### figure_options

```
figure_options(kind='static', *, choices=False)
```

List every figure keyword a builder takes, with the default it renders with.

The defaults are what a call actually renders with, the app's Scanpath design, so a script can diff its intended settings against what it would get. The *Figure options* page of these docs lists them by section, with their `render` flags.

Parameters:

- **`kind`** (`str`, default: `'static'` ) – "static" for plot_scanpath, "animation" for animate_scanpath (which takes a subset), or "comparison" for compare_scanpaths.
- **`choices`** (`bool`, default: `False` ) – Map each name to {"default": …, "choices": …} instead. choices is the tuple of values an enumerated option takes (heatmap_norm: ("Linear", "Log")), or None for a free one. An enumerated option takes any spelling of a choice, ignoring case, spaces, - and \_, so the CLI's "log" and "mark-border" work, and raises ValueError listing them for anything else.

Returns:

- `dict` – {name: default}, sorted by name.

Raises:

- `ValueError` – An unknown kind.

Examples:

```
{k: v for k, v in sps.figure_options().items() if k.startswith("show_")}
```

## Reproduce a figure in code

The app's **Share** subtab shows the API or CLI code that rebuilds the figure currently on screen — paste it into a notebook or terminal to get the same figure. `figure_code` is the headless form of that block, and `render --print-code` prints it for an invocation you already have.

```
print(
    sps.figure_code(
        participant="l7_1090",
        trial="l7_1090_2_1_1_Ele_r0",
        show_heatmap=True,
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
    show_heatmap=True,
)

sps.save_figure(fig, 'scanpath.png')
```

### figure_code

```
figure_code(
    *,
    kind="static",
    source="demo",
    source_options=None,
    participant="",
    trial="",
    screen=None,
    compare=None,
    compare_screen=None,
    compare_layout="overlay",
    compare_stimulus="both",
    compare_dataset="",
    compare_canvas=None,
    compare_labels=None,
    canvas_size=None,
    base_font_size=16,
    font_family=FONT_FAMILY,
    title="",
    caption="",
    fix_index_range=None,
    illustration_label="auto",
    drift_correction=None,
    drift_connectors=False,
    playback_speed=1.0,
    autoplay=True,
    flavor="python",
    explicit=False,
    output=None,
    **figure_overrides,
)
```

Write the API or CLI code that reproduces a figure.

The headless twin of the app's 🔗 Share → *Reproduce this figure in code* block. Give it the arguments you would give plot_scanpath (`kind="static"`), animate_scanpath (`"animation"`) or compare_scanpaths (`"comparison"`), and it returns the snippet that rebuilds that figure. Only the options that differ from figure_options are written, so the snippet stays readable. `code_snippet.ReproductionCode` is the structured form.

Parameters:

- **`kind`** (`str`, default: `'static'` ) – "static", "animation" or "comparison": the builder the snippet calls.
- **`source`** (`str`, default: `'demo'` ) – How the data is loaded: "demo", "synthetic", "files", "potec", "onestop", "author", "raw_gaze" (a dataset recorded as raw gaze alone, whose samples at source_options["raw_gaze"] are the data), or "unknown" for data a snippet can't name.
- **`source_options`** (`dict | None`, default: `None` ) – That loader's arguments: {"root": …}, {"words": [...], "fixations": [...]} and so on. With show_raw_gaze=True, "raw_gaze" (and an optional "raw_gaze_schema") names the raw-gaze files; the demo uses its own.
- **`participant`** (`str`, default: `''` ) – The participant id. Left empty, the snippet renders the first available trial, as render does.
- **`trial`** (`str`, default: `''` ) – The trial id, likewise.
- **`screen`** (`str | None`, default: `None` ) – A's screen of a multipart trial (screen=, --screen).
- **`compare`** (`tuple[str, str] | None`, default: `None` ) – B's (participant, trial), for a comparison or a co-animation.
- **`compare_screen`** (`str | None`, default: `None` ) – B's screen (screen_b=, --compare-screen).
- **`compare_layout`** (`str`, default: `'overlay'` ) – The comparison's layout, as compare_scanpaths takes it.
- **`compare_stimulus`** (`str`, default: `'both'` ) – Whose stimulus an overlay draws, as compare_scanpaths takes it.
- **`compare_dataset`** (`str`, default: `''` ) – The dataset B was loaded from, when it is a second one. Both forms then load B's own tables, from the placeholder paths B_WORDS / B_FIXATIONS that you point at its files (words_b= / fixations_b= / dataset_b=, and --compare-words / --compare-fixations).
- **`compare_canvas`** (`tuple[int, int] | None`, default: `None` ) – B's screen, (width, height), with compare_dataset: written as setup_b= and --compare-canvas, which a co-animation across datasets needs.
- **`compare_labels`** (`tuple[str, str] | None`, default: `None` ) – The two trace labels, when they are not the composed defaults: labels= and --label-a / --label-b.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – The monitor size. Defaults to the screen render assumes for the source (the demo's 2560×1440, PoTeC's 1680×1050, …), so both forms draw the same figure.
- **`base_font_size`** (`int`, default: `16` ) – As the builders take it.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – As the builders take it.
- **`title`** (`str`, default: `''` ) – As the builders take it.
- **`caption`** (`str`, default: `''` ) – As the builders take it.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – As the builders take it.
- **`illustration_label`** (`str`, default: `'auto'` ) – As the builders take it.
- **`drift_correction`** (`str | None`, default: `None` ) – Experimental, as in plot_scanpath.
- **`drift_connectors`** (`bool`, default: `False` ) – Experimental, as in plot_scanpath.
- **`playback_speed`** (`float`, default: `1.0` ) – As animate_scanpath takes it.
- **`autoplay`** (`bool`, default: `True` ) – As animate_scanpath takes it.
- **`flavor`** (`str`, default: `'python'` ) – "python", "cli", or "both" (separated by a blank line).
- **`explicit`** (`bool`, default: `False` ) – Write every option at its current value, not only the ones that differ from the defaults.
- **`output`** (`str | None`, default: `None` ) – The file the snippet saves. Defaults to scanpath.html for an animation (render --animate writes only HTML) and to a PNG otherwise.
- **`**figure_overrides`** (`Any`, default: `{}` ) – The figure options, as the builder takes them.

Returns:

- `str` – The snippet. Anything neither form can reproduce (a raw-gaze table with no path to name, an uploaded stimulus image, B's rows from a second corpus) follows as # Note: comments, as the app's ⚠️ captions and the Note: lines render --print-code writes to stderr say it.

Raises:

- `ValueError` – An unknown flavor.
- `TypeError` – An option the builder does not take.

Examples:

```
print(
    sps.figure_code(
        participant="l7_1090",
        trial="l7_1090_2_1_1_Ele_r0",
        show_heatmap=True,
        flavor="cli",
    )
)
```

## Save

### save_figure

```
save_figure(
    fig,
    path,
    *,
    scale=2,
    width=None,
    height=None,
    width_mm=None,
    width_in=None,
    dpi=None,
)
```

Save a figure, in the format its file extension names.

Parameters:

- **`fig`** (`Figure`) – The figure.
- **`path`** (`str | Path`) – The file to write: .html (interactive), or .png, .svg or .pdf (static, through Kaleido; see the export FAQ for its setup).
- **`scale`** (`float`, default: `2` ) – The static image's scale factor.
- **`width`** (`int | None`, default: `None` ) – The image width in px, overriding the figure's own. Ignored for .html.
- **`height`** (`int | None`, default: `None` ) – The image height in px, likewise.
- **`width_mm`** (`float | None`, default: `None` ) – A PNG's print width in mm, as the app's Export → Current figure sets it: 180 mm at 600 dpi is a 4,252 px wide PNG, its height following the figure's aspect, with the dpi written into the file. It replaces scale.
- **`width_in`** (`float | None`, default: `None` ) – The same in inches.
- **`dpi`** (`int | None`, default: `None` ) – The resolution for width_mm / width_in. Default 300.

Returns:

- `Path` – The path written.

### save_figure_layers

```
save_figure_layers(
    fig, directory, *, fmt="svg", scale=2, width=None, height=None
)
```

Save a scanpath figure as one file per layer, for editing.

Each *visible* layer (word boxes, fixations, saccades, heatmap, labels, stimulus image, frame) is the full figure with only that layer's elements, on a transparent background, at the same size and axis ranges. The files line up exactly when stacked in Illustrator or Inkscape.

Parameters:

- **`fig`** (`Figure`) – A scanpath figure.
- **`directory`** (`str | Path`) – The folder to write <layer>.<fmt> into.
- **`fmt`** (`str`, default: `'svg'` ) – Any save_figure extension without the dot. svg and pdf are vector and the best to edit; png and html work too.
- **`scale`** (`int`, default: `2` ) – Passed to save_figure.
- **`width`** (`int | None`, default: `None` ) – Passed to save_figure.
- **`height`** (`int | None`, default: `None` ) – Passed to save_figure.

Returns:

- `dict` – {layer: Path} for each file written.

## Recovery cache

### cache_status

```
cache_status()
```

Describe the recovery cache a local run keeps, without launching the app.

A local or desktop app stores completed uploaded datasets, column mappings, view settings, saved designs, metadata tables and annotations under your cache folder, so a refresh or a restart resumes where it left off. A hosted deployment never does. The same information is in the app's 🗂️ Data Management → *Saved on this computer*, and in `scanpath-studio cache`.

| Key                                              | What it holds                                                                                                                                |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `enabled`, `directory`                           | Whether caching is on, and where                                                                                                             |
| `exists`, `readable`                             | Whether its manifest is there and can be read                                                                                                |
| `datasets`                                       | Each stored dataset's name and per-frame row counts                                                                                          |
| `rows`, `bytes`, `saved_at`                      | The totals, and when it was last written                                                                                                     |
| `annotations`, `designs`, `metadata`, `settings` | What else is stored                                                                                                                          |
| `damaged`                                        | Each stored dataset whose entry or files are broken, with the reason. The app restores the others and keeps that one rather than dropping it |
| `damaged_metadata`                               | Why the stored metadata tables would not restore; `""` when they would                                                                       |

Returns:

- `dict` – The status, as a dict with the keys above. Delete the cache with clear_cache.

### clear_cache

```
clear_cache()
```

Delete the recovery cache.

Removes only the files the app wrote (`manifest.json` and the datasets' Parquet files); anything else in the folder is left alone. A *running* local app writes its session back out at its next change, so start it with `scanpath-studio run --no-persist` or `SCANPATH_STUDIO_PERSIST=0` to stop that.

Returns:

- `dict` – The cache's status afterwards, as cache_status gives it.

## Version and updates

### version_info

```
version_info()
```

Say which build of Scanpath Studio this is, without using the network.

The same is in the app's Help → About, and in `scanpath-studio version`.

| Field             | What it holds                                                                                                                                                                                                                                       |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version`         | `scanpath_studio.__version__`: the release itself (`"0.35.0"`), or between releases a PEP 440 version that sorts after it. `"0.35.0.post3+g8f18219"` is three commits after v0.35.0, at commit `8f18219`; it ends `.dirty` with uncommitted changes |
| `release`         | The release it descends from (`scanpath_studio.__release__`)                                                                                                                                                                                        |
| `distance`        | The commits since, `None` when unknown                                                                                                                                                                                                              |
| `commit`, `dirty` | The commit, and whether there were uncommitted changes                                                                                                                                                                                              |
| `source`          | How it was worked out: `"checkout"` (`git describe`), `"stamp"` (a desktop bundle's build stamp), `"vcs"` (a `pip install git+…`) or `"release"`                                                                                                    |

Returns:

- `BuildInfo` – The build, as a BuildInfo. Its describe() says it in a sentence.

### check_for_updates

```
check_for_updates(timeout=5.0)
```

Ask GitHub whether a newer release than this build is out.

The one call here that uses the network, and only when made. It reads the latest release from `api.github.com` (drafts and pre-releases excluded), compares it with version_info, and never raises. The same check is the app's Help → About → *Check for updates*, and `scanpath-studio version --check`.

| Field        | What it holds                                                                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `status`     | `"up_to_date"`, `"update_available"`, `"ahead"` (a development build past the latest release) or `"error"` (offline, no answer within `timeout` seconds, rate-limited, …) |
| `message`    | The status, in a sentence                                                                                                                                                 |
| `command`    | With an update available, the shell command that updates this install: `pip install -U scanpath-studio`, `uv tool upgrade scanpath-studio`, `git pull`, …                 |
| `latest.url` | The release notes                                                                                                                                                         |
| `download`   | In the desktop app, the archive for this computer                                                                                                                         |

Parameters:

- **`timeout`** (`float`, default: `5.0` ) – How long to wait for GitHub, in seconds.

Returns:

- `UpdateCheck` – The answer, as an UpdateCheck.

## See also

- [Export and share](https://lacclab.github.io/scanpath-studio/guides/exporting/index.md): the [batch pattern](https://lacclab.github.io/scanpath-studio/guides/exporting/#batch-pattern) for many trials, and [GIF/MP4 replays](https://lacclab.github.io/scanpath-studio/guides/exporting/#replays-as-gif-or-mp4).
- [CLI reference](https://lacclab.github.io/scanpath-studio/cli/index.md): the same figures from the command line.
