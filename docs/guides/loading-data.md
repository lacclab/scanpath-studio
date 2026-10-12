# Loading public and own data

## Choose a source

Open the dataset picker above the plot, or the :material/database: **Data Management** page.

- **Bundled demo** — a small OneStop sample, for learning the app.
- **Synthetic sample** — a hand-made six-word trial.
- **Public corpus** — OneStop or PoTeC, downloaded when you ask, on your own
  computer only (see [OneStop](../onestop.md)).
- **+ → Import files** — your own tables.
- **+ → Create manually** — type a text and place fixations on it by hand:
  click to add, drag to move, or edit the table.

## What your data needs

| Table | Minimum |
| --- | --- |
| Words (interest areas) — e.g. EyeLink's Interest Area Report | trial ID, word ID, and the word box (the word text, to show it) |
| Fixations — e.g. EyeLink's Fixation Report | trial ID, duration, and x/y or a word ID |

Either table alone also works. Participant and text IDs, timestamps, raw gaze,
conditions and reading measures are optional and unlock more features.

Files can be CSV, TSV, TXT, Parquet, Feather, Excel, or a `.zip` of any of
these. A `.zip` holding both EyeLink reports (one folder per participant, say)
can go in both rows: each row reads only its own reports and says which it
left out. See [Data format](../data-format.md) for every field.

## Import files

The import screen has three parts, and a fourth when the app runs on your own
computer:

1. **Name & description** — the description is optional.
2. **Upload data tables** — start from scratch, or with **Start from** reuse a
   setup you already have: a dataset you added before (its column mapping, the
   fields it kept and its recording setup, copied without a file) or a setup
   file saved with **:material/download: Download setup file**. Everything stays editable, and
   **Undo** puts the screen back. Then upload Fixations, Words (interest areas) and,
   optionally, raw gaze — each row says what its table must map. The app
   guesses which column is which; check its guesses. The trial count under each
   ID picker is a quick sanity check, and hovering the :material/visibility:
   icon beside a mapped field shows its first few values and how they are read,
   for example `0.12 → 120 ms` for a column in seconds. On a guess you have not
   confirmed yet, the same values are on the :material/auto_awesome: confirm
   button's tooltip. If trial order was randomized, map your item column as
   **Text ID**: `TRIAL_INDEX` only orders a participant's trials. Reading
   measures from an EyeLink
   interest-area report (`IA_DWELL_TIME`, …) are picked up automatically, and
   are what Corpus Analysis shows. Optional tables, one row per participant, trial
   or text, add fields to filter and group by.
3. **Recording setup** — the screen the data was recorded on (below).
4. **Stimulus images** — optional: a folder with a screenshot of each text or
   trial, drawn under the scanpath, and a filename pattern that names each file
   from your fields, such as `{text_id}.png`. The folder is saved with the
   dataset and never put on a share link.

Then click **:material/check: Add dataset**. Anything the app cannot use is listed above the
button before you confirm.

### Recording setup

Describe the screen the data was **recorded** on, not the one you are using
now. Four lines, each already filled in with the answer that invents nothing:

- **Screen** — estimated from the extent of your word boxes and fixations. That
  is a lower bound: text rarely fills the screen, so choose **I know it** and
  enter the real resolution if you have it.
- **Physical size** — off. **I know it** takes the monitor's width in
  millimetres (the visible area, not the diagonal); **Typical 597 mm** assumes
  one. The width gives the screen's DPI, which turns a font size in points into
  pixels; while it is off, a point size is read as pixels.
- **Text size** — each word sized to its box. **I know the size** takes the
  font size in points.
- **Font** — a generic monospace until you name the typeface (Courier New,
  Consolas, Arial, Times New Roman, …, or **Other…**). The word labels are then
  drawn in it wherever it is installed, so they line up with the stimulus.

Beside each value, a label says how it is known — *You entered it*, *From your
data*, *Estimated*, *Assumed* or *Off* — and that travels with the dataset, so
others can tell measured values from assumed ones. While a line is an estimate
or a default, a note above them asks for the real value; nothing waits on it,
and every line can be changed later on **Edit dataset**.

## The Data Management page

:material/database: **Data Management** lists every dataset with its counts; click a row to open it.
The :material/edit: on a row opens that dataset's editor under the list, below
its counts and tables. It changes its name, description, column mapping, recording setup,
stimulus images and metadata tables, or adds a table it is missing (Fixations, Words (interest areas) or raw
gaze); its mapped fields show the same value preview. On an
added dataset, changing an ID or coordinate column shows a few values as they
are now and as they will be after saving, and **:material/search: Count trials and check
joins** says whether trials would merge or the word boxes or a metadata table
would stop matching. Its
**:material/download: Download setup file** writes the mapping in your files' own column names, so
whoever has the same files can restore it on the add screen; anything a
restore cannot redo by itself is listed beside the button. For the demo and
the public corpora, a recording setup you save is your own for that dataset
alone: the setup the corpus declares is kept, and **Reset to source setup**
goes back to it. Nothing applies until you click **Save changes**;
**Cancel** discards all of it. The page also holds each dataset's tables and its
annotations, and at the foot, what is saved on this computer.

Above the open dataset's tables, **Data checks** looks for values that loaded
as numbers but cannot be right: fixations lasting 0 ms or less or with an
infinite duration or onset, fixations or raw-gaze samples whose position is
missing or infinite, word boxes with no width or height or at infinity, and
per-screen screen sizes that are infinite or 0 or less. Each finding gives the rows and trials affected, the columns
they came from, a few example rows, and what the app does with them. Nothing
is removed: the rows stay in every table and export. `check_data_health` runs
the same checks from Python, and `scanpath-studio check` from the terminal.

Columns keep the names they have in your files, so a column uploaded as
`CURRENT_FIX_DURATION` is called that in the tables. On chips, filters and
plot controls, a mapped field is named by its role (*Participant*, *Duration
(ms)*), with your column's name in its tooltip. A column marked *(computed)* is
one Scanpath Studio derived, such as a saccade's amplitude.

<figure class="sps-screenshot" markdown>
![The Data Management page: the available datasets, and the counts and tables of the open one](../assets/screenshots/data-page.webp)
</figure>
