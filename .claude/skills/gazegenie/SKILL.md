---
name: gazegenie
description: Use when running, driving, or cross-checking against GazeGenie — the reference tool whose line assignment (slice/DIST) and word measures we validate ours against (VAL-4, PRE-20, DATA-18). Covers its separate checkout and venv, the port, the slow first load, and the click path from an example .asc to a corrected trial.
---

# GazeGenie — run the reference app locally

[GazeGenie](https://github.com/Gittingthehubbing/GazeGenie) is our oracle, not a
dependency: a Streamlit app that takes the same `.asc` → cleaning → line
assignment → measures path we do, and reports each trial's word measures both its
own way (a popEye-derived aggregation) and through eyekit. Everything below keeps
it at arm's length — its own clone, its own venv. **Never install its requirements into `app/.venv`**;
torch + lightning + timm staying out of our runtime is the reason PRE-20 is parked.

Paths below are relative to the repository root (`app/`); the clone is a sibling
of `scanpath_studio/`, i.e. `../../GazeGenie`.

## Setup (once per machine)

1. `git clone --depth 1 https://github.com/Gittingthehubbing/GazeGenie.git ../../GazeGenie`
   — ~1.3 GB, almost all of it the DIST checkpoints in `models/`. Shallow is enough.
2. From the clone: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt`.
3. System libraries: `pycairo` and `pytesseract` need brew `cairo` and `tesseract`.
   If the install fails on either, `brew install cairo tesseract` and retry — no
   conda/mamba needed despite what its README says.

## Run

```
cd ../../GazeGenie && .venv/bin/streamlit run app.py --server.port 8502
```

or the `gazegenie` entry in `.claude/launch.json`. **Port 8502** — 8501, its
default, is usually taken on this machine.

**The first load takes ~40 s and the page stays blank** (torch import, then
`get_cached_models` reading the checkpoints). That is not a crash — wait, then
reload. Only conclude it died if the process is gone (`pgrep -f "streamlit run app.py"`).

## Drive it to a corrected trial

The single-file path is all the oracle work needs; the multi-file tab forks
worker processes and is not worth the trouble.

1. **Single File 📁 → .asc files**: the *uploaded file or example file?* radio already
   defaults to **Example File** — leave it there and click **Load selected data.**
   `testfiles/ABREV5.asc` yields 40 trials.
2. Pick a trial → **Load trial**.
3. **Apply cleaning** — reports what each filter discarded (blinks, long, out-of-text, short).
4. **Correct fixations for trial** — runs every algorithm selected under *Choose
   line-assignment algorithm* (defaults `slice` + `DIST`) and plots raw vs. corrected
   over the word boxes. `DIST` is the neural one; this is where the checkpoints load.
5. **Analysis for trial → Show Analysis results**: pick which corrected fixations to
   analyse (one algorithm at a time — `slice` or `DIST`; the measures depend on that
   assignment), then **Run and show analysis**. This is the VAL-4 payload: *Word measures*
   and *Sentence measures* tables, under two tabs — *Analysis without eyekit* and
   *Analysis using eyekit* — each with a **⏬ Download … measures data** button.
6. The intermediate frames (*Show Fixations Dataframe*, *Show Stimulus Dataframes*) have
   their own download buttons, but only once the expander is open. The full run
   configuration dumps via *⏬ Download all single .asc file settings as JSON* — save it
   next to any numbers you cite, since every cleaning switch moves them.

## Where the oracle numbers come from

| File | Reference implementation |
| --- | --- |
| `popEye_funcs.py` (`aggregate_words*`) | what the *Analysis without eyekit* tab actually runs |
| `analysis_funcs.py` | GazeGenie's own word/sentence measure definitions |
| `eyekit_measures.py` | the *Analysis using eyekit* tab |
| `emreading_funcs.py` | EMReading's cleaning/realignment — present, but only `parse_itemID` is wired into the app |
| `classic_correction_algos.py` | the classic line-assignment algorithms |
| `models.py` + `models/*.ckpt` | DIST / DIST-Ensemble |

For a VAL-4 cross-check: run one trial with a known-good line assignment through
both tools and diff the shared measures — FFD, gaze duration (FPRT), go-past (RPD),
total (TFD), skip, regression-in, regression-out. Every systematic difference is
either a bug or a definitional choice the manuscript should name.

Nothing from the clone belongs in this repo — it writes its results into its own
directory, and we cite it rather than vendor it.
