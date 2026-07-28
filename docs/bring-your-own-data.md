# Bring your own data

Getting your own eye-tracking export into the app. If you're coming from EyeLink
Data Viewer, it usually just works — upload the two reports and skip to
[when it goes wrong](#when-it-goes-wrong) if something looks off.

## What the app needs

Two tables — **words** (interest areas, with their positions on screen) and
**fixations**. Either one can be left out; the missing layer just isn't drawn.

**Words** must have a trial ID, a word ID, and a box for each word — either
`left/right/top/bottom` (EyeLink's `IA_LEFT` etc.) or `x/y/width/height`.

**Fixations** must have a trial ID, a duration, and a position — either `x`/`y`
coordinates or a word ID saying which word was fixated.

Everything else is optional, but three omissions change what you get:

| Left out | What happens |
|---|---|
| **Participant** (words table) | The boxes are treated as one shared layout and reused for every reader. Right for most corpora — wrong if your table really is one row per *reader × word*, in which case map it. |
| **Participant** (fixations) | Everyone becomes one anonymous reader called `(all)`. |
| **Text ID** | Falls back to the trial ID, so Corpus Analysis can't pool different readers of the same passage. |
| **Word text** | Labels become `w1`, `w2`, … and the reading text isn't drawn. |
| **Timestamp** | Fixation *order* survives, but the animation clock doesn't. |

!!! warning "Set your monitor resolution"
    Nothing in an eye-tracker export records the screen the stimulus was shown
    on, so the app can't guess it. Set it under **Experimental setup** in the
    wizard (uploads default to 2560 × 1440). Get it wrong and the plot is still
    internally consistent, but the reading text will look too big or too small.

## Loading it

Sidebar → **➕ Add data**, then work down the steps: name it → set the monitor
and font → upload your files → check the column mapping → pick which extra
columns to keep. Then **✅ Add dataset** and it's a switchable data source for
the rest of the session.

Two things about the mapping step:

- **You can build an ID out of several columns.** If no single column identifies a
  trial, pick participant + paragraph + repeated-reading and they're joined
  together. Only columns present in *every* uploaded table are offered.
- **Check what it pre-selected.** Each ID step counts distinct values as you go —
  *✓ 36 trials*, *✓ 12 participants* — which is the quickest sanity check you'll
  get. A red *no trial IDs are shared across tables* warning means the two tables
  don't line up at all.

You can upload **several files per table** and they're concatenated, with each
row remembering which file it came from — useful when the IDs are only in the
filename (see the second worked example below).

!!! tip "Large or sensitive data"
    Uploading reads the whole file into memory. For a big corpus — or data that
    shouldn't leave your machine — run it locally
    (`pip install scanpath-studio && scanpath-studio`) or use the
    [Python API](api.md), which reads paths and globs directly. See
    [Privacy](privacy.md).

## When it guesses the wrong column

The app matches your column names against a list of known conventions, ignoring
case and separators — so `IA_LEFT`, `ia_left` and `Ia-Left` are all the same, and
EyeLink names win when a table carries both EyeLink and Gazepoint spellings.

Every mapping widget shows what it found (`✨ auto-detected IA_LEFT`), and adds
`· overridden` once you change it. **A field with no caption matched nothing** —
worth a scan before you finish, because a missing *optional* field fails quietly.
A missing *required* field disables **Add dataset** and says exactly what's wrong.

To change a mapping later: 🔎 **Data Inspection → Column mapping** is an editable
form that re-derives everything in place. It can only offer columns that survived
the original import — anything dropped needs a re-upload.

!!! warning "Two column names beat your mapping"
    If your table has a column literally named `unique_trial_id` or
    `unique_paragraph_id`, those win over what you picked in the wizard (unless
    you built a multi-column ID, which is always authoritative). If one is left
    over from someone else's pipeline, rename or drop it before uploading.

**Headless**, pass a schema dict instead:

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data(
    "aoi/*.csv",
    "fixations/*.csv",
    word_schema=dict(participant="subj", trial="item", word_id="ianum",
                     text="token", left="x_left", right="x_right",
                     top="y_top", bottom="y_bot"),
    fix_schema=dict(participant="subj", trial="item", x="gaze_x", y="gaze_y",
                    duration="fix_dur", timestamp="t_onset"),
)
```

An explicit schema **replaces** auto-detection for that table rather than adding
to it — a field you leave out isn't auto-detected, it just isn't mapped. Omit the
argument entirely to auto-detect everything.

## Reusing a mapping

Above **✅ Add dataset** there's **⬇️ Download setup (JSON)**. For the next export
from the same pipeline, drop that file into *Restore a saved setup* at the top of
the mapping step and the widgets are pre-filled. It's the same format the 💾 Save
& restore panel reads, so the two are interchangeable.

## Two examples

??? example "EyeLink Data Viewer — IA report + fixation report"
    This needs **no manual mapping**: `RECORDING_SESSION_LABEL`, `TRIAL_INDEX`,
    `IA_ID`, `IA_LABEL`, the four `IA_*` box edges, and the `CURRENT_FIX_*`
    columns are all recognised. Pre-computed measures
    (`IA_FIRST_FIXATION_DURATION`, `IA_DWELL_TIME`, …) are carried through and
    **take precedence** over anything the app would compute — so on a normal
    EyeLink export the numbers are your eye-tracker's. That match is by exact
    name, so a renamed export loses them and falls back to recomputation.

    Two things to check:

    - **`TRIAL_INDEX` only identifies a trial within one reader**, and the text
      ID falls back to the trial ID — so trial 3 of every reader looks like the
      same text. If trial order was randomised, map your item column as **Text
      ID** or Corpus Analysis will pool the wrong readings.
    - **Repeated readings.** With a single-column trial mapping, a second reading
      of the same passage is automatically split off as `par3_r2`. Build a
      multi-column ID and that automatic split turns off — so add your
      repeat-marking column to the composite, or drop back to one column.

??? example "One file per reader, IDs only in the filename"
    PoTeC-shaped exports — `reader0_b0_scanpath.csv`, `reader0_b1_scanpath.csv`,
    … with no identity column inside the files.

    Upload them all into the *Fixations* box. In the wizard's **Derive IDs from
    filename** step, either split on `_` (giving `file_part_1` = `reader0`,
    `file_part_2` = `b0`) or use a regex with named groups
    (`(?P<reader>reader\d+)_(?P<item>b\d+)_scanpath`), which is more robust when
    the parts vary in length. Then map **Participant** = `reader` and **Trial** =
    `reader` + `item`.

    Headlessly this is `data.split_source_file` /
    `data.extract_columns_from_source_file`.

## When it goes wrong

Open 🔎 **Data Inspection** first — the headline counts (Participants · Texts ·
Trials · Fixations · Words) identify most of these at a glance.

??? failure "Every fixation is out-of-text; no word gets a measure"
    The fixations and the boxes are in different coordinate systems. Usually:
    **y measured from the bottom** in one table and from the top in the other;
    different **resolutions** (recorded at 1024 × 768, AOIs computed at 1920 ×
    1080); or **degrees of visual angle vs. pixels**. Compare the fixation `x`/`y`
    ranges against the word-box ranges in Data Inspection. The app applies no
    coordinate transform, so fix it in the export and re-upload.

??? failure "A trial shows fixations but no text or boxes"
    The two tables disagree about the trial ID *as a string*. The classic cause is
    `7` in one table and `7.0` in the other — one blank cell makes pandas read the
    column as a float. `p01` vs `1`, or trailing whitespace, do the same. Map the
    same column in both tables and make the types agree in the export.

??? failure "One trial only, or far fewer than expected"
    The trial column doesn't separate trials. Either it's effectively constant (a
    session label rather than a trial label — check its distinct count), or it's
    too coarse (`paragraph_id` alone merges every reader), or your multi-column ID
    doesn't distinguish repeated readings. Build the ID out of participant +
    passage + repeat.

??? failure "Far more trials than expected"
    The opposite — something that varies *within* a trial got into the composite
    ID (a fixation index, a timestamp). Drop it from the multiselect.

??? failure "Every reader shows every reader's word boxes"
    Your words table is one row per *reader × word*, but Participant was left
    unmapped, so it was treated as one shared layout. Map it on the words table.

??? failure "A column I need disappeared after import"
    Anything not claimed at import is dropped, for speed. Mapped columns,
    recognised reading measures and linguistic fields, and recognised trial
    conditions are kept by default; anything else is **off** unless you tick it
    under *Filter & keep → Additional fields to keep*. Getting one back needs a
    re-upload.

??? failure "Reading measures are missing or all zero"
    Either the fixations have no usable coordinates (see the first entry), or your
    pre-computed measure columns aren't under names the app recognises, so they
    were dropped and the fallback computation ran on whatever it could assign.

---

Related: [Data format](data-format.md) for the canonical column names ·
[Export & troubleshooting](export-troubleshooting.md) ·
[Contributing a dataset](contributing-a-dataset.md) to get a corpus shipped with
the app.
