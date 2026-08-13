# Data format

Scanpath Studio reads up to three tables — **words / areas-of-interest**,
**fixations**, and (optionally) **raw gaze** — as **CSV, TSV, Parquet, or
Feather**. Columns are auto-detected from common EyeLink, Gazepoint, and
snake-case conventions; the app's **Column mapping** panel (and the
`word_schema` / `fix_schema` arguments of
[`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]) override
any guess.

## Tables

| Table | Holds | Key columns (auto-detected) |
|-------|-------|-----------------------------|
| **Words / IA** | one row per word / interest area, with its on-screen box | participant id, trial id, word id, word text, and the box as **edges** (`IA_LEFT/RIGHT/TOP/BOTTOM`) **or** origin+size (`x/y/width/height`) |
| **Fixations** | one row per fixation | participant id, trial id, duration (ms); optionally x/y, timestamp, fixation id, word/IA id |
| **Raw gaze** *(optional)* | one row per gaze sample | participant id, trial id, x, y, timestamp |
| **Participant metadata** *(optional)* | one row per reader | participant id, plus anything you know about them |

Either main table may be omitted for single-report datasets — the missing layer
is simply skipped. A words-only table still draws a heatmap from its
pre-aggregated reading measures.

## Participant metadata

Attach a table of **one row per reader** — native language, age, a
comprehension score, a group label. When you upload your own data it is step 5
of the setup wizard (*About your readers*); for the demo, a public corpus, or a
dataset you added earlier, the same panel is on the 🗂️ **Data** page under **👤
Participant metadata**. Its columns then behave like fields in the data: they
filter trials (*More → By reader*), show up as chips above the plot, sort the
trial picker, group cohorts in Corpus Analysis, appear in Data Inspection, and
travel with exports and saved sessions.

```csv
participant_id,native_language,age,comprehension
p01,Hebrew,24,0.83
p02,English,31,0.91
```

Three rules are worth knowing:

- **The table is never copied onto your fixations.** It stays its own table, and
  a reader attribute stays distinguishable from a per-fixation measurement — on
  the way in, in the exported bundle (`metadata/participants.csv`), and
  everywhere in between.
- **Nothing is guessed.** The join is reported before anything uses it: readers
  in your data with no row, rows describing readers you did not load, and
  duplicate rows. Duplicates that *disagree* are dropped and named rather than
  resolved by taking the first one, so the field reads as missing.
- **A missing reader is missing, not excluded.** Attaching a table that forgets
  someone never removes them from the pool.

Headless, it is a `--participant-metadata FILE` flag on `scanpath-studio render`
and [`load_participant_metadata()`](api.md) in the Python API.

## Flexible loading

The loader bends to fit real corpora:

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

A logical `(participant_id, trial_id)` may contain several ordered screens. Map
these optional fields in both words and fixations:

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
columns, pass a nested manifest to the Python API or CLI. Selectors are exact and
must cover every row in the declared parent:

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

Legacy data without screen identity keeps its original two-column trial key and
behavior.

## Reading measures

If your data carries only raw fixations, the app computes the canonical per-word
measures itself — **FFD**, **FPRT** (gaze duration), **RPD** (go-past),
**TFD** (dwell), initial landing position/distance, second-pass and
single-fixation duration, plus skips and regression counts, following Rayner (1998) and
Inhoff & Radach (1998). Pre-aggregated EyeLink `IA_*` columns, when present, take
precedence. Areas of interest come **directly from your word boxes** — they are
not computed; only the fixation→word assignment is derived (bounding-box
containment with a small nearest-word fallback).

## Optional preprocessing and derived tables

The **Preprocessing** panel is off by default. When disabled, it returns the
normalized fixation table unchanged. When enabled, it can soft-mark
blink-adjacent or short fixations as `excluded`, merge short-and-close
fixations while retaining `original_duration_ms`, and materialize run/pass
columns. Rows are never silently deleted; `excluded_reason` and the per-trial
Cleaning QA table preserve the provenance.

Sentence IDs are accepted from the dataset or inferred at sentence-final
punctuation. The derived family includes sentence measures, first-class
saccades (pixels and optional degrees of visual angle), trial/reader summaries,
and a character grid with letter-based landing/launch positions. Trial text is
also auto-tagged `right_to_left` for Hebrew/Arabic-majority content; an explicit
column takes precedence.

## Setup wizard & saved setups

Uploading through the app's **➕ Add data** wizard walks you through naming the
dataset, the experimental setup (monitor resolution keeps everything
true-to-scale), upload, and column mapping. You can **download a setup** (the
column mapping as JSON) and **restore** it later on similar data to skip the
manual mapping. Finished uploads become first-class, switchable data sources.
