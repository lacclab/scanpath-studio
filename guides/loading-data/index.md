# Data management

Load your own data, open a public corpus, or try the bundled sample.

## Choose a dataset

Use the dataset picker or the Data Management page:

- Bundled demo: a small OneStop sample
- Hand-drawn sample: a six-word trial
- Public corpora: OneStop and PoTeC, downloaded on your computer
- - → Import files: your own tables
- - → Create manually: type text and place fixations

### OneStop

The demo comes from [OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) (Berzak et al., 2025), an English corpus with 360 participants. The full corpus is available as four datasets: ordinary reading, information seeking, and their repeated-reading versions. Each downloads once from [OSF](https://osf.io/2prdq/).

## What your data needs

At least one of the first three tables below; add others as needed.

| Table                  | Contents                                                       |
| ---------------------- | -------------------------------------------------------------- |
| Fixations              | One row per fixation: trial ID, duration, and x/y or a word ID |
| Words (interest areas) | One row per word: trial ID, word ID and bounding box           |
| Raw gaze               | One row per sample: participant ID, trial ID, x and y          |
| Participants           | One row per participant, with metadata                         |
| Trials                 | One row per trial, with metadata                               |
| Texts                  | One row per text, with metadata                                |

Columns are detected from common eye-tracker exports; check and correct the mapping when importing. Keep condition labels and other columns with Extra fields to keep. Metadata fields are available for filtering, sorting and grouping.

### Files and units

- CSV, TSV, TXT, Parquet, Feather, Excel, or a ZIP of these files
- Positions in pixels
- Times in milliseconds; headers marked `[s]` or `[μs]` are converted
- Word boxes as `x/y/width/height` or EyeLink's `IA_LEFT/RIGHT/TOP/BOTTOM`

### Trials over several screens

Map `screen_id` in your tables, and `screen_index` for their order if needed. The app displays one screen at a time.

### Reading measures

Include per-word reading measures in the Words table, such as first fixation duration or total fixation duration. EyeLink's `IA_*` columns are detected. Corpus Analysis uses the measures you supply.

## Add your own data

1. Choose + → Import files and name the dataset.
1. Upload your tables and check the column mapping.
1. Enter the recording screen size and typography where known.
1. Optionally attach stimulus screenshots from a local folder.
1. Click Add dataset.

## Load and inspect in code

Load the same files in a script; column names are detected automatically.

Python and CLI

```
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")
print(sps.list_trials(words, fixations))
```

```
scanpath-studio render --words ia.csv --fixations fixations.csv --list-trials
scanpath-studio check --words ia.csv --fixations fixations.csv
```

For raw gaze, metadata and explicit column mappings, see the [loaders](https://lacclab.github.io/scanpath-studio/api/#load) and [CLI input options](https://lacclab.github.io/scanpath-studio/cli/#render).

## Manage datasets

Click a dataset row to open it. Inspect its tables, annotations and data checks below the list.

Use Edit dataset to change its name, column mapping, recording setup or metadata, then Save changes. Download setup file saves the mapping and recording setup for reuse.

Only imported columns are available in the editor. To use a column left out at import, add the files again.
