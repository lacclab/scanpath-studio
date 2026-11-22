# What's new

## In development

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

### Fixed

- Compact Python and CLI snippets now omit settings that have no effect in the selected scanpath view. Comparisons and two-scanpath replays keep each reading’s own marker and saccade styles.
- The figure options reference now shows which settings affect a single plot, a replay, a comparison, or a two-scanpath replay. It also explains how to set each scanpath’s fixation index color.
- Share links now reopen PoTeC as scanpath B. If a public comparison corpus is missing, the link opens A and explains how to get B.
- Renaming an uploaded dataset keeps its annotations, comparison selection and saved data together. An upload named “This dataset” can be selected independently in Compare. Share links reopen comparisons between two uploads and tell recipients which files to add if scanpath B is missing.
- Sharing the hand-drawn sample now uses its own text and fixations, including after editing a different drawing.
- Metadata joins, filters and the command-line trial list include readings found only in Words, Fixations or Raw gaze and use the recorded text ID for each reading.
- Data-check reports now produce valid JSON for missing and infinite values in example rows.
- Removing or replacing a metadata upload clears the previous table’s fields in the dataset editor and the import wizard.

## Release v0.46.0

### Added

- Fixation index numbers can sit above, inside or below each fixation: Fixations → Fixation index → Position in the app, order_label_position in the Python API and share links, and --order-label-position in render.
- Clicking Apply under Derive columns from text fills an empty Trial, Participant or Text ID field with a derived column named like one, such as participant, trial or stimulus.
- The import screen says when the Fixations and Words tables' Trial or Text IDs differ only in upper and lower case, and how to make them match.
- The import screen suggests Merge character boxes into word boxes when a word's rows in the Words table are at different positions.
- A setup file now saves and restores Merge character boxes into word boxes, from both the import screen and Edit dataset.

[Browse earlier releases on GitHub](https://github.com/lacclab/scanpath-studio/releases)
