# Data format

Scanpath Studio reads **CSV, TSV, TXT, Parquet, Feather or Excel** files, or a
`.zip` of them. Columns are detected from common EyeLink, Gazepoint, Tobii, SMI
and Pupil Labs names, and you can correct any guess when you add the dataset.

## Tables

| Table | One row per | Needs |
|-------|-------------|-------|
| **Fixations** (e.g. EyeLink's Fixation Report) | fixation | trial ID, duration (ms), and x/y or a word ID |
| **Words (interest areas)** (e.g. EyeLink's Interest Area Report) | word | trial ID, word ID, and its box: `IA_LEFT/RIGHT/TOP/BOTTOM` or `x/y/width/height` |
| **Raw gaze** | gaze sample | participant ID, trial ID, x, y |
| **Participants** *(optional)* | participant | participant ID, plus any columns you like |
| **Trials** *(optional)* | trial | trial ID, plus any columns you like |
| **Texts** *(optional)* | text | text ID, plus any columns you like |

A dataset needs at least one of the first three. Otherwise, participant ID,
text ID and timestamps are optional.

**Units.** Times in milliseconds; a header naming another unit (`[s]`, `[μs]`)
is converted. Positions in **pixels**: screen fractions are not converted.

## Metadata tables

The participants, trials and texts tables work like columns of your data: they
filter trials, appear as chips, sort the trial list, group readers in Corpus
Analysis, and are exported beside the data. They are never copied onto the
fixations, and a participant missing from the table stays in the data.

## Multipart logical trials

A trial shown over several screens maps a `screen_id` column (and optionally a
`screen_index` for their order) in both tables. Each screen keeps its own
coordinates, and the app shows one screen at a time.

## Reading measures

Per-word reading measures (TFD, FFD, first-pass time, regression path…) are
columns of the **Words** table. An EyeLink interest-area report maps them from
its `IA_*` names. Corpus Analysis shows only the measures you mapped and
computes none of its own.
