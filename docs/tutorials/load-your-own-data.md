# Tutorial 1 — Load your own data

**Goal:** go from a raw eye-tracker export to a dataset you can plot, measure
and export — and *know* it loaded correctly rather than hoping.

**You need:** your own words/IA and fixation tables (CSV, TSV, Parquet or
Feather). No export handy? Every command below also runs against the bundled
demo files under `scanpath_studio/sample_data/` (`ia.csv` + `fixations.csv`),
which are a real EyeLink-shaped export.

---

## 1. Know what the loader is looking for

Two tables, either of which may be omitted (the missing layer just isn't drawn):

| Table | One row per | Must have |
| --- | --- | --- |
| **Words / IA** | word (interest area) | a trial id, a word id, and a box — `IA_LEFT/RIGHT/TOP/BOTTOM` **or** `x/y/width/height` |
| **Fixations** | fixation | a trial id, a duration, and a position — `x`/`y` **or** a word id |

Everything else is optional. The full canonical column list is in
[Data format](../data-format.md); what happens when you leave a field out is in
[Bring your own data → What the app needs](../bring-your-own-data.md#what-the-app-needs).

---

## 2. Load it in the app

Sidebar → **➕ Add data** opens the setup wizard. Work down the steps:

1. **Name it** — the name appears in **Data source**, so you can switch back
   later without re-uploading.
2. **Experimental setup** — set the **monitor resolution** the stimulus was
   shown on. Nothing in an eye-tracker export records this, so the app can't
   guess it; uploads default to 2560 × 1440. Get it wrong and the plot is still
   internally consistent, but the text renders too big or too small.
3. **Upload** — drop in your fixations and/or words tables. Several files per
   table are concatenated, each row remembering its `source_file`.
4. **Map columns** — auto-detection has already had a go; confirm or override.
5. **Filter & keep** — tick any extra columns you want to survive the import,
   then **✅ Add dataset**.

Stuck mid-wizard? **❓ Show setup guide** (inside the wizard) walks the steps
again in place.

!!! tip "Two things to check on the mapping step"
    Each ID step counts distinct values as you go — *✓ 36 trials*,
    *✓ 12 participants*. That running count is the fastest sanity check you'll
    get. And a mapping widget with **no caption matched nothing** — a missing
    *optional* field fails quietly.

The full walkthrough — composite trial ids, IDs that only exist in the
filename, saved-setup JSON, and a failure-by-failure troubleshooting list —
lives in **[Bring your own data](../bring-your-own-data.md)**. This tutorial
doesn't repeat it; go there once the basics load.

![The app with a scanpath drawn true-to-scale over the stimulus text](../assets/app_screenshot.png){ .sps-shot }

---

## 3. Load the same data headlessly

The app's wizard and the Python loader run the *same* inference. To skip the UI:

```python
from pathlib import Path

import scanpath_studio as sps

DATA = Path("scanpath_studio/sample_data")        # ← point at your own folder
words, fixations = sps.load_scanpath_data(DATA / "ia.csv", DATA / "fixations.csv")

combos = sps.list_trials(words, fixations)
print(f"{combos['participant_id'].nunique()} participants, {len(combos)} trials")
```

`load_scanpath_data` takes paths, quoted globs, or DataFrames, and either
argument may be `None`.

### See what auto-detection picked

Before trusting a load, print the schema the loader inferred. `propose_schema`
returns exactly what `load_scanpath_data` would use internally:

```python
import pandas as pd
from scanpath_studio.api import propose_schema

words_raw = pd.read_csv("scanpath_studio/sample_data/ia.csv", nrows=500)
fix_raw = pd.read_csv("scanpath_studio/sample_data/fixations.csv", nrows=500)

for kind, frame in (("words", words_raw), ("fixations", fix_raw)):
    print(kind)
    for field, column in propose_schema(frame, kind).items():
        print(f"  {field:<12} -> {column}")
```

On the bundled EyeLink-shaped export that prints:

```text
words
  participant  -> participant_id
  trial        -> unique_trial_id
  text_id      -> unique_paragraph_id
  word_id      -> IA_ID
  text         -> IA_LABEL
  line         -> None
  x            -> None
  y            -> None
  width        -> None
  height       -> None
  left         -> IA_LEFT
  right        -> IA_RIGHT
  top          -> IA_TOP
  bottom       -> IA_BOTTOM
fixations
  participant  -> participant_id
  trial        -> unique_trial_id
  text_id      -> unique_paragraph_id
  fixation_id  -> CURRENT_FIX_INDEX
  timestamp    -> CURRENT_FIX_START
  duration     -> CURRENT_FIX_DURATION
  x            -> CURRENT_FIX_X
  y            -> CURRENT_FIX_Y
  word_id      -> CURRENT_FIX_INTEREST_AREA_ID
```

`None` on `x`/`y`/`width`/`height` is fine here — the box came from the four
edges instead. `None` on something you *do* have is the signal to override it.

### Override a guess

Pass a schema dict; it **replaces** auto-detection for that table, so a field
you omit simply isn't mapped:

```python
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

---

## 4. Four checks that catch a bad load

Run these right after loading. They take seconds and catch the mistakes that
otherwise show up as a confusing plot ten minutes later.

```python
import scanpath_studio as sps

words, fixations = sps.load_scanpath_data("ia.csv", "fixations.csv")

# 1 — do the two tables agree about which trials exist?
combos = sps.list_trials(words, fixations)
print(f"{combos['participant_id'].nunique()} participants, {len(combos)} trials")

# 2 — are fixations and word boxes in the same coordinate system?
print("word boxes  x:", words["x"].min(), "→", (words["x"] + words["width"]).max())
print("            y:", words["y"].min(), "→", (words["y"] + words["height"]).max())
print("fixations   x:", fixations["x"].min(), "→", fixations["x"].max())
print("            y:", fixations["y"].min(), "→", fixations["y"].max())

# 3 — did fixations land on words?
print("unassigned fixations:", int(fixations["word_id"].isna().sum()))

# 4 — do the measures look like reading?
measures = sps.compute_word_metrics(words, fixations)
print("skip rate:", round(float(measures["skip_flag"].mean()), 3))
```

On the bundled sample that prints ranges like `word boxes x: 358 → 2183` /
`fixations x: 355 → 2163`, one unassigned fixation, and a skip rate of `0.565`.

How to read the numbers:

| Symptom | Almost always means |
| --- | --- |
| **0 trials**, or far fewer than expected | The two tables' trial ids don't match *as strings* — classically `7` vs `7.0`, or `p01` vs `1`. |
| Fixation and word-box ranges don't overlap | Different coordinate systems: y measured from the bottom in one table, different recording resolutions, or degrees of visual angle vs. pixels. The app applies **no** coordinate transform. |
| Most fixations unassigned | Same cause as above — assignment is bounding-box containment with a 50 px nearest-word fallback. |
| Skip rate near 1.0, all measures 0 | The fixations never reached the words; see the two rows above. |

Every one of these has a longer diagnosis under
[Bring your own data → When it goes wrong](../bring-your-own-data.md#when-it-goes-wrong).

In the app the same checks live in the 🔎 **Data Inspection** subtab: the
headline counts (Participants · Texts · Trials · Fixations · Words · Gaze
points), the raw tables themselves, a **Summary statistics** table with
mean/std/min/median/max per measure, and the active **Column mapping** — which
is editable, so a wrong guess can be fixed in place without re-uploading.

---

## 5. Confirm from the command line

One command tells you whether the CLI (and therefore any script or pipeline)
sees the same trials the app does:

```bash
scanpath-studio render --words ia.csv --fixations fixations.csv --list-trials
```

```text
participant_id              trial_id
      l37_1129 l37_1129_2_1_1_Ele_r0
      l37_1129 l37_1129_2_1_2_Ele_r0
      ...
```

Then render one to be sure it draws — HTML needs no browser:

```bash
scanpath-studio render --words ia.csv --fixations fixations.csv \
    -p l37_1129 -t l37_1129_2_1_1_Ele_r0 -o check.html
```

Multiple files per table work here too: pass several paths or a quoted glob
(`--fixations "fix/*.csv"`).

---

## Next

- Two readers of the same text, visually and numerically →
  **[Compare two readers](compare-two-readers.md)**
- Turn one of these trials into a figure →
  **[Produce a figure for a paper](figure-for-a-paper.md)**
- Something didn't map → **[Bring your own data](../bring-your-own-data.md)**
- Want your corpus to load with zero setup →
  **[Contributing a dataset](../contributing-a-dataset.md)**
