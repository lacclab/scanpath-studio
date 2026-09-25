# Loading public and own data

Scanpath Studio can use the bundled sample, supported public corpora, or tables from your own experiment.

## Choose a source

- **Bundled Demo:** immediate, small, and suitable for learning the interface.
- **Public corpus:** choose the corpus and local data directory; download when prompted.
- **➕ Add dataset:** upload or select your own files and map their columns (🗂️ **Data → 📂 Available datasets**).
- **✏️ Author a scanpath:** sketch a trial from text, with no files at all.

## What your data needs

The default workflow uses two tables:

| Table                  | Minimum useful fields                                             |
| ---------------------- | ----------------------------------------------------------------- |
| words / interest areas | trial ID, word ID, text, and either box edges or x/y/width/height |
| fixations              | trial ID, duration, and x/y or an assigned word ID                |

Participant ID, text ID, fixation timestamps, raw gaze, conditions, questions, and precomputed reading measures are optional but enable more features. Accepted files are CSV, TSV and tab-separated TXT, Parquet, Feather, Excel (`.xlsx` and the older `.xls`), and a `.zip` wrapping any of them. A text file's delimiter (comma, semicolon, tab or pipe) is read off its header line, a file that is not UTF-8 is read as Windows text, and an `.xls` that is really tab-separated text — EyeLink Data Viewer's "Excel" export — is read as text. See [Data format](https://lacclab.github.io/scanpath-studio/data-format/index.md) for canonical fields and units.

## Use the setup wizard

The wizard is **three numbered parts** on one screen, with **⬇️ Save setup** and **✅ Add dataset** at the foot.

**1. Dataset name** — what the dataset is called in 📂 **Available datasets**.

**2. Upload data tables.** One row per table — **Fixations**, **AOIs** (the words / interest areas) and **Raw gaze** — with the table's uploader on the left and its column mapping beside it; upload at least one. Fixations and AOIs take several files each if your export is split (one per participant, say); raw gaze takes one. Each row's pickers are pre-filled from the column names, and the tint says which were auto-detected: detection matches *names*, so this is where you confirm it picked the right columns.

- The first line of each row is its **identity** — trial, screen, reader, text, word and the table's own id. Pick several columns to build a composite trial ID when one is not unique enough; the trial count under each picker is the fastest sanity check, and a warning appears when the two tables share no trial — or share trials but no reader.
- The second line is the table's own **fields**: x/y, timestamp and duration for fixations; the word box (edges or origin + size) and line index for the AOI table, plus whether it has one row per **character** rather than per word.
- Under each table, **Extra fields to keep** lists every column the mapping does not use — recognised measures and conditions come pre-ticked — and whatever you keep is there later to filter, sort or colour by; the rest is dropped at normalization.
- **Derive columns from the filename** sits at the top once a table is in, for ids that live only in the file name.
- Below the three tables, under **Metadata**, are three optional keyed tables: **one row per reader** (native language, age, comprehension score), **one row per trial** (list name, presentation order) and **one row per text** — see [Participant metadata](https://lacclab.github.io/scanpath-studio/data-format/#participant-metadata) and [Trial metadata](https://lacclab.github.io/scanpath-studio/data-format/#trial-metadata). The same attach-and-report UI is on 🗂️ **Data → ✏️ Edit dataset** for datasets that do not come through this wizard.

↩️ **Restore a saved setup** is a popover beside this part's title.

**3. Recording setup** — the screen the data was recorded on; see below.

The wizard objects only once you press **✅ Add dataset**, and then about everything at once rather than one field at a time: a required field left empty turns red in place. Rows it cannot use are named directly above the button — cells in a mapped number column that don't parse, rows with no trial or reader id, positions that are screen fractions rather than pixels — together with what the load does with them.

📂 **Available datasets** lists the same headline fields shown in the active dataset summary — participants, texts, trials, fixations, words, gaze points and multipart screens; click a name to open it, and the open row is tinted. Rename or remove a source from its table row, or open ✏️ **Edit dataset** to change how it was mapped — the same field grid the wizard draws, and, for a dataset added with only one of the two main tables, an uploader for the other one. Adding the missing half there normalizes it and joins it to what is already loaded, so a fixations-only dataset can gain its word boxes (or an AOI-only one its fixations) without being added again.

For a public corpus you haven't opened, the **Counts** column shows its *Published* figures; once loaded it shows *Loaded* ones. ℹ️ **About** names the source of each published figure.

### The recording setup asks how you know

**Recording setup** describes the screen the data was **recorded** on — not the screen you are reading this on. Nothing is preselected: a wrong monitor size silently rescales every figure. Each of the three groups — *Screen*, *Physical size & viewing distance*, and *Reading text size* — asks how you know the value, with choices of its own:

| Group                            | Choice                                                                                                                                                                                             | Recorded as |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| Screen                           | *I know the resolution*                                                                                                                                                                            | `measured`  |
|                                  | *Estimate from my data* — derived from the extent of your word boxes and fixations; always available, always succeeds, and reported as a **lower bound**, since text rarely fills the whole screen | `estimated` |
|                                  | *Use a common default (2560×1440)*                                                                                                                                                                 | `assumed`   |
| Physical size & viewing distance | *I know them*                                                                                                                                                                                      | `measured`  |
|                                  | *Use typical lab values (597 mm / 800 mm)*                                                                                                                                                         | `assumed`   |
|                                  | *Skip — I don't need visual-angle units*                                                                                                                                                           | `skipped`   |
| Reading text size                | *Scale to the word boxes* or *I know the stimulus font*                                                                                                                                            | `measured`  |
|                                  | *Use a default (16 px)*                                                                                                                                                                            | `assumed`   |

**Add dataset** stays disabled until all three are answered. Values derived from a skipped group (pixels per degree, point-to-pixel conversion) are hidden rather than computed from a default.

The answer travels with the dataset — on share links, in the saved-setup JSON and in a bulk export's `plot_config.json` — so readers can tell measured values from assumed ones.

Answers are remembered across datasets in a session as **pre-filled values with the choice reset**: quick for a second export from the same lab, while still making you assert that the setup applies to this dataset too.

## Reuse the setup

✏️ **Edit dataset** can offer only the columns kept at import; to map a dropped column, add the files again.
