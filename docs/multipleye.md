# MultiplEYE dataset

> **Not on the docs site (DATA-54).** MultiplEYE is held back from the
> beta: its data is not openly available yet, and the loader was built
> and tested on one sample. The app offers it only with
> `SCANPATH_EXPERIMENTAL=1`; `load_multipleye` and `render --source
> multipleye` still work. This page is kept for the people using it.

[MultiplEYE](https://multipleye.eu/) is a multilingual eye-tracking-while-reading
corpus. Scanpath Studio loads a MultiplEYE session set from a local directory;
the loader was built and tested on the Zurich Chinese (ZH-CH) sample. This page
covers how the corpus is structured and the modelling decisions the loader
makes.

## Loading it

On the 🗂️ **Data** page, click **MultiplEYE** in **📂 Available datasets**, then
**✏️ Edit** it: point *Data directory* at a session set (the *Expected files*
panel lists the layout it looks for) and choose the **fixation source**
(`scanpaths` or `fixations`). The
whole session set loads — use the **filter funnel** beside the trial picker
(text and participant pickers, then the condition filters) to focus on specific
readers or stimuli.

!!! note "On a server other machines can reach"
    When the app is served to other machines (the hosted demo, or
    `--server.address 0.0.0.0`), the *Data directory* box and the 📁 folder
    picker are turned off: the corpus is read from the server's
    configured data location, and whoever runs it places the files there — or,
    on a trusted network, starts it with `SCANPATH_LOCAL_FS=1`. See
    [Launch](cli.md#launch).

## How the corpus is laid out

A MultiplEYE release has **no identity columns** — participant, session, trial,
and stimulus are encoded only in the folder and file names.

- Each export kind (`fixations/`, `scanpaths/`, `reading_measures/`, …) is a
  top-level folder holding one folder per reader session, named
  `{PID}_{LANG}_{COUNTRY}_{LAB}_ET{1|2}` (e.g. `001_ZH_CH_1_ET1`). **ET1 and ET2
  read disjoint stimuli**, so the reader key is participant **+** session. Each
  session folder has one comma-separated CSV per trial, named
  `{session}_trial_{n}_{Stim}_{id}_{kind}.csv`.
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
  `render --screen` / `--all-screens` / `--list-parts`, or
  `plot_scanpath(..., screen=…)`.
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
  image.
- **Character AOIs are aggregated into word boxes** — one bounding box per
  `(screen, word_idx)`. `word_idx` resets per screen, so word ids are unique
  within a screen, not within a trial.
- **Centered stimulus on the ZH-CH sample's 1920×1080 monitor** (fixed in the
  loader, not read from the session set). The stimulus image was shown
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
`load_multipleye`.

## Rich side data

A directory load also reads:

- **Reader metadata** from `participant_data.csv` (age, gender, languages, …) →
  the trial chip strip and Corpus Analysis grouping facets.
- **Comprehension questions** from `multipleye_comprehension_questions_*.xlsx` →
  the Stimulus & Context panel, joined by stimulus.
- **Pre-computed reading measures** from `reading_measures/` → canonical `IA_*`
  columns attached to **per-reader** word boxes (FFD, FPRT, RPD, TFT, skip,
  regression counts). They follow MultiplEYE's definitions, not the app's, and are
  used instead of the app's own computation.
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
  on the **stimulus image** to read the original text.
- **Corpus Analysis describes one screen at a time.** Word ids are unique within
  a *screen*, so the per-text views take a **Screen** picker beside the Text
  picker; the Groups tab's word profile shows the first screen.
