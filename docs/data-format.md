# Data format

Scanpath Studio reads up to three tables — **words / areas-of-interest**,
**fixations**, and (optionally) **raw gaze** — as **CSV, TSV, Parquet, or
Feather**. Columns are auto-detected from common EyeLink, Gazepoint, and
snake-case conventions; the app's **Column mapping** panel (and the
`word_schema` / `fix_schema` arguments of
[`load_scanpath_data`](api.md#scanpath_studio.api.load_scanpath_data)) override
any guess.

## Tables

| Table | Holds | Key columns (auto-detected) |
|-------|-------|-----------------------------|
| **Words / IA** | one row per word / interest area, with its on-screen box | participant id, trial id, word id, word text, and the box as **edges** (`IA_LEFT/RIGHT/TOP/BOTTOM`) **or** origin+size (`x/y/width/height`) |
| **Fixations** | one row per fixation | participant id, trial id, duration (ms); optionally x/y, timestamp, fixation id, word/IA id |
| **Raw gaze** *(optional)* | one row per gaze sample | participant id, trial id, x, y, timestamp |

Either main table may be omitted for single-report datasets — the missing layer
is simply skipped. A words-only table still draws a heatmap from its
pre-aggregated reading measures.

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

## Reading measures

If your data carries only raw fixations, the app computes the canonical per-word
measures itself — **FFD**, **FPRT** (gaze duration), **RPD** (go-past),
**TFD** (dwell), plus skips and regressions, following Rayner (1998) and
Inhoff & Radach (1998). Pre-aggregated EyeLink `IA_*` columns, when present, take
precedence. Areas of interest come **directly from your word boxes** — they are
not computed; only the fixation→word assignment is derived (bounding-box
containment with a small nearest-word fallback).

## Setup wizard & saved setups

Uploading through the app's **➕ Add data** wizard walks you through naming the
dataset, the experimental setup (monitor resolution keeps everything
true-to-scale), upload, and column mapping. You can **download a setup** (the
column mapping as JSON) and **restore** it later on similar data to skip the
manual mapping. Finished uploads become first-class, switchable data sources.
