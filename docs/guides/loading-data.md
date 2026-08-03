# Loading public and own data

Scanpath Studio can use the bundled sample, supported public corpora, or tables
from your own experiment.

## Choose a source

- **Bundled demo:** immediate, small, and suitable for learning the interface.
- **Public corpus:** choose the corpus and local data directory; download when
  prompted.
- **➕ Add data:** upload or select your own files and map their columns.

Run locally or use the desktop app for sensitive participant data.

## What your data needs

The default workflow uses two tables:

| Table | Minimum useful fields |
| --- | --- |
| words / interest areas | trial ID, word ID, text, and either box edges or x/y/width/height |
| fixations | trial ID, duration, and x/y or an assigned word ID |

Participant ID, text ID, fixation timestamps, raw gaze, conditions, questions,
and precomputed reading measures are optional but enable more features. Accepted
files are CSV, TSV, Parquet, and Feather. See [Data format](../data-format.md)
for canonical fields.

## Use the setup wizard

1. Enter a dataset name, monitor resolution, and stimulus font details.
2. Add the word/IA and fixation files; several files per table are allowed.
3. Check the automatically proposed participant, trial, text, geometry, and
   timing columns.
4. Build a composite ID when one column is not unique enough.
5. Keep any extra condition or analysis fields you will need later.
6. Select **Add dataset**.

The distinct-value counts shown beside ID mappings are the fastest sanity check.
After loading, open **Data Inspection** and confirm that both tables share the
expected trials and coordinate range.

## Derived and preserved fields

When x/y fixations and word boxes are available, the app can assign fixations to
words and compute standard per-word reading measures. Recognized precomputed
EyeLink IA measures take precedence. Fields not mapped or explicitly retained
may be dropped during normalization.

## Reuse the setup

Download the setup JSON from the wizard and restore it for the next export from
the same pipeline. If a mapping was wrong, edit it under
**Data Inspection → Column mapping** or reload the files when a required column
was not retained.
