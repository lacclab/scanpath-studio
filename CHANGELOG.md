# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changes not yet released are one file each in [`changelog.d/`](changelog.d/);
`scripts/changelog_fragments.py release` writes them in here.

## [0.50.0] - 2026-11-26

### Added
- A table button beside the dataset picker opens the Data Management page on the dataset's Tables, and the Annotations subtab's pointer opens its Annotations panel. ([#639](https://github.com/lacclab/scanpath-studio/issues/639), [#640](https://github.com/lacclab/scanpath-studio/issues/640))
- The Axis layout menu offers *Fixation index by word number*: each fixation's place in the reading against the word it landed on. ([#650](https://github.com/lacclab/scanpath-studio/issues/650))
- Charts can run either axis the other way with Reverse horizontal axis and Reverse vertical axis under Axes (--reverse-x / --reverse-y on the command line, reverse_x_axis / reverse_y_axis in Python), for example to put the first fixation at the top. ([#650](https://github.com/lacclab/scanpath-studio/issues/650))
- An empty Annotations tab on the Data page has a button that opens Scanpath → Annotations. ([#652](https://github.com/lacclab/scanpath-studio/issues/652))
- The Scanpath view shows when trial filters are on: a dot on the filter button and a line under the trial picker with how many trials the filters keep, what they are, and a Clear filters button. ([#652](https://github.com/lacclab/scanpath-studio/issues/652))
- Experimental: import EyeLink EDF recordings without Data Viewer — fixations, word boxes, stimulus screens, trial variables and, on request, raw gaze samples — into a resumable study folder with api.import_eyelink or scanpath-studio import-eyelink, then add it to the app with api.add_eyelink_dataset or --add; turn it on with SCANPATH_EXPERIMENTAL=1 and pip install "scanpath-studio[edf]", and it needs SR Research's edf2asc from the EyeLink Developers Kit. ([#658](https://github.com/lacclab/scanpath-studio/issues/658))
- The Comparisons grid draws its panels on the plot's axes, so a reading chart such as fixation index by word compares readings the way the main plot draws one, with one shared horizontal range per page (each panel keeps its own on an absolute clock). When every match is filed under the same trial, each panel is captioned by its participant. ([#659](https://github.com/lacclab/scanpath-studio/issues/659))
- The Comparisons tab can overlay its matches: View → Overlay draws the selected trial and the page's matches on one figure, each in its own colour, with the chip table's rows named in those colours. A link opens it with match_view=overlay beside match=, as do app_link(match_view="overlay") and scanpath-studio open --match-view overlay. ([#662](https://github.com/lacclab/scanpath-studio/issues/662))
- A link can open the Comparisons subtab with its Match field chosen: Share → Link writes `match=` when copied from Comparisons, as do `api.app_link(match=…)` and `scanpath-studio open --match`. ([#663](https://github.com/lacclab/scanpath-studio/issues/663))
- A repository script, scripts/eyegenbench_to_studio.py, adds the corpora of a local EyeGenBench checkout, with every model's generated readings, as datasets the app lists: word-level fixations, each model's version of a trial matched to the human one by source_trial, and each trial's held-out regime. ([#665](https://github.com/lacclab/scanpath-studio/issues/665))
- The replay can grow the current fixation over its duration and fade the fixations before it, with their numbers and the saccades, at a start size and faded opacity you choose (Playback settings, links, `render --grow-fixations` / `--fade-fixations`, and `animate_scanpath`). ([#670](https://github.com/lacclab/scanpath-studio/issues/670))

### Changed
- Leaving the Add-dataset wizard before uploading anything no longer warns that uploaded files will be lost. ([#652](https://github.com/lacclab/scanpath-studio/issues/652))
- The Add-dataset wizard lists the file formats it accepts and the size limit before the first upload. ([#652](https://github.com/lacclab/scanpath-studio/issues/652))
- A comparison on reading-chart axes (for example fixation index by word) can now be an overlay, and the Saccades layer joins each reading's fixations in order on any chart. A chart comparison, link or settings file with the default Overlay layout now opens as one panel instead of side by side (choose Side by side for the old figure), and charts that showed no line now show one unless Saccades is off. ([#660](https://github.com/lacclab/scanpath-studio/issues/660))

### Fixed
- A burst of seeks on the replay's time slider draws only the last frame, without reporting errors for the frames it replaced. ([#570](https://github.com/lacclab/scanpath-studio/issues/570))
- The Data page's experimental Stimuli table (with SCANPATH_EXPERIMENTAL=1), which shows each version of a screen with the readers who saw it since v0.49.0, now says so in its caption, as the Texts table does. ([#634](https://github.com/lacclab/scanpath-studio/issues/634))
- The Data page's Texts table keeps each word whose Word ID is blank as a word of its own, after its line's numbered words, instead of folding them into one word that depended on the row order. ([#636](https://github.com/lacclab/scanpath-studio/issues/636))
- Leaving the Add-dataset wizard after uploading a file no longer stops the bundled demo from loading ("Screen ID is set in only one table"). ([#652](https://github.com/lacclab/scanpath-studio/issues/652))
- A dataset loaded from its fixations alone, with no word boxes or screen positions, now works on reading charts: the Comparisons grid draws its matches, plot_scanpath, compare_scanpaths and render draw it instead of refusing it for lacking coordinates, and the plot no longer warns about missing positions on a chart that draws none. ([#659](https://github.com/lacclab/scanpath-studio/issues/659))

## [0.49.0] - 2026-11-25

### Added
- Hovering over Scanpath View, Corpus Analysis or Data Management in the top navigation now says what each view is for. ([#583](https://github.com/lacclab/scanpath-studio/issues/583))
- Smaller PNG files works outside the app too: `render --compact-png` and `save_figure(..., compact_png=True)` / `save_figure_layers(..., compact_png=True)` compress a PNG figure and its separate layers losslessly, keeping the pixels, the print dpi and the citation. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Share links carry *Keep this range across trials* (`fix_range_all_trials=1`), so a fixation window kept across trials stays kept when the link is opened, as it already did in a settings file. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Add a dataset to the app's dataset list from a script with `add_dataset` or `scanpath-studio add`, and remove one with `remove_dataset` or `scanpath-studio remove`; the next local app session opens on a dataset just added. ([#617](https://github.com/lacclab/scanpath-studio/issues/617))
- Each part of Plot controls (Presets, Palette, Modes, Customize) can be folded away with the chevron beside its label; a folded line names the current choice, and the browser remembers what you folded. ([#619](https://github.com/lacclab/scanpath-studio/issues/619))
- Read and write a saved dataset's favorites, tags and notes from a script with `read_annotations` / `write_annotations` or `scanpath-studio annotations export` / `import`, so a quality-control script's tags show up in the app's trial filters. ([#623](https://github.com/lacclab/scanpath-studio/issues/623))
- A script can open the app on a dataset it added, at one reading and figure: `api.app_link` writes the link Share would, and `scanpath-studio open` opens it in the browser (starting the app if it isn't running) with the figure set by the same flags `render` takes. ([#627](https://github.com/lacclab/scanpath-studio/issues/627))

### Changed
- Buttons, help text and guides now name the Scanpath View tab as it appears in the navigation. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- The hosted demo keeps its cached figures and tables within a memory budget, dropping the least recently used ones when many people use it at once. ([#583](https://github.com/lacclab/scanpath-studio/issues/583))
- The Texts and Participants summary captions now say how the means are weighted: each participant counts equally in a text mean, and each reading counts equally in a participant mean. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- A table inside a zip with rows that have more fields than its header is read like the same table on its own: the Add-dataset wizard skips those rows and names their lines, instead of refusing the archive. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Gaze charts name their axes clearly: recorded timestamps read "Recorded time (ms)" and pupil charts "Pupil area (tracker units)" or "Pupil diameter (tracker units)", instead of "Time (ms)" and the raw column name. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- `animate_scanpath` and `render --animate` now refuse a replay with both fixations and saccades hidden, which used to produce an empty replay, with a message naming the two settings. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Comparison links that use the Print / grayscale palette and were made before v0.48.0 draw the two readers in dark and light grey since v0.48.0, scanpath B with hollow markers and dashed saccades, instead of blue and red; set each scanpath's colors again under Scanpath A and Scanpath B in the Fixations and Saccades settings to bring blue and red back. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The fixation size legend is also off by default in `plot_scanpath` and `render` output since v0.48.0; turn it on with `duration_size_legend=True`, `render --duration-size-legend`, or Fixation sizes under Figure → Legends in the app. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- `render` now stops with a message when `--compare-words`, `--compare-fixations` or their mapping flags are given without `--compare-with`, which they need; before, it ignored them. ([#592](https://github.com/lacclab/scanpath-studio/issues/592))
- animate_scanpath refuses the raw-gaze style and heatmap colour-bar options by name, which the replay never draws, instead of accepting and ignoring them. ([#600](https://github.com/lacclab/scanpath-studio/issues/600))
- Excel workbooks, .xlsx and legacy .xls alike, are read with calamine, which pandas is moving to, instead of openpyxl and the deprecated xlrd; neither is installed with the app any more. ([#601](https://github.com/lacclab/scanpath-studio/issues/601))
- A scanpath figure or replay built directly with the plotting module (FigureSettings, make_scanpath_figure, make_scanpath_animation) now draws fixations at the app's, the API's and the CLI's default opacity, 0.7, not 1.0. ([#611](https://github.com/lacclab/scanpath-studio/issues/611))
- Changing a dataset's mapping in Edit dataset no longer adds unique_trial_id / unique_text_id columns that adding the same files with that mapping would not, so an edited dataset exports the columns a freshly added one does. ([#612](https://github.com/lacclab/scanpath-studio/issues/612))
- The "Stopped loading" notice is now a light banner with a clearer Try again button and a ✕ to close it. ([#619](https://github.com/lacclab/scanpath-studio/issues/619))
- Plot controls stay in view and scroll on their own beside the figure; Reset visualization is now a compact Reset, with larger Undo and Redo buttons. ([#619](https://github.com/lacclab/scanpath-studio/issues/619))
- Plot controls are grouped under Presets, Palette, Modes and Customize: View is now Presets, My views is now My presets, the Animation switch is now Playback, and Axis preset is now Axis layout. ([#619](https://github.com/lacclab/scanpath-studio/issues/619))
- The bundled demo keeps every screen of each reading — title, question preview, paragraph, question, answers and feedback — each with the experiment's own stimulus image placed where the experiment drew it, and raw gaze for every screen. A demo trial opens on its paragraph and numbers its fixations across all its screens; a demo link or settings file saved by an earlier release still opens the paragraph on the same fixations, but a script must now name the paragraph (`--screen Paragraph`, `screen="Paragraph"`) to draw it, a fixation-index window counts from the trial's first screen, and the demo's export bundle files each screen under `screens/`. ([#625](https://github.com/lacclab/scanpath-studio/issues/625))
- OneStop's word tables, the demo's included, carry stimulus_font_px and stimulus_font_family columns, and a demo link or settings file that never named a font now opens in Lucida Sans Typewriter; plot_scanpath, animate_scanpath and compare_scanpaths draw the declared font unless font_family is passed. ([#646](https://github.com/lacclab/scanpath-studio/issues/646))

### Removed
- The package no longer ships a CSV copy of the demo raw gaze (`sample_data/raw_gaze.csv`); `load_sample_raw_gaze()` reads the bundled Parquet, and the download is about 3 MB smaller. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))

### Fixed
- The Raw gaze switch can be turned off on a trial with no samples of its own, and its "no samples" warning no longer shows during Animation or for a dataset without raw gaze. ([#584](https://github.com/lacclab/scanpath-studio/issues/584))
- Clicking the Custom view no longer switches Compare readings on or off, or puts back an earlier replay speed, autoplay or smoothness. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- When the chosen axes are ones fixations don't have, such as pupil area, the Fixations switch and its menu now say so instead of greying out with no reason. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Gaze over time now draws its small onset markers in Compare readings too, so large markers no longer hide short fixations; choosing a view sets both readings' marker size. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- A replay always shows fixations or saccades: the last of the two cannot be switched off while it plays, and a replay opened with both off shows its fixations. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Changing the replay's speed, autoplay or smoothness no longer switches the view to Custom, and Essentials no longer reports it as a setting from Full. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- After Undo, opening Stimulus → Text and changing the font size, line spacing or other text settings back keeps your change instead of putting the undone value back. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Groups → Overlaid distributions with Z-score per participant now z-scores each participant once over all their selected trials before splitting the groups, so a participant who read both conditions keeps the difference between them. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Corpus Analysis stays responsive on large datasets while Study inclusion and exclusions is open: the report is worked out once per filter change instead of on every rerun, and its CSVs are written only when you download them. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Corpus Analysis keeps its place when you visit another view or open a Help item: the destination, profile and measure you chose are still there when you come back. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Measure on the stimulus keeps the stimulus version you chose for a text after you visit another view, instead of hiding the figure until you choose again. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- With Aggregate set to Sum, an IQR spread is now drawn as the 95% bootstrap interval of the sum, as SD and SEM already were, instead of the quartiles of the individual values around the total; the recipe and the methods draft say so. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The "Updated in this session" line under a trial's annotations now appears only in the editor of the trial you changed, and goes once you open another trial, instead of following you to every trial of the dataset. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- While a conflict over a trial's note waits for you to resolve it, the app no longer writes and deletes this tab's unsaved datasets on disk on every click. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- A damaged dataset-citation entry in the saved session no longer throws away every other restored setting: only that entry is left out. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Large CSV and TSV tables load faster again: a planned read no longer checks every line against the header before reading, only a table that turns out to have a row with a field too many, and that check keeps the loading card live and Cancel working. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Tables written by R's write.table() with its default row names (a header one column shorter than every row) load again, through the Add-dataset wizard, the API and the CLI, with the row names left out; a table with rows that really have too many fields now says how many and what each has. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Two tabs or windows that share saved work now merge each other's trial notes, stars and tags as promised, whatever page, trial or plot settings each has open: those are each tab's own, and the last one to save wins them. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- On Windows, a window that opens while another one is still saving large datasets now waits for that save, instead of giving up after about ten seconds, calling the saved work unreadable and pausing saving. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- CSV tables in an export bundle now carry the time they were written instead of 1 January 1980. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Changing an export setting while a large bundle is still downloading no longer stops the download; the replaced bundle stays available for 30 minutes. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Preview bundle contents in the Export tab is no longer re-planned on every interaction while it is open, which took seconds on a large corpus with a custom path pattern. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The read_csv.R reader in CSV bundles now says "Choose a CSV listed in dictionary$csv_files" for a path it does not know, instead of a cryptic R error. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- A figure too large for the raster pixel limit is no longer offered for Retry failed figure files, since retrying with the same settings cannot make it. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Retrying failed figures in an export bundle larger than 2 GiB now makes a ZIP that macOS Archive Utility and other extractors can open. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Exported GIFs and MP4s end on the complete scanpath again; most readings had lost their last one or two fixations. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The bundled demo's raw gaze leaves the pupil area blank where the tracker lost the eye, so a pupil chart shows a gap at each blink instead of dropping to zero. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Each category now keeps one color in every trial of a dataset, and up to 20 categories get clearly different colors; several used to look almost identical, such as three purples for the demo's saccade types. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- In a right-to-left or mixed-script passage, a word made only of digits or punctuation is drawn in the direction of the words around it, so a period ending an Arabic or Hebrew sentence sits on the left. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The experimental saccade table (with `SCANPATH_EXPERIMENTAL=1`) leaves the peak speed blank for a saccade that spans a blink or lost signal, instead of reporting thousands of degrees per second. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- In a replay, the first Previous fixation press after pausing or scrubbing goes to the fixation before the one on screen instead of seeming to do nothing, and the fixation buttons work in Safari before 15.4. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The replay timer has a light background in the light theme again, even when the computer is in dark mode. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Share links and settings files from before v0.48.0 that open a replay with fixations hidden show the fixations again, as they were drawn when saved, instead of an empty or saccades-only replay; a saccades-only replay linked from v0.48.0 itself also reopens with fixations, while links made from now on keep it saccades-only. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- `render --print-code` and `figure_code` keep scanpath B's fixation window (`--compare-fix-index-range`, `fix_index_range_b=`), so the printed recipe for a comparison or a two-reading replay draws the same B as the command it came from. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The sample-number axis (`x_field="sample_index"`, `render --x-field sample_index`) draws raw gaze recorded with timestamps too, numbering each reading's samples in recorded order per screen and eye, instead of an empty chart; and a shared link whose chart axis the opened reading lacks falls back to the screen axes, rather than plotting one field against itself. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- The chart axis pickers offer the sample number for gaze samples recorded with timestamps. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Each visitor to the bundled demo uses about 70 MB less memory: every session now shares one copy of the demo's gaze samples. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Each interaction on a trial with raw-gaze samples is faster, most on long high-rate recordings: finding the cached figure no longer reads all of the trial's samples. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Opening a large dataset and changing its trial filters is faster: finding the columns the trial picker can sort by no longer runs Python code for each reading. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Use this size for batch export now gives the export bundle the width of the prepared artwork, without the page margins, so batch figures print with the same lettering as the proof instead of about 5% larger; the editor also says that the crop, labels and caption are not applied to batch figures. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Prepare figure no longer fails to make an MP4 when the suggested caption is printed below the replay: every frame of the clip, and its poster, keeps room for the caption's longest reading time. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- A Corpus Analysis chart's Prepare figure for export section stays open, with its draft, when a note or control appears above the chart. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- An emptied caption in Prepare figure no longer leaves a blank caption line below the figure when the caption is set to print with it. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Preparing a PDF or the offline editor in Prepare figure now shows a loading card with its progress, as the clip does, instead of a page that seems to hang. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Two Prepare figure sections open at once, such as a Corpus Analysis chart and its text's stimulus, no longer rebuild each other's editor on every rerun. ([#585](https://github.com/lacclab/scanpath-studio/issues/585))
- Scanpath B's fixation and saccade filters, the exported figure's width and DPI, whether the trial summary shows above the plot, and "keep this range across trials" are kept when the app restarts. ([#588](https://github.com/lacclab/scanpath-studio/issues/588))
- A renamed built-in dataset that needs a number to stay unique keeps its name within the 80-character limit, as an uploaded dataset's already did. ([#589](https://github.com/lacclab/scanpath-studio/issues/589))
- Removing a dataset also clears its saved filters, remembered trial and Compare selection, and closes Edit dataset if it was open on it, so a dataset added later under the same name opens unfiltered on its own first trial, and saving the editor cannot rename another dataset. ([#589](https://github.com/lacclab/scanpath-studio/issues/589))
- Saving a drawn scanpath keeps the participant, trial and text tables attached to the draft, as it already kept the draft's annotations. ([#589](https://github.com/lacclab/scanpath-studio/issues/589))
- A share link with a value a menu does not offer (a misspelt line style or background, say) now says it ignored that value, as it already did for colours and numbers, instead of quietly using the default. Menu values are matched ignoring capitalisation, and a colour scale may be any Plotly scale, as on the command line. ([#590](https://github.com/lacclab/scanpath-studio/issues/590))
- Colouring by, hovering, or picking a column that the next dataset you open lacks no longer forgets the choice: it comes back when you return to a dataset that has the column, unless you changed it in between. ([#591](https://github.com/lacclab/scanpath-studio/issues/591))
- Share → Code for a comparison whose scanpath B comes from a second, hand-mapped dataset now passes B's column mapping on, so the code reads B's files as the app did. `render` takes it as `--compare-word-schema`, `--compare-fix-schema` and `--compare-raw-gaze-schema`, and `figure_code` as `compare_source_options`. ([#592](https://github.com/lacclab/scanpath-studio/issues/592))
- `compare_scanpaths` and `animate_scanpath` on a dataset recorded as raw gaze alone now say that they need fixations. Before, the comparison failed with a `TypeError` and the replay said no trial existed. ([#592](https://github.com/lacclab/scanpath-studio/issues/592))
- Splitting a comparison into one file per layer (`render --separable-layers`, `save_figure_layers`) now files its saccades, raw gaze and heatmap colour bar under their own layers; before, all three landed in the fixations file. ([#593](https://github.com/lacclab/scanpath-studio/issues/593))
- The stimulus image's offset boxes and the fixation-flag threshold boxes now stop at the range a share link carries (±5000 px, 1–60,000 ms). Before, a value past it showed on screen but a share link cut it back to the limit. A settings file holding such a value is now restored at the limit too. ([#593](https://github.com/lacclab/scanpath-studio/issues/593))
- With Favorites only, a tag filter or a trial-metadata filter on, for the scanpath or for Compare's second one, a click no longer re-filters the whole dataset: the filtered trials are kept until the data, the filter or your stars and tags change (about 0.5 s a click on a full OneStop corpus). ([#595](https://github.com/lacclab/scanpath-studio/issues/595))
- Compare and the Comparisons grid redraw their figures only when something in them changes, not on every click elsewhere in the app; the static figure already worked this way. ([#595](https://github.com/lacclab/scanpath-studio/issues/595))
- A long session, or a server shared by many, no longer keeps every scanpath figure it has drawn in memory: the app keeps the 32 most recent. ([#595](https://github.com/lacclab/scanpath-studio/issues/595))
- Preparing a publication figure no longer waits forever when the browser drawing it stops answering: after two minutes without a reply it stops with an error, and you can try again. ([#596](https://github.com/lacclab/scanpath-studio/issues/596))
- A closed settings menu no longer brings back a value you changed elsewhere for four controls: undoing the replay's Smoothness or a word highlight now holds, a palette set by a settings file stays on Corpus Analysis, and a new dataset gets its own Stimulus & context fields. ([#597](https://github.com/lacclab/scanpath-studio/issues/597))
- Editing a dataset's column mapping now keeps the files' own paragraph ids, as adding the files does, and no longer leaves behind a copy of the participant column that a combined Trial ID had used. ([#605](https://github.com/lacclab/scanpath-studio/issues/605))
- A colour range set by a settings file, a link or *Use this heatmap range for other trials* now stays, instead of going back to Auto or the old range when the menu showing it had been opened before. ([#609](https://github.com/lacclab/scanpath-studio/issues/609))
- Settings restored from a settings file, and an added dataset's own text size and spacing, no longer revert when a menu you had opened before sends back its old values. ([#610](https://github.com/lacclab/scanpath-studio/issues/610))
- A stimulus page image replaced on disk at the same path now shows the next time the figure is drawn, instead of the old page until a setting changed. ([#613](https://github.com/lacclab/scanpath-studio/issues/613))
- A setting changed by a view tile, Undo, Reset or a settings file no longer goes back to its old value when the app reruns itself right after, for example when a dialog closes or a Help page opens. ([#615](https://github.com/lacclab/scanpath-studio/issues/615))
- Choosing participants no longer brings back readings a condition leaves out: a condition only the Words table carries now still applies when the chosen readers have no Words rows. ([#618](https://github.com/lacclab/scanpath-studio/issues/618))
- Legends placed at neighbouring spots (along one edge, or round one corner) no longer overlap each other when one is wide or tall for the figure: the later one moves aside, unless that would carry it out of the figure. ([#622](https://github.com/lacclab/scanpath-studio/issues/622))
- The Plot controls rail stays below the header and inside the window, so its last controls show without scrolling the page. ([#624](https://github.com/lacclab/scanpath-studio/issues/624))
- Corpus Analysis no longer stops with an error on a screen whose reading-measure flags are all missing. ([#625](https://github.com/lacclab/scanpath-studio/issues/625))
- On a phone, a trial with several screens names its screen in a line of text beside its ◀ ▶ in place of the dropdown, so the screen steps take a short line and the figure's view choices stay on the first screen in Essentials. ([#625](https://github.com/lacclab/scanpath-studio/issues/625))
- The screen you picked in a multi-screen trial stays picked after a visit to Corpus Analysis or Data Management, and turning Compare off no longer stops undo from recording your next plot edit. ([#625](https://github.com/lacclab/scanpath-studio/issues/625))
- Stimulus & context keeps its highlighted spans when you step through a screen with no highlighted words, such as a title, and picks them up even when a trial opens on such a screen. ([#625](https://github.com/lacclab/scanpath-studio/issues/625))
- On multi-screen trials the experimental per-word reading measures (`compute_word_metrics`, behind `SCANPATH_EXPERIMENTAL=1`) keep each word's screen ID and screen number, so they merge back onto the words one row per word, and the Data page's derived Trial summary, Participant summary and Sentences tables now count every screen's words instead of folding screens that share word IDs together. ([#628](https://github.com/lacclab/scanpath-studio/issues/628))
- The Data page's Texts table no longer passes off one reader's version of a screen as every reader's: a screen, or a text, that readers saw differently — the demo's answer orders and feedback — is shown once per version with the readers who saw it, and a Differs by reader column names those screens. ([#630](https://github.com/lacclab/scanpath-studio/issues/630))
- The Data page's checks no longer flag a fixation that a screen's recording end cuts to 0 ms, as in the bundled demo. ([#635](https://github.com/lacclab/scanpath-studio/issues/635))
- `api.app_link` and `scanpath-studio open` open the bundled demo and the public corpora by the name the dataset list shows, instead of saying the dataset isn't available here. ([#638](https://github.com/lacclab/scanpath-studio/issues/638))
- The blank band between the header and the dataset and trial pickers is gone. ([#642](https://github.com/lacclab/scanpath-studio/issues/642))
- The trial summary's chips no longer turn black after the ✏️ menu is opened for the first time in a session. ([#643](https://github.com/lacclab/scanpath-studio/issues/643))
- Switching subtabs while scrolled to the bottom of a tall one, such as Export, no longer makes the page jump. ([#644](https://github.com/lacclab/scanpath-studio/issues/644))
- The bundled demo and OneStop draw their word labels in Lucida Sans Typewriter, the font the experiment used, at its size on every screen, so a one-word Feedback screen is no longer drawn too large; where the font isn't installed, labels fall back to the browser's monospace. ([#646](https://github.com/lacclab/scanpath-studio/issues/646))

## [0.48.0] - 2026-11-23

### Added
- Use the arrow keys to browse trials and Space to play or pause a scanpath replay, including from the replay time slider. ([#561](https://github.com/lacclab/scanpath-studio/issues/561))
- The check command reports how many rows were read and checked, including why a table supplied no usable rows. Use --json-report to save these counts alongside the findings. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Inspect the readings behind a cohort value, compare profile revisions, download a methods draft, calculate within-participant contrasts, and rerun a two-group word difference from its recipe. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- CSV bundles now include a type and unit dictionary and an editable R reader that preserves identifiers such as 01, literal NA identifiers, and missing measurements. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Preview bundle contents lists planned per-trial paths, table columns and selected annotations, and identifies stimulus words and images that may accompany a figure. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- The interaction benchmark measures opening a first trial, switching readings and recoloring markers, with counts of data reads, normalization, selections and figure builds for each action. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- A packaged synthetic study includes two source tables, recording setup, a tagged exclusion, figure settings and a cohort recipe written by Scanpath Studio v0.37.0. The example recreates its manuscript figure and checks the original results table. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Export can proof a side-by-side or stacked comparison at its manuscript width. Check the label sizes in points, save a vector SVG with physical dimensions, and restore the panel selection and shared color limits for a revision. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Use Previous fixation and Next fixation above a replay to inspect the fixation’s onset, duration and assigned word. The shared HTML replay keeps these controls when downloaded. Long replays now build the live view from a single trace template. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Retry failed figures and individual layer files in the last export bundle while the selected data and settings still match. Successful files keep their contents and paths. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Review incoming trial and screen annotations before applying them, inspect both versions of disputed notes, and keep independent edits from two local sessions. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Compare received readings with the experiment run sheet, inspect data-check findings by reading, preview changed reading IDs, and download inclusion counts and individual exclusion reasons. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Labs can attach a title, authors, version, DOI or preferred wording to an uploaded dataset. Cite and export bundles include the saved credits and identify the second dataset of a comparison. Programmatic comparison bundles include both dataset references in `CITATION.bib`. Open an included settings file to restore both readings, their selected screens and the comparison layout. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- In Python, load data with `include_source_cells=True` and call `explain_fixation()` to see a fixation’s input row, file, original units and word assignment. Merged fixations list their contributing rows. ([#564](https://github.com/lacclab/scanpath-studio/issues/564))
- Plot gaze position and pupil measurements against recorded time or sample number. The OneStop demo includes every recorded sample, with its tracked eye, pupil area and missing positions. ([#573](https://github.com/lacclab/scanpath-studio/issues/573))
- Animation can replay saccades with the fixation markers hidden, for one reading or two. ([#574](https://github.com/lacclab/scanpath-studio/issues/574))
- Bulk export can now use lossless compression for smaller PNG figures and layers. ([#575](https://github.com/lacclab/scanpath-studio/issues/575))
- Compare readings on shared numeric axes, highlight word borders in comparisons and replays, and use the fixation window and sequence line with markers hidden. Plot controls grey out when the selected view or data cannot use them. ([#576](https://github.com/lacclab/scanpath-studio/issues/576))
- Prepare the current scanpath, replay or corpus chart for a paper or slide. Download it directly, or crop it, label events and edit its caption. Print settings include journal and slide sizes. ([#578](https://github.com/lacclab/scanpath-studio/issues/578))
- Word highlights can now underline individual words in the current text color. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))

### Changed
- Corpus Analysis shows the participant profiles immediately after the measure and aggregation pickers. The cohort overlay, normalization and measure definition sit below the chart. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Fixation markers and saccades accept opacity from 0 to 1 in the app, shared settings, CLI and Python API, including fully transparent marks. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Open the import wizard directly from the welcome tour, find upload buttons by table name, and use the guide with reduced motion. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Choose a tool in the Essentials trial picker to open it in Full. Undo and Redo describe the value they will restore, Share explains what the recipient needs, and the import guide opens folded on narrow screens. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Large bundles use less memory when writing gaze CSVs and spend less time assigning duplicate filenames and preparing single-screen trials. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Switching trials reuses the current table’s position index, matching metadata is folded in groups, and out-of-text tests and cohort bootstrap intervals use bounded memory. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- After Add dataset identifies an unresolved mapping, activate its message to focus the matching control. Selecting the duration column clears its warning and shows how two source values convert to milliseconds. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- On phones, the Scanpath view choices sit directly below the figure, ahead of Export and the other trial panels. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Word-box heatmaps show the current reading’s dwell-time or count limits and can reuse those limits on other readings. Grayscale comparisons distinguish readers with filled and hollow markers and solid and dashed lines. A snapped illustration can be viewed beside the same trial’s original coordinates. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Data Management puts Add dataset above the list, shows full names on phones and restores click-to-sort column headers. Corpus Analysis opens with the analysis controls and keeps figure styling and the inclusion report below the results. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Essentials and Full share their view controls and Palette. Full adds comparison, animation settings, saved designs, and layers below them. ([#566](https://github.com/lacclab/scanpath-studio/issues/566))
- Full plot controls now have Layers, Axes and Figure tabs. Open a layer by name to style it, use its switch to change visibility, or choose a chart by fixation order or time in Axes. ([#567](https://github.com/lacclab/scanpath-studio/issues/567))
- In Full, search for a plot setting to open its controls directly. Each editor puts common adjustments first and groups detailed styling, timing and layout options under their own headings. ([#567](https://github.com/lacclab/scanpath-studio/issues/567))
- Switch Animation on or off from Plot controls, plot horizontal fixation position with Gaze over time, or return to your last hand-edited figure with Custom. ([#567](https://github.com/lacclab/scanpath-studio/issues/567))
- About & citation opens with a short project overview. Citation has the APA and BibTeX references, and App details groups privacy, updates and support. ([#568](https://github.com/lacclab/scanpath-studio/issues/568))
- Help now offers offline task guides and troubleshooting. Start the sample replay or import guide when you need it, and send suggestions to GitHub Ideas. Documentation ↗ opens in a new tab. ([#568](https://github.com/lacclab/scanpath-studio/issues/568))
- Data Management opens on the selected dataset with trial averages, six browsable tables and recording quality checks. The dataset library and saved work have their own tabs. ([#571](https://github.com/lacclab/scanpath-studio/issues/571))
- The fixation size legend starts hidden. Turn on Fixation sizes under Figure & canvas → Legends to include it in a figure. ([#572](https://github.com/lacclab/scanpath-studio/issues/572))
- The bundled demo now uses two readers from the published OneStop L1 cohort and includes recorded EyeLink gaze samples for all 24 readings. Demo participant and trial IDs have changed. ([#573](https://github.com/lacclab/scanpath-studio/issues/573))
- Bulk PNG, SVG and PDF exports reuse the browser page across trials and prepare the next figure during rendering. Large bundles download from temporary disk in small pieces as one ZIP. ([#575](https://github.com/lacclab/scanpath-studio/issues/575))
- Bulk exports run faster on large datasets whose rows are grouped by trial. ([#575](https://github.com/lacclab/scanpath-studio/issues/575))
- Corpus Analysis opens with a chart of texts or participants. Select a dot for its readings, open a word or participant profile, or choose Groups to compare two conditions. Chart settings, tables and downloads open on demand. ([#577](https://github.com/lacclab/scanpath-studio/issues/577))
- Corpus Analysis places profile shortcuts beside Texts and Participants, groups the dataset counts with their filters, and brings the reading measure and figure style together above the chart. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- Plot controls now show Colorblind-safe, Grayscale and High contrast as palette tiles with swatches, place My views below the view tiles, and put the Animation switch beside its playback settings. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- The main navigation tab for inspecting a reading is now called Scanpath View. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- The software credits and citations now include Carlson Büth and list Maya Grossman before Keren Gruteke Klein and Deborah N. Jakobi before Ella Lion. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- Data Management now lists the dataset’s supplied reading measures under Tables → Words. ([#579](https://github.com/lacclab/scanpath-studio/issues/579))
- The documentation screenshots and walkthroughs now show Scanpath View, the updated plot controls and the current export steps. ([#580](https://github.com/lacclab/scanpath-studio/issues/580))

### Removed
- Removed the undocumented Python helpers `scanpath_studio.export.pair_export` and `ComparisonSide`. Comparison figures can be saved from the app or with `save_figure`. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Retired the individual workflow GIFs in `assets/workflows/`. The docs carry the videos and posters, and the README keeps its overview animation. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))

### Fixed
- Static figure exports now require Kaleido 1.5.2 or later to prevent intermittent failures while the browser loads its plotting scripts. ([#551](https://github.com/lacclab/scanpath-studio/issues/551))
- Cohort figures use finite observations, weight repeated readings consistently, distinguish stimulus versions, and show gaps and units for the selected estimate. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Setting a reading’s fixation opacity to zero now makes its markers transparent in comparisons and two-reading replays. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Single and comparison heatmaps use the same word assignments and label log scales in their original units. Relative marker sizing uses both visible readings in Compare. Heart outlines respond to the selected width, and a category containing “heatmap” stays in the fixation export layer. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Two local app processes saving different review notes to the same recovery folder now preserve both edits. Clearing a folder waits for an active save or restore to finish. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Corpus Analysis distribution charts label within-participant z-scores in standard deviation units. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Comparison tables preserve lab columns that share a name with the dataset or A/B labels, and replacing attached metadata keeps the fields explicitly selected for publication. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Export previews follow the selected format, screen and file pattern. Incomplete scopes produce no trials, and screen selections include only those screens’ annotations and their parent trial notes. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Figure settings files restore narrowed fixation windows for both readings. Shared titles and captions preserve linguistic tags such as `<NP>`. Generated captions include raw gaze when the figure draws usable samples. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Importing large fixation tables uses less memory when recording source filenames. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Headless trial listings leave stderr quiet. Render and Share → Code preserve comparison IDs containing colons, uploaded column names containing commas, single-table inputs, and exact hover field selections. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Recipes, annotations, column mappings and multipart manifests accept UTF-8 BOMs and Unicode JSON encodings. An unmatched reading in a screen listing points to the available trials. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Table imports preserve literal reader IDs, report overlong records by line, identify the worksheet read, and show differences from a pilot’s saved mapping. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- The OneStop manuscript figures include the full recorded scanpaths, and the replay montage preserves the bottom of its final frame. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Word labels in mixed-script passages follow each word's writing direction. Two sample CSVs show a Hebrew and Arabic reading with English, numbers, punctuation and a return fixation. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Opening a direct link to Corpus Analysis, Data Management, or Help on a first visit now opens the requested destination without the welcome tour taking over. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- The manuscript scripts use canonical data columns and compare geometry-derived reading measures against EyeLink values. The corpus figure identifies the passage by its recorded ID and selects it consistently when reader counts tie. The benchmark uses the same readers in both input tables and labels post-stage memory measurements. The change verifier checks restored options and fresh output files. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Custom bundle paths extract on Windows even when participant or trial IDs use reserved device names or end in a period. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Publication-sized PNG layers use the composite’s dimensions and print density. Re-exporting layers removes obsolete files from the previous export. A failed render preserves the previous figure or layer set. Multipart figures retain their recorded screen numbers. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- The desktop launcher waits for Streamlit's health response before opening the window. Update instructions preserve VCS branches, forks and package subdirectories and identify installs pinned to a commit. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Categorical fixation colors stay consistent across readings, and the index chart respects the selected connector style, width and opacity. Figure descriptions count the fixations and gaze samples drawn. With stimulus redaction on, the Hover and Export panels identify selected text fields that can still appear in HTML. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Replays preserve recorded gaps before long fixations. At a low GIF or MP4 frame cap, each image shows the fixations reached by its display time. A late fixation can fall after the last image. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- If the local recovery cache cannot be locked, the app opens with saving paused and keeps the saved session available for a later launch. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- HTML replays build frames as you play or seek, reducing memory use for long readings in the app and in saved files. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Commands copied from Share now accept participant, trial and screen IDs that start with a hyphen on either side of a comparison. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Comparison links and generated Python and CLI commands preserve each reader’s marker fill, colors and line styles when using the print palette. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- A tab with an older recovery copy warns you before it can overwrite newer saved work. Your edits stay available in the tab to export. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- Saving a static figure uses the shared renderer and reports when an installed browser has not finished starting Kaleido. HTML, PNG, SVG and PDF retain their citation. ([#563](https://github.com/lacclab/scanpath-studio/issues/563))
- After Undo or Redo, you can reopen a plot menu and immediately change the restored setting again. ([#567](https://github.com/lacclab/scanpath-studio/issues/567))
- The replay timer is easier to read in dark mode. ([#569](https://github.com/lacclab/scanpath-studio/issues/569))
- Screens with gaze samples alone appear in the trial picker and exports. Comparisons place each reading’s samples on its recorded screen. Saccade peak speeds use consecutive positions from the same eye and screen and skip gaps in tracking. ([#573](https://github.com/lacclab/scanpath-studio/issues/573))

## [0.47.0] - 2026-11-22

### Added
- Python 3.15 is now supported and tested. ([#548](https://github.com/lacclab/scanpath-studio/issues/548))
- Reproduce a downloaded per-word cohort profile with its JSON recipe and the original data in Python or with the recipe command. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- Undo and Redo beside Reset visualization step through recent plot changes, including presets and resets. ([#556](https://github.com/lacclab/scanpath-studio/issues/556))
- Help opens the documentation and What’s new for your Stable or Dev build. The Dev docs include changes since the last release. ([#559](https://github.com/lacclab/scanpath-studio/issues/559))

### Changed
- Clearer, more welcoming wording throughout the app and documentation, including tutorials, data import, saved work, analysis and exports. ([#546](https://github.com/lacclab/scanpath-studio/issues/546))
- Full adds fixation-index and elapsed-time charts for horizontal and vertical screen position. Switching between Essentials and Full keeps the current plot and export choices. Choosing a design or resetting the visualization now replaces earlier axis and styling choices even after their controls have been closed. Shared links check imported recording tables before opening a view, and the import wizard identifies missing word-box fields. ([#554](https://github.com/lacclab/scanpath-studio/issues/554))
- Fixation index size, color, and position now share one definition across plot controls, saved settings, share links, and generated commands. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- Draw and replay fixations directly on a passage, reopen named drawings to edit them, and share the matching draft for use in the app or a script. ([#557](https://github.com/lacclab/scanpath-studio/issues/557))
- Updated the documentation screenshots and demos to show the current controls. ([#560](https://github.com/lacclab/scanpath-studio/issues/560))

### Fixed
- Compact Python and CLI snippets now omit settings that have no effect in the selected scanpath view. Comparisons and two-scanpath replays keep each reading’s own marker and saccade styles. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- The figure options reference now shows which settings affect a single plot, a replay, a comparison, or a two-scanpath replay. It also explains how to set each scanpath’s fixation index color. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- Share links now reopen PoTeC as scanpath B. If a public comparison corpus is missing, the link opens A and explains how to get B. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- Renaming an uploaded dataset keeps its annotations, comparison selection and saved data together. An upload named “This dataset” can be selected independently in Compare. Share links reopen comparisons between two uploads and tell recipients which files to add if scanpath B is missing. ([#555](https://github.com/lacclab/scanpath-studio/issues/555))
- Sharing the hand-drawn sample now uses its own text and fixations, including after editing a different drawing. ([#557](https://github.com/lacclab/scanpath-studio/issues/557))
- Metadata joins, filters and the command-line trial list include readings found only in Words, Fixations or Raw gaze and use the recorded text ID for each reading. ([#558](https://github.com/lacclab/scanpath-studio/issues/558))
- Data-check reports now produce valid JSON for missing and infinite values in example rows. ([#558](https://github.com/lacclab/scanpath-studio/issues/558))
- Removing or replacing a metadata upload clears the previous table’s fields in the dataset editor and the import wizard. ([#558](https://github.com/lacclab/scanpath-studio/issues/558))

## [0.46.0] - 2026-11-11

### Added
- Fixation index numbers can sit above, inside or below each fixation: Fixations → Fixation index → Position in the app, order_label_position in the Python API and share links, and --order-label-position in render. ([#542](https://github.com/lacclab/scanpath-studio/issues/542))
- Clicking Apply under Derive columns from text fills an empty Trial, Participant or Text ID field with a derived column named like one, such as participant, trial or stimulus. ([#543](https://github.com/lacclab/scanpath-studio/issues/543))
- The import screen says when the Fixations and Words tables' Trial or Text IDs differ only in upper and lower case, and how to make them match. ([#543](https://github.com/lacclab/scanpath-studio/issues/543))
- The import screen suggests Merge character boxes into word boxes when a word's rows in the Words table are at different positions. ([#543](https://github.com/lacclab/scanpath-studio/issues/543))
- A setup file now saves and restores Merge character boxes into word boxes, from both the import screen and Edit dataset. ([#543](https://github.com/lacclab/scanpath-studio/issues/543))

## [0.45.1] - 2026-11-11

### Removed
- The MultiplEYE session-set format, load_multipleye and render --multipleye are withdrawn for now. A session set's files still load as your own tables, and a dataset already added this way still opens. ([#539](https://github.com/lacclab/scanpath-studio/issues/539))

### Fixed
- A dataset over several screens with no screen number mapped no longer fails to plot when its Words table lists the screens in another order than the fixations do (page_10 before page_2): the screens follow the order they first appear in the fixations. ([#539](https://github.com/lacclab/scanpath-studio/issues/539))

## [0.45.0] - 2026-11-10

### Added
- The docs home page opens its "From recording to publication" tour with a short clip of a first look in Essentials. ([#527](https://github.com/lacclab/scanpath-studio/issues/527))
- Add a MultiplEYE session set from its folder or from its files: choose MultiplEYE session set under Dataset format when you import. Each reading of a stimulus is a trial, with its pages and comprehension questions as screens, drawn on the screen the session set's own config records. load_multipleye and render --multipleye load one in code. ([#533](https://github.com/lacclab/scanpath-studio/issues/533))

### Changed
- The README and docs screenshots and recordings show the current app, including the Essentials | Full switch, which the Scanpath guide's numbered overview now points out. ([#527](https://github.com/lacclab/scanpath-studio/issues/527))
- Scanpath Studio now needs Streamlit 1.67 and pandas 3.1, and asks for newer pyarrow, Kaleido, Pillow, imageio, watchdog and truststore. ([#532](https://github.com/lacclab/scanpath-studio/issues/532))
- The "This server saves nothing" notice is shorter: what a refresh loses, and a link to how to keep copies. ([#534](https://github.com/lacclab/scanpath-studio/issues/534))
- The button that opens a dataset in the Scanpath view, after Add dataset and on the Data Management page, now reads "Open in Scanpath view". ([#534](https://github.com/lacclab/scanpath-studio/issues/534))

### Fixed
- On Streamlit Community Cloud, the Essentials | Full switch no longer covers the toolbar's Fork and GitHub buttons; it sits to their left. ([#528](https://github.com/lacclab/scanpath-studio/issues/528))
- A side-by-side or stacked Compare figure with a title no longer draws the A/B legend under the title: the legend now has its own row between the title and the panels' names, and the figure grows to make room. ([#529](https://github.com/lacclab/scanpath-studio/issues/529))
- In a side-by-side or stacked Compare figure, a legend or the size key moved to a spot above the plot no longer lands on the panels' A / B names; it stacks above them and the A/B legend. ([#530](https://github.com/lacclab/scanpath-studio/issues/530))
- Word labels in a CJK font (MultiplEYE's Noto Sans Mono CJK) line up with the stimulus image's own text: no longer about 4 px above it, and no longer slid sideways in a word with two full-width punctuation marks side by side. ([#534](https://github.com/lacclab/scanpath-studio/issues/534))
- In a narrow window, a trial with screens keeps its ◀ ▶, screen picker and menus together on the line under the trial picker, without the gaps around them. ([#534](https://github.com/lacclab/scanpath-studio/issues/534))

## [0.44.0] - 2026-10-27

### Added
- Word IDs can be text, such as `w1` or `Hello_3`: fixations are matched to the word with the same ID in their trial, so a dataset keyed by text IDs loads without fixation coordinates, and its IDs are shown and exported as the file spells them. ([#415](https://github.com/lacclab/scanpath-studio/issues/415))

### Changed
- Moving between trials sends about a quarter less to the browser and takes about a third less server time, and on a slow connection the app's styling now arrives within a few seconds of the page instead of about 20 seconds after it. ([#506](https://github.com/lacclab/scanpath-studio/issues/506))

### Fixed
- A layer switch you flip right after picking a design preset now stays flipped instead of snapping back, and the first option you pick in a layer's ▾ menu after a preset is no longer undone. ([#485](https://github.com/lacclab/scanpath-studio/issues/485))
- Words that read "None", "NA" or "null", and blank word cells, in a CSV or TSV words table are kept as words under pandas 3.1 too, instead of being read as missing. ([#524](https://github.com/lacclab/scanpath-studio/issues/524))
- A built-in dataset whose column mapping cannot load now shows Save changes on its Edit dataset screen, so a field fixed there takes effect. ([#525](https://github.com/lacclab/scanpath-studio/issues/525))

## [0.43.0] - 2026-10-22

### Added
- The docs home page has a Cite button beside Tutorials, linking to how to cite Scanpath Studio. ([#512](https://github.com/lacclab/scanpath-studio/issues/512))
- Scanpath Studio is easier to cite: a Cite button beside the figure, replay and bundle downloads and in Share → Code gives a figure credit, APA, BibTeX and .bib / .ris files (naming OneStop or PoTeC too when the data comes from them), every figure, replay and page saved from Export, the API or the CLI (PNG, SVG, PDF, HTML, GIF, MP4) carries the citation in its file metadata, the export bundle adds a `CITATION.bib` and a README *Cite* section, an optional Credit line under the plot (Figure & canvas → Credit, `--credit`, `show_credit=True`) says where a shared figure came from, and `scanpath-studio cite` / `sps.cite()` print it headlessly. ([#514](https://github.com/lacclab/scanpath-studio/issues/514))
- An Essentials mode for first-time users: a trimmed Scanpath view that opens a new visit on a playing replay, with an Essentials | Full switch in the header that the browser remembers. ([#516](https://github.com/lacclab/scanpath-studio/issues/516))
- Data Management → Saved on this computer now lists every dataset on this computer in one list: the datasets you added and the public datasets you downloaded, each with its size and location. A downloaded dataset can be deleted from its row, after a confirmation; clearing what is saved still leaves downloads alone. ([#517](https://github.com/lacclab/scanpath-studio/issues/517))

## [0.42.1] - 2026-10-19

### Changed
- The README and docs home-page demo video show a new captioned tour of the Scanpath page: a replay, the Heatmap preset, a figure built layer by layer, saccade filters, redacted text, two participants side by side, Export and Share. ([#510](https://github.com/lacclab/scanpath-studio/issues/510))

## [0.42.0] - 2026-10-19

### Added
- After Add dataset, a dialog offers Open in Scanpath or Add another, and the Data page has an Open in Scanpath button beside Add dataset for the selected dataset. ([#490](https://github.com/lacclab/scanpath-studio/issues/490))
- Help → About now says where your data goes on the run you are using, the docs' About page has a Your data section (what is saved, where, for how long, how to clear it or turn it off), and the recovery cache no longer stores an empty raw-gaze file for a dataset without raw gaze. ([#498](https://github.com/lacclab/scanpath-studio/issues/498))
- Stepping to another trial (◀ ▶, the trial dropdown or slider) shows a Loading trial card over the plot until the new figure draws, and `streamlit run` from the repository (as the hosted demo is) compresses what it sends, about a third as much data for each change. ([#505](https://github.com/lacclab/scanpath-studio/issues/505))

### Changed
- Highlight words now starts off, so the demo no longer colors its answer span until you tick it; plot_scanpath, animate_scanpath, compare_scanpaths and scanpath-studio render highlight nothing unless given a highlight column. ([#488](https://github.com/lacclab/scanpath-studio/issues/488))
- The import wizard, its setup guide and Edit dataset now use the same words for the same things (Name, I know it, Extra fields to keep, an optional Participant ID, Skip guide), in plainer English; Edit dataset shows a stored word box's Edges option greyed out with the reason. ([#499](https://github.com/lacclab/scanpath-studio/issues/499))
- The welcome tour and the Scanpath view use plain, literal wording, and the row of trial fields above the plot is now called the trial summary (Trial summary above the plot) everywhere, instead of chips. ([#501](https://github.com/lacclab/scanpath-studio/issues/501))
- Trial ids in the bundled demo and in the OneStop datasets drop the reading suffix: the demo trial l37_1129_2_1_1_Ele_r0 is now l37_1129_2_1_1_Ele, since each OneStop regime holds one reading of each paragraph per reader. ([#503](https://github.com/lacclab/scanpath-studio/issues/503))
- The replay's Play, Pause and Restart buttons, time slider and readout now sit in one compact row above the figure, its title and its legend, so turning on Animate (alone or with Compare) no longer shrinks the plot; this applies in the app and in saved HTML replays. ([#504](https://github.com/lacclab/scanpath-studio/issues/504))
- The docs and README screenshots, workflow videos and app demo show the current app: trial ids without the reading suffix, the replay toolbar above the figure, and the trial summary. ([#508](https://github.com/lacclab/scanpath-studio/issues/508))

### Fixed
- Compare's A/B legend names each reading by its text and participant (2_2_1_Adv · l37_1129), instead of repeating the whole trial id, so it fits on one row above the text. ([#488](https://github.com/lacclab/scanpath-studio/issues/488))
- A typed page address or a Share link now opens where it says on a local install; only a bare visit resumes the view you were last on. ([#491](https://github.com/lacclab/scanpath-studio/issues/491))
- The BibTeX in ❓ Help → About now matches the docs' citation: it drops the stale month, links the DOI, and lists one author per line. ([#492](https://github.com/lacclab/scanpath-studio/issues/492))
- The first `scanpath-studio` launch on a new computer no longer stops at Streamlit's terminal prompt for an email address, and no longer prints its usage-statistics notice. ([#493](https://github.com/lacclab/scanpath-studio/issues/493))
- A share link with a number that overflows to infinity (such as marker_size_range=1,1e309) no longer replaces the page with a crash note; non-finite numbers, on/off values other than 1/0, true/false, yes/no or on/off, and figure text over 500 characters are now ignored with a notice, and a number outside its control's range is clamped with a notice instead of silently. ([#494](https://github.com/lacclab/scanpath-studio/issues/494))
- Closing the "Reset visualization?" dialog with ✕, Esc or a click outside now closes it for good, instead of it reopening on the next click. ([#495](https://github.com/lacclab/scanpath-studio/issues/495))
- A dataset name now shows exactly as typed, with no Markdown, colour, maths or icon formatting, and is limited to 80 characters; a longer name saved earlier still loads and is shortened with an ellipsis in the dataset table, with the full name on hover. ([#496](https://github.com/lacclab/scanpath-studio/issues/496))
- When a dropped connection loses the dataset being added, the Data page now says so and asks for the file again; the hosted demo's upload step notes it needs a steady connection, and reloading or closing the page while the add-dataset screen holds a file or a typed name now asks before leaving. ([#497](https://github.com/lacclab/scanpath-studio/issues/497))
- The import wizard now says plainly why an uploaded file can't be used (empty, header only, not a text table, not a Parquet file), skips and reports rows with more fields than the header instead of reading them shifted, and says why Add dataset is off. ([#499](https://github.com/lacclab/scanpath-studio/issues/499))
- Adding a dataset no longer redraws the Bundled demo or any other dataset on the new dataset's screen size and text settings: each dataset opens with its own recording setup. ([#500](https://github.com/lacclab/scanpath-studio/issues/500))
- The welcome tour always runs on the Scanpath view: started from Data Management or Corpus Analysis it switches there first, and leaving Scanpath mid-tour folds it to its tab. Its card moves to the left edge while the filters, trial summary and plot controls are shown, and to the top for the panels under the plot, and its text names icon-only buttons as they appear on screen. ([#501](https://github.com/lacclab/scanpath-studio/issues/501))
- A field mapped to a column that isn't numbers is now named in the add-dataset warning and marked at the field with the column to choose instead; negative, infinite and hour-long durations and positions too far off the screen to draw are warned about at import and no longer break the plot; the Scanpath view says when most of a table fails the Data checks; and Edit dataset says how to use a column it doesn't list. ([#502](https://github.com/lacclab/scanpath-studio/issues/502))
- The welcome tour no longer shows its text and buttons unstyled at the top of the page while the app is still loading on a slow connection. ([#505](https://github.com/lacclab/scanpath-studio/issues/505))

## [0.41.0] - 2026-10-19

### Added
- Stimulus → Text → Redact (render --redact-text, redact_text=) draws a rounded block over each word's letters instead of the word, for figures that must not show the stimulus text. ([#482](https://github.com/lacclab/scanpath-studio/issues/482))
- The plot gallery has two new examples: Redacted text, and Title, caption & legend. ([#484](https://github.com/lacclab/scanpath-studio/issues/484))

### Changed
- The docs screenshots and the export-bundle, add-your-data and share-link videos were re-captured, so they show the app's current labels. ([#480](https://github.com/lacclab/scanpath-studio/issues/480))
- About, citation and privacy information are on one page, with a shorter citation for the bundled demo. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The gallery's Fully customizable example (renamed) comes last, with one fixation per word. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The documentation and README are copy-edited for clarity and consistency with the app: current control names, one set of terms throughout, and a few corrected claims. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The plot gallery's app instructions are written for your own data, not for specific demo trials. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- Reading schematic comes just before Fully customizable, and both use the same six-fixation reading. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The figure options are part of the Python API reference, with their defaults and CLI flags. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The replay example in the docs says how to play it and how to make one from your own data. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))

### Fixed
- The build line under About no longer counts the hosted demo's release merges as commits after the release. ([#481](https://github.com/lacclab/scanpath-studio/issues/481))
- Maya Grossman's LinkedIn link in the app and the docs is fixed. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))
- The homepage workflow videos' captions are orange on a dark background throughout. ([#486](https://github.com/lacclab/scanpath-studio/issues/486))

## [0.40.0] - 2026-10-17

### Changed
- Unclear labels across the app are renamed, with no carry-over of old link or settings values: fixation flags *Hide* (was Discard) and *Outside the text*, saccades *One color*, the *Smoothed* heatmap, *Word ID*, one *Words table* name, *Draw a scanpath*, *Monitor width*, US-spelled palettes, drift-correction algorithms described by what they do, and plainer Corpus Analysis view names. ([#478](https://github.com/lacclab/scanpath-studio/issues/478))

## [0.39.1] - 2026-10-17

### Changed
- The app's help texts, messages, captions and tours are shorter and plainer, and the few that named the wrong control or promised more than the app does are corrected. ([#476](https://github.com/lacclab/scanpath-studio/issues/476))

## [0.39.0] - 2026-10-17

### Added
- A **Send feedback** entry under ❓ Help lists where to report a bug, suggest a feature, share an idea or ask a question, with the version and system details a bug report needs ready to copy. ([#464](https://github.com/lacclab/scanpath-studio/issues/464))

### Changed
- The Slack release notification links to the GitHub release notes instead of the PyPI page. ([#468](https://github.com/lacclab/scanpath-studio/issues/468))
- Code comments, the contributor guides and the changelog no longer carry internal tracker IDs or development history, and an experimental feature's error says it is experimental and off by default. ([#471](https://github.com/lacclab/scanpath-studio/issues/471))
- Code that nothing used is removed, with no change to what the app does; old share links and settings files open as before. ([#474](https://github.com/lacclab/scanpath-studio/issues/474))

### Removed
- The hidden harmonised benchmark corpora (EyeGenBench), their loader and `render --eyegenbench` / `--eyegenbench-dataset` are removed (they were only reachable with `SCANPATH_EXPERIMENTAL=1`). ([#471](https://github.com/lacclab/scanpath-studio/issues/471))
- MultiplEYE support is removed: its corpus entry and upload format (only offered with `SCANPATH_EXPERIMENTAL=1`), the `MULTIPLEYE_DATA_DIR` server bundle, `load_multipleye`, and `render --source multipleye` / `--export` / `--no-question-screens`. ([#471](https://github.com/lacclab/scanpath-studio/issues/471))

### Fixed
- Opening a corpus a server cannot download now switches the dataset picker to the bundled demo, and a demo standing in for a missing corpus is drawn on its own screen instead of the corpus', which cut its text off. ([#469](https://github.com/lacclab/scanpath-studio/issues/469))
- The Metadata heading on the add-dataset and ✏️ Edit dataset screens shows its intended bold, accent-coloured style. ([#471](https://github.com/lacclab/scanpath-studio/issues/471))

## [0.38.4] - 2026-10-16

### Added
- Add a heart-shaped fixation and arrowed-saccade gallery example with app, Python and CLI recipes. ([#462](https://github.com/lacclab/scanpath-studio/issues/462))

### Changed
- Made installation choices easier to scan with platform download buttons, compact alternative cards and expandable setup details. ([#458](https://github.com/lacclab/scanpath-studio/issues/458))
- Removed the redundant coding-agent guide; its old URL redirects to the Python API reference. ([#458](https://github.com/lacclab/scanpath-studio/issues/458))
- Every docs page has its own search title and description, the home page carries a schema.org record for search engines, and the PyPI and Zenodo keywords cover eye trackers, eye movements, gaze, fixations and saccades. ([#459](https://github.com/lacclab/scanpath-studio/issues/459))
- The Reference docs are easier to use: a new Figure options page groups every option by plot-rail section with a description, the CLI reference is organized by command with every `render` flag listed by topic, and each Python API entry has an at-a-glance index row and a parameter list. ([#460](https://github.com/lacclab/scanpath-studio/issues/460))
- The Slack release notification now posts only the version, its PyPI link and how many items each changelog group holds, not the release notes. ([#461](https://github.com/lacclab/scanpath-studio/issues/461))
- Bring workflow recordings into the homepage and feature guides, simplify the header links, and guide new users through saving their first figure. ([#462](https://github.com/lacclab/scanpath-studio/issues/462))
- Added word-box heatmap and text-highlight examples, animated the replay preview, clarified full-reader comparisons and two-line schematics, and replaced the bottom plots with an across-experiment trend. ([#462](https://github.com/lacclab/scanpath-studio/issues/462))
- Shorten the privacy page to explain local data processing and the hosted-demo distinction in two sentences. ([#462](https://github.com/lacclab/scanpath-studio/issues/462))
- Refine the homepage demos, add a Customize tab, simplify getting started, and add an About page with developers, citation and feedback links. ([#466](https://github.com/lacclab/scanpath-studio/issues/466))

### Fixed
- In Animate, the highlight note and the fixation-size key no longer straddle the plot's bottom border. ([#455](https://github.com/lacclab/scanpath-studio/issues/455))
- Keep outlined documentation buttons legible when hovered or focused in both themes. ([#462](https://github.com/lacclab/scanpath-studio/issues/462))

## [0.38.3] - 2026-10-16

### Changed
- Simplified the README with one overview demo, clear download links, a compact feature overview, and links to detailed documentation. ([#456](https://github.com/lacclab/scanpath-studio/issues/456))
- Scanpath Studio now runs on Streamlit 1.66, which adds a "Skip to main content" link and screen-reader names for icon buttons. ([#452](https://github.com/lacclab/scanpath-studio/issues/452))
- Shorten tutorials, remove unsupported interpretations, and clarify heatmap scales and static bundle exports. ([#453](https://github.com/lacclab/scanpath-studio/issues/453))
- Streamlined the home page and tutorials, added workflow demos, consolidated setup guidance, and removed the public computation register. ([#456](https://github.com/lacclab/scanpath-studio/issues/456))
- Modernized the docs with clearer navigation, Inter typography, refined light and dark palettes, and consistent cards, tables and code panels. Removed page date stamps. ([#456](https://github.com/lacclab/scanpath-studio/issues/456))
- Rebuilt the plot gallery with visual previews, app-first instructions, CLI and Python recipes, and a separate recordings page. ([#456](https://github.com/lacclab/scanpath-studio/issues/456))
- Integrated Python and CLI examples into the feature guides, with contextual export recipes and dedicated technical references. ([#456](https://github.com/lacclab/scanpath-studio/issues/456))

### Fixed
- Demo updates preserve deployment-only changes when advancing to a release. ([#453](https://github.com/lacclab/scanpath-studio/issues/453))
- Export bundles keep stimulus images, Illustration labels and complete figure settings; Share code retains custom word fields. ([#453](https://github.com/lacclab/scanpath-studio/issues/453))
- Stray dash marks no longer show on the welcome tour, the Tutorials dialog and the page's top-right corner. ([#454](https://github.com/lacclab/scanpath-studio/issues/454))

## [0.38.2] - 2026-10-16

### Added
- The docs' Scanpath visualization guide gains an All controls page: every button and setting on the Scanpath page, menu by menu, with what it does. ([#436](https://github.com/lacclab/scanpath-studio/issues/436))

### Changed
- Each docs tutorial is now a section of real tasks, most with a recording of it in the app: Optimize data collection (check a session, compare two eye trackers, audit an experimenter), Filter data, Export figures and Analyze a corpus. ([#436](https://github.com/lacclab/scanpath-studio/issues/436))
- The README lists every table a dataset can bring: fixations, words (interest areas), raw gaze, and participant, trial and text metadata. ([#436](https://github.com/lacclab/scanpath-studio/issues/436))
- The docs' task cards and tutorials now walk through the example use cases: comparing two eye trackers on one text, picking participants by a field such as native language and exporting the marked trials, saving a figure's look as a design, and seeing reading progress over time. ([#436](https://github.com/lacclab/scanpath-studio/issues/436))
- A chip color in the trial chips menu has a ✕ that puts it back to the default gray, instead of picking that gray by hand. ([#446](https://github.com/lacclab/scanpath-studio/issues/446))
- The docs' Reference tab is now Data & methods: a shorter Data format page, a Computations page without developer details, a short OneStop page, and no Glossary. ([#449](https://github.com/lacclab/scanpath-studio/issues/449))

## [0.38.1] - 2026-10-13

### Added
- In Compare, each scanpath's word boxes have their own line and fill opacity under Word boxes, as well as their own colors. ([#429](https://github.com/lacclab/scanpath-studio/issues/429))
- The note naming the highlighted words is a Figure & canvas → Legends row of its own: show or hide it, place it and size its text, on every surface. ([#433](https://github.com/lacclab/scanpath-studio/issues/433))

### Changed
- The workflow recordings in the README and the Gallery are re-recorded from the current app, and the one adding a dataset no longer shows a folder path from the machine it was recorded on. ([#426](https://github.com/lacclab/scanpath-studio/issues/426))
- The Border switch (Figure & canvas) now also hides or recolours the border in Animate and Compare, which always drew it in black. ([#427](https://github.com/lacclab/scanpath-studio/issues/427))
- Legend text is black, the fixation size key no longer draws its largest circle, and a size key above or below the plot lines up with the legend beside it. ([#427](https://github.com/lacclab/scanpath-studio/issues/427))
- Legends above the plot sit just over the text and fixations instead of at the plot's top edge, so the figure loses the empty band above it. ([#427](https://github.com/lacclab/scanpath-studio/issues/427))
- A fixation size key above the plot sits a little lower, coming down toward the fixations and text under it without touching them. ([#430](https://github.com/lacclab/scanpath-studio/issues/430))
- A fixation size key above the plot always sits right on the screen's top line, never on top of it. ([#432](https://github.com/lacclab/scanpath-studio/issues/432))
- The screen note under the plot now appears when the view is cropped to the data, saying so, instead of under the full screen. ([#434](https://github.com/lacclab/scanpath-studio/issues/434))
- The docs home page now lists what Scanpath Studio is for, by research stage: data collection, validation, filtering, figure export, and comparison. ([#435](https://github.com/lacclab/scanpath-studio/issues/435))
- The app demo at the top of the README and the docs home page is re-recorded from the current app. ([#437](https://github.com/lacclab/scanpath-studio/issues/437))
- The README's and the Gallery's recordings of the app are taken in a wider window, so the trial picker's slider and its buttons share one line. ([#438](https://github.com/lacclab/scanpath-studio/issues/438))
- The README now says up front what data it reads, and shows one workflow recording per feature, with the rest linked from the gallery. ([#442](https://github.com/lacclab/scanpath-studio/issues/442))
- The docs pages no longer show the *Edit this page* and *View source* buttons. ([#443](https://github.com/lacclab/scanpath-studio/issues/443))

### Removed
- Data Management's dataset list no longer has a language filter; search by name and the Kind buttons remain. ([#431](https://github.com/lacclab/scanpath-studio/issues/431))

### Fixed
- A refresh keeps scanpath B's trial and dataset in Compare, as it already kept scanpath A's, and the screen each one shows on a trial recorded over several screens. ([#428](https://github.com/lacclab/scanpath-studio/issues/428))
- The plot background no longer turns black after opening the Stimulus menu and switching dataset, and the same fix covers Compare's per-scanpath colors and opacities and the font picker. ([#434](https://github.com/lacclab/scanpath-studio/issues/434))
- The desktop app exports GIF, MP4 and PDF on macOS again; a renderer whose browser fails to start now reports an error instead of waiting forever. ([#439](https://github.com/lacclab/scanpath-studio/issues/439))
- Downloads from the desktop app's own window open a Save dialog and confirm where the file went; before, they saved silently with no sign in the window. ([#441](https://github.com/lacclab/scanpath-studio/issues/441))

## [0.38.0] - 2026-10-10

### Added
- Recording setup asks which font the text was shown in, on the add and edit screens, so word labels can be drawn in the experiment's own typeface. ([#399](https://github.com/lacclab/scanpath-studio/issues/399))
- Export only the screens you pick from trials that span several screens: Screens in the Export bundle, render --screens, and the screens argument of api.render_parent_trial. ([#402](https://github.com/lacclab/scanpath-studio/issues/402))
- The README's *See it in action* and the docs Gallery's *The app at work* show thirteen tasks in the app — adding your own data, finding and starring trials, styling the plot, replaying, comparing, Corpus Analysis, exporting and sharing — each recorded with its clicks counted; `scripts/record_workflow_demos.py` re-records them. ([#409](https://github.com/lacclab/scanpath-studio/issues/409))
- The welcome tour, tutorial and setup guide cards can be dragged by their title, and folded to a small tab that reopens where it was left. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- Participant, trial and text metadata tables can each be uploaded as several files, stacked into one table; the CLI's --participant-metadata, --trial-metadata and --text-metadata take several files too. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- The Comparisons subtab has the chip table from above the plot: the selected trial and each match on the page, one row each, under the fields picked in the chips menu. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Crop to data's margin can be set: Figure & canvas → Screen & framing → Margin (Auto keeps the old 5% margin, or set it in screen px), also as a link setting, render --crop-margin PX and the API's crop_margin. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Saccades have an Opacity: it fades the saccade lines and their direction arrows on the static figure, the replay and both scanpaths of a comparison (render --saccade-opacity, saccade_opacity on a link and in the API). ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Seven figure choices that were fixed are now yours to set: the heatmap's opacity, the title's and caption's text size and the caption's colour, the border round the plot, the saccade arrowheads' size, the fixation markers' outline, the coordinate grid's label size, and each colour bar's thickness and length — in the rail, the link, the settings file, `render` and the API. ([#424](https://github.com/lacclab/scanpath-studio/issues/424))

### Changed
- The chip table spans the plot column, with headers at the size of the selector labels. ([#405](https://github.com/lacclab/scanpath-studio/issues/405))
- The Scanpath plot sizes itself to the window so the subtab bar under it (Annotations … Export) stays on screen without scrolling. ([#405](https://github.com/lacclab/scanpath-studio/issues/405))
- The Legends table has column titles and a Show checkbox per row (each legend's only on/off switch), and lists only the legends the figure draws; the fixation-colour legend can now be hidden. ([#407](https://github.com/lacclab/scanpath-studio/issues/407))
- Legends take one of eight spots (each corner, the middle of the top and bottom edges, or down the left or right side), each inside or outside the plot, and legends sharing a spot stack; positions spelled the old way still work. ([#410](https://github.com/lacclab/scanpath-studio/issues/410))
- Each dataset's row on the Data Management page now has its own Edit button beside Remove, replacing the one under the dataset's description. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- Each table's column mapping on the add and edit screens is three short lines of at most four fields, instead of two long ones, so column names are no longer cut off. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- The add and edit screens' Recording setup starts filled in with the answers that invent nothing — the screen estimated from your data, physical size off, text sized to the word boxes — labels how each value is known, asks for the real values while any are estimates, and no longer holds up Add dataset. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- The setup guide no longer narrows the add-dataset screen, which now keeps its full width. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- Recording setup's *Visual angle* line is now *Physical size*: it asks only for the monitor's width, which converts a point-sized font to pixels, and no longer for a viewing distance nothing used. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- The add-dataset screen opens its upload part with Start from: from scratch, from a dataset you added before (its mapping, kept fields and recording setup, copied without a file), or from a saved setup file, with Undo. It replaces the Restore a saved setup popover. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- The add and edit screens' Name, Description and switch help is on the field's dotted-underlined title, like every mapping field, instead of a ? icon. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- Before a file is uploaded, each table on the add-dataset screen says what it holds and what it needs, and offers a larger drop area; a file that can't be read is reported beside the row, where it no longer hides the file's remove button. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- More space between the add-dataset screen's first heading and the dataset name. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- When the Words and Fixations tables cover different trials, the trial picker, list_trials, render --list-trials and the export bundle all list every trial either table has, once, and each draws with the tables it has; list_trials used to list only the trials both tables had, and the picker dropped the trials only the Words table had. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- Each dataset keeps its own stimulus-image folder and filename pattern: they are saved with it, asked for on the add screen, and wait for Save changes on Edit dataset, instead of carrying over to the next dataset and disappearing on restart. ([#417](https://github.com/lacclab/scanpath-studio/issues/417))
- The Share subtab's code names a dataset's own stimulus page with show_stimulus_image=True (and the image folder it came from) instead of a path on this computer, and an overlay or co-animation that draws scanpath B's text now draws B's stimulus page instead of A's. ([#420](https://github.com/lacclab/scanpath-studio/issues/420))
- When the X / Y fields can't be changed (Animate, Compare), their hover says why and how to get them back; on non-screen axes Crop to data and the grid grey out with a reason, since they have nothing to act on. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The background's color box shows the color in use, and a color picked in it applies at once, without choosing Custom first. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The chip table's values are in the app's regular weight, like the trial picker above them, instead of a bolder one. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Comparisons subtab drops the caption that repeated Match field; what the field does is its hover help, on one label and field row. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Comparisons grid shows its matches 12 at a time, in number order (participant 2 before 10), with a pager above and below it, so every match can be seen, not just the first 60. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Save current design dialog fills in a name, My design 1, then 2 and on, so a design can be saved without naming it. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The rail's help text no longer names one corpus: line spacing and the Highlight row are described in general terms. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Fonts read the same on Recording setup and Stimulus → Text: one font list (now with Multilingual), sizes in px or pt on both, Fit to word boxes with its line spacing on both, and a point size read as pixels when the dataset has no physical size. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Plot controls rail is shorter: the design presets sit as close as their columns, the line under Palette sits midway between it and Fixations, and Reset visualization is the presets' height. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The note under Animate is gone; hovering the Animate switch says what it greys, and hovering a greyed rail switch (Fixations, Heatmap, Raw gaze, or one with nothing to draw) says why. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Animate menu shows the trial's duration and its playback time under Replay, beside the speed they follow from. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Animate menu's Frames group explains what a frame is, keeps its spacing and limit sliders live under every preset, names the default grid Standard, and says under Result which of the two decided this trial's frames. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Snap above words is now Snap to line: a snapped fixation keeps its x and moves only up or down onto its text line, and a Position slider sets where on the line it sits (render --snap-position, snap_position on a link, fixation_snap_to_line and fixation_snap_position in the API). ([#423](https://github.com/lacclab/scanpath-studio/issues/423))

### Removed
- The add-dataset screen no longer offers Download example tables. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- Figure & canvas and Filters & highlights no longer draw a line above their first group. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The API's fixation_snap_to_word option is gone; fixation_snap_to_line replaces it. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))

### Fixed
- Scanpath B's row reads Dataset B · Trial B · Screen B, and its screen picker is the same width as A's. ([#405](https://github.com/lacclab/scanpath-studio/issues/405))
- The setup guide no longer scrolls a part of the Add-dataset screen under the top bar, the screen's own header bar stays on screen as you scroll, and on a narrow window the fields under the guide card can be scrolled clear of it. ([#406](https://github.com/lacclab/scanpath-studio/issues/406))
- On a narrow window, or with the plot controls open beside it, the trial picker rows compress and then wrap onto a second line instead of running over the plot controls. ([#408](https://github.com/lacclab/scanpath-studio/issues/408))
- An added dataset's font is its own: opening another dataset no longer draws it in the font chosen for the last one. ([#411](https://github.com/lacclab/scanpath-studio/issues/411))
- A ZIP with a README or other non-table file beside the data now uploads: only the table files in it are read. ([#414](https://github.com/lacclab/scanpath-studio/issues/414))
- A save to the recovery cache that fails part-way (a full disk, a closed app) no longer brings back a mix of old and new tables, metadata and settings: the next launch restores the last complete save. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- On the command line, render -t no longer picks the first participant of a trial id several participants share; it asks for -p, as the app and the API do. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- Corpus Analysis groups defined on a field only one table has (a difficulty level on the Words table, say) now hold the same trials in every measure and count: each group's fixation measures no longer pool every fixation, a field neither table has makes the group unavailable instead of selecting everyone, and a trial the two tables disagree on is left out with a note. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- The Comparisons subtab no longer drops a matching trial whose participant and trial IDs read the same as another's once joined (such as `p1` · `t1 · t2` and `p1 · t1` · `t2`): each gets its own panel and its own row in the similarity table. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- An export bundle's file-name pattern can no longer give a trial's file the name of the bundle's README, index.csv, columns.json, a metadata or a combined table: that file gets the next free name (README-2.md), so every file in the ZIP is the one index.csv lists. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- The Text ID you map is used even when a table also has a unique_paragraph_id column, so such a table no longer fails to join its fixations or groups them under the wrong text. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- A repeated reading's generated trial ID no longer merges with a real trial of the same name: when a participant already has a trial `a_r2`, the second reading of `a` is written `a__r2`, so the two stay separate scanpaths. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- The trial picker lists every participant's reading when participants share a Trial ID (each labelled with its participant, such as `3 [p2]`), a link naming a participant opens that participant's reading, and a link or saved selection that names only a shared Trial ID says it is ambiguous instead of opening the first participant's. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- A trial filter on a field only one table has (a difficulty level on the Words table, say) now narrows every table, so an excluded trial no longer stays in the trial picker through its fixations; a trial whose Words and Fixations tables disagree about the field is left out, and a warning names it. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- Fixations with no X/Y whose Word/IA IDs are text (w1, w2) are no longer all drawn on the first word: adding such a dataset is blocked with a message saying why, and a blank or unreadable Word/IA ID never places a fixation on a box. ([#416](https://github.com/lacclab/scanpath-studio/issues/416))
- The Setup help and Cancel buttons on the Add and Edit dataset screens are no longer clipped at the top when the page is scrolled. ([#419](https://github.com/lacclab/scanpath-studio/issues/419))
- The headless stimulus-image folder now draws: show_stimulus_image=True on plot_scanpath, animate_scanpath and compare_scanpaths (render --show-stimulus-image) draws each trial's own page, and the new api.attach_stimulus_images matches a folder of pages to frames already loaded, the corpus loaders' included. ([#420](https://github.com/lacclab/scanpath-studio/issues/420))
- Cancel in the Save current design dialog closes it whatever the name field holds, and drops the draft name. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Turning word boxes on, changing their colors and changing the heatmap's color bar no longer pause the plot for a second or more on a long page: the figure with word boxes and a heatmap builds about 15 times faster, and an overlay comparison about 20 times faster. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Fixations color bar row, greyed when the color is one color, Line or a categorical column, now says why on hover, and where the legend a categorical color gets is switched off (Figure & canvas, Legends). ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The Illustration label no longer names snapped fixations while the Fixations layer is off, or saccade arcs while Saccades is off, and names neither in Animate or Compare, which draw neither; with the fixations off, the saccades run between the recorded positions. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- My designs has even margins: its list, the save button and Export / Import line up on both sides, with no extra space at the bottom, and design names start at the left of their cards. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- A dataset without fixation onsets (PoTeC) no longer shows a Trial duration of about a second beside a minute of fixations: the chip is left out, and the replay calls its span Total fixation time, played back to back. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- A plot-control popover no longer shakes while the pointer rests on its last rows: a field's tooltip opens above its title when there is no room below. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- A replay's frame limit is now exact: a limit of 120 gives at most 120 frames, not 121, in the app, the API and render --anim-max-frames. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- The title and caption's Available fields, their check and their preview now use the selected trial and the fields the figure renders with: the preview shows the trial's real ids, the trial's own fields such as TRIAL_INDEX are listed and accepted, and the list says which fields it leaves out and why. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))
- Picking a word-box fill color now shows it: a fill fainter than 0.15 opacity is raised to 0.20, and a color picked in a plot-controls popover is kept when you close the popover by clicking the page. ([#423](https://github.com/lacclab/scanpath-studio/issues/423))

## [0.37.1] - 2026-10-07

### Added
- Choose where each legend sits: Figure & canvas → Legends places the Compare, saccade-type, colour and size-key legends above, below, beside or inside the plot, stacked or in a row, at any text size. ([#384](https://github.com/lacclab/scanpath-studio/issues/384))

### Changed
- The plot rail's Flag fixations section is now Filters & highlights, with a filter icon. ([#396](https://github.com/lacclab/scanpath-studio/issues/396))

### Fixed
- The desktop app's Update & restart is sturdier: a failed download says why (a missing file, a full disk) instead of asking whether you are offline, Cancel works until the moment it restarts, two updates started at once no longer collide, and About stops mentioning the last update after a week. ([#394](https://github.com/lacclab/scanpath-studio/issues/394))
- Changing trials no longer leaves a scanpath's fixation index range narrowed to a few fixations, and the plot now says so whenever the index range hides some of a trial's fixations. ([#395](https://github.com/lacclab/scanpath-studio/issues/395))
- A line's first word now sits at the left edge of its box, as it was shown in the experiment, instead of being centred in a box that carries only the gap after it. ([#397](https://github.com/lacclab/scanpath-studio/issues/397))
- Stretch text to AOI boxes now reads the exact font from monospace word boxes padded with half a space on each side, instead of drawing the text several percent too small. ([#397](https://github.com/lacclab/scanpath-studio/issues/397))
- The hosted demo follows each release again; it had stayed on v0.35.0. ([#400](https://github.com/lacclab/scanpath-studio/issues/400))

## [0.37.0] - 2026-10-07

### Added
- Help → About can check for updates: it shows whether a newer release is out and the command that updates your install, or the download for the desktop app; also scanpath-studio version --check and api.check_for_updates(), and only ever when asked. ([#139](https://github.com/lacclab/scanpath-studio/issues/139))
- The desktop app updates itself: Help → About → Check for updates → Update & restart downloads, checks and tests the new version, then restarts into it, and puts the old one back if it doesn't start. ([#385](https://github.com/lacclab/scanpath-studio/issues/385))

### Changed
- Every build now reports its own version: between releases it is a development build such as 0.35.0.post3+g8f18219 (three commits after 0.35.0), shown in About, scanpath-studio --version, crash reports and exports, and as scanpath_studio.__version__; the hand-set release number is scanpath_studio.__release__. ([#139](https://github.com/lacclab/scanpath-studio/issues/139))

### Fixed
- Dataset downloads now trust the certificates your operating system trusts, so they no longer fail with CERTIFICATE_VERIFY_FAILED on a python.org Python on macOS or behind a network that inspects HTTPS. ([#391](https://github.com/lacclab/scanpath-studio/issues/391))

## [0.36.0] - 2026-10-07

### Added
- The chips above the plot can be hidden from the ✏️ menu at the end of the trial row, which keeps their fields for when you show them again; a share link carries the choice. ([#373](https://github.com/lacclab/scanpath-studio/issues/373))
- A Windows installer (ScanpathStudio-windows-x86_64-setup.exe): one download that installs the desktop app for your account, adds it to the Start menu and uninstalls from Settings → Apps, with no unzipping. The .zip is still there for running without installing. ([#387](https://github.com/lacclab/scanpath-studio/issues/387))

### Changed
- The dataset and trial dropdowns (and Compare's) open as wide as their longest option, so long names are read in full. ([#381](https://github.com/lacclab/scanpath-studio/issues/381))
- The scanpath plot is centred in its column and grows to fill the column when the window has room, rather than stopping at its true size; the chip table keeps each trial on one line. ([#381](https://github.com/lacclab/scanpath-studio/issues/381))
- The screen picker sits at the right end of the trial row as a compact dropdown with ◀ ▶, instead of a row of its own under each trial row, with the sort, filter and chips menus after it at the row's end. ([#381](https://github.com/lacclab/scanpath-studio/issues/381))
- The Export subtab asks *Self-contained HTML* only once HTML is the chosen format, under that format — the bundle asks its own. ([#382](https://github.com/lacclab/scanpath-studio/issues/382))

### Removed
- The Export subtab's *Download this comparison as a bundle* expander. ([#382](https://github.com/lacclab/scanpath-studio/issues/382))

### Fixed
- A metadata table uploaded to one dataset no longer attaches itself to the next dataset you open; switching datasets now empties the metadata uploaders. ([#380](https://github.com/lacclab/scanpath-studio/issues/380))
- A UTF-16 table, such as an EyeLink Data Viewer report, now reads its column names instead of showing every column as "Unnamed". ([#383](https://github.com/lacclab/scanpath-studio/issues/383))

## [0.35.0] - 2026-10-07

### Added
- The dataset setup guide now ends on a step about saving: Add dataset, and Download setup file to reuse the mapping next time. ([#365](https://github.com/lacclab/scanpath-studio/issues/365))
- The Corpus Analysis address names the open section (`?corpus_subtab=Per+reader`), so a bookmark or a copied link reopens it. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- Screen readers announce the scanpath figure, the animated replay, the Corpus Analysis charts and the Share link box by name. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- Help → About links to Discussions → Q&A for questions and to the bug-report form, and the FAQ says where to ask, how to report a bug, and that a 0.x release may change links, settings, the API and the CLI. ([#371](https://github.com/lacclab/scanpath-studio/issues/371))
- An unexpected error now says it is most likely a bug in the app and links to the bug-report form and Q&A, above the error details to paste into the report. ([#376](https://github.com/lacclab/scanpath-studio/issues/376))
- Export → Current figure, save_figure and render take a print width (mm or in) and DPI, written into the PNG; Share → Code writes the same pixels as the download. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Data Management → Saved on this computer names everything it restores, and Clear what is saved… deletes it after a confirmation and starts the app over. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))

### Changed
- When the fixation table maps a Word/IA ID, fixations now count for exactly that word, and a blank means no word; without one, a fixation counts for the word box it falls in and is no longer snapped to a word up to 50 px away. ([#352](https://github.com/lacclab/scanpath-studio/issues/352))
- In Compare, the Saccades popover now lays out like Fixations: the Line group becomes Scanpath A's colour, style and width, with Scanpath B's group under it, instead of greyed figure-wide rows followed by a duplicate per-scanpath block. ([#361](https://github.com/lacclab/scanpath-studio/issues/361))
- In Compare, the Word boxes popover now has a Scanpath A and a Scanpath B group, each with its own line and fill colour (the new box_fill_color style key, on the Share link, CLI --style-a/--style-b and the API too). ([#363](https://github.com/lacclab/scanpath-studio/issues/363))
- The hosted app's run-locally tip now says a local install is faster and handles much larger datasets. ([#365](https://github.com/lacclab/scanpath-studio/issues/365))
- The add-dataset wizard's Setup help popover is now a compact two-row menu (Show setup guide · More documentation). ([#365](https://github.com/lacclab/scanpath-studio/issues/365))
- Edit dataset.
- The Data page's Participants, Trials and Texts tabs list the ids in your data, with counts, when no separate table is attached — and the Participants and Trials tabs add every column that holds one value per reader or trial. ([#367](https://github.com/lacclab/scanpath-studio/issues/367))
- In Compare, the Raw gaze popover now has a Scanpath A and a Scanpath B group, each with its own sample colour (the new raw_gaze_color style key, also on the Share link, CLI --style-a/--style-b and the API). ([#368](https://github.com/lacclab/scanpath-studio/issues/368))
- Debug opens from ❓ Help → About as a resizable drawer on the right, beside the view it describes. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- Typing a dataset's description or a built-in dataset's new name, or flipping the editor's character-box toggle, no longer reruns the page; the value is applied when you save. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- Name fields (a new dataset, an edited one, a saved or renamed design) no longer accept an empty name; clearing one keeps the last name. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- Requires Streamlit 1.65. ([#369](https://github.com/lacclab/scanpath-studio/issues/369))
- In Compare, the Heatmap popover now has a Scanpath A and a Scanpath B group, each with its own colour scale on the shared range, and a colour bar each when they differ (the new heatmap_colorscale style key, also on the Share link, CLI --style-a/--style-b and the API). ([#370](https://github.com/lacclab/scanpath-studio/issues/370))
- The README, Getting started and the hosted demo's tips now put the desktop app first for working with your own data. ([#371](https://github.com/lacclab/scanpath-studio/issues/371))
- The documentation site is now published with each release, so it describes the version pip installs, and each GitHub release page opens with what the tool is and how to get it. ([#371](https://github.com/lacclab/scanpath-studio/issues/371))
- On the hosted demo, clicking a public corpus the server doesn't hold (PoTeC, OneStop) now says in a dialog that it opens in the desktop app or a pip install, instead of opening the demo in its place. ([#371](https://github.com/lacclab/scanpath-studio/issues/371))
- The README's replay and two-reader animations, the app demo, and the docs screenshots were re-captured from the current app. ([#372](https://github.com/lacclab/scanpath-studio/issues/372))
- A misspelt CLI flag gives a short error with a suggestion, options put before the command say where they belong, render takes --word-boxes, --heatmap, --no-text and US/UK spellings, and cache prints real plurals. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Compare names its pickers Scanpath B from and Scanpath B, titles side-by-side panels A and B, and shows its legend by default; Comparisons matches on the same text or the same participant. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Hovering a fixation names the word it landed on: Fixation 41 · 336 ms · on “Droppings!” (word 27). ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- The API and CLI draw the app's Scanpath design by default (no heatmap, word boxes or fixation numbers unless asked, A/B legend on), and the bundled demo uses its recorded screen; reproduction code written before this may need those layers turned on. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Debug moved from the Help menu into About; the welcome tour no longer starts over a restored session; the FAQ says where data goes for where the app runs. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Only the bundled demo highlights its answer span by default, and a highlighted figure carries a key saying what is marked. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Corpus Analysis says participant, not reader: the Per participant subtab (old links to Per reader still open it), its labels and counts. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Mapped fields are named by their role (Participant, Text, Trial) with the source column in a tooltip, and a trial is written the same way in the picker, Comparisons, Annotations and Corpus Analysis. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- The trial chip Total reading time is now Total fixation time, beside a new Trial duration chip; the replay's clock is labelled Trial time. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Labels, help and messages across the app, CLI and docs use one term per concept (participant, dataset, settings file, Flag fixations) and US spelling. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- The add and edit screens call the word table Words (interest areas), say which EyeLink report goes in each row, detect an item column as Text ID and keep condition columns. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))

### Removed
- Groups → Paired summary bars no longer draws error bars, which pooled words across participants; its title follows the Aggregate. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- The tutorials' Don't auto-show checkbox, which no setting read, is gone. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))

### Fixed
- Switching datasets no longer leaves the text highlight on another dataset's column (the demo read IA_SKIP after a trip through OneStop). ([#358](https://github.com/lacclab/scanpath-studio/issues/358))
- The computations reference now describes run/pass columns and per-reader normalization as the code computes them. ([#359](https://github.com/lacclab/scanpath-studio/issues/359))
- Figure titles and hovers spell a column ending in `_id` as "ID" ("Participant ID", not "Participant Id"). ([#359](https://github.com/lacclab/scanpath-studio/issues/359))
- The code `render --print-code` writes for `--words` / `--fixations` now passes on the `--word-schema` / `--fix-schema` mapping the files were read with. ([#359](https://github.com/lacclab/scanpath-studio/issues/359))
- Comparing with a trial whose id already reads like a de-duplicated label ("x [p2]") no longer hides another reader's trial of the same id: every candidate keeps its own entry in the Compare to picker. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- A comprehension_questions value of the wrong shape (an object, nulls, nested values) no longer crashes the trial: unreadable records are skipped with one warning, and the Stimulus & Context tab now renders only while it is open. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- Importing a designs file now checks every setting the way a link is checked: an invalid value is skipped and named in the import message instead of crashing the app when the design is applied, and a file from a newer version says so. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- Questions, answers and context fields in Stimulus & Context are shown as the literal text in the data: Markdown, links, images and HTML in a value no longer format the panel or make the browser fetch a remote image. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- Span and answer flags written as the text "False" now read as false: false span rows are no longer highlighted or counted as fixated, an incorrect answer no longer shows as correct, and a true/false filter keeps both of its classes. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- A stimulus image whose origin is (0, 0) in the words table now sits at (0, 0) instead of taking the fixation table's origin. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- Files that share a name in different folders of a ZIP, or of a multi-file upload, now keep distinct source_file labels (reader-a/fixations, reader-b/fixations), so mapping that label as participant or trial no longer merges two readers into one. ([#360](https://github.com/lacclab/scanpath-studio/issues/360))
- The Synthetic sample's row in Available datasets shows its counts on a server with no recovery cache, such as Streamlit Community Cloud, instead of Not loaded. ([#364](https://github.com/lacclab/scanpath-studio/issues/364))
- The package summary on PyPI no longer says the app computes reading measures. ([#371](https://github.com/lacclab/scanpath-studio/issues/371))
- Screen readers hear plain control names (no markdown or icon words), and the figure can be reached with Tab. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Corpus Analysis captions name only the views offered, Groups keeps its comparison across subtabs, the trend line breaks at filtered-out trials and Per text opens on the trial viewed in Scanpath. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- A ZIP holding both fixation and interest-area reports is split by kind: each table row reads only its own reports and says which files it left out. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- At 1024–1280 px the plot rail keeps its labels and design names, and wide tables show that they scroll. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- The Python API accepts any spelling of a figure option's value (case, dashes, the CLI's names) and raises on an unknown one instead of drawing the default. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- A Share link to a dataset you added names it, and a recipient who doesn't have it is told which dataset is missing and how to get it, instead of the view being applied to another dataset. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Share → Code writes only options that change the figure, None as None, and a palette only when the colors match it. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- Corpus Analysis and word exports leave a skipped word out of FFD, FPRT, RPD and single-fixation duration instead of counting an imported 0 (TFD keeps its 0); a blank imported second-pass duration is 0 where the fixation count is known. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))
- A palette or design preset no longer reverts after a rail popover has been opened, an annotation no longer jumps the view to trial 1, and each dataset reopens on the trial it was left on. ([#377](https://github.com/lacclab/scanpath-studio/issues/377))

## [0.34.0] - 2026-10-06

### Added
- The Illustration label's text can be edited (rail, link, settings file, `render --illustration-text`, `illustration_text=`), and title and caption have their own switches. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Word boxes: the outline has its own opacity (rail, share link, `--word-box-line-opacity`, `word_box_line_opacity=`), and each opacity now sits beside its colour. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Data checks also report infinite fixation durations and onsets, word boxes at infinity, and per-screen screen sizes that are infinite or 0 or less. ([#351](https://github.com/lacclab/scanpath-studio/issues/351))

### Changed
- Data Management's Status column says *Loaded* (opens at once) or *Available* (opening reads its files) instead of *Ready*. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Figure & canvas: *Whole monitor* is now an unticked *Crop to data* box, the monitor size and the px/degree line left the rail (set on the Data page), and the axes row warns that fields other than x / y draw fixation markers only. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Both colour scales (fixations and heatmap) open in Blues, and colour bars are shown by default. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Heatmap: *Duration mass* is removed (links and settings files naming it open *Interpolated*); Interpolated gets a **Blur** row — Auto (showing the σ it uses) or a fixed σ in px (`heatmap_sigma_px`, `render --heatmap-sigma`); the colour range starts at 0 and is offered for Fixation count too. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- The fixations and the heatmap each have their own colour bar settings (show, orientation, tick angle and size), under their layer in the rail; `render` takes `--no-fixation-colorbar` / `--fixation-colorbar-*` and the heatmap equivalents, and links or settings files using the old shared settings apply them to both. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Shorter help texts throughout the plot controls. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- The command-line help, API reference, error messages and computation register no longer show internal tracker IDs. ([#354](https://github.com/lacclab/scanpath-studio/issues/354))

### Removed
- The px-per-degree figure is no longer shown in the Recording setup forms, and the export's saccade table no longer converts amplitudes to degrees. ([#349](https://github.com/lacclab/scanpath-studio/issues/349))
- Measures the app computes itself are held back until validated: the reading-measure, summary, preprocessing and analysis-table API functions, the `analyze` command, the export bundle's measure family, and the computed Corpus Analysis views (Reading summary, Progressive vs regressive, Landing-position curve, Reader summary table) now need `SCANPATH_EXPERIMENTAL=1`. ([#354](https://github.com/lacclab/scanpath-studio/issues/354))

### Fixed
- `render` accepts v0.33.0's `--colorbars` and shared `--colorbar-orientation` / `--colorbar-tickangle` / `--colorbar-tickfont-size` again, the last three setting both colour bars unless a bar's own flag is given. ([#351](https://github.com/lacclab/scanpath-studio/issues/351))
- A figure's title, caption, Illustration label, word-heatmap title and the names of compared scanpaths are drawn as written: angle brackets, `&` and `%{…}` no longer act as Plotly markup, and only a real newline starts a new caption line. ([#351](https://github.com/lacclab/scanpath-studio/issues/351))
- An infinite position, duration, onset or word-box size no longer stretches a figure's axes or crashes it or its replay; the figure leaves such a row out (or times it by duration), and a per-screen screen size that is not finite and positive falls back to the dataset's own. ([#351](https://github.com/lacclab/scanpath-studio/issues/351))
- The plot rail shows "Word boxes" in full at a 1280-pixel window. ([#351](https://github.com/lacclab/scanpath-studio/issues/351))
- `scanpath-studio cache` no longer prints Streamlit's "No runtime found" warnings, the CLI docs list the `check` command, and the MultiplEYE and benchmark-corpus loaders are no longer advertised in the package's public names. ([#354](https://github.com/lacclab/scanpath-studio/issues/354))
- Corpus Analysis › Per reader › Fixation duration over time opens on a per-fixation measure instead of an empty notice. ([#354](https://github.com/lacclab/scanpath-studio/issues/354))
- An Export bundle's README mentions `annotations.json` only when the bundle holds it, that is, when an exported trial has an annotation. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- A Share link to a comparison whose second reader or trial id contains a colon now restores that comparison. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- The export's file path pattern must stay inside the ZIP: an empty pattern, a leading `/` or drive, a backslash, and an empty, `.` or `..` folder or file name are refused before anything is rendered, in the app and by `bulk_export`. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- Metadata tables saved on this computer that can't be read back are kept as they are, said under **Saved on this computer** with **Retry** and **Remove from cache**, instead of being deleted by the next save. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- An infinite value in a participant, trial or text metadata table counts as no value, so its filter opens instead of failing, and **Keep unknown values** decides whether those records stay. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- Ids that only differ as "1" and "1.0" in one column stay two readers or trials, and a participant or trial id that is only spaces or tabs is reported and left out like a missing one, in raw gaze too. ([#355](https://github.com/lacclab/scanpath-studio/issues/355))
- Compare's A/B trial table fits its column — a long trial id wraps instead of pushing the last columns out of view, and a table still too wide shows its scrollbar — and a value both scanpaths share is written in both rows instead of one merged cell that read as B's left blank. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- The dataset table offers Remove only for datasets you added: on the demo and the public corpora it only hid the row for the session, with no way back. The table also sits a little lower under the Data Management title. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- The rail's design-preset highlight goes back to the preset when Compare is switched on and then off again, instead of staying on Custom. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- Export's HTML option is labelled Self-contained HTML, and its help says it makes the file open without an internet connection. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- Corpus Analysis › Per text › Per-reader profiles leaves room for each reader's title, which no longer sits on the panel above. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- With saving switched off at launch, Saved on this computer says so in plain words, and names the setting only in a small line under it. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- The welcome tour's last step rings the whole nav once instead of drawing a bracket round each link, and the ring goes when the tour ends. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))
- The add-dataset screen's setup guide counts its three parts (Part 2 of 3) instead of its cards, leaves room beside the form on a wide screen instead of covering the upload rows, and its help pill is a compact Setup help next to Cancel. ([#356](https://github.com/lacclab/scanpath-studio/issues/356))

## [0.33.0] - 2026-10-04

### Added
- `scanpath-studio check` and `check_data_health`: a *Data checks* line on the Data page flags impossible values (≤ 0 ms fixations, missing positions, zero-area word boxes). ([#339](https://github.com/lacclab/scanpath-studio/issues/339))
- Compare draws raw gaze, and each reading's word-box outline can be recoloured. ([#311](https://github.com/lacclab/scanpath-studio/issues/311), [#345](https://github.com/lacclab/scanpath-studio/issues/345))
- Export bundles list their files in `index.csv`, preview their size before building, can be stopped, and can be saved as self-contained offline HTML. ([#337](https://github.com/lacclab/scanpath-studio/issues/337))
- Edit dataset previews mapping changes before saving, can add a raw-gaze table, and lets you set your own recording setup for built-in corpora. ([#337](https://github.com/lacclab/scanpath-studio/issues/337))
- Corpus Analysis shows which filters apply, explains each measure in place, and saves a JSON recipe beside every table download. ([#328](https://github.com/lacclab/scanpath-studio/issues/328), [#335](https://github.com/lacclab/scanpath-studio/issues/335))
- Add dataset offers downloadable example tables; Color by offers any numeric column a dataset kept. ([#328](https://github.com/lacclab/scanpath-studio/issues/328), [#339](https://github.com/lacclab/scanpath-studio/issues/339))
- Public datasets download into one folder you choose; OneStop is now four datasets, one per reading regime. ([#288](https://github.com/lacclab/scanpath-studio/issues/288), [#295](https://github.com/lacclab/scanpath-studio/issues/295))

### Changed
- The app, API and exports name columns as they are in your files; `load_scanpath_data(names="canonical")` gives the internal names. ([#333](https://github.com/lacclab/scanpath-studio/issues/333), [#338](https://github.com/lacclab/scanpath-studio/issues/338))
- Fixation markers use one fixed duration scale by default, so a duration is the same size in every figure. ([#335](https://github.com/lacclab/scanpath-studio/issues/335))
- Word boxes have their own rail section with outline and fill colours. ([#343](https://github.com/lacclab/scanpath-studio/issues/343))
- Faster: plot setting changes on large datasets (~3×), the animated replay (~3×), and switching back to the previous dataset. ([#289](https://github.com/lacclab/scanpath-studio/issues/289), [#339](https://github.com/lacclab/scanpath-studio/issues/339), [#342](https://github.com/lacclab/scanpath-studio/issues/342))
- Edit dataset holds every change until Save changes and opens below the dataset list; the Data tab is now Data Management. ([#319](https://github.com/lacclab/scanpath-studio/issues/319), [#337](https://github.com/lacclab/scanpath-studio/issues/337))
- Trial chips are a compact table (two rows in Compare) and trial ids read part by part. ([#303](https://github.com/lacclab/scanpath-studio/issues/303), [#305](https://github.com/lacclab/scanpath-studio/issues/305), [#313](https://github.com/lacclab/scanpath-studio/issues/313), [#326](https://github.com/lacclab/scanpath-studio/issues/326))
- Public corpora download at a pinned, size-checked version. ([#321](https://github.com/lacclab/scanpath-studio/issues/321))
- Shorter docs with fresh screenshots; the app uses its Material icons throughout. ([#285](https://github.com/lacclab/scanpath-studio/issues/285), [#302](https://github.com/lacclab/scanpath-studio/issues/302))

### Removed
- Corpus Analysis → Groups no longer runs significance tests; it reports group means and their difference. ([#335](https://github.com/lacclab/scanpath-studio/issues/335))

### Fixed
- Compare: each reading keeps its own screen, canvas and stimulus image; categorical colouring and Animate + Compare work in every layout. ([#337](https://github.com/lacclab/scanpath-studio/issues/337), [#339](https://github.com/lacclab/scanpath-studio/issues/339), [#340](https://github.com/lacclab/scanpath-studio/issues/340))
- IDs no longer merge: zero-padded ids, underscores in composite ids, and PoTeC's trial id (now reader + text). ([#291](https://github.com/lacclab/scanpath-studio/issues/291), [#335](https://github.com/lacclab/scanpath-studio/issues/335), [#337](https://github.com/lacclab/scanpath-studio/issues/337))
- Corpus Analysis measures are counted correctly: skip / regression rates, reading speed without timestamps, per-screen sentences, and Groups cohorts. ([#324](https://github.com/lacclab/scanpath-studio/issues/324), [#335](https://github.com/lacclab/scanpath-studio/issues/335))
- Edit dataset's Cancel, Estimate, Save setup and added tables behave as expected. ([#291](https://github.com/lacclab/scanpath-studio/issues/291), [#337](https://github.com/lacclab/scanpath-studio/issues/337))
- Heatmaps, colour bars, GIF/MP4 frames, arc saccades and word labels draw correctly in more cases. ([#294](https://github.com/lacclab/scanpath-studio/issues/294), [#339](https://github.com/lacclab/scanpath-studio/issues/339), [#340](https://github.com/lacclab/scanpath-studio/issues/340))
- Share links and settings files restore Compare and Animate state, and say why when a reading can't be opened. ([#337](https://github.com/lacclab/scanpath-studio/issues/337), [#339](https://github.com/lacclab/scanpath-studio/issues/339))
- A damaged dataset in the recovery cache no longer blocks the others; a corrected large table no longer reloads its old values. ([#314](https://github.com/lacclab/scanpath-studio/issues/314), [#339](https://github.com/lacclab/scanpath-studio/issues/339))
- The macOS folder button no longer crashes the app; icon-only buttons have screen-reader names. ([#298](https://github.com/lacclab/scanpath-studio/issues/298), [#324](https://github.com/lacclab/scanpath-studio/issues/324), [#328](https://github.com/lacclab/scanpath-studio/issues/328))

### Security
- Figures no longer offer Plotly's "Share chart…" button, which uploaded data to Plotly Cloud. ([#310](https://github.com/lacclab/scanpath-studio/issues/310))

## [0.32.1] - 2026-10-01

### Added
- Corpus Analysis → Groups can now split or filter a cohort by an attached trial- or text-metadata field (marked 📋 and 📄), alongside reader fields and trial conditions.

### Changed
- The README and docs-home app demo recording is re-recorded from the current app.
- Export, `analyze` and `api.analysis_tables` write only the reading measures the dataset brought and compute none, as Corpus Analysis does; the Export bundle's Mega-table option is replaced by a "Combine all trials into one file" toggle that writes each chosen table once with every trial stacked in it.
- A replay's page is now a fraction of its old size: frames travel packed and are rebuilt in the browser, so the demo's longest trial loads as 0.3 MB instead of 12 MB (0.7 MB instead of 66 MB at the finest frame grid), in the app, the saved HTML and the docs gallery alike.

### Fixed
- A missing corpus's "isn't here yet" note no longer carries over to the next dataset you open after a load that stopped at a column-mapping problem.
- The bundled demo now holds only readers it has fixations for: the third reader, who had word boxes but no fixations, is gone, so every trial the Data page counts can be opened.
- A Participants, Trials or Texts table now picks its id column by itself whenever the data would, so a Texts table keyed by `unique_paragraph_id` needs no manual pick.
- A text-metadata field picked in the chips now shows its value above the plot, like participant and trial fields; before, the chip silently rendered nothing.
- Favorites, tags and notes now belong to the dataset they were made on: another dataset that reuses the same participant and trial ids no longer shows them, and annotations saved by an earlier version come back on the added dataset that has their trial, or else on the first dataset you open.
- A word table with no participant column now attaches to each reading by its trial ID, or by Text ID when the trial IDs include the reader, so the add-dataset screen says how the words attached and stops with a message instead of adding a dataset with no word boxes; with no Text ID mapped, a repeated reading now shares its first reading's text ID, so per-text grouping pools re-readings.
- The Texts count on the Data page and in a dataset's Stats now counts the text ids in every table, so a dataset whose text id is only on its fixations no longer says it has none.
- An AOI export whose word-id column is `AOI_ID` now maps it by itself, next to `AOI_LABEL` and the `AOI_*` box edges, instead of sending you to map it by hand.
- When scanpath B comes from a second dataset, the Share code snippet's Python and CLI halves now both load B's own tables (placeholders `B_WORDS` / `B_FIXATIONS` to point at its files) and state B's screen, instead of looking B's reader up in the first dataset.
- Wizard and Edit-dataset metadata rows keep their Participants / Trials / Texts title visible once a file is attached.
- Long 'Extra fields to keep' chip lists wrap onto more rows instead of scrolling sideways out of sight.
- Two trial filters over columns that read the same, such as `TRIAL_INDEX` and `trial_index`, no longer share a title: the second names its column, as the chip editor already did.
- Narrowing the trial pool no longer switches the design preset to 🛠️ Custom, and a trial with no fixations no longer clears the fixation hover fields you picked.
- A dataset recorded as raw gaze alone now opens showing its samples: the Raw gaze layer is on by default when a dataset has no fixations, samples-only trials are pickable, the chips count gaze samples instead of showing zero reading time and fixations, no "derived from raw gaze" Illustration label appears, Animate and Compare fall back to the static figure with the reason, the Export bundle draws the samples and can include them as a table, and `render --raw-gaze` and `plot_scanpath(raw_gaze=…)` accept raw gaze as the only input.

## [0.32.0] - 2026-09-30

### Added
- In Compare, each scanpath has its own filters — fixation window, short / long / off-text / blink flags and saccade types.
- Column auto-detection catches a vendor prefix or suffix on a known column name.
- The macOS desktop app is signed and Apple-notarized, and ships as a `.dmg`.
- A Code of Conduct, linked from the README and CONTRIBUTING.
- The desktop app opens in its own window, not a browser tab.
- A title or caption can name a metadata table's fields, and a data table's saved fields, as `{table.field}`.
- A long wait says what the app is doing: a card with the step, a count, the elapsed time and a Cancel.
- Cancel a dataset load, an animation build, Compare's second dataset or a download, and go back to where you were.
- A dataset has a description, and the Data page lists every annotation on it — to export, import or delete.
- Saved designs export to a file and import from one, and the Export bundle can include the exported trials' annotations.

### Changed
- Corpus Analysis shows the reading measures your report brings and computes none; map them on the AOI table.
- The repository drops the pre-migration tracker archive and seven finished design plans.
- Changelog entries are one file per item in `changelog.d/`, written into CHANGELOG.md at release, so parallel PRs no longer conflict; entries are one line, with no Details half.
- Add a dataset beside the picker: create manually or import files, with a synthetic sample ready to explore.
- A dataset that takes a while to open shows a skeleton of the page and its steps, not a lone banner.
- Building an animation counts its frames, and the plot shows a placeholder until the browser has drawn it.
- The trial picker walks trials in the order the data has them; Trial ID is a choice in ⇅.
- Compare's A/B legend is larger, so the two readings' names read at a glance.
- 📂 Available datasets is a focused table: click a row to open it; Status says whether it is loaded.
- The open dataset is described in one plain sentence, with its home page and a note only where a figure reads differently.
- Rename a dataset on ✏️ Edit dataset, opened by one Edit dataset button; Status sits beside the name.
- 💾 Session is gone: Debug is under ❓ Help, what's saved at the foot of 🗂️ Data, the settings file in 🔗 Share.

### Fixed
- Choosing the Synthetic sample shows it; the editor opens from its Edit button.
- Removing a dataset you added removes the annotations on its trials, as its confirmation says.
- Attached participant, trial and text tables survive a refresh, and their fields stay in the filters, chips and trial sorting.
- ✅ Save changes on ✏️ Edit dataset no longer strips the word boxes and text from a dataset whose AOI table has no reader column.
- ✅ Save changes on ✏️ Edit dataset keeps an estimated screen, and the estimate reads the data.
- Metadata tables belong to the dataset they were attached to.
- AOI box columns with a prefix or suffix auto-fill even when the table carries two box encodings.
- Clearing the screen fields in a mapping makes the table single-screen again.
- The documented check for IDs an open PR has taken actually reads the PR's changelog.
- The plot-controls rail no longer looks cut off while a figure is being drawn.
- Plot controls use the full right column without a separate scrollbar.
- A corpus that isn't on this machine no longer shows the demo's counts as its own.
- An auto-detected Trial, Participant or Text ID is highlighted, with a ✨ button to confirm it, like every other field.
- The trial slider is wider, and a long trial id under it no longer wraps behind the chips.
- The Share link is readable in dark mode.
- A saved design or Custom view carries every plot control: Compare, each scanpath's styles and filters, the fixation windows and the replay speed.

## [0.31.2] - 2026-09-27

### Changed
- `export_animation` needs no frame time, and `plots.animation_autoplay_frame_duration` is gone.

### Fixed
- The replay runs in real time: a 20.8 s reading takes 20.8 s to replay, not 26 s.
- Changing the replay's speed or Autoplay no longer rebuilds every frame.
- With 🎬 Animate on, a click that doesn't change the replay no longer reloads it: 0.4 s instead of 19 s at 2,000 frames.

## [0.31.1] - 2026-09-26

### Added
- Scanpath Studio has a Zenodo DOI, and every release archives itself there.
- A docs Gallery: each figure drawn from the demo while the site builds, with the code that makes it.
- Cite, Changelog and Glossary pages, and hover definitions for FFD, FPRT, RPD, TFD and the rest.
- The docs list every CLI flag and every figure option, generated from the code.

### Changed
- The plot-controls rail drops its tinted card for one divider line.
- The README is a landing page: three ways to run it, a docs map, and the detail left to the docs.
- The docs site is organised by reader: Use the app, Automate, Reference, Project.
- The feature guides show the app, in screenshots a script re-captures.
- The docs site navigates without reloading, serves its own fonts, dates each page, and publishes `/llms.txt`.
- The docs keep only what the beta stands behind: no security audit, no internal pages, no claims the code doesn't back.
- MultiplEYE and the benchmark set-up entry are held back from the beta.
- The app no longer discovers datasets on its own: a bundle on disk no longer puts its corpora in the picker.
- `render` no longer takes `--monitor-mm`, `--viewing-distance` or their `--compare-*` twins, which nothing read.
- CI's Coverage check measures through `sys.monitoring`, taking about half as long.
- The app draws its icons from one Material Symbols set instead of emoji.
- The current figure, the Compare pair bundle and the animation's HTML each download in one click.
- The current figure's PNG and SVG save instantly from the browser, and the plot's camera saves the same PNG.
- Clicking a rail section's name flips its switch, or opens its settings where it has none.
- Compare's B picker lists every trial, A's own included, so A and B count the same trials.
- A side-by-side or stacked comparison of two different texts no longer carries a caption saying so.
- Fixation color or Colorscale sits beside "Color fixations by", on the same row.
- Fixation index, its label colour and its label size share one row, greyed while it is off.
- "Snap fixations above words" moves to the bottom of 👁️ Fixations ▾.
- A colour range's *Auto* checkbox sits on the range's own row.
- 👁️ Fixations ▾ is regrouped: one *Marker* group with a caption per row, a narrower title column, and more space between rows.
- ↗️ Saccades ▾ takes the Fixations layout: one *Line* group, and *Direction arrows* as a Show row.
- 🔥 Heatmap ▾: a *Style* row with Duration mass's spread beside it, and one *Color* group.
- 🔵 Raw gaze ▾: one *Marker* group.
- 🧹 Filter ▾: the fixation classes are one table, and *All trials* sits on the index range's row.
- 📄 Stimulus ▾ and 📐 Figure & canvas ▾ take the Fixations layout.
- The 🎬 Animate and ⚖️ Compare ▾ popovers take the same layout.

### Fixed
- The rail's "Plot controls" heading is compact again, on one line, with its new icon.
- `color_by="line"` and `render --color-by line` colour each fixation by its text line, as the app's "line" option does.
- A refused cross-screen overlay says what actually happened on each surface, and `render` names its own flags.
- `animate_scanpath` co-animates one second reading, not B's whole corpus; `trial_b=` picks it.
- The missing-browser hint works in the desktop app, and the in-app FAQ drops its developer-only entry.
- A co-animation of two datasets is held to the overlay's screen check from the API and the CLI too.
- A `help=` tooltip shows only while its own button is hovered or keyboard-focused, and closes when the pointer leaves.
- The ✏️ Edit dataset and add-dataset header bars take the dark theme's background instead of staying white.
- One click on a popover's ▾ opens it; it no longer sometimes takes two or three.
- A stacked comparison no longer titles only its lower panel when the A/B legend is off.
- A rail popover no longer scrolls down into empty space below its last row.
- Saccade class colours and the Filter's highlight colours show their real colour in the picker, not black.

## [0.31.0] - 2026-09-24

### Added
- A ⛶ Fullscreen control on the scanpath, animation, comparison and stimulus figures.
- `render` can name the two traces of a comparison — `--label-a` / `--label-b`.
- Column auto-detection knows Tobii, SMI, Pupil Labs and Gazepoint exports, and ignores a trailing unit.
- Excel 97–2003 `.xls` workbooks open, instead of being refused.
- A deployment can cap uploads for itself — `SCANPATH_MAX_UPLOAD_MB`.
- A share link carries the recording setup and Compare's per-scanpath styles.
- `render` has a flag for every figure option, so a copied command draws the figure on screen.

### Changed
- Streamlit 1.63.
- Streamlit 1.64.
- The replay starts at ×1 — real time — instead of ×4.
- The welcome tour names the app's own icons, picks a trial before narrowing the pool, and says where you already are.
- Animate + Compare greys the Compare settings instead of hiding them, and its *Stimulus from* control works there.
- Compare warns when the two readings are of different texts, under the figure rather than inside a popover.
- The 🗂️ chip named "Image x" says what it is, and the chip picker uses the strip's own vocabulary.
- The reproduce-in-code block opens with `pip install scanpath-studio`.
- The AI-assistance note asks for an issue, and stops asking for a Session JSON backup.
- The manuscript's MultiplEYE figure shows its Illustration label.
- The ℹ️ About a dataset blurbs are shorter, and OneStop's 330 texts is explained correctly.
- The recovery cache follows the server's bind address, not the URL the browser reports.
- `requirements.txt` is gone — `pyproject.toml` is the only dependency manifest.
- Local folder access is off by default on a server other machines can reach.
- The `other_vis/` scratch folder is gone.
- The repo sheds its strays, ignores what must never be committed, and the edit hook lints with the pinned ruff.
- The hosted demo installs the app, not its test tools.
- The dependency floors are the versions CI tests.
- CI runs current actions and tool pins.
- A `SECURITY.md` says how to report a vulnerability privately.
- Words keep the interest areas the experiment defined.
- A default figure's colour ranges are scaled to its own trial, as the API and `render` draw them.
- The docs match the app they describe.

### Fixed
- The figure draws offline.
- Groups → Effect size + test compares readers, not pooled words.
- A zipped Parquet, Feather or Excel file uploads again.
- The setup wizard reads an upload's columns once, not on every click.
- The docs and in-app hints name the controls the app actually has.
- The docs site publishes even when a test is flaky, and a release refuses a tag that doesn't match the version.
- The package credits and licenses the bundled OneStop demo, and builds without deprecation warnings.
- An installed copy downloads corpora to a per-user data folder, not into `site-packages`.
- The LaCC lab OneStop option no longer prefills one maintainer's personal OneDrive path.
- An animated cross-screen comparison no longer says it is shown side by side while showing one scanpath.
- A click with 🎬 Animate on no longer rebuilds the whole replay.
- A broken mapping or an empty filter no longer leaves a stuck "Loading…" and no way to switch dataset.
- The selected trial survives a visit to Corpus Analysis or the 🗂️ Data page.
- The 🗂️ Data page no longer crashes on MultiplEYE.
- Corpus Analysis computes the reading measures when the data doesn't ship them.
- Computing the reading measures is ~6× faster, and no longer quadratic in corpus size.
- The normalized corpus is no longer re-hashed on every rerun.
- Raw gaze is no longer re-read and re-normalized on every rerun.
- An uploaded table can no longer make a shared deployment read a file off its own disk.
- Three tutorial steps pointed at nothing: two never opened 📤 Export, one outlined a control that isn't on the Data page.
- Corpus Analysis computes only the subtab you have open.
- Regression-path (go-past) time counts the fixations of a regression that lands on a skipped word.
- A word first reached by a regression counts as skipped.
- A word nobody fixated no longer counts as a 0 ms fixation in every mean.
- Regression-out is a first-pass event, as in EyeLink's reports.
- The centred landing distance is measured from the word's actual centre.
- A fixation off the text ends a word's first run.
- Words per minute counts every screen's words on multi-page trials.
- The mean forward saccade leaves out return sweeps.
- The computation register says what the code computes.
- The preview launcher runs the project's own Streamlit, not whatever is on `PATH`.
- A `help=` tooltip left open by a rerun now closes on its own, not only on the next pointer move.
- The plot rail's sub-headings no longer sit on the switch below them.
- A comparison you labelled by hand reproduces under your labels, not the builder's.
- `api.figure_code` writes the caveats it used to throw away.
- A drift-corrected figure no longer parks one float per fixation in session state, every rerun.
- A stimulus-image folder no longer costs two syscalls per row of the corpus, on every rerun.
- `{trial_id}.png` resolved to `7.0.png` on a table that happened to hold a float column.
- The derived canvas is no longer re-estimated from the whole corpus on every rerun.
- An untouched fixation-index slider no longer copies the trial's fixations.
- The selected trial's `combos` row is masked once per rerun, and only when something asks.
- A GIF export no longer holds every decoded frame in memory, and one too large for the server is refused up front.
- A hand-edited share link can no longer crash the app through raw gaze's sliders or a colour.
- A malformed recovery cache no longer crashes the app on every launch.
- Raw gaze's colour, size and opacity controls change the figure, and survive a save and a restart.
- A share link carries the fixation flags, the replay speed, the stimulus image, Show full monitor, the colour bars and the span border.
- The saved config keeps the raw-gaze switch, the replay speed, the A/B legend and the blink flag; the recovery cache keeps Compare.
- Restoring an annotations-only backup no longer resets the view settings.
- A share link or saved config can no longer put a clickable link in the recipient's figure.
- A word spelled "None", "NA" or "null" no longer makes the dataset impossible to add.
- A decimal-comma export reads as numbers, and a numeric column that doesn't parse is named instead of silently filled.
- An Excel-named text export, a Windows-encoded CSV or an empty file no longer crashes the upload.
- A blank row no longer makes a dataset impossible to add.
- A second reading of a text gets that text's word boxes when the word table is keyed by text alone.
- A Trial ID picked by hand is the one used, even when the table also has a `unique_trial_id` column.
- A zero-padded id (`007`) matches across tables that read it differently.
- Vendor time columns in seconds, microseconds or nanoseconds are read in milliseconds, and screen-fraction positions are flagged.
- A `;`-separated CSV and a tab-separated `.txt` read as tables, not as one column.
- A blank row in a metadata table no longer becomes a reader, trial or text named "nan".
- `render --sample` and `load_sample_data()` no longer open with a warning about word ids.
- The loading guides describe the add-dataset wizard as it is: three parts, each table mapped in its own row.
- A words table that joins to none of the fixations is said, on every page, and a column mapping no longer carries over to another dataset with the same headers.
- `render --animate` honours every styling flag the replay can draw.
- `render --compare-with` honours `--fix-index-range`.
- A palette choice no longer reproduces as a command that colours saccades by type.
- Bad CLI input is a message, not a traceback — and `--word-schema` / `--fix-schema` map unrecognised columns.
- The documented examples run as written.
- `api.figure_code()`'s defaults write a recipe that runs, with both flavours drawing the same figure.
- An export bundle no longer holds two `aggregate/all_fixations` files.
- A headless comparison draws the app's default marker opacity.
- `analyze` writes a readable `cleaning_qa.csv`, and `corpus --kind difference` refuses a table with no `diff`.
- A `color_by` / `highlight_column` naming a missing column raises, instead of drawing a flat figure.
- The package root exports what the docs list, and a mistyped command says so.
- `scanpath-studio` listens on this computer only unless told otherwise.

## Before 0.31.0

Releases 0.9–0.30 were development builds before the first public beta. Their
notes are in the repository history: `git show v0.30.1:CHANGELOG.md`.
