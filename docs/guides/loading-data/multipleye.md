---
title: "MultiplEYE session sets"
description: "Add a MultiplEYE session set from its folder or files, with no columns to map: each stimulus a trial, its pages and questions as screens."
---

# MultiplEYE session sets

!!! info "Beta"
    MultiplEYE support is new and has been tested on one session set so far,
    Zurich Chinese. If yours doesn't load, or something looks wrong, please
    [tell us](https://github.com/lacclab/scanpath-studio/issues/new?template=bug_report.md).
    Feedback of any kind is welcome.

[MultiplEYE](https://multipleye.eu/) labs export each data collection as a
**session set** folder. Scanpath Studio reads it as it is, so there are no
columns to map.

## Add one

<video class="sps-shot" controls muted loop playsinline preload="none"
       poster="../../../assets/workflows/multipleye_poster.webp" data-autoplay
       aria-label="Adding a MultiplEYE session set from its folder, then stepping through its screens">
  <source src="../../../assets/workflows/multipleye.mp4" type="video/mp4">
</video>

1. Choose **+** → :material/upload: **Import files** and name the dataset.
2. Under **Dataset format**, choose **MultiplEYE session set**.
3. Under **Files**, point it at your data:
    - **Folder on this computer** (desktop app or pip install): choose the
      session set's folder with :material/folder_open:.
    - **Upload files** (the online demo): the `*_scanpath.csv` files, plus the
      `*_aoi.csv` files for word boxes. See [what else you can
      upload](#uploading-files).
4. Click :material/check: **Add dataset**. The recording setup is filled in
   for you.

## What you get

- **One trial per stimulus a participant read.** Each MultiplEYE session, such
  as `001_ZH_CH_1_ET1`, is a participant.
- **Pages and questions as screens.** A trial's reading pages and its
  comprehension questions are separate screens: step through them with the
  screen navigator beside the trial picker.
- **The lab's own screen.** The plot is drawn on the monitor the reader saw,
  with each participant's details and the comprehension questions alongside.

Each session set is its own dataset, so several labs or languages can sit side
by side.

## Details

### Uploading files

When you can't point the app at a folder, upload the per-trial
`*_scanpath.csv` (or `*_fixation.csv`) files, and optionally:

- the `*_aoi.csv` files, for word boxes;
- the comprehension-questions workbook and `participant_data.csv`;
- `config_*.py` and `*_lab_configuration.json` from `stimuli_*/config/`, for
  the screen size and font.

The question screens need the `*_fixation.csv` files (the scanpath export has
none), the `*_aoi_questions.csv` files and `stimulus_order_versions_*.csv`.
Page images and reading measures are read only from a folder.

### If something is missing

- **The plot isn't on the full monitor.** The screen size comes from the two
  configuration files. Without them, the Add screen says which values are
  missing, and you can enter them under **Recording setup**.
- **No question screens.** They need `stimulus_order_versions_*.csv`, which
  says which answer layout each reader saw.
- **A screen is skipped.** Screens with no word boxes, such as rating screens,
  are left out.
- **Word labels don't match the page image.** Install the font named in the
  **Stimulus** menu; the app doesn't bundle it.

Corpus Analysis looks at one screen at a time, so its per-text views have a
**Screen** picker beside the text picker.

### Load it in code

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
      -p 001_ZH_CH_1_ET1 -t 001_ZH_CH_1_ET1_Lit_Alchemist_4 --screen page_1 \
      -o page.html
    ```

See [`load_multipleye`][scanpath_studio.datasets.load_multipleye] for its
options. In code, pass `base_font_size` and `font_family` (`--font-size`,
`--font-family`) to match the stimulus font. Share → **Code** writes all of
this for you from a loaded MultiplEYE dataset.
