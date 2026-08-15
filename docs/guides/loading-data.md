# Loading public and own data

Scanpath Studio can use the bundled sample, supported public corpora, or tables
from your own experiment.

## Choose a source

- **Bundled demo:** immediate, small, and suitable for learning the interface.
- **Public corpus:** choose the corpus and local data directory; download when
  prompted. Corpora prepared from a local benchmark bundle appear here too, one
  entry each — see [Harmonised benchmark corpora](../benchmark-corpora.md).
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

The wizard is seven steps. Work down them in order, or jump straight to one with
the progress chips at the top; your answers are kept as you move around.

1. **Your data** — add the word/IA and fixation files; several files per table are
   allowed. A summary card names the columns that were auto-detected and the ones
   still missing — it is a report, not a shortcut: detection matches column
   *names*, so steps 2 and 3 are where you confirm it actually picked the right
   ones. Raw gaze and *Restore a saved setup* live behind the two popovers.
2. **Trials & readers** — check the proposed trial ID, and the optional
   participant and text IDs. Pick several columns to build a composite ID when one
   is not unique enough. The readout below the pickers is the fastest sanity
   check: *N trials · N readers · N texts*.
3. **Fixations & text** — fixation x/y/duration and the word ID/text/box. Anything
   unusual (word ID on fixations, timestamps, line index, character-AOI
   aggregation) is behind **⚙️ Advanced**.
4. **Recording setup** — see below.
5. **About your readers** — optional: attach a table with **one row per reader**
   (native language, age, comprehension score). See
   [Participant metadata](../data-format.md#participant-metadata); the same
   attach-and-report UI is on the 🗂️ **Data** page for datasets that don't come
   through this wizard.
6. **Extra fields** — keep any condition or analysis fields you will need later,
   and choose which become trial filters.
7. **Name & add** — review every decision in one table, then **Add dataset**.

After loading, open the 🗂️ **Data** page and confirm that both tables share the
expected trials and coordinate range.

### The recording setup asks how you know

Step 4 describes the screen the data was **recorded** on — not the screen you are
reading this on. It has **no defaults**: a wrong monitor size silently rescales
every figure, so the app will not guess one for you. Each of the three groups asks
how you know the value:

| Choice | Recorded as | Use when |
| --- | --- | --- |
| *I know these* | `measured` | You have the real numbers. |
| *Estimate from my data* | `estimated` | You don't. Derived from the extent of your word boxes and fixations — always available, always succeeds, and reported as a **lower bound**, since text rarely fills the whole screen. |
| *Use a named default* | `assumed` | A typical lab value is good enough for what you are doing. |
| *Skip* | `skipped` | Only on **physical size & viewing distance**, when you don't need visual-angle units. |

**Add dataset** stays disabled until all three are answered. Nothing derived from
a skipped group is shown: with no physical width there is no honest pixels-per-
degree or point-to-pixel conversion, so those are hidden rather than computed from
a default.

The answer travels with the dataset. It appears in the step-7 review table and
under 🗂️ **Data → Recording setup**, rides a share link as `setup_prov`,
and is written into the saved-setup JSON and into `plot_config.json` in a bulk
export — so a figure set records that its monitor size was assumed, and whoever
opens your link can tell your measurements from the app's guesses.

Answers are remembered across datasets in a session as **pre-filled values with
the choice reset**: quick for a second export from the same lab, while still
making you assert that the setup applies to this dataset too.

## Derived and preserved fields

When x/y fixations and word boxes are available, the app can assign fixations to
words and compute standard per-word reading measures. Recognized precomputed
EyeLink IA measures take precedence. Fields not mapped or explicitly retained
may be dropped during normalization.

## Reuse the setup

Download the setup JSON from the wizard and restore it for the next export from
the same pipeline. If a mapping was wrong, edit it under
🗂️ **Data → Column mapping** or reload the files when a required column
was not retained.
