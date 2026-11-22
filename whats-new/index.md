# What's new

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
