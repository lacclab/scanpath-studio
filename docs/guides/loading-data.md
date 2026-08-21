# Loading public and own data

Scanpath Studio can use the bundled sample, supported public corpora, or tables
from your own experiment.

## Choose a source

- **Bundled demo:** immediate, small, and suitable for learning the interface.
- **Public corpus:** choose the corpus and local data directory; download when
  prompted. Corpora prepared from a local benchmark bundle appear here too, one
  entry each — see [Harmonised benchmark corpora](../benchmark-corpora.md).
- **➕ Add dataset:** upload or select your own files and map their columns
  (🗂️ **Data → 📂 Available datasets**).
- **✏️ Author a scanpath:** sketch a trial from text, with no files at all.

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

The wizard is **two parts**, in the only order they can happen in — there is
nothing to map until a file has been read — with the dataset's name above both
and **✅ Add dataset** at the foot. Everything in part 2 is on one screen, so the
whole mapping is visible at once.

**1. Upload data files.** Add the word/IA and fixation files; several files per
table are allowed. Raw gaze goes here too, as does an optional table with **one
row per reader** (native language, age, comprehension score) — see
[Participant metadata](../data-format.md#participant-metadata); the same
attach-and-report UI is on the 🗂️ **Data** page for datasets that don't come
through this wizard. A summary card names the columns that were auto-detected and
the ones still missing — it is a report, not a shortcut: detection matches column
*names*, so part 2 is where you confirm it picked the right ones. *Restore a
saved setup* lives behind a popover here.

**2. Map data fields**, four sections deep:

1. **Trials & readers** — check the proposed trial ID, and the optional
   participant and text IDs. Pick several columns to build a composite ID when one
   is not unique enough. The readout below the pickers is the fastest sanity
   check: *N trials · N readers · N texts*.
2. **Fixation features** — fixation x/y/duration, then the word ID/text/box under
   their own heading. Anything unusual (word ID on fixations, timestamps, line
   index, character-AOI aggregation) is behind **⚙️ Advanced**.
3. **Recording setup** — see below.
4. **Extra fields** — keep any condition or analysis fields you will need later,
   and choose which become trial filters.

The wizard objects only once you press **✅ Add dataset**, and then about
everything at once rather than one field at a time.

After loading, open the 🗂️ **Data** page and confirm that both tables share the
expected trials and coordinate range.

📂 **Available datasets** lists the same headline fields shown in the active
dataset summary — participants, texts, trials, fixations, words, gaze points and
multipart screens; click a name to open it, and the open row is tinted. Rename or
remove a source from its table row, or open ✏️ **Edit dataset** to change how it
was mapped. Uploaded data is renamed or deleted in the session; packaged and
public sources keep their stable identifiers and are renamed for display or
hidden for this session.

A public corpus arrives with its own published figures, so a row you have never
opened is not a blank one. The **Counts** column says which you are reading —
*Published* is a claim about the corpus, *Loaded* a fact about this session — and
ℹ️ **About** names where each published figure came from, setting the two side by
side once the dataset is open. Loading **less** than a corpus publishes is the
ordinary case (one OneStop regime, one MultiplEYE session folder) and is not
flagged; loading **more** is, because only a wrong published figure explains it.

### The recording setup asks how you know

**Recording setup** describes the screen the data was **recorded** on — not the
screen you are reading this on. It has **no defaults**: a wrong monitor size
silently rescales every figure, so the app will not guess one for you. Each of
the three groups — *Screen*, *Physical size & viewing distance*, and *Reading
text size* — asks how you know the value:

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

The answer travels with the dataset. It appears in the review table beside
**✅ Add dataset** and under 🗂️ **Data → ✏️ Edit dataset → Recording setup**,
rides a share link as `setup_prov`, and is written into the saved-setup JSON and
into `plot_config.json` in a bulk export — so a figure set records that its
monitor size was assumed, and whoever opens your link can tell your measurements
from the app's guesses.

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
🗂️ **Data → ✏️ Edit dataset → Column mapping** or reload the files when a
required column was not retained.
