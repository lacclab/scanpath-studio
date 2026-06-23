# MultiplEYE dataset

[MultiplEYE](https://multipleye.eu/) is a large multilingual eye-tracking-while-reading
corpus. Scanpath Studio has first-class support for loading it, both from a local
directory and via the browser-upload wizard. This page covers how the corpus is
structured and the modelling decisions the loader makes; the implementation lives
in [`datasets.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/datasets.py)
and [`data.py`](https://github.com/lacclab/scanpath-studio/blob/main/scanpath_studio/data.py).

## Enabling it

MultiplEYE is exposed as a **Public dataset**. Public datasets are currently
behind a feature flag:

```bash
SCANPATH_PUBLIC_DATASETS=1 streamlit run streamlit_app.py
```

Then pick **Public datasets → MultiplEYE** and choose the session / stimulus /
fixation source. A directory load surfaces all the rich side data (below); the
browser-upload path supports a subset (see *Uploading* at the end).

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
  `top_left_x / top_left_y / width / height`.
- Fixation coordinates are `location_x / location_y`; the timestamp is `onset`.
- A stimulus spans `page_1..page_N` plus non-reading screens (`question_*`,
  `familiarity_rating_screen`, `subject_difficulty_screen`) that must be filtered out.

## Modelling decisions

These are the choices the loader makes to fit MultiplEYE into Scanpath Studio's
canonical schema:

- **One trial per `(stimulus, page)`.** `trial_id = "<stim>__page_0N"` (zero-padded
  so the picker sorts pages numerically; displayed as `"<stim> · page N"`),
  `participant_id` = the full session, `text_id` = the stimulus. Pages reuse the
  same on-screen coordinate space, so per-page is the only non-overlapping way to
  plot them.
- **Character AOIs are aggregated into word boxes** — one bounding box per
  `(page, word_idx)`. `word_idx` resets per page, so the word id is effectively
  composite.
- **Centered stimulus on a 1920×1080 monitor.** The stimulus image was shown
  centered on the real screen, so image-relative coordinates are shifted by
  `(monitor − image) / 2` onto their true screen position. This makes the plot
  true-to-scale on the full monitor and lets the page image be placed exactly
  underneath the scanpath.
- **Non-reading screens are dropped**; the pre-filtered `scanpath` file is
  preferred as the fixation source when available.

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
  this sidesteps CJK/RTL font rendering entirely for the text underlay.
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
- **Don't write into the dataset tree** — treat the corpus as read-only.

## Uploading via the browser

The Add-dataset wizard has a **Dataset format** selector with a **MultiplEYE**
preset. Because browsers strip folder structure, identity is recovered from each
row's `source_file`; the lowercase AOI filenames are case-matched to the
CamelCase fixation stimuli. Reading measures and stimulus images require the full
directory tree, so those surfaces are available only on a directory load.
