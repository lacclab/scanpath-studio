# What's new

## In development

### Added

- Use the arrow keys to browse trials and Space to play or pause a scanpath replay, including from the replay time slider.
- The check command reports how many rows were read and checked, including why a table supplied no usable rows. Use --json-report to save these counts alongside the findings.
- Inspect the readings behind a cohort value, compare profile revisions, download a methods draft, calculate within-participant contrasts, and rerun a two-group word difference from its recipe.
- CSV bundles now include a type and unit dictionary and an editable R reader that preserves identifiers such as 01, literal NA identifiers, and missing measurements.
- Preview bundle contents lists planned per-trial paths, table columns and selected annotations, and identifies stimulus words and images that may accompany a figure.
- The interaction benchmark measures opening a first trial, switching readings and recoloring markers, with counts of data reads, normalization, selections and figure builds for each action.
- A packaged synthetic study includes two source tables, recording setup, a tagged exclusion, figure settings and a cohort recipe written by Scanpath Studio v0.37.0. The example recreates its manuscript figure and checks the original results table.
- Export can proof a side-by-side or stacked comparison at its manuscript width. Check the label sizes in points, save a vector SVG with physical dimensions, and restore the panel selection and shared color limits for a revision.
- Use Previous fixation and Next fixation above a replay to inspect the fixation’s onset, duration and assigned word. The shared HTML replay keeps these controls when downloaded. Long replays now build the live view from a single trace template.
- Retry failed figures and individual layer files in the last export bundle while the selected data and settings still match. Successful files keep their contents and paths.
- Review incoming trial and screen annotations before applying them, inspect both versions of disputed notes, and keep independent edits from two local sessions.
- Compare received readings with the experiment run sheet, inspect data-check findings by reading, preview changed reading IDs, and download inclusion counts and individual exclusion reasons.
- Labs can attach a title, authors, version, DOI or preferred wording to an uploaded dataset. Cite and export bundles include the saved credits and identify the second dataset of a comparison. Programmatic comparison bundles include both dataset references in `CITATION.bib`. Open an included settings file to restore both readings, their selected screens and the comparison layout.
- In Python, load data with `include_source_cells=True` and call `explain_fixation()` to see a fixation’s input row, file, original units and word assignment. Merged fixations list their contributing rows.

### Changed

- Corpus Analysis shows the participant profiles immediately after the measure and aggregation pickers. The cohort overlay, normalization and measure definition sit below the chart.
- Fixation markers and saccades accept opacity from 0 to 1 in the app, shared settings, CLI and Python API, including fully transparent marks.
- Open the import wizard directly from the welcome tour, find upload buttons by table name, and use the guide with reduced motion.
- Choose a tool in the Essentials trial picker to open it in Full. Undo and Redo describe the value they will restore, Share explains what the recipient needs, and the import guide opens folded on narrow screens.
- Large bundles use less memory when writing gaze CSVs and spend less time assigning duplicate filenames and preparing single-screen trials.
- Switching trials reuses the current table’s position index, matching metadata is folded in groups, and out-of-text tests and cohort bootstrap intervals use bounded memory.
- After Add dataset identifies an unresolved mapping, activate its message to focus the matching control. Selecting the duration column clears its warning and shows how two source values convert to milliseconds.
- On phones, the Scanpath view choices sit directly below the figure, ahead of Export and the other trial panels.
- Word-box heatmaps show the current reading’s dwell-time or count limits and can reuse those limits on other readings. Grayscale comparisons distinguish readers with filled and hollow markers and solid and dashed lines. A snapped illustration can be viewed beside the same trial’s original coordinates.
- Data Management puts Add dataset above the list, shows full names on phones and restores click-to-sort column headers. Corpus Analysis opens with the analysis controls and keeps figure styling and the inclusion report below the results.
- Essentials and Full share the same four view tiles and Palette. Full adds comparison, animation settings, saved designs, and layers below them.
- Data Management opens on the selected dataset with trial averages, six browsable tables and recording quality checks. The dataset library and saved work have their own tabs.
- The fixation size legend starts hidden. Turn on Fixation sizes under Figure & canvas → Legends to include it in a figure.

### Removed

- Removed the undocumented Python helpers `scanpath_studio.export.pair_export` and `ComparisonSide`. Comparison figures can be saved from the app or with `save_figure`.
- Retired the individual workflow GIFs in `assets/workflows/`. The docs carry the videos and posters, and the README keeps its overview animation.

### Fixed

- Static figure exports now require Kaleido 1.5.2 or later to prevent intermittent failures while the browser loads its plotting scripts.
- Cohort figures use finite observations, weight repeated readings consistently, distinguish stimulus versions, and show gaps and units for the selected estimate.
- Setting a reading’s fixation opacity to zero now makes its markers transparent in comparisons and two-reading replays.
- Single and comparison heatmaps use the same word assignments and label log scales in their original units. Relative marker sizing uses both visible readings in Compare. Heart outlines respond to the selected width, and a category containing “heatmap” stays in the fixation export layer.
- Two local app processes saving different review notes to the same recovery folder now preserve both edits. Clearing a folder waits for an active save or restore to finish.
- Corpus Analysis distribution charts label within-participant z-scores in standard deviation units.
- Comparison tables preserve lab columns that share a name with the dataset or A/B labels, and replacing attached metadata keeps the fields explicitly selected for publication.
- Export previews follow the selected format, screen and file pattern. Incomplete scopes produce no trials, and screen selections include only those screens’ annotations and their parent trial notes.
- Figure settings files restore narrowed fixation windows for both readings. Shared titles and captions preserve linguistic tags such as `<NP>`. Generated captions include raw gaze when the figure draws usable samples.
- Importing large fixation tables uses less memory when recording source filenames.
- Headless trial listings leave stderr quiet. Render and Share → Code preserve comparison IDs containing colons, uploaded column names containing commas, single-table inputs, and exact hover field selections.
- Recipes, annotations, column mappings and multipart manifests accept UTF-8 BOMs and Unicode JSON encodings. An unmatched reading in a screen listing points to the available trials.
- Table imports preserve literal reader IDs, report overlong records by line, identify the worksheet read, and show differences from a pilot’s saved mapping.
- The OneStop manuscript figures include the full recorded scanpaths, and the replay montage preserves the bottom of its final frame.
- Word labels in mixed-script passages follow each word's writing direction. Two sample CSVs show a Hebrew and Arabic reading with English, numbers, punctuation and a return fixation.
- Opening a direct link to Corpus Analysis, Data Management, or Help on a first visit now opens the requested destination without the welcome tour taking over.
- The manuscript scripts use canonical data columns and compare geometry-derived reading measures against EyeLink values. The corpus figure identifies the passage by its recorded ID and selects it consistently when reader counts tie. The benchmark uses the same readers in both input tables and labels post-stage memory measurements. The change verifier checks restored options and fresh output files.
- Custom bundle paths extract on Windows even when participant or trial IDs use reserved device names or end in a period.
- Publication-sized PNG layers use the composite’s dimensions and print density. Re-exporting layers removes obsolete files from the previous export. A failed render preserves the previous figure or layer set. Multipart figures retain their recorded screen numbers.
- The desktop launcher waits for Streamlit's health response before opening the window. Update instructions preserve VCS branches, forks and package subdirectories and identify installs pinned to a commit.
- Categorical fixation colors stay consistent across readings, and the index chart respects the selected connector style, width and opacity. Figure descriptions count the fixations and gaze samples drawn. With stimulus redaction on, the Hover and Export panels identify selected text fields that can still appear in HTML.
- Replays preserve recorded gaps before long fixations. At a low GIF or MP4 frame cap, each image shows the fixations reached by its display time. A late fixation can fall after the last image.
- If the local recovery cache cannot be locked, the app opens with saving paused and keeps the saved session available for a later launch.
- HTML replays build frames as you play or seek, reducing memory use for long readings in the app and in saved files.
- Commands copied from Share now accept participant, trial and screen IDs that start with a hyphen on either side of a comparison.
- Comparison links and generated Python and CLI commands preserve each reader’s marker fill, colors and line styles when using the print palette.
- A tab with an older recovery copy warns you before it can overwrite newer saved work. Your edits stay available in the tab to export.
- Saving a static figure uses the shared renderer and reports when an installed browser has not finished starting Kaleido. HTML, PNG, SVG and PDF retain their citation.
- The replay timer is easier to read in dark mode.

## Release v0.47.0

### Added

- Python 3.15 is now supported and tested.
- Reproduce a downloaded per-word cohort profile with its JSON recipe and the original data in Python or with the recipe command.
- Undo and Redo beside Reset visualization step through recent plot changes, including presets and resets.
- Help opens the documentation and What’s new for your Stable or Dev build. The Dev docs include changes since the last release.

### Changed

- Clearer, more welcoming wording throughout the app and documentation, including tutorials, data import, saved work, analysis and exports.
- Full adds fixation-index and elapsed-time charts for horizontal and vertical screen position. Switching between Essentials and Full keeps the current plot and export choices. Choosing a design or resetting the visualization now replaces earlier axis and styling choices even after their controls have been closed. Shared links check imported recording tables before opening a view, and the import wizard identifies missing word-box fields.
- Fixation index size, color, and position now share one definition across plot controls, saved settings, share links, and generated commands.
- Draw and replay fixations directly on a passage, reopen named drawings to edit them, and share the matching draft for use in the app or a script.
- Updated the documentation screenshots and demos to show the current controls.

### Fixed

- Compact Python and CLI snippets now omit settings that have no effect in the selected scanpath view. Comparisons and two-scanpath replays keep each reading’s own marker and saccade styles.
- The figure options reference now shows which settings affect a single plot, a replay, a comparison, or a two-scanpath replay. It also explains how to set each scanpath’s fixation index color.
- Share links now reopen PoTeC as scanpath B. If a public comparison corpus is missing, the link opens A and explains how to get B.
- Renaming an uploaded dataset keeps its annotations, comparison selection and saved data together. An upload named “This dataset” can be selected independently in Compare. Share links reopen comparisons between two uploads and tell recipients which files to add if scanpath B is missing.
- Sharing the hand-drawn sample now uses its own text and fixations, including after editing a different drawing.
- Metadata joins, filters and the command-line trial list include readings found only in Words, Fixations or Raw gaze and use the recorded text ID for each reading.
- Data-check reports now produce valid JSON for missing and infinite values in example rows.
- Removing or replacing a metadata upload clears the previous table’s fields in the dataset editor and the import wizard.

[Browse earlier releases on GitHub](https://github.com/lacclab/scanpath-studio/releases)
