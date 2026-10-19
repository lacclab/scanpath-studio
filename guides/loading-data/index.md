# Data Management

Load your own data, open a public dataset, or try the bundled demo.

## Choose a dataset

Pick a dataset in **Select dataset** above the plot, or in the dataset list on the **Data Management** page:

- **Bundled demo**: 24 trials from OneStop, with two participants and 12 texts.
- **Hand-drawn sample**: a scanpath drawn by hand over a short English text, which you can edit.
- Public datasets: OneStop and PoTeC. In the desktop app or a pip install, each downloads the first time you open it.
- **+** → **Import files**: your own tables.
- **+** → **Draw a scanpath**: write a text and place its fixations by hand.

### OneStop

The bundled demo comes from [OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) (Berzak et al., 2025), an English corpus with 360 participants. The full corpus is available as four public datasets: **OneStop · Ordinary reading**, **OneStop · Information seeking**, **OneStop · Repeated reading** and **OneStop · Information seeking (repeated)**. Each downloads once from [OSF](https://osf.io/2prdq/).

## What your data needs

A dataset needs at least one of the first three tables below. Add the others as you need them.

| Table                  | Contents                                                       |
| ---------------------- | -------------------------------------------------------------- |
| Fixations              | One row per fixation: trial ID, duration, and x/y or a word ID |
| Words (interest areas) | One row per word: trial ID, word ID and word box               |
| Raw gaze               | One row per gaze sample: trial ID, x and y                     |
| Participants           | One row per participant, with metadata                         |
| Trials                 | One row per trial, with metadata                               |
| Texts                  | One row per text, with metadata                                |

The app detects columns from common eye-tracker exports. Check and correct the mapping when you import. To keep condition labels and other columns, pick them under **Extra fields to keep**. You can filter, sort and group trials by any metadata field.

### Files and units

- CSV, TSV, TXT, Parquet, Feather, Excel, or a ZIP of these files
- Positions in pixels
- Times in milliseconds. A time column whose header names its unit, such as `[s]`, `[μs]` or `[ns]`, is converted.
- Word boxes as `x/y/width/height` or EyeLink's `IA_LEFT/RIGHT/TOP/BOTTOM`

### Trials over several screens

Map the **Screen ID** field in your tables. A column named `screen_index` sets the order of the screens. Without one, the screens are ordered by where they first appear. The app draws one screen at a time.

### Reading measures

Corpus Analysis uses the per-word reading measures in your Words table, such as first fixation duration or total fixation duration. Map them when you import. EyeLink's `IA_*` columns are detected.

## Add your own data

1. Choose **+** → **Import files** and name the dataset.
1. Upload your tables and check the column mapping.
1. Under **Recording setup**, enter the **Screen**, **Monitor width** and **Text size** if you know them.
1. Optionally, in the desktop app or a local install, attach the stimulus images from a folder.
1. Click **Add dataset**.

\[!\[

\](../../assets/workflows/add-your-data_poster.webp)\](../../assets/workflows/add-your-data.mp4)

## Load and inspect in code

Load the same files in a script. The loaders detect column names the same way the app does.

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

For raw gaze, metadata and explicit column mappings, see the [loaders](https://lacclab.github.io/scanpath-studio/api/#load-your-data) and [CLI input options](https://lacclab.github.io/scanpath-studio/cli/#flags-input).

## Manage datasets

Click a dataset in the dataset list to open it. Below the list, **What's in *‹dataset›*** shows its tables, annotations and **Data checks**.

Use **Edit dataset** to change its name, column mapping, recording setup or metadata, then click **Save changes**. **Download setup file** saves the mapping and recording setup, so you can apply them to similar data.

The editor offers only the columns kept when the dataset was added. To use a column you left out, add the files again and keep it under **Extra fields to keep**.
