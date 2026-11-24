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

Every function on this page is importable from `scanpath_studio`. The figure builders also take the [figure options](#figure-options) as keywords.

## At a glance

| Function                                      | What it does                                                                          |
| --------------------------------------------- | ------------------------------------------------------------------------------------- |
| **Load your data**                            |                                                                                       |
| load_scanpath_data                            | Load and normalize a Words table, a Fixations table, or both.                         |
| ScanpathData                                  | The `(words, fixations)` frames `load_scanpath_data` returns, with their names.       |
| propose_schema                                | Find the column mapping auto-detection would use for a raw table.                     |
| attach_stimulus_images                        | Fill `image_path` from a folder of stimulus images, on frames already loaded.         |
| load_raw_gaze                                 | Load and normalize a raw, sample-level gaze table, for `raw_gaze=`.                   |
| load_participant_metadata                     | Load a participant-level metadata table: one row per participant.                     |
| load_trial_metadata                           | Load a trial-level metadata table: one row per trial.                                 |
| load_text_metadata                            | Load a text-level metadata table: one row per text.                                   |
| **Load the bundled demo and public datasets** |                                                                                       |
| load_sample_data                              | Load the bundled demo, normalized and ready to plot.                                  |
| load_sample_raw_gaze                          | Load recorded EyeLink gaze samples for every reading in the bundled OneStop demo.     |
| load_potec                                    | Load PoTeC as normalized `(words, fixations)` frames, ready to plot.                  |
| load_onestop                                  | Load OneStop as normalized `(words, fixations)` frames, ready to plot.                |
| **Draw a scanpath**                           |                                                                                       |
| build_authored_scanpath                       | Build normalized Words and Fixations frames from a hand-drawn scanpath.               |
| load_authored_scanpath                        | Load a draft file as normalized Words and Fixations frames.                           |
| **Inspect**                                   |                                                                                       |
| list_trials                                   | List every plottable trial: one row per participant and trial.                        |
| list_parts                                    | List the ordered screens of multipart data, optionally for one trial.                 |
| check_data_health                             | Check durations, positions and word boxes for data problems.                          |
| run_analysis_recipe                           | Recreate a corpus overview, per-word cohort profile or two-group difference profile.  |
| **Plot**                                      |                                                                                       |
| plot_scanpath                                 | Build one trial's scanpath figure, by default in the app's Scanpath design.           |
| animate_scanpath                              | Build the animated replay of one trial's scanpath, or of two on one clock.            |
| compare_scanpaths                             | Build a figure comparing two scanpaths: the app's **Compare** mode.                   |
| render_parent_trial                           | Render every screen of one multipart trial, each in its own coordinates.              |
| plot_corpus_figure                            | Plot a corpus overview, profile, distribution or difference from a tidy table.        |
| **Figure options**                            |                                                                                       |
| figure_options                                | List figure options and their default values.                                         |
| **Reproduce a figure in code**                |                                                                                       |
| figure_code                                   | Write the API or CLI code that reproduces a figure.                                   |
| **Save**                                      |                                                                                       |
| save_figure                                   | Save a figure as HTML, PNG, SVG or PDF.                                               |
| publication_figure                            | Prepare one Plotly figure to edit and export.                                         |
| save_publication                              | Save an editable publication project or its physical-size SVG, PDF, PNG, TIFF or MP4. |
| save_panel_proof                              | Save a split comparison as an SVG with its manuscript width in millimetres.           |
| save_figure_layers                            | Save a scanpath figure as one file per layer, for editing.                            |
| **Recovery cache**                            |                                                                                       |
| add_dataset                                   | Add a dataset to the app's dataset list from a script.                                |
| app_link                                      | A link that opens the local app on a dataset, a reading and a figure.                 |
| remove_dataset                                | Remove a dataset from the app's dataset list from a script.                           |
| cache_status                                  | Describe the recovery cache a local run keeps, without launching the app.             |
| clear_cache                                   | Delete the recovery cache.                                                            |
| **Version and updates**                       |                                                                                       |
| version_info                                  | Return version and installation details without a network request.                    |
| check_for_updates                             | Check GitHub for a newer release.                                                     |
| **Citation**                                  |                                                                                       |
| cite                                          | Return a citation for Scanpath Studio and, optionally, a public corpus.               |

## Column names

The API preserves the column names from your files. For example, the bundled demo's Words table uses `IA_ID` for word IDs and `IA_DWELL_TIME` for total fixation duration. Use those names when selecting columns in functions and figure options. Columns created by Scanpath Studio use its internal names.

Pass `names="canonical"` to `load_scanpath_data` to use the same internal names across datasets. The example below shows the names returned for the bundled demo:

```
import scanpath_studio as sps

words, fixations = sps.load_sample_data()
print(sps.list_trials(words, fixations).head(3))

columns = ["IA_ID", "IA_LABEL", "IA_FIRST_FIXATION_DURATION", "IA_DWELL_TIME"]
print(words[columns].head(3))
```

```
  participant_id    unique_trial_id
0        l37_273  l37_273_2_1_1_Ele
1        l37_273  l37_273_2_1_2_Ele
2        l37_273  l37_273_2_1_3_Adv
   IA_ID  IA_LABEL  IA_FIRST_FIXATION_DURATION  IA_DWELL_TIME
0      1    Robert                       243.0            243
1      2  Myslajek                       192.0            192
2      3     stops                       140.0            140
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
    include_source_cells=False,
    _row_counts=None,
    _schemas=None,
)
```

Load and normalize a Words table, a Fixations table, or both.

Columns keep the names your files give them: `CURRENT_FIX_DURATION`, not `duration_ms`. A column Scanpath Studio built, converted, computed or changed keeps its internal name, and `data.column_names` records what every column was called. Every API function takes these frames, and every column option (`color_by=`, the hover fields …) takes either name.

Columns are auto-detected from EyeLink, Gazepoint, Tobii, SMI, Pupil Labs and snake_case names. Normalization keeps the mapped fields and the recognized optional ones (eye, EyeLink's interest-area measures, linguistic features …) and drops the rest, unless `keep_columns` names them.

Set `include_source_cells=True` to inspect original fixation cells with `data.explain_fixation(participant, trial, order)`. It reports file data rows, parsed values, units and word assignments. Original cells are private columns of that opt-in fixation frame.

- **One table is enough.** Leave out the table a dataset doesn't have: it comes back as an empty frame, and the plots skip that layer.
- **Stimulus-level words.** A Words table without a participant column holds each text's word boxes once, and they are copied onto every trial in the fixations. Each trial is matched by its trial ID, else the trial ID it had before a repeat's `_r2` suffix, else its `text_id` (for trial IDs that embed the participant). Trials that match none raise a `data.StimulusJoinWarning` (a `UserWarning`).
- **Fixations without x/y** but with a word ID are placed at the centers of their word boxes.
- **Text word IDs.** A word ID column that holds text and no numbers (`w1`, `Hello_3`) is read as keys, kept in a `word_key` column (under the column's own name with `names="source"`). Each word's `word_id` is then its position in its text, 1, 2, … in the Words table's row order (the order of the reading that lists the most of the text), one number for every reader, and a fixation's is the number of the word with the same text ID in its trial — exactly the same text, else none. A text ID never matches a number.
- **Bookkeeping columns.** Columns named in `data.INTERNAL_COLUMNS` are the pipeline's own; `data.drop_internal_columns` removes them.

Parameters:

- **`words`** (`TablesLike | None`, default: `None` ) – The Words table, one word box per row: a DataFrame; a .csv, .tsv, .txt, .tab, .parquet, .feather, .xlsx or .xls file, or a .zip of them; a glob pattern; or a list of paths. Several files (one per participant and/or text) are concatenated, with each file's stem in a source_file column.
- **`fixations`** (`TablesLike | None`, default: `None` ) – The Fixations table, in any form words takes.
- **`word_schema`** (`dict | None`, default: `None` ) – A mapping from field to column name for the Words table, replacing auto-detection. Start from propose_schema.
- **`fix_schema`** (`dict | None`, default: `None` ) – The same for the Fixations table.
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
- `StimulusJoinError` – A stimulus-level Words table shares neither a trial ID nor a text_id with any trial (or, multipart, with every screen a trial has fixations on). A ValueError.
- `UnplacedFixationsError` – The fixations have no x/y, and not one of their word IDs names a word: text IDs the Words table does not have, or numbers against a Words table of text IDs. A ValueError.

### ScanpathData

Bases: `tuple`

The `(words, fixations)` frames `load_scanpath_data` returns, with their names.

It is a tuple, so `words, fixations = load_scanpath_data(…)` unpacks it, and `.words` / `.fixations` name the two frames. `column_names` holds the dataset's own name for every canonical column, per table: `{"words": ColumnNames, "fixations": ColumnNames}`.

With `names="source"` (the default) the frames' columns are the dataset's own names and each frame carries its map, so any API function takes it, sliced, filtered or merged, and the names it writes are yours. With `names="canonical"` they are the internal names, the same for every dataset.

#### explain_fixation

```
explain_fixation(participant, trial, order, *, screen=None)
```

Inspect a recorded fixation by its one-based parent trial order.

Load with `include_source_cells=True` to keep original inputs and row numbers. The report describes file records after parsing, with the header excluded.

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
load_raw_gaze(
    table,
    *,
    raw_gaze_schema=None,
    names=NAMES_SOURCE,
    _row_counts=None,
    _schemas=None,
)
```

Load and normalize a raw, sample-level gaze table, for `raw_gaze=`.

Raw gaze is the third table plot_scanpath can draw, under the fixations: one row per eye-tracker sample, with a participant, a trial, `x` / `y` and usually a timestamp. Optional fields include the tracked eye, pupil area and pupil diameter in the recording's own units. `plot_scanpath` keeps the selected reading's samples. Use `x_field="timestamp_ms", y_field="pupil_area"` to inspect pupil area over time.

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

- **`table`** (`TablesLike`) – A DataFrame, or a path or glob to a CSV, TSV, Parquet or Excel file, or a list of them, stacked into one table. It holds an ID column plus anything known about each participant (native_language, age, a comprehension score).
- **`id_column`** (`str | None`, default: `None` ) – The participant ID column. Defaults to the first recognized spelling (participant_id, subject, RECORDING_SESSION_LABEL, …).
- **`participants`** (`DataFrame | list | None`, default: `None` ) – A normalized frame or a list of IDs to validate the join against. The result's .report then names the participants missing from either side.

Returns:

- `ParticipantMetadata` – A ParticipantMetadata: the cleaned frame, a field registry (name, label, grain, dtype, missingness) and the join report.

Examples:

```
words, fixations = sps.load_sample_data()
meta = sps.load_participant_metadata("participants.csv", participants=fixations)
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

**The key is yours to state, and it changes what the table means.** Keyed by trial ID alone, a row describes a *text*, and every trial of it inherits that row. Keyed by participant **and** trial (`participant_column`), a row describes one *trial*. Nothing in a file says which a corpus is, so this is never inferred.

Parameters:

- **`table`** (`TablesLike`) – A DataFrame or file(s), as load_participant_metadata takes, stacked into one table. It holds a trial ID column plus anything known about each trial (a list name, a condition, a per-trial comprehension score).
- **`id_column`** (`str | None`, default: `None` ) – The trial ID column. Defaults to the first recognized spelling (trial_id, item_id, TRIAL_INDEX, …).
- **`participant_column`** (`str | None`, default: `None` ) – The participant ID column, to key each row by participant and trial. Left out, rows are keyed by trial ID alone.
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

- **`table`** (`TablesLike`) – A DataFrame or file(s), as load_participant_metadata takes, stacked into one table. It holds a text ID column plus anything known about each text (genre, difficulty, a stimulus-level comprehension score).
- **`id_column`** (`str | list[str] | None`, default: `None` ) – The text ID column, or several columns that build a composite ID, as the Text ID mapping can. Defaults to the first recognized spelling (text_id, paragraph_id, stimulus_id, …).
- **`texts`** (`DataFrame | list | None`, default: `None` ) – A normalized fixations or words frame, or any iterable of text IDs, to validate the join against. The result's .report then names the texts missing from either side.

Returns:

- `TextMetadata` – A TextMetadata: the cleaned frame, a field registry and the join report.

Examples:

```
words, fixations = sps.load_sample_data()
meta = sps.load_text_metadata("texts.csv", texts=words)
meta.names  # ('genre', 'difficulty')
```

## Load the bundled demo and public datasets

### load_sample_data

```
load_sample_data(*, names=NAMES_SOURCE)
```

Load the bundled demo, normalized and ready to plot.

The bundled demo is a subset of OneStop: two participants, twelve trials each, every one with fixations. The frames carry the demo's recorded screen (OneStop's 2560×1440), so `plot_scanpath` draws them on it without a `canvas_size`, as `scanpath-studio render --sample` does.

Parameters:

- **`names`** (`str`, default: `NAMES_SOURCE` ) – "source" for the demo's own column names, "canonical" for the internal ones (see load_scanpath_data).

Returns:

- `ScanpathData` – The (words, fixations) frames, as a ScanpathData.

### load_sample_raw_gaze

```
load_sample_raw_gaze(*, names=NAMES_SOURCE)
```

Load recorded EyeLink gaze samples for every reading in the bundled OneStop demo.

The table includes each sample during paragraph reading, with screen x/y in pixels, the tracked eye and pupil area in the tracker's units. Timestamps are milliseconds from trial recording start on the fixation report's clock. Samples with missing positions keep their timestamps; their pupil value is missing too, since the tracker measured nothing.

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

A participant is a PoTeC reader id, as a string. A trial is one reader's reading of one text, `<reader>_<text>` (`"0_b0"`), and its `text_id` is the text: `b0`–`b5` are biology, `p0`–`p5` physics. The full corpus is 75 participants × 12 texts = 900 trials.

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

## Draw a scanpath

### build_authored_scanpath

```
build_authored_scanpath(text, events=None, **layout_options)
```

Build normalized Words and Fixations frames from a hand-drawn scanpath.

Parameters:

- **`text`** (`str`) – The text to lay out as word boxes. Explicit line breaks are kept.
- **`events`** (`DataFrame | None`, default: `None` ) – The fixations, one row each, with the columns the app's Draw a scanpath table has (fixation_id, order_in_trial, word_id, x, y, duration_ms). Left out, each word gets one fixation at its center.
- **`**layout_options`** (`Any`, default: `{}` ) – Passed to authoring.layout_text (canvas_width, margin, character_width, word_height, line_height, right_to_left).

Returns:

- `tuple[DataFrame, DataFrame]` – The (words, fixations) frames, ready to plot.

### load_authored_scanpath

```
load_authored_scanpath(source)
```

Load a draft file as normalized Words and Fixations frames.

Parameters:

- **`source`** (`str | Path`) – The JSON the app's Download draft (JSON) saves on Draw a scanpath: its path, or its text.

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

- `DataFrame` – The participant and trial IDs, sorted by participant, then trial, under the names the frames carry.

### list_parts

```
list_parts(
    words, fixations, participant=None, trial=None, *, raw_gaze=None
)
```

List the ordered screens of multipart data, optionally for one trial.

Screens can come from any of the three tables, including a screen on which the tracker recorded samples and no fixations.

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

Check durations, positions and word boxes for data problems.

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

### run_analysis_recipe

```
run_analysis_recipe(
    recipe,
    words,
    fixations=None,
    *,
    raw_gaze=None,
    participant_metadata=None,
    trial_metadata=None,
    text_metadata=None,
    annotations=None,
    column_names=None,
)
```

Recreate a corpus overview, per-word cohort profile or two-group difference profile.

Parameters:

- **`recipe`** (`dict | str | Path`) – The downloaded recipe JSON path or its decoded object.
- **`words`** (`DataFrame`) – Normalized Words table from load_scanpath_data or a corpus loader.
- **`fixations`** (`DataFrame | None`, default: `None` ) – The matching normalized Fixations table, when present.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – Normalized samples from load_raw_gaze when the text filter uses their IDs.
- **`participant_metadata`** (`TablesLike | None`, default: `None` ) – The original participant metadata table for a reader filter.
- **`trial_metadata`** (`TablesLike | None`, default: `None` ) – The original trial metadata table for a trial filter.
- **`text_metadata`** (`TablesLike | None`, default: `None` ) – The original text metadata table for a text filter.
- **`annotations`** (`str | Path | None`, default: `None` ) – Path to the dataset's exported annotations JSON for a star or tag filter.
- **`column_names`** (`dict | None`, default: `None` ) – Source column maps when supplying canonical frames.

Returns:

- `DataFrame` – The published table under the dataset's own output column names.

Raises:

- `ValueError` – Unsupported recipe, missing filter fields or mismatched result.

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

Every figure option is a keyword (`show_heatmap=True`, `color_by="pass_index"`, `x_field="order_in_trial"`), and figure_options lists them with their defaults. An option naming a column takes either name: frames under the dataset's own column names, as `load_scanpath_data` returns them by default, are read through the map they carry. Use `x_field="@elapsed_seconds"` with `y_field="x"` or `"y"` to draw fixation durations against time since the reading's first recorded onset. Selecting a screen or index window keeps that origin.

Parameters:

- **`words`** (`DataFrame | None`, default: `None` ) – A normalized words frame from load_scanpath_data, or None for a dataset recorded as raw gaze alone.
- **`fixations`** (`DataFrame | None`, default: `None` ) – The normalized fixations frame, or None likewise. A categorical color_by gives each label of its column in this whole frame a color, so a category keeps its color in every trial drawn from the same frame.
- **`participant`** (`str | None`, default: `None` ) – The participant ID. It may be left out when the frames hold one trial.
- **`trial`** (`str | None`, default: `None` ) – The trial ID. It may be left out when the frames hold one trial.
- **`screen`** (`str | None`, default: `None` ) – The screen of a multipart trial to draw. Left out, the first recorded screen; coordinate spaces are never concatenated.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – The monitor size in px, (width, height). Estimated from the data's extent by default; pass the real resolution ((2560, 1440) for OneStop) to keep coordinates true to scale.
- **`base_font_size`** (`int`, default: `16` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.
- **`raw_gaze`** (`DataFrame | None`, default: `None` ) – Samples from load_raw_gaze, filtered to the trial and drawn as recorded, under the fixations. It can be the only table: with words and fixations None, the trial is looked up in the samples, the canvas is estimated from their extent, and the figure is the samples alone. No fixations are detected from them, so the fixation, saccade and heatmap layers stay empty.
- **`drift_correction`** (`str | None`, default: `None` ) – Experimental. Without SCANPATH_EXPERIMENTAL=1, anything but None or "off" raises ValueError.
- **`drift_connectors`** (`bool`, default: `False` ) – Experimental, with drift_correction.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – (start, end): draw only fixations start to end of the trial, 1-based and both inclusive. The app's Filters & highlights → Fixations → Index range.
- **`illustration`** (`bool`, default: `False` ) – Apply the Illustration design: fixations snapped to their lines, arced saccades, one color for the fixations and one for the saccades, no heatmap or word boxes. Keywords you pass still win.
- **`illustration_label`** (`str`, default: `'auto'` ) – "auto" labels the figure an illustration when it no longer shows the data as recorded; "show" and "hide" decide it.
- **`title`** (`str`, default: `''` ) – A title band stamped onto the figure without shrinking the plot, like the app's Title & labels. Literal text, not the app's {trial_id}-style pattern, since you know which trial it is.
- **`caption`** (`str`, default: `''` ) – A caption band, likewise.
- **`column_names`** (`dict | None`, default: `None` ) – The column map for frames loaded with names="canonical" (data.column_names). The options then take the dataset's names too, and the figure's text uses them.
- **`**figure_overrides`** (`Any`, default: `{}` ) – Any figure option, in place of the app's default. Three take a word of explanation: palette= ("default", "print" or "high-contrast", or the app's names) sets a group of colors at once. A color you pass explicitly wins. show_stimulus_image=True draws the trial's own stimulus page under the scanpath, as the app's Stimulus → Image does: the image_path its rows carry (from load_scanpath_data(image_root=…) or attach_stimulus_images; the bundled demo ships its pages), at its image_x / image_y. A background_image= you pass wins. fixation_snap_to_line=True moves each fixation up or down onto its text line, keeping its x: its word's line, else the nearest. fixation_snap_position says where, in line heights from the line's middle (default −0.5, its top edge). The saccades' ends move with the markers, and it does nothing with show_fixations=False.

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

Save it as interactive HTML with save_figure, whose page keeps the replay's timing, or render it to GIF or MP4 with `animation_export.export_animation`, which keeps the same timing. `fig.show()` plays it on Plotly's frame queue, which runs slower than the reading did.

The replay takes a subset of plot_scanpath's options (`figure_options("animation")`), and the ones they share default alike, so the replay matches the static figure. Set `show_fixations=False` to replay the saccades alone. The replay uses fixation times and positions and has no raw-gaze layer.

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
- **`dataset_b`** (`str | None`, default: `None` ) – The name of B's dataset, when it is another one. The pair is then checked as an overlay, and B's participant IDs are prefixed with it, so a hover says which dataset the participant is from.
- **`setup`** (`SetupSnapshot | None`, default: `None` ) – A's experimental_setup.SetupSnapshot, the screen the overlay check reads. A side without one is read off its data: the extent of that one trial, which rarely spans the whole screen, so state both when you know them.
- **`setup_b`** (`SetupSnapshot | None`, default: `None` ) – B's.
- **`**animation_overrides`** (`Any`, default: `{}` ) – Any figure option the replay takes. Also: words_b / fixations_b: B's frames. Without trial_b they must hold one trial. style_a / style_b: each scanpath's style, with the keys compare_scanpaths takes for markers and saccades (fix_color, marker_size_range, opacity, hollow, saccade_color, saccade_style, saccade_width), so the replay and the static comparison draw each trial alike. A lone replay ignores them. fixation_flags_b: B's own fixation flags. None uses A's fixation_flags, or style_b's when it names some. show_stimulus_image=True draws the trial's own page, as in plot_scanpath. A co-animation draws one page, under the text it draws: B's when compare_stimulus="b", else A's. palette= works here too. Colors it implies that the replay doesn't take are dropped rather than raising, since you named a look, not those keys.

Returns:

- `Figure` – The animated Plotly figure.

Raises:

- `ValueError` – The trial has no fixations (one recorded as raw gaze alone, or a words-only one). Also for raw_gaze=; draw samples with plot_scanpath(raw_gaze=…).
- `ValueError` – An option the replay does not take (the message names the valid ones), a style naming saccade_classes (the replay has no saccade-class filter), or B frames holding several trials without trial_b.
- `ValueError` – show_fixations=False with show_saccades=False, which leaves the replay nothing to draw.
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
    illustration_label="auto",
    column_names=None,
    **figure_overrides,
)
```

Build a figure comparing two scanpaths: the app's **Compare** mode.

**Multipart trials.** Each scanpath is one screen, never a whole multipart trial: every screen is its own coordinate space, so pooling them would draw saccades across page boundaries. `list_parts()` lists the screens.

**Two datasets.** `words_b` / `fixations_b` draw B from a *different* dataset. Two datasets can hold the same `(participant_id, trial_id)`, so B's participant IDs are prefixed with `dataset_b` inside the merged frames. Without that, the figure could draw the wrong reading, or rows of both mixed into one. The frames you pass in are not modified, and only the trace labels show the prefix.

**Numeric axes.** Set `x_field` and `y_field` to compare index, position, duration or other numeric fields in panels with matching ranges. An overlay request uses side-by-side panels on these axes. Elapsed seconds start at each full reading's first recorded fixation onset.

**The overlay gate.** A spatial overlay needs both readings on screens of the same size, or it raises `ValueError` (the app falls back to side by side). That holds across datasets, and within one when the two screens carry different `canvas_width` / `canvas_height` or `setup_b` states another screen. Pass `layout="side_by_side"` or `"stacked"` to compare readings from different screens; each panel is then drawn to its own. Nothing is rescaled.

**Per-scanpath style.** `style_a` / `style_b` restyle one scanpath with these keys:

| Key                                    | What it sets                                                                                                    | Left out                                         |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `fix_color`                            | Fixation markers and index numbers                                                                              | The scanpath's palette color                     |
| `saccade_color`                        | Saccade lines                                                                                                   | The scanpath's palette color                     |
| `marker_size_range`                    | Smallest and largest fixation markers                                                                           | The figure's `marker_size_range`                 |
| `opacity`, `hollow`                    | Its fixation markers                                                                                            | Its default                                      |
| `saccade_style`, `saccade_width`       | Its saccade lines                                                                                               | Its default                                      |
| `box_color`                            | The outline of that reading's word boxes                                                                        | Its `fix_color`                                  |
| `box_fill_color`                       | Their fill                                                                                                      | `word_box_fill_color`                            |
| `box_line_opacity`, `box_fill_opacity` | Their outline's and fill's opacity, 0–1 (0 hides it)                                                            | `word_box_line_opacity`, `word_box_fill_opacity` |
| `raw_gaze_color`                       | That reading's raw-gaze samples                                                                                 | Its `fix_color`                                  |
| `heatmap_colorscale`                   | That reading's word-box heatmap color scale, on the range both share; two different scales get a color bar each | `heatmap_colorscale`                             |
| `fixation_flags`, `saccade_classes`    | That scanpath's own filters, in place of the figure's                                                           | The figure's                                     |

For a replay of two scanpaths, see animate_scanpath for the supported styles.

Parameters:

- **`words`** (`DataFrame`) – The words frame holding both trials, or A's when words_b is given.
- **`fixations`** (`DataFrame`) – The fixations frame, likewise.
- **`trial_a`** (`tuple[str, str]`) – A's (participant, trial).
- **`trial_b`** (`tuple[str, str]`) – B's (participant, trial).
- **`screen`** (`str | None`, default: `None` ) – A's screen of a multipart trial. Left out, its first recorded screen, as in plot_scanpath.
- **`screen_b`** (`str | None`, default: `None` ) – B's screen, looked up in B's own frames, so it may be a later page or another dataset's.
- **`words_b`** (`DataFrame | None`, default: `None` ) – B's words frame, to draw B from another dataset.
- **`fixations_b`** (`DataFrame | None`, default: `None` ) – B's fixations frame, likewise.
- **`dataset_b`** (`str`, default: `'Dataset B'` ) – The name B's participant IDs are prefixed with.
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
- **`illustration_label`** (`str`, default: `'auto'` ) – As in plot_scanpath. An authored reading on either side labels the comparison.
- **`title`** (`str`, default: `''` ) – As in plot_scanpath.
- **`caption`** (`str`, default: `''` ) – As in plot_scanpath.
- **`column_names`** (`dict | None`, default: `None` ) – As in plot_scanpath. A's names, or column_names, name the options and the figure's text; either dataset's frames may come under their own names.
- **`**figure_overrides`** (`Any`, default: `{}` ) – Any figure option a comparison takes (figure_options("comparison")). Some act per scanpath: fixation_flags and saccade_classes filter both scanpaths, unless a style gives one its own. background_image is A's page. A split layout draws B's panel over background_image_b (with background_image_size_b / background_image_origin_b), and over nothing without it, never A's, since sharing a dataset says nothing about sharing a page. show_stimulus_image=True takes each reading's own page from its rows: a split layout draws A's and B's, each in its panel, and an overlay the page of the text it draws (B's for compare_stimulus="b", else A's). An image passed explicitly wins.

Returns:

- `Figure` – The Plotly figure.

Raises:

- `ValueError` – fixations is None: a dataset recorded as raw gaze alone has no scanpath to compare.
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
- **`participant`** (`str | None`, default: `None` ) – The participant ID.
- **`trial`** (`str | None`, default: `None` ) – The parent trial's ID.
- **`animate`** (`bool`, default: `False` ) – Build replays with animate_scanpath instead of plot_scanpath's figures.
- **`transition_mode`** (`str`, default: `'instant'` ) – "instant" or "recorded". Each animated figure's layout.meta['transition_after_ms'] records the delay before the next screen: zero for "instant", the observed parent-clock gap for "recorded".
- **`screens`** (`Sequence[str] | None`, default: `None` ) – Only these screen IDs (one may be given as a string), in the trial's order, as the app's Export → Screens does. None renders them all. Each figure's screen_index meta stays the screen's place in the trial.
- **`**options`** (`Any`, default: `{}` ) – Passed to plot_scanpath or animate_scanpath.

Returns:

- `dict[str, Figure]` – {screen_id: figure} in the trial's order, ready to save as per-screen files. A single-screen trial gives {"screen-1": figure}.

Raises:

- `ValueError` – A screen ID the trial does not have, or screens for a trial with no screens to choose from.

### plot_corpus_figure

```
plot_corpus_figure(
    data,
    *,
    kind,
    measure_label="Value",
    series_col="series",
    value_col="value",
    as_percent=False,
    colors=None,
    canvas_width=1000,
    base_font_size=14,
    font_family=FONT_FAMILY,
)
```

Plot a corpus overview, profile, distribution or difference from a tidy table.

The headless form of Corpus Analysis's figures, in the same colors.

Parameters:

- **`data`** (`DataFrame`) – The tidy table. kind="profile" reads word_id and value_col (and optional lo / hi), "distribution" reads value_col, and "difference" reads word_id and diff. An "overview" reads the group ID in series_col, the mean in value_col, and its observed minimum and maximum in lo and hi. It plots the 12 highest means.
- **`kind`** (`str`) – "overview", "profile", "distribution" or "difference".
- **`measure_label`** (`str`, default: `'Value'` ) – The measure's label, and the series' name when the table has no series_col.
- **`series_col`** (`str`, default: `'series'` ) – The group ID for an overview, or the column naming each overlaid series.
- **`value_col`** (`str`, default: `'value'` ) – The column holding the values.
- **`as_percent`** (`bool`, default: `False` ) – Display overview proportions as percentages on the axis and in hover labels. Supply values and bounds on the 0–1 scale.
- **`colors`** (`tuple[str, ...] | None`, default: `None` ) – The series' colors, in order. Left out, the app's palette.
- **`canvas_width`** (`int`, default: `1000` ) – The figure's width in px.
- **`base_font_size`** (`int`, default: `14` ) – The base font size in px.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – The font family.

Returns:

- `Figure` – The figure.

Raises:

- `ValueError` – The table lacks a column its kind reads (the message names it and the columns present), or kind is unknown.

## Figure options

Set layers, colors, sizes and legends with keyword arguments to `plot_scanpath`, `animate_scanpath` or `compare_scanpaths`. The tables below list each option's default and matching CLI `render` flag, under the section names of the app's **Plot controls**. If an option applies to fewer than four views, its row names them. **Single plot** and **Single replay** show one scanpath. **Compare** shows two scanpaths together or in separate panels, and **Compare readings** with **Animation** replays two scanpaths.

For options with a fixed set of values, case, spaces, `-` and `_` are ignored; other values raise a `ValueError`. A `--no-…` flag turns off an option that is on by default.

`figure_options()` returns the keywords a builder accepts and their defaults. `figure_options(choices=True)` also lists the accepted values.

### figure_options

```
figure_options(kind='static', *, choices=False)
```

List figure options and their default values.

The defaults follow the app's Scanpath design. Some accepted keywords affect only certain views. For example, `order_font_color` sets the fixation index color for a single scanpath. With two scanpaths, each index takes its scanpath's fixation color. The *Figure options* table lists the views and matching `render` flags.

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

### Fixations

| Option and `render` flag                                              | Default       | Description                                                                                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_fixations` `--no-fixations`                                     | `True`        | Hide the fixations.                                                                                                                                                                                                                                                                                                                                             |
| `fixation_color` `--fixation-color`                                   | `'#0072B2'`   | Fixation color when `--color-by` is '(uniform)'. For two scanpaths, set `fix_color` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                                                                                                    |
| `color_by` `--color-by`                                               | `'(uniform)'` | Fixations table column to color the fixations by, e.g. duration_ms, or 'line' for each fixation's text line (same as `--color-by-line`). Default: '(uniform)', one color, since marker size already shows duration.                                                                                                                                             |
| `color_by_line` `--color-by-line`                                     | `False`       | Color each fixation by the text line it lands on, with the lines found from the word boxes. Overrides `--color-by`. Same as `--color-by` line.                                                                                                                                                                                                                  |
| `fixation_colorscale` `--fixation-colorscale`                         | `'Blues'`     | Color scale for `--color-by`, e.g. Viridis.                                                                                                                                                                                                                                                                                                                     |
| `fixation_color_range` `--fixation-color-range`                       | `None`        | Fix the `--color-by` color scale to LO..HI instead of the trial's range, so several figures share one scale.                                                                                                                                                                                                                                                    |
| `fixation_opacity` `--fixation-opacity`                               | `0.7`         | Opacity of fixation markers, 0–1. For two scanpaths, set `opacity` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                                                                                                                     |
| `fixation_symbol` `--fixation-symbol`                                 | `'circle'`    | Fixation marker shape. Unlike color, shape survives a grayscale print. One of `'circle'`, `'square'`, `'diamond'`, `'triangle-up'`, `'cross'`, `'x'`, `'star'`, `'hexagon'`, `'heart'`.                                                                                                                                                                         |
| `hollow_fixations` `--hollow-fixations`                               | `False`       | Draw the fixations as outlines instead of filled markers. For two scanpaths, set `hollow` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                                                                                              |
| `fixation_outline_color` `--fixation-outline-color`                   | `'#111111'`   | Color of that outline.                                                                                                                                                                                                                                                                                                                                          |
| `fixation_outline_width` `--fixation-outline-width`                   | `0.5`         | Outline width around each filled fixation marker, 0–5 px; 0 draws none.                                                                                                                                                                                                                                                                                         |
| `marker_size_scale` `--marker-size-scale`                             | `'sqrt'`      | How duration sets marker size. sqrt, linear and log map `--marker-duration-range` onto `--marker-size-range`, so a duration gets the same size in every trial, comparison and replay. With sqrt, marker area grows with duration. relative stretches each figure from its shortest to its longest fixation. One of `'sqrt'`, `'linear'`, `'log'`, `'relative'`. |
| `marker_size_range` `--marker-size-range`                             | `(8, 24)`     | Smallest and largest fixation marker size in px, e.g. 4 12. A smaller range suits thumbnails. Each scanpath uses this range unless its style supplies one.                                                                                                                                                                                                      |
| `marker_duration_range` `--marker-duration-range`                     | `(50, 600)`   | The durations in ms that get the smallest and largest marker. Shorter and longer fixations are clamped to them. Not used by `--marker-size-scale` relative.                                                                                                                                                                                                     |
| `show_fixation_colorbar` `--no-fixation-colorbar`                     | `True`        | Leave out `--color-by`'s color bar.                                                                                                                                                                                                                                                                                                                             |
| `fixation_colorbar_orientation` `--fixation-colorbar-orientation`     | `'Vertical'`  | Fixation color bar: beside the plot (vertical, default) or below it. One of `'Vertical'`, `'Horizontal'`.                                                                                                                                                                                                                                                       |
| `fixation_colorbar_length` `--fixation-colorbar-length`               | `None`        | Fixation color bar: length as a share of the plot's side, 0.1–1.0.                                                                                                                                                                                                                                                                                              |
| `fixation_colorbar_thickness` `--fixation-colorbar-thickness`         | `14`          | Fixation color bar: thickness, 4–40 px.                                                                                                                                                                                                                                                                                                                         |
| `fixation_colorbar_tickangle` `--fixation-colorbar-tickangle`         | `0`           | Fixation color bar: tick-label angle, -90–90.                                                                                                                                                                                                                                                                                                                   |
| `fixation_colorbar_tickfont_size` `--fixation-colorbar-tickfont-size` | `12`          | Fixation color bar: tick-label size.                                                                                                                                                                                                                                                                                                                            |
| `show_order` `--no-fixation-index` `--fixation-index`                 | `False`       | Number the fixations in order (the app's Fixation index).                                                                                                                                                                                                                                                                                                       |
| `order_font_size` `--order-font-size`                                 | `10`          | Size of the fixation index numbers.                                                                                                                                                                                                                                                                                                                             |
| `order_font_color` `--order-font-color`                               | `'#111111'`   | Color of the fixation index numbers for a single scanpath. For two scanpaths, set `fix_color` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                                                                                          |
| `order_label_position` `--order-label-position`                       | `'above'`     | Where each fixation index number sits on its fixation. One of `'above'`, `'inside'`, `'below'`.                                                                                                                                                                                                                                                                 |
| `fixation_snap_to_line` `--snap-fixations`                            | `False`       | Move each fixation up or down onto its text line: its word's line, else the nearest. Its x stays. `--snap-position` sets where on the line. *Single plot.*                                                                                                                                                                                                      |
| `fixation_snap_position` `--snap-position`                            | `-0.5`        | Where on its line a snapped fixation sits, in line heights from the line's middle: 0 centers it, -0.5 is the top edge, 0.5 the bottom edge. Used with `--snap-fixations`. *Single plot.*                                                                                                                                                                        |

### Saccades

| Option and `render` flag                                                      | Default       | Description                                                                                                                                                                                                                                                                                     |
| ----------------------------------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_saccades` `--no-saccades`                                               | `True`        | Hide the saccades.                                                                                                                                                                                                                                                                              |
| `saccade_color` `--saccade-color`                                             | `'#CC79A7'`   | Saccade line and arrow color, as hex or a CSS name. For two scanpaths, set `saccade_color` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                             |
| `saccade_style` `--saccade-style`                                             | `'solid'`     | Saccade line dash style. One of `'solid'`, `'dash'`, `'dot'`, `'dashdot'`. For two scanpaths, set `saccade_style` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                      |
| `saccade_width` `--saccade-width`                                             | `2.0`         | Saccade line width in px, 0.5–10. For two scanpaths, set `saccade_width` in `style_a` or `style_b`. *Single plot, Single replay.*                                                                                                                                                               |
| `saccade_opacity` `--saccade-opacity`                                         | `1.0`         | Opacity of saccade lines and arrows, 0–1.                                                                                                                                                                                                                                                       |
| `show_saccade_arrows` `--saccade-arrows`                                      | `False`       | Draw an arrowhead on each saccade (the app's Direction arrows).                                                                                                                                                                                                                                 |
| `saccade_arrow_size` `--saccade-arrow-size`                                   | `12.0`        | Size of the `--saccade-arrows` arrowheads, 4–40 px.                                                                                                                                                                                                                                             |
| `saccade_render_mode` `--saccade-arcs`                                        | `'Straight'`  | Draw saccades as upward arcs instead of straight lines (the app's Shape: Arc). One of `'Straight'`, `'Arc'`. *Single plot.*                                                                                                                                                                     |
| `saccade_color_mode` `--saccade-color-by-type` `--saccade-color-by-direction` | `'One color'` | Color each saccade by its type: forward, skip, refixation, return sweep or regression (the app's By type). One of `'One color'`, `'Forward / regression'`, `'By type'`. *Single plot.*                                                                                                          |
| `saccade_class_colors` `--saccade-type-color`                                 | `None`        | Set one saccade type's color, e.g. `--saccade-type-color` regression=#000000. Repeatable. Types: forward, skip, refixation, return_sweep, regression. Implies `--saccade-color-by-type`. With `--saccade-color-by-direction`, it sets the forward and regression colors instead. *Single plot.* |

### Stimulus

| Option and `render` flag                              | Default       | Description                                                                                                                                                                                                                         |
| ----------------------------------------------------- | ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_word_labels` `--no-text`                        | `True`        | Hide the stimulus text.                                                                                                                                                                                                             |
| `redact_text` `--redact-text`                         | `False`       | Replace each word with a rounded block in the text color and hide its text in tooltips. Preserves the text layout while concealing the words (the app's Text → Redact).                                                             |
| `line_spacing` `--line-spacing`                       | `3.0`         | Line spacing, in font sizes: the text's font size is the distance between lines ÷ N.                                                                                                                                                |
| `scale_text_to_boxes` `--no-scale-text-to-boxes`      | `True`        | Draw the text at `--font-size` instead of fitting it to the word boxes (the app's Fit to word boxes).                                                                                                                               |
| `text_color` `--text-color`                           | `'#000000'`   | Stimulus text color.                                                                                                                                                                                                                |
| `highlight_column` `--highlight-column`               | `None`        | Boolean Words table column that marks the words to highlight (e.g. is_in_aspan, OneStop's answer span; default: none). `--critical-span-style` sets how they are drawn.                                                             |
| `highlight_text_color` `--highlight-text-color`       | `'#D55E00'`   | Color of the `--highlight-column` words under `--critical-span-style` mark-text.                                                                                                                                                    |
| `critical_span_style` `--critical-span-style`         | `'Mark text'` | How the `--highlight-column` words are marked: mark-text recolors them, mark-border outlines their boxes, underline underlines each word, none hides the marks. One of `'Mark text'`, `'Mark border'`, `'Underline'`, `'None'`.     |
| `span_border_color` `--span-border-color`             | `'#000000'`   | Box color under `--critical-span-style` mark-border.                                                                                                                                                                                |
| `show_stimulus_image` `--show-stimulus-image`         | `False`       | Draw each trial's stimulus image under the scanpath, from the image_path column of its rows, placed at image_x / image_y. `--image-root` fills that column, and `--sample` ships its images. `--stimulus-image` takes precedence.   |
| `background_image` `--stimulus-image`                 | `None`        | Draw an image (PNG or JPG) under the scanpath as the stimulus. It is sized to the PNG's pixel size, else to the canvas. Use `--stimulus-image-size` and `--stimulus-image-origin` to place a cropped image in fixation coordinates. |
| `background_image_size` `--stimulus-image-size`       | `None`        | Stimulus image size in px, e.g. 1310x991. Use with `--stimulus-image`.                                                                                                                                                              |
| `background_image_origin` `--stimulus-image-origin`   | `None`        | Top-left corner of the stimulus image in screen px, e.g. 305,44. Use with `--stimulus-image` to line a centered crop up with the fixations.                                                                                         |
| `background_image_opacity` `--stimulus-image-opacity` | `1.0`         | Stimulus image opacity, 0.1–1.0. Lower it so the fixations, saccades and word boxes stand out on a busy image.                                                                                                                      |

### Word boxes

| Option and `render` flag                          | Default     | Description                                                                                                                                        |
| ------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_words` `--no-word-boxes` `--word-boxes`     | `False`     | Draw the word boxes.                                                                                                                               |
| `word_box_color` `--word-box-color`               | `'#6c757d'` | Word-box outline color. In a comparison, each scanpath's boxes are outlined in its color instead. *Single plot, Single replay, Compare + Animate.* |
| `word_box_line_opacity` `--word-box-line-opacity` | `1.0`       | Word-box outline opacity, 0–1; 0 draws the fill only. Below 1 the outline color must be #rrggbb, #rgb or rgb(r, g, b).                             |
| `word_box_fill_color` `--word-box-fill-color`     | `'#646464'` | Word-box fill color, drawn at `--word-box-fill-opacity`: #rrggbb, #rgb or rgb(r, g, b).                                                            |
| `word_box_fill_opacity` `--word-box-fill-opacity` | `0.05`      | Word-box fill opacity, 0–1; 0 draws outlines only.                                                                                                 |

### Heatmap

| Option and `render` flag                                            | Default         | Description                                                                                                                                                                                                |
| ------------------------------------------------------------------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_heatmap` `--no-heatmap` `--heatmap`                           | `False`         | Draw the heatmap. *Single plot, Compare.*                                                                                                                                                                  |
| `heatmap_style` `--heatmap-style`                                   | `'Word boxes'`  | Heatmap style: word-boxes tints each word box, smoothed blurs the fixations. One of `'Word boxes'`, `'Smoothed'`. *Single plot.*                                                                           |
| `heatmap_metric` `--heatmap-metric`                                 | `'duration_ms'` | What the heatmap colors by (the app's Color → By): the fixation duration column, under your file's name or as duration_ms, or counts for the fixation count. Default: duration_ms. *Single plot, Compare.* |
| `heatmap_colorscale` `--heatmap-colorscale`                         | `'Blues'`       | Heatmap color scale, e.g. Greens. *Single plot, Compare.*                                                                                                                                                  |
| `heatmap_norm` `--heatmap-norm`                                     | `'Linear'`      | Heatmap color scaling: linear (default) or log. Log keeps a few words with long dwell times from washing out the rest. One of `'Linear'`, `'Log'`. *Single plot, Compare.*                                 |
| `heatmap_range` `--heatmap-range`                                   | `None`          | Fix the heatmap's color scale to LO..HI instead of the trial's range. *Single plot, Compare.*                                                                                                              |
| `heatmap_opacity` `--heatmap-opacity`                               | `None`          | Heatmap opacity, 0.05–1.0. *Single plot, Compare.*                                                                                                                                                         |
| `heatmap_sigma_px` `--heatmap-sigma`                                | `None`          | Blur of `--heatmap-style` smoothed, as a Gaussian σ in px. *Single plot.*                                                                                                                                  |
| `word_heatmap_col` `--word-heatmap-col`                             | `None`          | With `--heatmap`, for a dataset with no fixations: tint each word box by this numeric Words table column, e.g. gpt2_surprisal, instead of its total fixation duration. *Single plot.*                      |
| `word_heatmap_title` `--word-heatmap-title`                         | `None`          | Color-bar title for `--word-heatmap-col`. *Single plot.*                                                                                                                                                   |
| `show_heatmap_colorbar` `--no-heatmap-colorbar`                     | `True`          | Leave out the heatmap's color bar. *Single plot, Compare.*                                                                                                                                                 |
| `heatmap_colorbar_orientation` `--heatmap-colorbar-orientation`     | `'Vertical'`    | Heatmap color bar: beside the plot (vertical, default) or below it. One of `'Vertical'`, `'Horizontal'`. *Single plot, Compare.*                                                                           |
| `heatmap_colorbar_length` `--heatmap-colorbar-length`               | `None`          | Heatmap color bar: length as a share of the plot's side, 0.1–1.0. *Single plot, Compare.*                                                                                                                  |
| `heatmap_colorbar_thickness` `--heatmap-colorbar-thickness`         | `14`            | Heatmap color bar: thickness, 4–40 px. *Single plot, Compare.*                                                                                                                                             |
| `heatmap_colorbar_tickangle` `--heatmap-colorbar-tickangle`         | `0`             | Heatmap color bar: tick-label angle, -90–90. *Single plot, Compare.*                                                                                                                                       |
| `heatmap_colorbar_tickfont_size` `--heatmap-colorbar-tickfont-size` | `12`            | Heatmap color bar: tick-label size. *Single plot, Compare.*                                                                                                                                                |

### Raw gaze

| Option and `render` flag                        | Default     | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_raw_gaze` `--raw-gaze` `--no-raw-gaze`    | `False`     | The Raw gaze table to draw under the fixations, in the formats `--fixations` reads and auto-detected the same way. Several paths, or a quoted glob, are stacked into one table. Drawn on static figures and `--compare-with` comparisons, where each scanpath's samples take its color, but not with `--animate`. As the only input it is the dataset: its trials are listed and drawn as recorded, and no fixations are detected from the samples. *Single plot, Compare.* |
| `raw_gaze_color` `--raw-gaze-color`             | `'#888888'` | Raw gaze sample color. In a comparison, each scanpath's samples are drawn in its color instead. In Compare, set `raw_gaze_color` in `style_a` or `style_b`. *Single plot.*                                                                                                                                                                                                                                                                                                  |
| `raw_gaze_marker_size` `--raw-gaze-marker-size` | `4.0`       | Raw gaze sample size, 1–12 px. *Single plot, Compare.*                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `raw_gaze_opacity` `--raw-gaze-opacity`         | `0.6`       | Raw gaze sample opacity, 0.1–1.0. *Single plot, Compare.*                                                                                                                                                                                                                                                                                                                                                                                                                   |

### Filters & highlights

| Option and `render` flag              | Default                        | Description                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ------------------------------------- | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fixation_flags` `--fixation-flag`    | `None`                         | Highlight or hide one kind of fixation, like the app's Filters & highlights. Repeatable. SPEC is CATEGORY=MODE[,threshold_ms=N][,symbol=S][,color=#RRGGBB]. CATEGORY is short, long, oob (outside every word box) or blink. MODE is off, highlight or hide. threshold_ms applies to short and long only. hide removes the fixations from the figure only; measures and exports keep them. E.g. `--fixation-flag` short=hide,threshold_ms=80. |
| `saccade_classes` `--saccade-classes` | `list`, see `figure_options()` | Draw only these saccade types, comma-separated, e.g. `--saccade-classes` regression,return_sweep. Types: forward, skip, refixation, return_sweep, regression, other (off the text). A hidden type loses its line and its arrow. Default: all. *Single plot, Compare.*                                                                                                                                                                        |

### Screen & framing

| Option and `render` flag                | Default     | Description                                                                                 |
| --------------------------------------- | ----------- | ------------------------------------------------------------------------------------------- |
| `background_color` `--background-color` | `'#ffffff'` | Plot background color.                                                                      |
| `fit_to_monitor` `--no-full-monitor`    | `True`      | Frame the plot on the data instead of the whole `--canvas` screen (the app's Crop to data). |
| `crop_margin` `--crop-margin`           | `None`      | The margin around the data, in screen px, when cropping to it. Implies `--crop-to-data`.    |
| `show_plot_frame` `--no-plot-frame`     | `True`      | Leave out the border around the plot area.                                                  |
| `plot_frame_color` `--plot-frame-color` | `'#000000'` | Color of the border around the plot area.                                                   |

### Axes

| Option and `render` flag                                  | Default | Description                                                                                                                                                                                                                              |
| --------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `show_coordinate_grid` `--coordinate-grid`                | `False` | Draw a grid in screen pixels over the scanpath (the app's Axes & grid → Grid).                                                                                                                                                           |
| `coordinate_grid_spacing` `--coordinate-grid-spacing`     | `None`  | The grid's major spacing in px. Implies `--coordinate-grid`. Leave it out for an automatic spacing of 1, 2 or 5 × 10ⁿ px.                                                                                                                |
| `coordinate_grid_font_size` `--coordinate-grid-font-size` | `18`    | Size of the coordinate grid's labels, 6–36 px.                                                                                                                                                                                           |
| `x_field` `--x-field`                                     | `'x'`   | Horizontal axis of the static chart. Choose a numeric fixation field, @elapsed_seconds from the first recorded fixation, or a raw sample field such as timestamp_ms, sample_index, pupil_area or pupil_diameter. *Single plot, Compare.* |
| `y_field` `--y-field`                                     | `'y'`   | Vertical axis of the static chart. Takes the same fields as `--x-field`. *Single plot, Compare.*                                                                                                                                         |

### Title & labels

| Option and `render` flag                  | Default     | Description                                                                                                                                                     |
| ----------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `illustration_text` `--illustration-text` | `''`        | The Illustration label's text.                                                                                                                                  |
| `illustration_reasons`                    | `None`      | Why the figure is labeled an illustration. The builder works it out from `illustration_label`. Pass it only to word the label yourself. *Single plot, Compare.* |
| `title_font_size` `--title-size`          | `20`        | Size of the `--title` text, 8–48 px.                                                                                                                            |
| `caption_font_size` `--caption-size`      | `13`        | Size of the `--caption` text, 6–36 px.                                                                                                                          |
| `caption_color` `--caption-color`         | `'#555555'` | Color of the `--caption` text.                                                                                                                                  |
| `show_credit` `--credit`                  | `False`     | A small 'Made with Scanpath Studio' line under the plot. The figure grows to fit it.                                                                            |

### Hover fields

| Option and `render` flag                          | Default                        | Description                                                  |
| ------------------------------------------------- | ------------------------------ | ------------------------------------------------------------ |
| `word_hover_fields` `--word-hover-fields`         | `list`, see `figure_options()` | Comma-separated word columns to show on hover, in order.     |
| `word_hover_measure` `--word-hover-measure`       | `'total_fixation_duration_ms'` | The reading measure a word's hover shows.                    |
| `fixation_hover_fields` `--fixation-hover-fields` | `list`, see `figure_options()` | Comma-separated fixation columns to show on hover, in order. |

### Legends

| Option and `render` flag                                                    | Default | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| --------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `legend_layout` `--legend`                                                  | `None`  | Place one legend. Repeatable. SPEC is KIND=POSITION[,ARRANGEMENT][,SIZE]. KIND is compare (Compare (A/B)), saccades (Saccade types), colors (Fixation colors), size-key (Fixation sizes) or highlight (Text highlight). POSITION is auto, or SPOT-outside or SPOT-inside, with SPOT one of top-left, top-center, top-right, left, right, bottom-left, bottom-center, bottom-right. Outside grows the figure, and left and right run down the side. ARRANGEMENT is stacked or side-by-side, and SIZE the text size in px. E.g. `--legend` saccades=right-outside,stacked,14. Each legend's switch still decides whether it is drawn. |
| `show_color_legend` `--no-color-legend`                                     | `True`  | Hide the Fixation colors legend, which lists the categories of a categorical `--color-by` and the highlighted fixations. The markers still draw.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `show_highlight_legend` `--no-highlight-legend`                             | `True`  | Hide the Text highlight legend, which names the highlighted words. The words stay marked. `--legend` highlight=SPEC places it.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `saccade_type_legend` `--no-saccade-type-legend`                            | `True`  | With `--saccade-color-by-type`: hide the Saccade types legend. The colored lines still draw. *Single plot.*                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| `duration_size_legend` `--no-duration-size-legend` `--duration-size-legend` | `False` | Show reference circles labeled in milliseconds for the sqrt, linear or log fixation size scale (off by default).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

### Animate

| Option and `render` flag                  | Default | Description                                                                                                                                        |
| ----------------------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `anim_grid_step_ms` `--anim-grid-step-ms` | `None`  | With `--animate`: one frame per MS of reading time. A smaller step is smoother and makes a larger file. *Single replay, Compare + Animate.*        |
| `anim_max_frames` `--anim-max-frames`     | `None`  | With `--animate`: at most N frames. A trial too long for that many at `--anim-grid-step-ms` gets a wider step. *Single replay, Compare + Animate.* |

### Compare

| Option and `render` flag                                | Default        | Description                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `label_a` `--label-a`                                   | `'Scanpath A'` | Name of scanpath A in the legend and tooltips. Requires `--compare-with` and `--label-b`. In Python, pass `labels=(a, b)` to `compare_scanpaths`. *Compare, Compare + Animate.*                                                                                                                                                           |
| `label_b` `--label-b`                                   | `'Scanpath B'` | Name of scanpath B in the legend and tooltips. Requires `--label-a`. In Python, pass `labels=(a, b)` to `compare_scanpaths`. *Compare, Compare + Animate.*                                                                                                                                                                                |
| `style_a` `--style-a`                                   | `None`         | Style for scanpath A, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid |
| `style_b` `--style-b`                                   | `None`         | Style for scanpath B, repeatable: KEY=VALUE[,...]. Colors (#RRGGBB): fix_color, saccade_color, box_color (word-box outline; default fix_color), box_fill_color (default `--word-box-fill-color`), raw_gaze_color (default fix_color). Also heatmap_colorscale (default `--heatmap-colorscale`, on the shared range), saccade_style (solid |
| `show_legend` `--no-compare-legend`                     | `True`         | Draw the Compare (A/B) legend, which names the two scanpaths. On by default; `--no-compare-legend` hides it. Also applies to `--animate`. *Compare, Compare + Animate.*                                                                                                                                                                   |
| `compare_stimulus` `--compare-stimulus`                 | `'both'`       | On an overlay, whose word boxes and text to draw. Two datasets' word boxes line up only when the text is the same. A two-scanpath replay shows B's text for 'b' and A's text for 'a' or 'both'. One of `'both'`, `'a'`, `'b'`. *Compare, Compare + Animate.*                                                                              |
| `words_b`                                               | `None`         | Scanpath B's Words table when it comes from a second dataset. *Compare, Compare + Animate.*                                                                                                                                                                                                                                               |
| `fixations_b`                                           | `None`         | Scanpath B's Fixations table when it comes from a second dataset. *Compare, Compare + Animate.*                                                                                                                                                                                                                                           |
| `fixation_flags_b` `--compare-fixation-flag`            | `None`         | Filters & highlights for scanpath B only. Repeatable. Same SPEC as `--fixation-flag`, e.g. `--compare-fixation-flag` short=hide,threshold_ms=80. Replaces `--fixation-flag` for B. In Python, pass `style_b={'fixation_flags': flags}` to `compare_scanpaths`. *Compare, Compare + Animate.*                                              |
| `background_image_b` `--stimulus-image-b`               | `None`         | Scanpath B's stimulus image, for a side-by-side or stacked comparison across two datasets, where each panel draws its image. Sized and placed like `--stimulus-image`. *Compare.*                                                                                                                                                         |
| `background_image_size_b` `--stimulus-image-size-b`     | `None`         | Size of `--stimulus-image-b` in px. *Compare.*                                                                                                                                                                                                                                                                                            |
| `background_image_origin_b` `--stimulus-image-origin-b` | `None`         | Top-left corner of `--stimulus-image-b` in B's screen px. *Compare.*                                                                                                                                                                                                                                                                      |

## Reproduce a figure in code

The app's **Share** tab → **Code** shows the Python or CLI code that rebuilds the figure on screen. Paste it into a notebook or a terminal to get the same figure. `figure_code` writes the same code without the app, and `render --print-code` prints it for a `render` command you already have.

```
print(
    sps.figure_code(
        participant="l7_183",
        trial="l7_183_2_1_1_Ele",
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
    participant='l7_183',
    trial='l7_183_2_1_1_Ele',
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
    compare_source_options=None,
    canvas_size=None,
    base_font_size=16,
    font_family=FONT_FAMILY,
    title="",
    caption="",
    fix_index_range=None,
    fix_index_range_b=None,
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

The headless form of the app's **Share** → **Code**. Give it the arguments you would give plot_scanpath (`kind="static"`), animate_scanpath (`"animation"`) or compare_scanpaths (`"comparison"`), and it returns the snippet that rebuilds that figure. Only the options that differ from figure_options are written, so the snippet stays readable. `code_snippet.ReproductionCode` is the structured form.

Parameters:

- **`kind`** (`str`, default: `'static'` ) – "static", "animation" or "comparison": the builder the snippet calls.
- **`source`** (`str`, default: `'demo'` ) – How the data is loaded: "demo", "synthetic", "files", "potec", "onestop", "author", "raw_gaze" (a dataset recorded as raw gaze alone, whose samples at source_options["raw_gaze"] are the data), or "unknown" for data a snippet can't name.
- **`source_options`** (`dict | None`, default: `None` ) – That loader's arguments: {"root": …}, {"words": [...], "fixations": [...]} and so on. With show_raw_gaze=True, "raw_gaze" (and an optional "raw_gaze_schema") names the raw-gaze files; the demo uses its own.
- **`participant`** (`str`, default: `''` ) – The participant ID. Left empty, the snippet renders the first available trial, as render does.
- **`trial`** (`str`, default: `''` ) – The trial ID, likewise.
- **`screen`** (`str | None`, default: `None` ) – A's screen of a multipart trial (screen=, --screen).
- **`compare`** (`tuple[str, str] | None`, default: `None` ) – B's (participant, trial), for a comparison or a co-animation.
- **`compare_screen`** (`str | None`, default: `None` ) – B's screen (screen_b=, --compare-screen).
- **`compare_layout`** (`str`, default: `'overlay'` ) – The comparison's layout, as compare_scanpaths takes it.
- **`compare_stimulus`** (`str`, default: `'both'` ) – Whose stimulus an overlay draws, as compare_scanpaths takes it.
- **`compare_dataset`** (`str`, default: `''` ) – The dataset B was loaded from, when it is a second one. Both forms then load B's own tables (words_b= / fixations_b= / dataset_b=, and --compare-words / --compare-fixations), from compare_source_options, else from the placeholder paths B_WORDS / B_FIXATIONS that you point at its files.
- **`compare_canvas`** (`tuple[int, int] | None`, default: `None` ) – B's screen, (width, height), with compare_dataset: written as setup_b= and --compare-canvas, which a co-animation across datasets needs.
- **`compare_labels`** (`tuple[str, str] | None`, default: `None` ) – The two trace labels, when they are not the composed defaults: labels= and --label-a / --label-b.
- **`compare_source_options`** (`dict | None`, default: `None` ) – How B's tables load when B is a second dataset, as source_options says it for A's files: "words" / "fixations" / "raw_gaze" paths in place of the placeholders, and "word_schema" / "fix_schema" / "raw_gaze_schema" mappings (--compare-word-schema and its siblings). Without compare_dataset, B is named "Dataset B", as render names it.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – The monitor size. Defaults to the screen render assumes for the source (the bundled demo's 2560×1440, PoTeC's 1680×1050, …), so both forms draw the same figure.
- **`base_font_size`** (`int`, default: `16` ) – As the builders take it.
- **`font_family`** (`str`, default: `FONT_FAMILY` ) – As the builders take it.
- **`title`** (`str`, default: `''` ) – As the builders take it.
- **`caption`** (`str`, default: `''` ) – As the builders take it.
- **`fix_index_range`** (`tuple[int, int] | None`, default: `None` ) – As the builders take it.
- **`fix_index_range_b`** (`tuple[int, int] | None`, default: `None` ) – B's window, with compare, as compare_scanpaths and animate_scanpath take it (--compare-fix-index-range).
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

- `ValueError` – An unknown flavor, or a key compare_source_options does not take.
- `TypeError` – An option the builder does not take.

Examples:

```
print(
    sps.figure_code(
        participant="l7_183",
        trial="l7_183_2_1_1_Ele",
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
    proof_width_mm=None,
    compact_png=False,
)
```

Save a figure as HTML, PNG, SVG or PDF.

The file carries the citation of Scanpath Studio in its metadata — PNG text chunks, an SVG `<metadata>` element, the PDF's document properties, the HTML page's `<head>` — so a figure found later on its own still says how to cite it (cite prints it). Nothing is drawn.

Parameters:

- **`fig`** (`Figure`) – The figure.
- **`path`** (`str | Path`) – The file to write: .html (interactive), or .png, .svg or .pdf (static, through Kaleido; see the export FAQ for its setup). Use .publication.json for an editable recipe or .publication.html for the offline figure editor.
- **`scale`** (`float`, default: `2` ) – The static image's scale factor.
- **`width`** (`int | None`, default: `None` ) – The image width in px, overriding the figure's own. Ignored for .html.
- **`height`** (`int | None`, default: `None` ) – The image height in px, likewise.
- **`width_mm`** (`float | None`, default: `None` ) – A PNG's print width in mm, as the app's Export → Current figure sets it: 180 mm at 600 dpi is a 4,252 px wide PNG, its height following the figure's aspect, with the dpi written into the file. It replaces scale.
- **`width_in`** (`float | None`, default: `None` ) – The same in inches.
- **`dpi`** (`int | None`, default: `None` ) – The resolution for width_mm / width_in. Default 300.
- **`proof_width_mm`** (`float | None`, default: `None` ) – Total manuscript width of a split comparison SVG, as in save_panel_proof.
- **`compact_png`** (`bool`, default: `False` ) – Compress the PNG losslessly, as the app's Export bundle does under Smaller PNG files: the same pixels and metadata in a smaller file, for a little more time. Only for .png.

Returns:

- `Path` – The path written.

### Publication figures

Pass the Plotly figure you want to prepare. A `.json` file reopens in the app and an `.html` file opens an offline editor. Other supported extensions render the artwork.

```
recipe = sps.publication_figure(
    scanpath,
    name="Figure 2",
)
sps.save_publication(recipe, "figure-2.json")
sps.save_publication(recipe, "figure-2.svg")
```

### publication_figure

```
publication_figure(
    figures, *, name="Untitled figure", width_mm=170, layout="stack"
)
```

Prepare one Plotly figure to edit and export.

Use the returned recipe with save_publication or open its JSON in Prepare figure. The recipe includes the plotted data and embedded images.

### save_publication

```
save_publication(recipe, path)
```

Save an editable publication project or its physical-size SVG, PDF, PNG, TIFF or MP4.

### save_panel_proof

```
save_panel_proof(fig, path, *, width_mm)
```

Save a split comparison as an SVG with its manuscript width in millimetres.

Both readings must have matching screen dimensions. The panel order, letters, shared scales, legends and relative size of the stimulus come from `compare_scanpaths`.

### save_figure_layers

```
save_figure_layers(
    fig,
    directory,
    *,
    fmt="svg",
    scale=2,
    width=None,
    height=None,
    width_mm=None,
    width_in=None,
    dpi=None,
    compact_png=False,
)
```

Save a scanpath figure as one file per layer, for editing.

Each *visible* layer (stimulus image, heatmap, word boxes, saccades, fixations, raw gaze, labels, frame) is the full figure with only that layer's elements, on a transparent background, at the same size and axis ranges. The files line up when stacked in Illustrator or Inkscape. The app's Export bundle writes the same files under *Layers as separate files*. A successful revision replaces this format's previous exported layers. An inventory in the directory identifies the owned files.

Parameters:

- **`fig`** (`Figure`) – A scanpath figure.
- **`directory`** (`str | Path`) – The folder to write <layer>.<fmt> into.
- **`fmt`** (`str`, default: `'svg'` ) – Any save_figure extension without the dot. svg and pdf are vector and the best to edit; png and html work too.
- **`scale`** (`float`, default: `2` ) – Passed to save_figure.
- **`width`** (`int | None`, default: `None` ) – Passed to save_figure.
- **`height`** (`int | None`, default: `None` ) – Passed to save_figure.
- **`width_mm`** (`float | None`, default: `None` ) – PNG print width in millimetres.
- **`width_in`** (`float | None`, default: `None` ) – PNG print width in inches.
- **`dpi`** (`int | None`, default: `None` ) – Resolution for the print width, shared by every layer.
- **`compact_png`** (`bool`, default: `False` ) – Compress each PNG layer losslessly, as save_figure does. Only for png.

Returns:

- `dict[str, Path]` – {layer: Path} for each file written.

## Recovery cache

A local app keeps the datasets you add, so they are there the next time it starts. `add_dataset` adds one from a script: prepare the tables in Python, add them, then run `scanpath-studio` and the app opens on them. `app_link` writes a link that opens the app on one of them, at a reading, with the figure you describe in `plot_scanpath`'s options. `remove_dataset` takes one off the list again.

```
sps.add_dataset(
    "Pilot 3",
    words="pilot3/ia_report.csv",
    fixations="pilot3/fixation_report.csv",
    canvas_size=(1920, 1080),
)
url = sps.app_link("Pilot 3", "p07", "t12", show_heatmap=True)
```

### add_dataset

```
add_dataset(
    name,
    words=None,
    fixations=None,
    *,
    raw_gaze=None,
    word_schema=None,
    fix_schema=None,
    raw_gaze_schema=None,
    trial_parts_manifest=None,
    keep_columns=None,
    canvas_size=None,
    setup=None,
    description=None,
    select=True,
    replace=False,
)
```

Add a dataset to the app's dataset list from a script.

The tables load as load_scanpath_data and load_raw_gaze load them, and the dataset is saved where a local app keeps the datasets added with ➕ **Add dataset** (the recovery cache, see cache_status). Start the app with `scanpath-studio` and it is in the list, opened unless `select=False`. An app already open shows it once its browser tab is reloaded. The same as `scanpath-studio add`.

It works for a local app only: the app on this computer, the desktop app, or a `scanpath-studio run` on this machine. A hosted app keeps no saved datasets.

Parameters:

- **`name`** (`str`) – The name the dataset list shows. A built-in source's name is refused.
- **`words`** (`TablesLike | None`, default: `None` ) – The Words table, in any form load_scanpath_data takes.
- **`fixations`** (`TablesLike | None`, default: `None` ) – The Fixations table, in the same forms.
- **`raw_gaze`** (`TablesLike | None`, default: `None` ) – The Raw gaze table, in the same forms. Any one of the three tables is enough.
- **`word_schema`** (`dict | None`, default: `None` ) – The Words table's column mapping, replacing auto-detection, as load_scanpath_data takes it. The app shows it as the dataset's mapping, and ✏️ Edit dataset starts from it.
- **`fix_schema`** (`dict | None`, default: `None` ) – The same for the Fixations table.
- **`raw_gaze_schema`** (`dict | None`, default: `None` ) – The same for the Raw gaze table, as load_raw_gaze takes it.
- **`trial_parts_manifest`** (`dict | None`, default: `None` ) – As load_scanpath_data takes it.
- **`keep_columns`** (`Iterable[str] | None`, default: `None` ) – As load_scanpath_data takes it.
- **`canvas_size`** (`tuple[int, int] | None`, default: `None` ) – The recording's screen, (width, height) px. Without it, the screen a table records is used, else one estimated from the extent of the data, as ➕ Add dataset suggests it. With replace, leaving out both this and setup keeps the saved dataset's setup.
- **`setup`** (`SetupSnapshot | None`, default: `None` ) – The full recording setup, an experimental_setup.SetupSnapshot (screen, monitor width, text size), in place of canvas_size.
- **`description`** (`str | None`, default: `None` ) – The sentence the 🗂️ Data page shows under its name.
- **`select`** (`bool`, default: `True` ) – Open the app on this dataset next time it starts.
- **`replace`** (`bool`, default: `False` ) – Replace the tables of the saved dataset with this name, keeping its annotations, metadata tables, share links, and its description and recording setup unless new ones are given. Without it, a name already saved is an error.

Returns:

- `str` – The name the dataset was saved under.

Raises:

- `ValueError` – No table was given, a table can't be loaded (as load_scanpath_data raises), the name is empty, too long or a built-in source's, or the saved work can't be read or was written by another version. Nothing is saved then.
- `StoredDatasetExistsError` – A dataset with this name is already saved and replace is off. A ValueError.
- `TypeError` – setup is not a SetupSnapshot.
- `RuntimeError` – Saving is turned off (SCANPATH_STUDIO_PERSIST=0).

Examples:

```
sps.add_dataset(
    "Pilot 3",
    words="pilot3/ia_report.csv",
    fixations="pilot3/fixation_report.csv",
    canvas_size=(1920, 1080),
)
```

Then run `scanpath-studio` and the app opens on *Pilot 3*. Reload a tab that is already open right away: changes made in it after the dataset was added are not saved, as when two tabs change the same saved work.

### app_link

```
app_link(
    dataset,
    participant=None,
    trial=None,
    *,
    screen=None,
    port=8501,
    animate=False,
    illustration=False,
    **figure_options,
)
```

A link that opens the local app on a dataset, a reading and a figure.

The link names the dataset as the app's dataset list shows it, the reading by its participant and trial IDs, and the figure by the options plot_scanpath takes, written as 🔗 **Share → Link** writes the same view. Open it in a browser while the app runs on this computer (`scanpath-studio` serves it at `localhost:8501`), or let `scanpath-studio open` start the app and open it. The dataset is one added in the app or with add_dataset. The same as `scanpath-studio open --print`.

For a dataset saved on this computer the link also carries its share ID and a digest of its tables, as Share's does, so the app checks it is the same data; its tables are read to compute it. Settings the link leaves out keep the values the app has. A link whose dataset the app doesn't have opens nothing from it, and says which dataset is missing.

Parameters:

- **`dataset`** (`str`) – The dataset's name in the app's dataset list, ignoring case for one saved on this computer.
- **`participant`** (`str | None`, default: `None` ) – The participant ID. Without it, a trial ID that only one participant has still opens that reading.
- **`trial`** (`str | None`, default: `None` ) – The trial ID. Without it, the app opens the participant's first trial, or the reading it last showed.
- **`screen`** (`str | None`, default: `None` ) – The screen ID of a trial recorded over several screens.
- **`port`** (`int`, default: `8501` ) – The port the app listens on.
- **`animate`** (`bool`, default: `False` ) – Open the replay instead of the static figure.
- **`illustration`** (`bool`, default: `False` ) – The Illustration design, as plot_scanpath takes it; an option given beside it wins.
- **`**figure_options`** (`Any`, default: `{}` ) – Figure options, as plot_scanpath takes them, with its fix_index_range and illustration_label, plus palette and the replay's anim_grid_step_ms, anim_max_frames, playback_speed and autoplay. None leaves the app's own value, except where it is a choice of its own (heatmap_metric counts fixations, fixation_flags turns them off). A link carries no file, so background_image and its size and origin are refused (show_stimulus_image=True draws the dataset's own pages), and no title or caption, which the app writes from its own patterns.

Returns:

- `str` – The link, http://localhost:<port>/?dataset=….

Raises:

- `TypeError` – An option a link can't carry, or no figure option at all.
- `ValueError` – An empty dataset name, a screen without a trial, a port outside 1–65535, or a value the app would ignore or clamp.

Examples:

```
sps.add_dataset("Pilot 3", words="ia.csv", fixations="fixations.csv")
url = sps.app_link("Pilot 3", "p07", "t12", show_heatmap=True)
import webbrowser; webbrowser.open(url)
```

### remove_dataset

```
remove_dataset(name, *, missing_ok=False)
```

Remove a dataset from the app's dataset list from a script.

The counterpart of add_dataset, and the same as the dataset's **Remove** on the 🗂️ **Data** page: its tables go, with its annotations, metadata tables, description and share ID. Any dataset you added counts, in the app or from a script; the built-in and public datasets can't be removed. When the app last had it open, it next opens on its default dataset. Reload a tab that is already open right away: changes made in it after the removal are not saved. The same as `scanpath-studio remove`.

Parameters:

- **`name`** (`str`) – The name the dataset list shows, ignoring case.
- **`missing_ok`** (`bool`, default: `False` ) – Return False when no dataset has the name, instead of raising.

Returns:

- `bool` – Whether a dataset was removed.

Raises:

- `StoredDatasetNotFoundError` – No saved dataset has this name, and missing_ok is off. A LookupError.
- `ValueError` – The saved work can't be read or was written by another version. Nothing is removed then.
- `RuntimeError` – Saving is turned off (SCANPATH_STUDIO_PERSIST=0).

Examples:

```
sps.remove_dataset("Pilot 3")
```

### cache_status

```
cache_status()
```

Describe the recovery cache a local run keeps, without launching the app.

A local or desktop app stores completed uploaded datasets, column mappings, view settings, saved designs, metadata tables and annotations under your cache folder, so a refresh or a restart resumes where it left off. A hosted deployment, such as the online demo, keeps none. The same information is on the app's **Data Management** page under *Saved work*, and in `scanpath-studio cache`.

| Key                                              | What it holds                                                                                                                                |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `enabled`, `directory`                           | Whether caching is on, and where                                                                                                             |
| `exists`, `readable`                             | Whether its manifest is there and can be read                                                                                                |
| `datasets`                                       | Each stored dataset's name, per-frame row counts and size in bytes                                                                           |
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

Return version and installation details without a network request.

The same is in the app's Help → About & citation, and in `scanpath-studio version`.

| Field                 | What it holds                                                                                                                                                                                                                                       |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `version`             | `scanpath_studio.__version__`: the release itself (`"0.35.0"`), or between releases a PEP 440 version that sorts after it. `"0.35.0.post3+g8f18219"` is three commits after v0.35.0, at commit `8f18219`; it ends `.dirty` with uncommitted changes |
| `release`             | The release it descends from (`scanpath_studio.__release__`)                                                                                                                                                                                        |
| `channel`, `docs_url` | `"stable"` or `"dev"` and the matching documentation URL                                                                                                                                                                                            |
| `distance`            | The commits since, `None` when unknown                                                                                                                                                                                                              |
| `commit`, `dirty`     | The commit, and whether there were uncommitted changes                                                                                                                                                                                              |
| `source`              | How it was worked out: `"checkout"` (`git describe`), `"stamp"` (a desktop bundle's build stamp), `"vcs"` (a `pip install git+…`) or `"release"`                                                                                                    |

Returns:

- `BuildInfo` – The build, as a BuildInfo. Its describe() says it in a sentence.

### check_for_updates

```
check_for_updates(timeout=5.0)
```

Check GitHub for a newer release.

The one call here that uses the network, and only when made. It reads the latest release from `api.github.com` (drafts and pre-releases excluded), compares it with version_info, and never raises. The same check is available under Help → About & citation → App details → *Check for updates* in a local install or the desktop app, and from `scanpath-studio version --check`.

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

## Citation

### cite

```
cite(format='bibtex', corpus=None)
```

Return a citation for Scanpath Studio and, optionally, a public corpus.

The same entries as the app's Help → About & citation and *Cite* buttons, and `scanpath-studio cite`. Every figure, replay and page `save_figure` writes also carries the citation in its file metadata.

```
print(sps.cite())                       # BibTeX
print(sps.cite("apa", corpus="onestop"))  # APA, plus OneStop's reference
```

Parameters:

- **`format`** (`str`, default: `'bibtex'` ) – "bibtex", "apa", "ris" (Zotero, Mendeley, EndNote), "csl-json", or "credit" — one sentence to paste into a figure caption.
- **`corpus`** (`str | None`, default: `None` ) – "onestop" or "potec" to add that corpus's citation after the software's; None for the software alone.

Returns:

- `str` – The citation as text (APA without Markdown).

Raises:

- `ValueError` – For an unknown format or corpus.

## See also

- [Export and share](https://lacclab.github.io/scanpath-studio/dev/guides/exporting/index.md): the [batch pattern](https://lacclab.github.io/scanpath-studio/dev/guides/exporting/#batch-pattern) for many trials, and [GIF/MP4 replays](https://lacclab.github.io/scanpath-studio/dev/guides/exporting/#replays-as-gif-or-mp4).
- [CLI reference](https://lacclab.github.io/scanpath-studio/dev/cli/index.md): the same figures from the command line.
