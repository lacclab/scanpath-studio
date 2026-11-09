---
title: "MultiplEYE session sets"
description: "Add a MultiplEYE session set from its folder or from its files: each stimulus a trial, its pages and comprehension questions as screens, on the lab's own screen."
---

# MultiplEYE session sets

[MultiplEYE](https://multipleye.eu/) is a multilingual eye-tracking-while-reading
project. Its labs export each data collection as a **session set**: a folder of
per-trial CSVs, the stimuli with their character areas of interest, and the
experiment's configuration. Scanpath Studio reads a session set as it is laid
out, so there are no columns to map.

The format was built and tested on one session set, Zurich Chinese
(`MultiplEYE_ZH_CH_Zurich_1_2025`).

## Add one

1. Choose **+** → :material/upload: **Import files** and name the dataset.
2. Under **Dataset format**, choose **MultiplEYE session set**.
3. Under **Files**, choose where it comes from:
    - **Folder on this computer** (the desktop app or a pip install): type the
      session set's folder, or choose it with :material/folder_open:. It is the
      folder that holds `scanpaths/` (or `fixations/`) and `stimuli_*/`.
      **Fixations from** picks the export the reading pages are read from:
      `scanpaths`, where each fixation is already mapped to its word, or
      `fixations`, where it is not.
    - **Upload files**: the per-trial `*_scanpath.csv` or `*_fixation.csv`
      files, and optionally the `*_aoi.csv` files for word boxes, the
      comprehension-questions workbook, `participant_data.csv` and the two
      configuration files. On a server other machines can reach, such as the
      online demo, uploads are the only choice.
4. **Comprehension-question screens** is on by default. Turn it off to load the
   reading pages only.
5. Check **Recording setup**, which is filled in from the session set's
   configuration, and click :material/check: **Add dataset**.

Each session set you add is its own dataset, so several labs or languages can
sit side by side in the dataset list.

## The screen

A session set's coordinates are relative to its stimulus image, which the
experiment drew centred on a larger monitor. The app reads both sizes from the
session set itself:

- `stimuli_*/config/config_*.py`: `RESOLUTION`, `IMAGE_WIDTH_PX` /
  `IMAGE_HEIGHT_PX`, `SCREEN_SIZE_CM`, `DISTANCE_CM`, `FONT_SIZE` and `FONT`;
- `stimuli_*/config/*_lab_configuration.json`: `Monitor_resolution_in_px`,
  `Screen_size_in_cm` and `Distance_in_cm`, used where the first file leaves
  a value out.

With the monitor resolution and the image size, every fixation and word box is
moved to where the reader saw it, and the plot is drawn on the real monitor.
Without either one, nothing is assumed: the coordinates stay relative to the
image, the screen is estimated from the data, and the Add screen says which
values are missing so you can enter them under **Recording setup**.

## How the trials are built

A session set has no ID columns. Participant, session, trial and stimulus come
from the folder and file names.

- **A trial is one reading of one stimulus**, such as `Lit_Alchemist_4`. Its
  screens are the reading pages, `page_1` to `page_N`, then the
  comprehension-question screens, `question_<id>`. Step through them with the
  screen navigator beside the trial picker.
- **A participant is a session**, such as `001_ZH_CH_1_ET1`. ET1 and ET2 read
  different stimuli.
- **The screen order comes from the reader's own fixations**, so a reader's
  shuffled question order is kept. `screen_kind` is `reading` or `question`.
- **Question screens always come from `fixations/`**, because the `scanpaths/`
  export has only the reading pages. Their word boxes depend on which answer
  layout the reader saw, which is looked up in
  `stimuli_*/config/stimulus_order_versions_*.csv`. Without that file the
  question screens are left out.
- **Character areas of interest are joined into word boxes**, one per word on
  each screen.
- **A screen with no word boxes is left out**, such as the rating screens,
  which have no areas of interest, or a page missing from the AOI files.

## What else is read

- **Participant metadata** from `participant_data.csv`: age, gender, native
  language and education, shown beside each trial and usable as filters.
- **Comprehension questions** from
  `stimuli_*/multipleye_comprehension_questions_*.xlsx`, shown under the
  stimulus text.
- **Reading measures** from `reading_measures/` (folder only): first fixation
  duration, gaze duration, go-past time, total fixation duration, skips and
  regressions, used by Corpus Analysis.
- **Page images** from `stimuli_*/stimuli_images_*/` and
  `stimuli_*/question_images_*/` (folder only), drawn under the scanpath with
  **Stimulus** → **Image** → **Show**.
- **The typeface** from `FONT_SIZE` and `FONT`, so the word labels are drawn at
  the size and in the font of the stimulus. The font file is not bundled:
  install it for the labels to match the image exactly. The app names the font
  and links to it in the **Stimulus** menu.

## Load it in code

=== "Python"

    ```python
    import scanpath_studio as sps

    words, fixations = sps.load_multipleye("data/MultiplEYE_ZH_CH_Zurich_1_2025")
    pid, tid = sps.list_trials(words, fixations).iloc[0]
    fig = sps.plot_scanpath(words, fixations, pid, tid, screen="page_1")
    ```

=== "CLI"

    ```bash
    scanpath-studio render --multipleye data/MultiplEYE_ZH_CH_Zurich_1_2025 --list-trials
    scanpath-studio render --multipleye data/MultiplEYE_ZH_CH_Zurich_1_2025 \
      -p 001_ZH_CH_1_ET1 -t Lit_Alchemist_4 --screen page_1 -o page.html
    ```

[`load_multipleye`][scanpath_studio.datasets.load_multipleye] takes `sessions`
and `stimuli` to read part of a session set, `fixation_source`, and
`include_question_screens`. `render` takes `--multipleye-fixations` and
`--no-question-screens`. In code the screen comes with the data, but the font
does not: pass `base_font_size` and `font_family` (`--font-size` and
`--font-family`) for the session set's typeface. Share → **Code** writes this
call for a MultiplEYE dataset, with the folder it was read from and the font.

Corpus Analysis describes one screen at a time: word IDs are unique within a
screen, so its per-text views have a **Screen** picker beside the text picker.
