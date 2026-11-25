# EyeLink EDF import — design

Status: Approved; implemented (experimental) · 2026-11-25

## Intent

Researchers who record with an SR Research EyeLink today open every EDF in Data
Viewer, define interest periods, and export a fixation report and an interest-area
(IA) report before Scanpath Studio can show anything. This feature lets them hand
Scanpath Studio the `.edf` files the experiment wrote and get, with no Data Viewer
step, the three tables the app already works with:

- **fixations** — one row per fixation,
- **words / IA report** — the interest areas (word boxes), with reading measures,
- **raw gaze** — every sample (optional: large and slow, so off by default),

plus the stimulus each screen showed. The main user path is programmatic: someone
tells Claude "add these EDFs to Scanpath Studio", Claude calls the API (or CLI),
and the person then opens the app and sees the dataset like any other.

What must be plottable, in priority order: 1. fixations, 2. the stimulus, 3. the
word boxes, 4. raw gaze. Raw gaze is the lowest priority: a full study's samples
are huge, and if they cost time the work goes to fixations first.

## Goals

- An `.edf` (or a folder of them, or an `.asc`) becomes a saved dataset with
  fixations, word boxes, stimulus images and trial metadata; raw gaze on request.
- Uses `edf2asc`, which the user installs themselves (SR Research licence); we find
  it and run it, never bundle it.
- Fixations are **EyeLink's own** (the tracker's online parser events, `EFIX`), the
  same ones Data Viewer's fixation report starts from.
- Reuse existing packages rather than reimplementing: pymovements reads the ASC.
- Works with just the `.edf`; the word boxes and stimulus come from the files
  Experiment Builder writes beside it, found automatically.
- Experimental: off unless `SCANPATH_EXPERIMENTAL=1`.
- **Scale: a full study.** OneStop is 360 sessions, 28 GB of ASC, about 2M samples
  and 14 s of parsing per session. An import of the whole study must finish in a
  practical time, survive being interrupted, and open in the app without loading
  every sample into memory.

## Non-goals (this round)

- Fixation detection by algorithm (pymovements I-VT / I-DT). Added later as an
  opt-in `fixations="pymovements-idt"`-style option; the design leaves room for it.
- Matching Data Viewer's output exactly (its fixation clean-up, merging, interest
  periods). A later stage; this round only reports how far we are on OneStop.
- Showing a full study's raw gaze in the app (needs an on-demand source).
- A dedicated app screen. Nice to have, not needed; the dataset appears in the
  existing dataset list.
- Reading the EDF directly through SR's `edfapi` (eyelinkio / pyedfread).

## Anti-goals

- Fixations or boxes silently placed on the wrong screen of a trial.
- Writing into the user's experiment folder (output goes to the study folder).
- Shipping, downloading or wrapping SR's licensed binaries.

## Constraints and findings

- An EDF carries samples, EyeLink's fixation/saccade/blink events, `TRIALID` /
  `TRIAL_VAR` messages and `DISPLAY_COORDS`. It does **not** carry the word boxes
  or images: it carries messages pointing at them —
  `!V IAREA FILE aoi/IA_1.ias` and `!V DRAW_LIST graphics/VC_1.vcl`, paths relative
  to the EDF's own folder (`results/<session>/`). A `.vcl` is a timeline of displays
  (`<offset> CLEAR r g b`, `<offset> IMGLOAD TOP_LEFT ../../runtime/images/x.png x y [w h]`);
  a `.ias` is `<offset> RECTANGLE id left top right bottom label`. Experiments may
  also log `!V IAREA RECTANGLE …` / `!V IMGLOAD …` inline instead of in files.
- pymovements 0.28 `gaze.from_asc(events=True, messages=True)` parses a 64 MB
  OneStop ASC in ~14 s: samples (time, pupil, pixel), EyeLink events
  (`fixation_eyelink`, `saccade_eyelink`, `blink_eyelink` with onset/offset), and
  every message. These OneStop ASCs need `encoding="latin-1"`. It pulls polars,
  scikit-learn, scipy and matplotlib, so it is an optional extra.
- On the maintainer's M1 Mac, `/usr/local/bin/edf2asc` and `edfapi.framework` are
  x86_64-only and Rosetta is not installed ("bad CPU type"). The wrapper must name
  that cause and the fix (`softwareupdate --install-rosetta`, or a Developers Kit
  with an Apple Silicon build). Development proceeds from existing ASC files.
- The app already has the pieces downstream: multipart trials (`screen_id`,
  `screen_index`), trial metadata tables, per-row `image_path` stimulus images,
  the raw-gaze table, `measures.compute_per_word_measures` (EyeLink `IA_*`
  definitions, experimental), and `api.add_dataset`. The closest precedent is the
  experimental MultiplEYE format (`datasets.load_multipleye`, `render --multipleye`).

## Approaches

- **A. pymovements reads the ASC; our code does the EyeLink-specific glue.**
  *Chosen.* Reuses a tested parser; adding pymovements' detection later is one
  option. Cost: a heavy optional dependency.
- **B. Our own ASC parser** (extending `update_sample_data._trial_samples`). No new
  dependency, faster, but reimplements parsing (binocular, HREF, encodings, blinks)
  that pymovements already handles. Rejected: against "don't reimplement".
- **C. Read the EDF through `edfapi` (eyelinkio).** Skips `edf2asc`, but needs the
  same SR library (x86-only here), and is less mature. Rejected for now.

## Design

### Pipeline (new module `scanpath_studio/eyelink.py`)

1. **Find `edf2asc`.** `SCANPATH_EDF2ASC` env var, then `PATH`, then the Developers
   Kit's usual install locations per OS. Missing → `Edf2AscNotFoundError` naming
   where to get it. `OSError` "bad CPU type" → the Rosetta message.
2. **Convert.** `edf2asc <edf> -t -c -y -utf8 -e -p <tmp_dir>` (the flags the lab
   already uses, plus `-e`: events and messages only, no samples; argument list, no
   shell). Without samples an ASC is ~40× smaller and parses ~40× faster (OneStop
   `l42_2070`: 1.5 MB and 0.3 s, against 64 MB and 14 s). With raw gaze requested,
   `-e` is dropped. An `.asc` input skips this step.
3. **Parse** with `pymovements.gaze.from_asc(events=True, messages=True)`, trying
   UTF-8 then latin-1.
4. **Trials.** A trial runs from `TRIALID n` to `TRIAL_RESULT` (or the next
   `TRIALID`); `trial_id` is `n`. `participant_id` is the EDF's file stem.
   `TRIAL_VAR name value` pairs become a **trial metadata table** (one row per
   participant × trial).
5. **Screens.** Each `DRAW_LIST` / inline `IMGLOAD` display (each `CLEAR` in a
   `.vcl`, at message time adjusted by its offset) starts a screen that lasts until
   the next display or the trial's end; `screen_id` / `screen_index` number them in
   order. Samples and fixations are assigned to the screen whose span holds their
   onset. A trial with one display is a single-screen trial.
6. **Word boxes.** `.ias` rectangles (and inline `IAREA RECTANGLE`s) for the screen
   they were logged on: `word_id` = IA id, `text` = label, `x`/`y`/`width`/`height`
   from left/top/right/bottom. Screens without boxes (questions, blanks) have none.
7. **Stimulus.** Each screen's display is composed into one PNG (Pillow: the
   `CLEAR` colour, then each `IMGLOAD` at its position and size), written to the
   study folder's `images/` and set as `image_path`. Unsupported VCL commands are skipped and reported.
8. **Fixations.** `EFIX` events: onset, duration, mean x/y (EyeLink's own average
   position, not recomputed from samples), eye; `timestamp_ms` relative to the
   trial's start, as in the bundled demo. pymovements 0.28 keeps an event's
   onset/offset/duration but drops the `EFIX` average position, so the positions
   are read from the `EFIX` lines themselves (a few lines of glue), matched on
   eye and onset.
9. **Raw gaze** (only with `raw_gaze=True`). All samples inside trials: x, y, pupil, eye, `timestamp_ms` on the
   same clock; a sample without a position keeps a missing pupil, not 0
   (`update_sample_data.without_lost_pupil`).
10. **Setup.** `DISPLAY_COORDS` gives the screen size (`canvas_size`).
11. **IA report.** The words table goes through the normal pipeline;
    `measures.compute_per_word_measures` supplies the reading measures (it is
    already behind the experimental flag).

**Finding the session files** (builder's call). The `!V` paths are relative to the
folder the EDF was recorded into, `results/<session>/`. They are resolved against,
in order: an explicit `session_dir=` (CLI `--session-dir`); the input file's own
folder; `<experiment_dir>/results/<file stem>/` when an `experiment_dir=` is given
(CLI `--experiment-dir`), which covers ASCs kept apart from their sessions, as
OneStop's are. The `** CONVERTED FROM` header path is not used: it records a
machine-specific path that rarely survives.

### Full-study scale (builder's call, following the user's "a full study")

The app's saved datasets today are Parquet frames read whole into memory
(`persistence.py`), sized for demo data. A full study's raw gaze (~700M samples
for OneStop) cannot work that way. The precedent is `onestop_shard.py`: one
Parquet file per participant, read only when that participant is shown.

- **Study folder.** An import writes a folder the user names (`--study-dir`,
  required): `fixations/<pid>.parquet`, `words/<pid>.parquet`,
  `raw_gaze/<pid>.parquet` (only when requested; sorted by trial and time, row
  groups per trial),
  `trial_metadata/<pid>.parquet`, `images/` (composed stimulus PNGs,
  de-duplicated by content) and `manifest.json` (per session: source path,
  size, mtime, the session and experiment folders given and the session folder
  found, status, notes, parser version).
- **Per session, in parallel.** Each session is convert → parse → write its own
  files, in a process pool (default: CPU count − 1). Sessions are independent, so
  one bad EDF is reported in the manifest and the rest go on.
- **Incremental and resumable.** A session whose source, folders and parser
  version match its manifest entry is skipped (one left `writing` by a stopped
  import is redone); re-running after an interruption or after adding
  EDFs only does the new work. `--rebuild` forces it.
- **ASC is transient.** Converted to a temp folder, parsed, deleted;
  `keep_asc=True` keeps it beside the study folder.
- **Progress.** `progress.report()` per session, so the CLI prints
  `[n/N] <participant>` as each session finishes and the API takes a callback.
- **Opening in the app.** `add_eyelink_dataset` reads the study folder and saves
  fixations, words and trial metadata through the existing `add_dataset` (Parquet
  in the recovery cache, loaded whole: OneStop is about 3M fixations); the stimulus
  images stay in the study folder and are referenced by absolute `image_path`.
  The local check measures the memory this takes.
- **Raw gaze this round** is opt-in at import and reaches the app only for the
  participants asked for (`add_eyelink_dataset(..., raw_gaze_participants=[...])`),
  through the existing whole-frame path; scripts read any participant with
  `load_eyelink(study_dir, participants=[...])`. A full study's raw gaze in the app
  needs an on-demand, per-participant raw-gaze source: a later round.
- **Images** live in the study folder, so the dataset needs no session files to
  reopen.

Missing session files are not an error: fixations (and raw gaze) still load, and
the result says which boxes / images were not found.

### Surfaces

- **API**: `import_eyelink(paths, study_dir, *, session_dir=None,
  experiment_dir=None, workers=None, rebuild=False, keep_asc=False, progress=None)
  -> StudyReport` builds or updates the study folder; `load_eyelink(study_dir,
  participants=None)` reads it back as frames (words, fixations, raw_gaze when
  imported, trial_metadata, setup, notes) for scripts;
  `add_eyelink_dataset(name, study_dir, raw_gaze_participants=None)` registers the
  study folder as a saved dataset. `import_eyelink` takes `raw_gaze=False`. `paths` is an `.edf` / `.asc`, a
  list, or a folder searched recursively.
- **CLI**: `scanpath-studio import-eyelink PATH… --study-dir DIR [--add NAME]
  [--raw-gaze] [--workers N] [--rebuild]`, and `render --eyelink-study DIR` (hidden from
  `--help` while experimental).
- **App**: no new screen; the dataset appears in the dataset list. Agreed scope
  for this round, an exception to the every-surface rule while experimental.
- **Install**: optional extra `scanpath-studio[edf]` (pymovements). Without it,
  `load_eyelink` raises naming the extra.

### Verification

- Unit tests on a small hand-written ASC + `.ias` + `.vcl` fixture under `tests/`
  (no `edf2asc` in CI); the wrapper tested with a fake `edf2asc` script.
- Local check on OneStop `l42_2070.asc` with its session folder
  `ose_3p_l1_l60_tower_st_mit_l1_latest_widthfix/results/l42_2070/`: fixation counts and positions per trial
  against Data Viewer's fixation report, word boxes against the IA report, and a
  screenshot of a trial in the app. Differences are reported, not tuned away.
- Full OneStop run (360 ASCs): wall time, peak memory of the import, the study
  folder's size, the app's memory and time to open the dataset and draw one
  trial, and a resumed run that skips everything. Raw gaze is timed separately on
  a few sessions.

## Results

Measured on 2026-11-25 on a 10-core Mac with 64 GB of memory, from the OneStop
ASCs (`edf2asc` does not run on this machine), with `scripts/eyelink_onestop_check.py`
for the comparison and scratch scripts for the timings.

**Against Data Viewer (`l42_2070`).** The script imports the session with its
experiment folder and sets it against Data Viewer's paragraph fixation and
interest-area reports (`fixations_P.tsv`, `ia_P.tsv`). Trials are matched on the
`Trial_Index_` trial variable, which both carry; both time a fixation from the
trial's `START` line, so a fixation is paired by its last millisecond, or by its
first when Data Viewer cut its end. All 4,490 of Data Viewer's fixations in its
68 paragraph trials pair with an imported one, at exactly the same position
(largest difference 0.0 px). The remaining differences are where the two draw the
paragraph's edges. Data Viewer cuts a fixation that straddles its interest
period's start or end to that edge (127 fixations, onset differences up to
2,967 ms where a fixation began well before the paragraph
appeared). The import gives a fixation to the screen on which it began, so 67
fixations that straddle the paragraph's onset sit on the screen before. Its
screen runs to the next display, so 5 fixations that begin up to 17 ms after Data
Viewer's interest period ends are on the paragraph screen only in the import.
Word boxes equal the interest areas in all 68 trials (7,736 boxes: id, label,
left, top, width and height).

**Full study (360 ASCs, 28 GB).** One `import_eyelink` call per experiment
folder (26 folders; every session's folder was found), with the default 9
workers:

| Measure | Result |
|---|---|
| Sessions imported / failed | 360 / 0 |
| Wall time | 1,873 s (31 min) |
| Peak memory, whole process tree | 16.0 GiB |
| Study folder | 831 MB (images 718 MB, 13,486 PNGs; fixations 64 MB; words 27 MB; trial metadata 22 MB) |
| Fixations / word boxes / readings | 3,756,552 / 4,004,908 / 27,212 |
| Re-run | 360 skipped, 0.2 s |
| `load_eyelink` of the whole study | 354 s, 3.2 GiB |
| `add_eyelink_dataset` | 392 s, 9.4 GiB peak |
| App: open the dataset and draw one trial (AppTest) | 26 s first run, 4.6 s rerun, 5.8 GiB peak |
| App's dataset | 3,558,393 fixations (1.1 GiB in memory), 4,004,783 boxes (1.2 GiB), 24,876 readings |

Every session has a note; most are expected. 355 sessions have fixations before
their trial's first screen, and 5 have fixations outside every trial (10 in all).
Four sessions of `ose_3n_l1_l60_tower_st` name stimulus images that the folder
does not hold (507 notes); those screens are drawn without them. Fourteen
sessions each lose the word boxes of one trial whose `.ias` file matches no
display (58 notes): its groups sit 19 to 772 ms from the nearest display, beyond
the one-refresh shift the import allows.

The import fits a full study. Opening it in the app does not fit comfortably:
the app holds the whole study's fixations and boxes in memory (5.8 GiB), and
adding the dataset takes 6.5 minutes, nearly all in `load_eyelink`, which
resolves each row's image path one row at a time. Making that per unique path
is a small fix; on-demand, per-participant loading of fixations and words in the
app is the next round's work.

**Raw gaze (3 sessions, 61–73 MB ASCs, 2 workers).** With raw gaze the import
took 57.6 s against 54.9 s for events only, at a peak of 4.4 GiB for both. Raw
gaze added 78 MB to the study folder (6.8M samples), and `load_eyelink` read
them back in 3.2 s.

## Left to the builder

Module and function names, cache layout, the exact VCL / IAS edge cases beyond
`CLEAR`, `IMGLOAD` and `RECTANGLE`, binocular handling (keep both eyes in `eye`),
and how `add_dataset` stores a trial metadata table for the app to restore.

## Suggested order

1. Single-session pipeline, fixations first (parse, trials, screens, fixations,
   boxes, images) on the fixture and on `l42_2070`.
2. Study folder: parallel, incremental, manifest, CLI `import-eyelink`.
3. Saved dataset referencing the study folder.
4. Full OneStop run and the comparison with Data Viewer's reports.
5. Raw gaze, opt-in (samples, the per-participant files, the few-participants path
   into the app).

Later rounds: the app's on-demand raw-gaze source for a full study; pymovements
fixation detection as an option; matching Data Viewer.
