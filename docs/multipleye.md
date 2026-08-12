# MultiplEYE dataset

[MultiplEYE](https://multipleye.eu/) is a large multilingual eye-tracking-while-reading
corpus. Scanpath Studio has first-class support for loading it, both from a local
directory and via the browser-upload wizard. This page covers how the corpus is
structured and the modelling decisions the loader makes; the implementation lives
in [`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py)
and [`data.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/data.py).

## Enabling it

MultiplEYE is exposed as a **Public dataset**, which is on by default. To hide
the public-dataset sources (e.g. on a deployment that should only take uploads),
set `SCANPATH_PUBLIC_DATASETS=0`.

Pick **Public datasets → MultiplEYE**, point *Data directory* at a session
set (the *Expected files* panel lists the layout it looks for), and choose the
**fixation source** (`scanpaths` or `fixations`). The whole session set loads —
use the **Narrow by** trial filters to focus on specific readers or stimuli. A
directory load surfaces all the rich side data (below); the browser-upload path
supports a subset (see *Uploading* at the end).

## How the corpus is laid out

A MultiplEYE release has **no identity columns** — participant, session, trial,
and stimulus are encoded only in the folder and file names.

- Per-session folders are named `{PID}_ZH_CH_1_ET{1|2}`. Each reader is a
  *session*; **ET1 and ET2 read disjoint stimuli**, so the reader key must be
  participant **+** session, not participant alone.
- Each session folder holds `fixations/`, `saccades/`, `scanpaths/`,
  `reading_measures/`, `raw_data/`, and `metadata/`, with one comma-separated CSV
  per trial named `{session}_trial_{n}_{Stim}_{id}_{kind}.csv`.
- Word/AOI boxes live separately under `stimuli_.../aoi_stimuli_*/{stim}_{id}_aoi.csv`.
  They are **character-level**, **stimulus-level** (no participant), with columns
  `top_left_x / top_left_y / width / height`. The comprehension questions' AOIs are
  in a sibling `{stim}_{id}_aoi_questions.csv`, one set of rows per **answer
  layout version**.
- Fixation coordinates are `location_x / location_y`; the timestamp is `onset`.
- A stimulus spans `page_1..page_N`, then the comprehension-question screens
  (`question_<id>`), then `familiarity_rating_screen_*` and
  `subject_difficulty_screen`.

## Modelling decisions

These are the choices the loader makes to fit MultiplEYE into Scanpath Studio's
canonical schema:

- **One trial per reading of a stimulus, with every screen inside it.**
  `trial_id = text_id = "<stim>"`, `participant_id` = the full session, and the
  screens the reader saw are `screen_id` values — `page_1 … page_N` and
  `question_<id>` — each with its own coordinate space. Step through them with
  the screen navigator beside the trial picker, `?screen=` on a share link,
  `render --screen` / `--all-screens` / `--list-screens`, or
  `plot_scanpath(..., screen=…)`. Pages reuse the same on-screen coordinates, so
  screens (never a merged trial) are what keeps them from stacking.
- **`screen_index` comes from the reader's own fixation onsets**, never from the
  screen name. Reading pages are presented in page order, but the **question
  order is shuffled per reader**, so a name-derived order would silently
  reorder the trial.
- **`screen_kind` is `reading` or `question`.** The rating and difficulty screens
  are excluded: the corpus ships no AOI file for them, and Scanpath Studio
  rejects a screen with no word boxes by design.
- **Question fixations always come from `fixations/`**, whatever the *fixation
  source* setting says — the `scanpaths/` export is pre-filtered to reading
  pages, so it is the only place they survive. A trial therefore mixes two
  provenances: reading pages from the source you picked (word-tagged when that is
  `scanpaths`), question screens from the raw fixation export (no word linkage).
  `screen_kind` is what tells them apart.
- **Question word boxes are per reader.** Which answer layout a reader saw is
  looked up in `stimuli_*/config/stimulus_order_versions_*.csv` by their bare
  participant id, and that version selects both the AOI rows and the question
  image. Within a screen the five blocks (question stem, target, three
  distractors) each restart `word_idx` at 0, so the loader orders the blocks by
  the geometry of their first character and runs one counter across them — the
  word id is unique within the screen and in reading order, and the block name is
  kept as a per-word `aoi_block` column.
- **Character AOIs are aggregated into word boxes** — one bounding box per
  `(screen, word_idx)`. `word_idx` resets per screen, so word ids are unique
  within a screen, not within a trial.
- **Centered stimulus on a 1920×1080 monitor.** The stimulus image was shown
  centered on the real screen, so image-relative coordinates are shifted by
  `(monitor − image) / 2` onto their true screen position. This makes the plot
  true-to-scale on the full monitor and lets the page image be placed exactly
  underneath the scanpath. Question images are the same size, so they line up the
  same way.
- **A screen with no word boxes is dropped, not guessed** — a question screen
  whose layout version is unknown, or a page missing from the AOI file. Likewise
  a page a reader never fixated gets no boxes, so a partial session degrades
  instead of failing to load.

To load the reading pages alone, pass `include_question_screens=False` to
`load_multipleye` / `multipleye_raw_frames`.

## Rich side data

When loading from a directory, several extra surfaces are populated by enriching
the loaded frames so the app's existing panels render them:

- **Reader metadata** from `participant_data.csv` (age, gender, languages, …) →
  Trial Info chips and Corpus Analysis grouping facets.
- **Comprehension questions** from `multipleye_comprehension_questions_*.xlsx` →
  the Stimulus & questions panel, joined by stimulus.
- **Pre-computed reading measures** from `reading_measures/` → canonical `IA_*`
  columns attached to **per-reader** word boxes (FFD, FPRT, RPD, TFT, skip,
  regression counts). The app prefers these pre-aggregated columns over recomputing.
- **Stimulus page images** rendered as a background layer at exact coordinates —
  this sidesteps CJK/RTL font rendering entirely for the text underlay. Question
  screens get their own image from the reader's answer-layout version directory
  (`question_images_*/question_images_version_<N>/`).
- **Reading typeface** from the stimulus config (`config_*.py` — `FONT_SIZE` +
  `FONT`) stamped as `stimulus_font_px` / `stimulus_font_family`. On a dataset
  switch the app snaps its font controls to the exact size (e.g. 28 px) and CJK
  font, so the overlaid word labels line up with the printed stimulus text
  instead of being inferred from box geometry in a generic font.
- **Session (ET1/ET2)** and **genre** (Lit / Arg / Ins / Enc / PopSci) as filter facets.

## Caveats

- **Install the stimulus font for exact text alignment.** The app reads the
  experiment's font name from the stimulus config and snaps to it, but the font
  file itself isn't bundled. If it isn't installed on the machine viewing the
  app, the browser falls back **per script** — CJK glyphs land (every CJK font is
  full-width-square), but a CJK font's **Latin** glyphs are half-width, so a
  fallback Latin font renders wider and the overlaid labels drift (URLs/digits
  are the worst offenders). Install the named font (the app shows which one and a
  download link under **Text font**) and reload for a pixel match, or just turn
  on the **stimulus image** to read the original text. A future RTL sample
  (Hebrew/Arabic) will additionally need text-direction handling. The stimulus
  page-image background is the reliable fallback for scripts the renderer can't
  lay out.
- **Corpus Analysis describes one screen at a time.** Word ids are unique within
  a *screen*, so the per-text views take a **Screen** picker beside the Text
  picker and every figure — per-reader profiles, the word × reader heatmap, the
  cohort band, word difficulty on the stimulus, the feature scatter and the
  skip/regression rates — describes the screen you picked. There is no
  "all screens" option on purpose: a profile across screens would be keyed on a
  `word_id` that means a different word per page, and the stimulus view draws
  word *boxes*, which are measured against their own screen's origin, so two
  screens' geometry would be drawn on top of each other. The Groups tab's word
  profile shows the first screen and says so. (Making word ids stimulus-global
  instead would diverge from the corpus's published `word_idx`.)
- **Don't write into the dataset tree** — treat the corpus as read-only.

## Uploading via the browser

The Add-dataset wizard has a **Dataset format** selector with a **MultiplEYE**
preset. Because browsers strip folder structure, identity is recovered from each
row's `source_file`; the lowercase AOI filenames are case-matched to the
CamelCase fixation stimuli. Reading measures and stimulus images require the full
directory tree, so those surfaces are available only on a directory load.

Reading pages become screens from the uploaded AOI + fixation files alone. The
**question screens additionally need two files**, both dropped into the *Word AOI
CSVs* box alongside the ordinary `*_aoi.csv` files:

- the stimulus' `*_aoi_questions.csv`, and
- `stimulus_order_versions_*.csv` — without it the reader's answer layout is
  unknowable, and picking one at random would draw entirely plausible boxes in
  the wrong places, so the question screens are skipped with a warning instead.

Upload the `*_fixation.csv` files (not only the `*_scanpath.csv` ones) for the
trials whose question screens you want: the scanpath export does not contain
them. A stimulus whose `*_aoi.csv` you did not upload has no word boxes at all,
so its fixations are dropped (with a warning) rather than left as screens the
plot cannot draw.
