# What's new

## In development

### Fixed

- The dataset library and the current dataset's Overview show Unknown under Participants for a dataset with no participant column, instead of counting its placeholder reader as 1.

## Release v0.50.0

### Added

- A table button beside the dataset picker opens the Data Management page on the dataset's Tables, and the Annotations subtab's pointer opens its Annotations panel.
- The Axis layout menu offers *Fixation index by word number*: each fixation's place in the reading against the word it landed on.
- Charts can run either axis the other way with Reverse horizontal axis and Reverse vertical axis under Axes (--reverse-x / --reverse-y on the command line, reverse_x_axis / reverse_y_axis in Python), for example to put the first fixation at the top.
- An empty Annotations tab on the Data page has a button that opens Scanpath → Annotations.
- The Scanpath view shows when trial filters are on: a dot on the filter button and a line under the trial picker with how many trials the filters keep, what they are, and a Clear filters button.
- Experimental: import EyeLink EDF recordings without Data Viewer — fixations, word boxes, stimulus screens, trial variables and, on request, raw gaze samples — into a resumable study folder with api.import_eyelink or scanpath-studio import-eyelink, then add it to the app with api.add_eyelink_dataset or --add; turn it on with SCANPATH_EXPERIMENTAL=1 and pip install "scanpath-studio[edf]", and it needs SR Research's edf2asc from the EyeLink Developers Kit.
- The Comparisons grid draws its panels on the plot's axes, so a reading chart such as fixation index by word compares readings the way the main plot draws one, with one shared horizontal range per page (each panel keeps its own on an absolute clock). When every match is filed under the same trial, each panel is captioned by its participant.
- The Comparisons tab can overlay its matches: View → Overlay draws the selected trial and the page's matches on one figure, each in its own colour, with the chip table's rows named in those colours. A link opens it with match_view=overlay beside match=, as do app_link(match_view="overlay") and scanpath-studio open --match-view overlay.
- A link can open the Comparisons subtab with its Match field chosen: Share → Link writes `match=` when copied from Comparisons, as do `api.app_link(match=…)` and `scanpath-studio open --match`.
- A repository script, scripts/eyegenbench_to_studio.py, adds the corpora of a local EyeGenBench checkout, with every model's generated readings, as datasets the app lists: word-level fixations, each model's version of a trial matched to the human one by source_trial, and each trial's held-out regime.
- The replay can grow the current fixation over its duration and fade the fixations before it, with their numbers and the saccades, at a start size and faded opacity you choose (Playback settings, links, `render --grow-fixations` / `--fade-fixations`, and `animate_scanpath`).

### Changed

- Leaving the Add-dataset wizard before uploading anything no longer warns that uploaded files will be lost.
- The Add-dataset wizard lists the file formats it accepts and the size limit before the first upload.
- A comparison on reading-chart axes (for example fixation index by word) can now be an overlay, and the Saccades layer joins each reading's fixations in order on any chart. A chart comparison, link or settings file with the default Overlay layout now opens as one panel instead of side by side (choose Side by side for the old figure), and charts that showed no line now show one unless Saccades is off.

### Fixed

- A burst of seeks on the replay's time slider draws only the last frame, without reporting errors for the frames it replaced.
- The Data page's experimental Stimuli table (with SCANPATH_EXPERIMENTAL=1), which shows each version of a screen with the readers who saw it since v0.49.0, now says so in its caption, as the Texts table does.
- The Data page's Texts table keeps each word whose Word ID is blank as a word of its own, after its line's numbered words, instead of folding them into one word that depended on the row order.
- Leaving the Add-dataset wizard after uploading a file no longer stops the bundled demo from loading ("Screen ID is set in only one table").
- A dataset loaded from its fixations alone, with no word boxes or screen positions, now works on reading charts: the Comparisons grid draws its matches, plot_scanpath, compare_scanpaths and render draw it instead of refusing it for lacking coordinates, and the plot no longer warns about missing positions on a chart that draws none.

[Browse earlier releases on GitHub](https://github.com/lacclab/scanpath-studio/releases)
