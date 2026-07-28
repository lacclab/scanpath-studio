# Bring your own data

The path from a raw eye-tracker export to a dataset you can plot: what the app
actually needs, how it guesses your column names, how to correct it when the
guess is wrong, and what each failure symptom means.

- The column reference — which tables, which canonical names — is
  [Data format](data-format.md). This page doesn't repeat it.
- Packaging a corpus so it ships **with** the app as a built-in source is
  [Contributing a dataset](contributing-a-dataset.md).

## 1. The minimum

Two tables, and neither one has to be complete. Required means *validation
blocks* — the wizard won't let you finish until it's mapped. Either table may
also be left out entirely: a words-only or a fixations-only upload is valid, and
the missing layer is simply not drawn.

### Words / interest areas

| Field | Required | If it's missing |
|---|---|---|
| **Trial ID** | ✅ | Blocks. Several columns may be combined into one id. |
| **Word/IA ID** | ✅ | Blocks. It's the key fixations attach to and the word order within a trial. |
| **Word box** | ✅ | Blocks. Either `left/right/top/bottom` (EyeLink `IA_LEFT/IA_RIGHT/IA_TOP/IA_BOTTOM`) **or** `x/y/width/height`. |
| Participant ID | — | The table is treated as **stimulus-level** and each trial's boxes are broadcast to every participant who has fixations for that trial. Correct for one-layout-per-text corpora. Map it whenever the table really is one row per *(reader, word)* — otherwise every reader gets every reader's boxes. |
| Word text | — | Labels fall back to `w1`, `w2`, … The reading text isn't drawn and word tooltips are unhelpful. |
| Text ID | — | Falls back to the trial id, so Corpus Analysis *Per text* groups by trial. If your trial id is per-reader (e.g. EyeLink `TRIAL_INDEX`), readers of the same passage are never pooled. |
| Line index | — | Nothing visible changes. `line_idx` becomes a constant `1`, and every line-aware feature — color-by-line, the true-to-scale line pitch, drift correction — derives visual lines from word-box `y` instead (`measures.cluster_word_lines`), because IA exports usually ship a constant line number and it can't be trusted. Mapping it only affects two secondary sorts (the per-word bar chart, the reconstructed passage text). |

### Fixations

| Field | Required | If it's missing |
|---|---|---|
| **Trial ID** | ✅ | Blocks. |
| **Duration (ms)** | ✅ | Blocks. Drives marker size, dwell time, and every reading measure. |
| **X + Y** *or* **Word/IA ID** | ✅ (one of) | Blocks if neither. With a Word/IA ID but no coordinates, each fixation is placed at its word box's centre — an AOI-sequence dataset plots fine, but landing positions are synthetic. |
| Participant ID | — | Every row becomes one anonymous reader, shown as `(all)`. |
| Timestamp (ms) | — | Falls back to per-trial **row order** (0, 1, 2, …). Fixation order survives; the animation clock and any real-time axis do not. |
| Fixation ID | — | Row order within the trial. |
| Word/IA ID (with X/Y present) | — | Assignment becomes geometric: bounding-box containment, then the nearest word centre within 50 px, else unassigned (`NaN`) and counted as out-of-text. A mapped word id is **authoritative** and overrides that. |

A third **raw gaze** table is optional and only adds the sample-level overlay. It
needs a trial id and x/y; participant and timestamp are optional (same fallbacks
as above).

!!! warning "The monitor size is not a column"
    Word boxes and fixations are drawn true-to-scale against the **recording
    monitor's resolution**, which no export carries. Set it under *Experimental
    setup* in the wizard (uploads default to 2560 × 1440). Get it wrong and the
    geometry is still self-consistent but the reading text is sized against the
    wrong canvas — see [Export & troubleshooting](export-troubleshooting.md).

## 2. Load it — the Add-dataset wizard

Sidebar → **➕ Add data**. The steps, in order:

1. **Dataset name** — plus a **Dataset format** switch. `Generic` maps your own
   columns; `MultiplEYE` is a preset that skips mapping entirely (see
   [MultiplEYE](multipleye.md)).
2. **Experimental setup** — monitor resolution, font, text scaling.
3. **Upload your data** — one box per table: *Raw gaze (optional)*, *Fixations*,
   *Words / Interest Areas*. Each box reports its row count and previews the
   first rows. **Several files per table are concatenated**, and each row keeps
   its file's stem in a `source_file` column (see
   [example 5c](#5c-one-file-per-reader-with-the-ids-only-in-the-filename)).
4. **Column mapping** — sub-steps, in order: *Restore a saved setup* · *Derive
   ids from filename* (only shown when a `source_file` column exists, and it has
   its own on/off toggle) · *Trial identifier* · *Participants* · *Texts* ·
   *Fixations* · *Text & Interest Areas* · *More text mappings* · *More fixation
   mappings* · *Raw gaze overlay*. Finished steps collapse; the first unfinished
   one opens.
5. **Filter & keep** — which extra source columns to carry through
   normalization, and which become trial filters.

Then **✅ Add dataset**. It becomes a switchable entry in *Data source* for the
rest of the session.

Three things about step 4 worth knowing before you start:

- **Identifiers are picked once for all tables.** *Trial identifier*,
  *Participants* and *Texts* each render one multiselect over the columns
  **common to every uploaded table**, with a *Different … per table* toggle for
  the rare export that names them differently.
- **Picking several columns composes an id**, joined with `_`. That's how you
  build a unique trial from `participant + paragraph + repeated_reading` when no
  single column identifies a trial.
- **The wizard's default Trial ID is often a composite, not the column
  auto-detection would have picked.** A trial is *one reading of one passage*, so
  the step pre-selects, in this order:

    1. the auto-detected trial column, when it's a genuine trial id — i.e. not
       the same column as the passage id;
    2. otherwise participant + the finest passage id present
       (`unique_paragraph_id` / `paragraph_id`, else `unique_text_id` /
       `text_id`) + a repeated-reading column (`repeated_reading_trial` /
       `reread`) when there is one;
    3. otherwise a fallback chain — paragraph id + text id when the table has
       both, else the detected trial column, else the passage id alone, else
       nothing and you pick.

    Only columns present in **every** uploaded table are candidates, so a
    participant column that exists in the fixations but not the words table
    can't join the composite. Check the pre-selection rather than clicking past
    it — see the repeated-reading caveat in
    [example 5a](#5a-eyelink-data-viewer-ia-report-fixation-report).

Each of the three steps counts distinct values as you map and reports them
(*✓ N trials* / *N participants* / *N texts*) — the cheapest check that your
mapping is right. For the trial id the check is per table: a green count when
both tables agree, an *ℹ️ trial coverage differs* note when they overlap
partially, and a **⚠️ no trial ids are shared across tables** warning when they
don't line up at all.

!!! tip "Large or sensitive data"
    Browser upload reads the whole file into the server process. For a big corpus
    — or data that shouldn't leave your machine — run locally
    (`pip install scanpath-studio && scanpath-studio`) or use the
    [Python API](api.md), which reads paths and globs directly.

## 3. How columns are detected — and how to override

Each field has a candidate list, walked in priority order. Matching is **case-
and separator-insensitive**, so `IA_LEFT` = `ia_left` = `Ia-Left`, and
`Participant ID` = `participant_id`. The first candidate with any match wins,
which is why EyeLink names beat Gazepoint ones when a table has both.

| Field | Candidates (in priority order) |
|---|---|
| Participant | `participant_id`, `subject_id`, `participant`, `recording_session_label`, `reader_id` |
| Trial | `unique_trial_id`, `trial_id`, `unique_paragraph_id`, `paragraph_id`, `text_id`, `trial`, `trial_index` |
| Text ID | `unique_paragraph_id`, `paragraph_id`, `unique_text_id`, `text_id` |
| Word/IA id | `word_id`, `IA_ID`, `ia_index`, `word_index`, `aoi`, `word_idx`, `char_idx` |
| Word text | `text`, `IA_LABEL`, `label`, `word`, `content`, `token` |
| Box edges | `IA_LEFT` / `IA_RIGHT` / `IA_TOP` / `IA_BOTTOM`, `left`/`right`/`top`/`bottom`, `start_x`/`end_x`/`start_y`/`end_y` |
| Box origin+size | `x`, `y`, `width`, `height` (also `top_left_x` / `top_left_y`) |
| Fixation x / y | `x`, `CURRENT_FIX_X`, `FPOGX`, `location_x` (and the `y` equivalents) |
| Fixation duration | `duration_ms`, `CURRENT_FIX_DURATION`, `CURRENT_FIX_LEN`, `duration`, `fixation_duration` |
| Fixation timestamp | `timestamp_ms`, `CURRENT_FIX_START`, `CURRENT_FIX_START_TIME`, `CURRENT_FIX_TIME`, `CURRENT_FIX_ONSET`, `onset` |
| Fixation word id | `word_id`, `IA_ID`, `CURRENT_FIX_INTEREST_AREA_ID`, `CURRENT_FIX_INTEREST_AREA_INDEX`, `word_index_in_text`, `word_index`, `word_idx`, `char_idx` |

The full lists are the `*_CANDIDATES` constants in
[`data.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/data.py).

**Auto-detection shows its work.** Every mapping widget prints what it found —
`✨ auto-detected IA_LEFT` — and appends `· overridden` once you change it; a
field with no caption at all matched nothing. If a *required* field can't be
found, **Add dataset** stays disabled and the exact problem is listed, e.g.
*"Words/IA: missing Word/IA ID; need either (x, y, width, height) or (left,
right, top, bottom)"*. An unmatched *optional* field fails quietly, which is why
the captions are worth a pass before you finish.

!!! warning "Two column *names* outrank your mapping"
    Normalization reads a couple of columns by name, before it looks at the
    schema — so a table that happens to carry them ignores what you picked:

    - a **`unique_trial_id`** column wins over a single-column *Trial ID*
      mapping. Composing the trial id from several columns overrides it (a
      composite is authoritative); mapping one other column does not.
    - a **`unique_paragraph_id`** column wins over the *Text ID* mapping, and
      also becomes `unique_text_id`.

    If your export has a leftover `unique_trial_id` / `unique_paragraph_id`
    column from someone else's pipeline, rename or drop it before uploading.

### Overriding later

- **A dataset you already added**: 🔎 **Data Inspection → Column mapping** is an
  editable remap form. It re-derives the frames in place. It can only offer
  columns that *survived* the original import — anything dropped is listed under
  *⚠️ N columns dropped at import* and needs a re-upload to get back.
- **The bundled demo and public datasets**: the sidebar carries the same
  *Column mapping* panels, pre-filled with auto-detection.
- **Headless**: pass explicit `word_schema` / `fix_schema` dicts to
  [`load_scanpath_data`][scanpath_studio.api.load_scanpath_data]. Field keys are
  the same ones the UI shows.

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data(
    "aoi/*.csv",
    "fixations/*.csv",
    word_schema=dict(
        participant="subj", trial="item", word_id="ianum", text="token",
        left="x_left", right="x_right", top="y_top", bottom="y_bot",
    ),
    fix_schema=dict(
        participant="subj", trial="item",
        x="gaze_x", y="gaze_y", duration="fix_dur", timestamp="t_onset",
    ),
)
```

A partial dict is fine, but an explicit schema **replaces** detection for that
table rather than being merged into it: a field you leave out is not
auto-detected, it falls back as in §1. In the example above, dropping
`text="token"` doesn't fall back to the `token` column — the labels become `w1`,
`w2`. Omit the argument entirely to auto-detect the whole table.

## 4. Save a mapping, reuse it on the next export

Directly above **✅ Add dataset**: **⬇️ Download setup (JSON)**. It writes
`scanpath_studio_setup.json` — the column mapping plus provenance (dataset name,
export time, app version, config-schema version).

For the next export from the same lab pipeline, open the wizard and drop that
file into **Restore a saved setup (optional)** (the first sub-step of *Column
mapping*). The mapping widgets are seeded from it and a caption confirms which
dataset and date it came from, so you can tell you loaded the right one. It's the
same JSON format the 💾 **Save & restore** panel reads, so a setup file and a
saved plot config are interchangeable inputs.

For scripted runs, keep one Python dict per corpus instead — the `word_schema` /
`fix_schema` arguments above are the same mapping in another form.

## 5. Worked examples

### 5a. EyeLink Data Viewer — IA report + fixation report

The common case, and it needs **no manual mapping at all**. Interest-area report:

```text
RECORDING_SESSION_LABEL,TRIAL_INDEX,IA_ID,IA_LABEL,IA_LEFT,IA_RIGHT,IA_TOP,IA_BOTTOM,IA_FIRST_FIXATION_DURATION,IA_DWELL_TIME,IA_FIXATION_COUNT
p01,1,1,The,100,166,300,340,201,251,1
p01,1,2,quick,176,266,300,340,202,252,1
```

Fixation report:

```text
RECORDING_SESSION_LABEL,TRIAL_INDEX,CURRENT_FIX_INDEX,CURRENT_FIX_X,CURRENT_FIX_Y,CURRENT_FIX_DURATION,CURRENT_FIX_START,CURRENT_FIX_INTEREST_AREA_ID
p01,1,1,133.0,320.0,201,1250,1
p01,1,2,221.0,320.0,202,1500,2
```

What auto-detection produces:

| Field | Words/IA | Fixations |
|---|---|---|
| Participant | `RECORDING_SESSION_LABEL` | `RECORDING_SESSION_LABEL` |
| Trial | `TRIAL_INDEX` | `TRIAL_INDEX` |
| Word/IA id | `IA_ID` | `CURRENT_FIX_INTEREST_AREA_ID` |
| Word text | `IA_LABEL` | — |
| Box | `IA_LEFT` / `IA_RIGHT` / `IA_TOP` / `IA_BOTTOM` | — |
| X / Y | — | `CURRENT_FIX_X` / `CURRENT_FIX_Y` |
| Duration | — | `CURRENT_FIX_DURATION` |
| Timestamp | — | `CURRENT_FIX_START` |
| Fixation id | — | `CURRENT_FIX_INDEX` |

Three things to check before you accept it:

- **`TRIAL_INDEX` identifies a trial only within a reader.** That's fine —
  trials are keyed `(participant, trial)` — but the *text* id falls back to the
  trial id, so trial 3 of every reader is treated as the same text. If trial
  order was randomised, map your item/condition column as **Text ID**, or
  Corpus Analysis will pool the wrong readings.
- **A paragraph/item column outranks `TRIAL_INDEX`.** `TRIAL_INDEX` is last in
  the trial candidate list, so a report that also carries `paragraph_id` /
  `text_id` maps the trial to *that* — which is what you want for cross-reader
  comparison, but it merges repeated readings unless they're separated. They
  are, automatically: with no `unique_trial_id` column, a mapped participant and
  a `TRIAL_INDEX` column present, the second reading of the same id becomes
  `par3_r2` (ranked by `TRIAL_INDEX`), the third `par3_r3`.
  **The `_r2` suffixing runs only for a single-column trial mapping.** Compose
  the trial id from several columns and the composite is taken as authoritative
  — so `participant + paragraph_id`, which is what the wizard pre-selects here,
  collapses both readings into one trial, while `paragraph_id` alone would have
  split them. If your export marks repeats with a column of its own, add that
  column to the composite; if it doesn't, drop back to the single-column mapping
  and let the `TRIAL_INDEX` ranking do it.
- **Pre-aggregated measures win.** `IA_FIRST_FIXATION_DURATION`, `IA_DWELL_TIME`,
  `IA_FIRST_RUN_DWELL_TIME`, `IA_REGRESSION_*`, `IA_SKIP`, `IA_FIXATION_COUNT` …
  are carried through under canonical names and take precedence over the
  fixation-based recomputation. Matching here is by **exact** source name (not
  the fuzzy candidate matching), so a renamed export loses them and the app
  recomputes from fixations instead.

### 5b. A plain CSV with x/y/width/height

`words.csv`:

```text
participant_id,trial_id,word_id,text,x,y,width,height
s1,t1,1,The,100,300,80,40
s1,t1,2,quick,190,300,80,40
```

`fixations.csv`:

```text
participant_id,trial_id,x,y,duration,timestamp
s1,t1,140.0,320.0,211,1000
s1,t1,230.0,320.0,212,1250
```

Every column here is mapped except one: **`timestamp` is not in the fixation
timestamp candidate list** (`timestamp_ms` and the EyeLink/MultiplEYE names are).
Left alone, fixation ordering silently falls back to row order. Either rename the
column to `timestamp_ms` or map it by hand under *More fixation mappings*.

The fixations here carry no word id, so assignment is geometric — with these
boxes each fixation lands inside one, and `compute_word_metrics` returns FFD /
TFD / counts per word.

### 5c. One file per reader, with the ids only in the filename

PoTeC-shaped exports: `reader0_b0_scanpath.csv`, `reader0_b1_scanpath.csv`, … and
no identity column inside the files at all.

Upload all of them into the *Fixations* box (or pass a glob to the API). They're
concatenated, and each row keeps the file's stem in `source_file`. Then, in the
wizard's **Derive ids from filename** step, either:

- *Split on a delimiter* — `_` turns `reader0_b0_scanpath` into `file_part_1` =
  `reader0`, `file_part_2` = `b0`, `file_part_3` = `scanpath`; or
- *Regex named groups* — `(?P<reader>reader\d+)_(?P<item>b\d+)_scanpath` gives
  columns `reader` and `item`, which is robust when a part's length varies. A
  group whose name collides with an existing column is skipped (the real data
  wins) and the wizard warns, so rename the group rather than assume it applied.
  Avoid group names the auto-detector already claims — a group called `text`
  would be picked up as the *word text* on a words table.

Now map **Participant ID** = `reader` and **Trial ID** = `reader` + `item`
(two columns → the composite id `reader0_b0`). The trial picker then offers one
cascading selector per component instead of one opaque dropdown.

Headlessly the same two helpers are `data.split_source_file` and
`data.extract_columns_from_source_file`, applied to the frame from
`data.read_tables("fixations/reader*_scanpath.csv")` before you call
`load_scanpath_data` with an explicit schema.

## 6. When it goes wrong

Open 🔎 **Data Inspection** first: the headline counts (Participants · Texts ·
Trials · Fixations · Words · Gaze points) identify most of these in one glance,
and the raw tables below let you check actual values.

??? failure "Every fixation is flagged out-of-text; no word gets a measure"
    The fixations and the boxes are in different coordinate frames. The usual
    culprits, in order of frequency:

    - **Y measured from the bottom** of the screen in one table and from the top
      in the other. On a 1080 px screen a fixation at `y = 320` becomes `y = 760`
      — outside every box, and beyond the 50 px nearest-word fallback, so it is
      left unassigned.
    - **Different resolutions** — fixations recorded at 1024 × 768, AOIs computed
      on the 1920 × 1080 presentation screen.
    - **Different units** — degrees of visual angle vs pixels.

    Check it in Data Inspection: the fixation `x`/`y` ranges must overlap the
    word-box ranges. Fix it in the export (the app applies no coordinate
    transform), then re-upload.

??? failure "The boxes are drawn, but the whole plot looks off-scale"
    Geometry is self-consistent; the canvas isn't. Set the real recording
    resolution under *Experimental setup* — word labels are sized in data space
    from the line pitch and then converted to screen pixels, so a canvas that
    isn't the presentation monitor makes the reading text too large or too small.
    Details in [True-to-scale rendering](rendering.md).

??? failure "A trial shows fixations but no text and no boxes"
    The two tables disagree about the **trial id string**. The trial picker is
    built from the *fixations*; boxes are then looked up by the exact
    `(participant_id, trial_id)` pair, as strings. So:

    - `7` in the fixations vs `7.0` in the words — one stray blank cell makes
      pandas read that column as float, and `"7" != "7.0"`.
    - `p01` vs `1`, or an id with trailing whitespace on one side.

    Map the *same* column in both tables (the unified identifier picker does this
    by default) and make the dtypes agree in the export. The same mismatch on
    `participant_id` produces the same empty result. The wizard catches the total
    version of this at mapping time — *"⚠️ No trial ids are shared across
    tables"* — but a partial mismatch only shows up as a coverage note.

    With a **stimulus-level** words table (no participant column) the same
    mismatch is worse: the broadcast across readers is an inner join on
    `trial_id`, so unmatched word rows are dropped outright and the Words count
    in Data Inspection reads `0` rather than merely being wrong for one trial.

??? failure "One trial only, or far fewer trials than expected"
    The mapped trial column doesn't separate trials. Three causes, in order of
    frequency:

    - **It's effectively constant** — a session/experiment label rather than a
      trial label. Check its distinct-value count in Data Inspection.
    - **It's too coarse** — `paragraph_id` alone merges every reader's reading
      of that paragraph if no participant is mapped. Compose the trial id from
      several columns (`participant` + `paragraph` + `repeated`) in the *Trial
      identifier* step.
    - **The composite is too coarse for repeated readings.** The wizard
      pre-selects `participant + passage` when it can, and a composite turns off
      the automatic `_r2` suffixing — so two readings of the same passage land on
      one trial id. Add the repeat-marking column to the composite (see
      [example 5a](#5a-eyelink-data-viewer-ia-report-fixation-report)).

??? failure "Far more trials than expected"
    The opposite: something that varies *within* a trial got into the composite
    id — a fixation index, a timestamp, a per-fixation flag. Drop it from the
    multiselect; the trial count in Data Inspection updates immediately.

??? failure "The only participant is `(all)`"
    No participant column was mapped on the fixations table, so every row became
    a single anonymous reader. Map it in the *Participants* step.

??? failure "Every reader shows every reader's word boxes"
    The words table is one row per *(reader, word)* but Participant ID was left
    unmapped, so it was treated as stimulus-level and broadcast across all
    readers with fixations for that trial. Map the participant column on the
    words table too.

??? failure "A column I need disappeared after import"
    Everything not claimed at import is dropped, for speed. What survives:
    mapped columns; recognised reading-measure and linguistic fields (ticked by
    default under *Additional fields to keep*); recognised trial-level condition
    fields (ticked by default under *Filter trials by*); and anything else you
    tick yourself. A column the app doesn't recognise is **off by default** —
    tick it under *Filter & keep → Additional fields to keep*. For an
    already-imported dataset the dropped list is shown in Data Inspection →
    Column mapping; recovering one needs a re-upload.

??? failure "I mapped a column and the app used a different one"
    Two source column *names* are read directly by normalization and win over
    the mapping: `unique_trial_id` (over a single-column *Trial ID*) and
    `unique_paragraph_id` (over *Text ID*). See the warning in
    [§3](#3-how-columns-are-detected-and-how-to-override). Data Inspection →
    Column mapping shows the mapping that was *submitted*, not this override, so
    compare the trial ids in the raw table against the ones in the picker.

??? failure "Reading measures are missing or all zero"
    Either the fixations have no usable coordinates (so nothing was assigned to a
    word — see the first entry), or your pre-aggregated measure columns aren't
    under the exact names the app recognises, in which case they're dropped and
    the fallback computation runs on whatever fixations were assigned.
