# Data format

Scanpath Studio reads up to three tables — **words / areas-of-interest**,
**fixations**, and (optionally) **raw gaze** — as **CSV, TSV, TXT, Parquet,
Feather, or Excel**, or a `.zip` of any of them. Columns are auto-detected from
common EyeLink, Gazepoint, Tobii, SMI, Pupil Labs, and snake-case conventions;
the app's **Column
mapping** panel (and the
`word_schema` / `fix_schema` arguments of
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]) override
any guess.

## Tables

| Table | Holds | Key columns (auto-detected) |
|-------|-------|-----------------------------|
| **Words / IA** | one row per word / interest area, with its on-screen box | trial id, word id, and the box as **edges** (`IA_LEFT/RIGHT/TOP/BOTTOM`) **or** origin+size (`x/y/width/height`); optionally participant id and word text |
| **Fixations** | one row per fixation | trial id, duration (ms), and x/y or a word/IA id; optionally participant id, timestamp, fixation id |
| **Raw gaze** *(optional)* | one row per gaze sample | participant id, trial id, x, y, timestamp |
| **Participant metadata** *(optional)* | one row per reader | participant id, plus anything you know about them |
| **Trial metadata** *(optional)* | one row per trial | trial id, plus anything you know about that trial |
| **Text metadata** *(optional)* | one row per text | text id, plus anything you know about that text |

**Units.** Durations and timestamps are read in milliseconds. A column whose
header names another unit — `[s]`, `[μs]`, `[ns]`, as Tobii and Pupil Labs Neon
write — is converted, and so are the vendor columns documented in seconds
(Gazepoint `FPOGD` / `FPOGS`, Pupil Labs Core `start_timestamp`). Positions must
be **pixels**: screen fractions (Gazepoint `FPOGX` / `FPOGY`, Pupil Labs Core
`norm_pos_x` / `norm_pos_y`) are flagged with a warning but not converted, since
the load does not know the screen size — multiply them by the screen width and
height in pixels first.

Either main table may be omitted — the missing layer is skipped, and a
words-only table still draws a heatmap from its pre-aggregated reading measures.

## Participant metadata

Attach a table of **one row per reader** — native language, age, a
comprehension score, a group label. When you upload your own data it is one of
the **Metadata** uploaders in part 2 of the setup wizard; for the demo, a public
corpus, or a dataset you added earlier, the same uploader is on 🗂️ **Data → ✏️ Edit dataset**
under **Metadata → Participants**. Its columns then behave like fields in the
data: they filter trials (the filter funnel's *By reader* section), show up as
chips above the plot, sort the trial picker, group cohorts in Corpus Analysis,
appear in the dataset's inspection tables, and travel with exports and saved
sessions.

```csv
participant_id,native_language,age,comprehension
p01,Hebrew,24,0.83
p02,English,31,0.91
```

Three rules are worth knowing:

- **The table is never copied onto your fixations.** It stays its own table and
  is exported separately (`metadata/participants.csv`).
- **Nothing is guessed.** The join is reported before anything uses it: readers
  in your data with no row, rows describing readers you did not load, and
  duplicate rows. Duplicates that *disagree* are dropped and named rather than
  resolved by taking the first one, so the field reads as missing.
- **A missing reader is missing, not excluded.** Attaching a table that forgets
  someone never removes them from the pool.

Headless, it is a `--participant-metadata FILE` flag on `scanpath-studio render`
and [`load_participant_metadata()`](api.md) in the Python API.

## Trial metadata

The same idea one grain down: a table of **one row per trial** — a list
name, a presentation order, a per-trial comprehension score, whatever your
design recorded about the trial rather than about the reader. It attaches
beside the participant table — under **Metadata** in part 2 of the add-dataset
wizard, and on 🗂️ **Data → ✏️ Edit dataset** under **Metadata → Trials** for a
dataset that is already loaded — and its columns behave like fields in the data in the same
way: they filter trials, show up as chips above the plot, sort the trial picker,
appear in the inspection tables, and travel with exports
(`metadata/trials.csv`) and saved sessions.

```csv
trial_id,list_name,presentation_order,comprehension
t01,A,1,1
t02,A,2,0
```

**The key decides what a row means.** Keyed by trial id alone, a row describes
a *text*, and every reader's reading of it inherits that row — right for a design
where the trial id names the material. The app always keys the table this way:
its **Trial ID column** picker takes one column, or several to build the id the
way the data's own Trial ID mapping does. Keyed by reader **and** trial, a row
describes **one reading**, which is what you need as soon as the same reader
reads the same text twice — and that table attaches headlessly only, with
`--trial-metadata-reader-column` on the CLI or `participant_column=` in the
Python API.

Join reporting and duplicate handling are as for the participant table.

Headless, it is `--trial-metadata FILE` on `scanpath-studio render` and
[`load_trial_metadata()`](api.md) in the Python API.

## Text metadata

The third grain: a table of **one row per text** — a genre, a difficulty rating,
a stimulus-level comprehension score. It attaches beside the other two (under
**Metadata → Texts** in the wizard and on ✏️ **Edit dataset**), keyed by text id
alone — never by reader, since a text is a stimulus rather than something one
reader owns — and, like the trial table, the id may be built from several
columns. Its columns behave like fields in the data in the same way, travel with
exports (`metadata/texts.csv`) and saved sessions, and follow the same join
rules.

Headless, it is `--text-metadata FILE` on `scanpath-studio render` and
[`load_text_metadata()`](api.md) in the Python API.

## Flexible loading

- **Many files per table** — pass several paths or a glob; they're concatenated,
  each row tagged with its `source_file` (e.g. one file per participant or text).
- **Stimulus-level word boxes** — a words table with no participant column is
  broadcast across every participant found in the fixations.
- **AoI-only fixations** — fixations with a word/IA id but no x/y are placed at
  the matching word-box centers.
- **Composite trial ids** — when no single column identifies a trial, map *Trial
  ID* to several columns (e.g. participant + paragraph + repeated-reading) and a
  combined unique id is built on the fly.

## Multipart logical trials

A logical `(participant_id, trial_id)` may contain several ordered screens.
These optional columns are auto-detected by name in both tables (headlessly they
are also `word_schema` / `fix_schema` keys):

| Canonical field | Meaning |
| --- | --- |
| `screen_id` | Stable child id inside the logical trial. |
| `screen_index` | Positive, 1-based display order. If omitted, first appearance defines order. |
| `canvas_width`, `canvas_height` | Optional monitor/canvas pixels, constant within that screen. |
| `screen_timestamp_ms` | Optional fixation onset that resets within a screen. |
| `screen_fixation_id` | Optional fixation id that resets within a screen. |

`timestamp_ms`, `fixation_id`, and `order_in_trial` remain parent-global. The
screen-local clock/id are retained alongside them; neither overwrites the other.
Screen id and order must map one-to-one within a parent, and the words and
fixations reports must contain the same set of screens. These validations reject
orphan screens instead of silently joining the wrong coordinate spaces.

All geometry-dependent operations group by screen: fixation-to-word assignment,
saccades, passes, regressions, and word measures never cross a screen boundary.
The main view shows one screen with previous/next navigation; annotations can be
stored on the parent trial or the current screen. Bulk output uses deterministic
`screens/screen-001-<id>/` folders.

If source reports have arbitrary page markers instead of mappable screen
columns, pass a nested manifest (`trial_parts_manifest=` in
`load_scanpath_data`, `--trial-parts-manifest` on the CLI). Selectors are exact
and must cover every row in the declared parent:

```json
{
  "trials": [{
    "participant_id": "p1",
    "trial_id": "t1",
    "parts": [
      {
        "screen_id": "intro",
        "screen_index": 1,
        "canvas_width": 1920,
        "canvas_height": 1080,
        "words": {"page_code": "A"},
        "fixations": {"page_code": "A"}
      }
    ]
  }]
}
```

## Reading measures

Per-word measures missing from your data are computed from the fixations;
imported EyeLink `IA_*` columns take precedence. Definitions are in
[Computations & methodology](computations.md).
