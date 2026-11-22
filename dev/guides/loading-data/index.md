# Data Management

Load your own data, open a public dataset, or try the bundled demo.

## Choose a dataset

Pick a dataset in **Select dataset** above the plot, or in the dataset list on the **Data Management** page:

- **Bundled demo**: 24 trials from OneStop, with two participants and 12 texts.
- **Hand-drawn sample**: a scanpath drawn by hand over a short English text, which you can edit.
- Public datasets: OneStop and PoTeC. In the desktop app or a pip install, each downloads the first time you open it.
- **+** → **Import files**: your own tables.
- **+** → **Draw a scanpath**: write a text and place its fixations by hand.

### Draw a scanpath

Choose **+ → Draw a scanpath**, then type your passage. In **Draw** mode, click the words in reading order. Click a word twice for two visits, or click the space between words for a fixation without a target. For a regular sequence, **Reset to one fixation per word** places a 220 ms fixation on each word.

Use **Select & move** to drag a marker. The **Fixation** list lets you select visits that land on top of one another. Change **Duration (ms)** and use **Play preview** to check the timing. The **Fixation table** also accepts keyboard edits. Leaving both coordinates empty places the fixation at the center of its target word.

**Save dataset** opens the figure. To revise it, go to **Data Management** and click **Edit** on its row. **Save changes** updates the drawing, and **Save as copy** keeps a separate version. For another computer, download the editable draft from **Share** and open it with **Load a saved draft** in the drawing editor.

### OneStop

The bundled demo comes from [OneStop Eye Movements](https://github.com/lacclab/OneStop-Eye-Movements) (Berzak et al., 2025), an English corpus with 360 participants. The full corpus is available as four public datasets: **OneStop · Ordinary reading**, **OneStop · Information seeking**, **OneStop · Repeated reading** and **OneStop · Information seeking (repeated)**. Each downloads once from [OSF](https://osf.io/2prdq/).

## What your data needs

Start with a Fixations, Words or Raw gaze table. You can add the other tables whenever you need them.

To try a right-to-left passage, import the bundled `sample_data/mixed_script_words.csv` and `sample_data/mixed_script_fixations.csv`. The two synthetic lines combine Hebrew, Arabic, English, digits and punctuation. Use an 800 × 250 px canvas to see the recorded layout. The tenth fixation revisits the Arabic word on the second line.

| Table                  | Contents                                                       |
| ---------------------- | -------------------------------------------------------------- |
| Fixations              | One row per fixation: trial ID, duration, and x/y or a word ID |
| Words (interest areas) | One row per word: trial ID, word ID and word box               |
| Raw gaze               | One row per gaze sample: trial ID, x and y                     |
| Participants           | One row per participant, with metadata                         |
| Trials                 | One row per trial, with metadata                               |
| Texts                  | One row per text, with metadata                                |

The app recognizes column names from common eye-tracker exports. Check the mapping when you import. To keep condition labels and other columns, pick them under **Extra fields to keep**. You can filter, sort and group trials by any metadata field.

### Files and units

- CSV, TSV, TXT, Parquet, Feather, Excel, or a ZIP of these files
- Positions in pixels
- Times in milliseconds. A time column whose header names its unit, such as `[s]`, `[μs]` or `[ns]`, is converted.
- Word boxes as `x/y/width/height` or EyeLink's `IA_LEFT/RIGHT/TOP/BOTTOM`
- Word IDs as numbers, or as text such as `w1`. Text IDs must match exactly in the Fixations and Words tables. With text IDs, the order of the rows in the Words table sets the word order.
- Several files for one table, such as one file per trial, are stacked into one table, with each file's name in a `source_file` column. When an ID is only in the file name, use **Derive columns from text** to extract it into a column you can map. When you click **Apply**, a derived column named like an ID, such as `participant`, `trial` or `stimulus`, fills that ID field if it is empty.
- Trial and Text IDs are matched exactly, so spell them the same way in both tables, including upper and lower case. The import screen says when they differ only in case.
- Words tables with one box per character, as in Chinese or Japanese: turn on **Merge character boxes into word boxes**. The import screen suggests it when a word's rows are at different positions.

### Trials over several screens

Map the **Screen ID** field in your tables. A column named `screen_index` sets the order of the screens. Without one, the screens are ordered by where they first appear, using the Fixations table if available. The app draws one screen at a time.

### Reading measures

Corpus Analysis uses the per-word reading measures in your Words table, such as first fixation duration or total fixation duration. Map them when you import. EyeLink's `IA_*` columns are detected.

## Add your own data

1. Choose **+** → **Import files** and name the dataset.
1. Upload your tables and check the column mapping.
1. Under **Recording setup**, enter the **Screen**, **Monitor width** and **Text size** if you know them.
1. Optionally, in the desktop app or a local install, attach the stimulus images from a folder.
1. Click **Add dataset**, then **Open in Scanpath view** to see its first trial. Later, **Open in Scanpath view** beside **Add dataset** on the Data page does the same for the selected dataset.

To import similar files again, click **Download setup file** before **Add dataset**. Next time, choose **Start from** → **A setup file** and upload your tables: the column mapping, derived columns, character-box merge and recording setup are filled in.

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

For raw gaze, metadata and explicit column mappings, see the [loaders](https://lacclab.github.io/scanpath-studio/dev/api/#load-your-data) and [CLI input options](https://lacclab.github.io/scanpath-studio/dev/cli/#flags-input).

## Manage datasets

Click a dataset in the dataset list to open it. Below the list, **What's in *‹dataset›*** shows its tables, annotations and **Data checks**. When a check flags more than half of a table, such as every duration read as 0 ms, the Scanpath view says so above the plot.

Use **Edit dataset** to change its name, column mapping, recording setup or metadata, then click **Save changes**. **Download setup file** saves the mapping, recording setup and character-box merge, so you can apply them to similar data.

The editor offers only the columns kept when the dataset was added. To use a column that isn't listed, remove the dataset and add it again from its files, mapping the column or keeping it under **Extra fields to keep**.

Under **Data checks**, **Compare with the experiment run sheet** accepts a CSV with `participant_id` and `trial_id`. Add `screen_id` to check an individual screen. Enter a reason in `planned_omission` for readings you intended to omit and leave it blank for the rest. The report distinguishes missing readings, unscheduled recordings, and readings with raw gaze alone. **Review affected readings** shows all the rows behind a finding, one reading at a time, while your trial filters stay in place.

Excel imports use the first worksheet and show its name. ID columns preserve literal labels such as `01` and `NA`. Leave a cell empty for a missing ID. On restoring a pilot setup, the wizard names files whose headers or time units differ from the saved mapping.

Under **Name → Dataset citation**, an upload can carry its title, authors or lab, version, DOI, and preferred credit. An unpublished study can supply just its preferred wording. Reopen **Edit dataset** to revise the credit. **Cite** and the export bundle include these references alongside the software citation.
