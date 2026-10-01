# Loading public and own data

## Choose a source

Open the dataset picker above the plot, or the **Data** page.

- **Bundled Demo** — a small OneStop sample, for learning the app.
- **Synthetic sample** — a hand-made six-word trial.
- **Public corpus** — OneStop or PoTeC; the app downloads it when asked.
- **+ → Import files** — your own tables.
- **+ → Create manually** — type a text and place fixations on it by hand: click to add, drag to move, or edit the table.

## What your data needs

| Table                         | Minimum                                   |
| ----------------------------- | ----------------------------------------- |
| words / interest areas (AOIs) | trial ID, word ID, text, and the word box |
| fixations                     | trial ID, duration, and x/y or a word ID  |

Either table alone also works. Participant and text IDs, timestamps, raw gaze, conditions and reading measures are optional and unlock more features.

Files can be CSV, TSV, TXT, Parquet, Feather, Excel, or a `.zip` of any of these. See [Data format](https://lacclab.github.io/scanpath-studio/data-format/index.md) for every field.

## Import files

The import screen has three parts:

1. **Name** — and an optional one-line description.
1. **Tables** — upload fixations, AOIs and, optionally, raw gaze. The app guesses which column is which; check its guesses. The trial count under each ID picker is a quick sanity check. Reading measures from an EyeLink interest-area report (`IA_DWELL_TIME`, …) are picked up automatically, and are what Corpus Analysis shows. Optional tables, one row per reader, trial or text, add fields to filter and group by.
1. **Recording setup** — the screen the data was recorded on (below).

Then click **Add dataset**. Anything the app cannot use is listed above the button before you confirm.

### Recording setup

Describe the screen the data was **recorded** on, not the one you are using now. A wrong resolution rescales every figure, so nothing is preselected. For each value, say how you know it: measured, estimated from your data, or a default. That answer travels with the dataset, so others can tell measured values from assumed ones.

## The Data page

**Data** lists every dataset with its counts; click a row to open it. **Edit dataset** changes a dataset's name, column mapping and recording setup, or adds a table it is missing. Changes apply when you click **Save changes**; **Cancel** discards them. The page also holds each dataset's tables and its annotations, and at the foot, what is saved on this computer.
