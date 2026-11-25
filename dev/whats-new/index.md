# What's new

## In development

### Added

- The Axis layout menu offers *Fixation index by word number*: each fixation's place in the reading against the word it landed on.
- Charts can run either axis the other way with Reverse horizontal axis and Reverse vertical axis under Axes (--reverse-x / --reverse-y on the command line, reverse_x_axis / reverse_y_axis in Python), for example to put the first fixation at the top.

## Release v0.49.0

### Added

- Hovering over Scanpath View, Corpus Analysis or Data Management in the top navigation now says what each view is for.
- Smaller PNG files works outside the app too: `render --compact-png` and `save_figure(..., compact_png=True)` / `save_figure_layers(..., compact_png=True)` compress a PNG figure and its separate layers losslessly, keeping the pixels, the print dpi and the citation.
- Share links carry *Keep this range across trials* (`fix_range_all_trials=1`), so a fixation window kept across trials stays kept when the link is opened, as it already did in a settings file.
- Add a dataset to the app's dataset list from a script with `add_dataset` or `scanpath-studio add`, and remove one with `remove_dataset` or `scanpath-studio remove`; the next local app session opens on a dataset just added.
- Each part of Plot controls (Presets, Palette, Modes, Customize) can be folded away with the chevron beside its label; a folded line names the current choice, and the browser remembers what you folded.
- Read and write a saved dataset's favorites, tags and notes from a script with `read_annotations` / `write_annotations` or `scanpath-studio annotations export` / `import`, so a quality-control script's tags show up in the app's trial filters.
- A script can open the app on a dataset it added, at one reading and figure: `api.app_link` writes the link Share would, and `scanpath-studio open` opens it in the browser (starting the app if it isn't running) with the figure set by the same flags `render` takes.

### Changed

- Buttons, help text and guides now name the Scanpath View tab as it appears in the navigation.
- The hosted demo keeps its cached figures and tables within a memory budget, dropping the least recently used ones when many people use it at once.
- The Texts and Participants summary captions now say how the means are weighted: each participant counts equally in a text mean, and each reading counts equally in a participant mean.
- A table inside a zip with rows that have more fields than its header is read like the same table on its own: the Add-dataset wizard skips those rows and names their lines, instead of refusing the archive.
- Gaze charts name their axes clearly: recorded timestamps read "Recorded time (ms)" and pupil charts "Pupil area (tracker units)" or "Pupil diameter (tracker units)", instead of "Time (ms)" and the raw column name.
- `animate_scanpath` and `render --animate` now refuse a replay with both fixations and saccades hidden, which used to produce an empty replay, with a message naming the two settings.
- Comparison links that use the Print / grayscale palette and were made before v0.48.0 draw the two readers in dark and light grey since v0.48.0, scanpath B with hollow markers and dashed saccades, instead of blue and red; set each scanpath's colors again under Scanpath A and Scanpath B in the Fixations and Saccades settings to bring blue and red back.
- The fixation size legend is also off by default in `plot_scanpath` and `render` output since v0.48.0; turn it on with `duration_size_legend=True`, `render --duration-size-legend`, or Fixation sizes under Figure → Legends in the app.
- `render` now stops with a message when `--compare-words`, `--compare-fixations` or their mapping flags are given without `--compare-with`, which they need; before, it ignored them.
- animate_scanpath refuses the raw-gaze style and heatmap colour-bar options by name, which the replay never draws, instead of accepting and ignoring them.
- Excel workbooks, .xlsx and legacy .xls alike, are read with calamine, which pandas is moving to, instead of openpyxl and the deprecated xlrd; neither is installed with the app any more.
- A scanpath figure or replay built directly with the plotting module (FigureSettings, make_scanpath_figure, make_scanpath_animation) now draws fixations at the app's, the API's and the CLI's default opacity, 0.7, not 1.0.
- Changing a dataset's mapping in Edit dataset no longer adds unique_trial_id / unique_text_id columns that adding the same files with that mapping would not, so an edited dataset exports the columns a freshly added one does.
- The "Stopped loading" notice is now a light banner with a clearer Try again button and a ✕ to close it.
- Plot controls stay in view and scroll on their own beside the figure; Reset visualization is now a compact Reset, with larger Undo and Redo buttons.
- Plot controls are grouped under Presets, Palette, Modes and Customize: View is now Presets, My views is now My presets, the Animation switch is now Playback, and Axis preset is now Axis layout.
- The bundled demo keeps every screen of each reading — title, question preview, paragraph, question, answers and feedback — each with the experiment's own stimulus image placed where the experiment drew it, and raw gaze for every screen. A demo trial opens on its paragraph and numbers its fixations across all its screens; a demo link or settings file saved by an earlier release still opens the paragraph on the same fixations, but a script must now name the paragraph (`--screen Paragraph`, `screen="Paragraph"`) to draw it, a fixation-index window counts from the trial's first screen, and the demo's export bundle files each screen under `screens/`.
- OneStop's word tables, the demo's included, carry stimulus_font_px and stimulus_font_family columns, and a demo link or settings file that never named a font now opens in Lucida Sans Typewriter; plot_scanpath, animate_scanpath and compare_scanpaths draw the declared font unless font_family is passed.

### Removed

- The package no longer ships a CSV copy of the demo raw gaze (`sample_data/raw_gaze.csv`); `load_sample_raw_gaze()` reads the bundled Parquet, and the download is about 3 MB smaller.

### Fixed

- The Raw gaze switch can be turned off on a trial with no samples of its own, and its "no samples" warning no longer shows during Animation or for a dataset without raw gaze.
- Clicking the Custom view no longer switches Compare readings on or off, or puts back an earlier replay speed, autoplay or smoothness.
- When the chosen axes are ones fixations don't have, such as pupil area, the Fixations switch and its menu now say so instead of greying out with no reason.
- Gaze over time now draws its small onset markers in Compare readings too, so large markers no longer hide short fixations; choosing a view sets both readings' marker size.
- A replay always shows fixations or saccades: the last of the two cannot be switched off while it plays, and a replay opened with both off shows its fixations.
- Changing the replay's speed, autoplay or smoothness no longer switches the view to Custom, and Essentials no longer reports it as a setting from Full.
- After Undo, opening Stimulus → Text and changing the font size, line spacing or other text settings back keeps your change instead of putting the undone value back.
- Groups → Overlaid distributions with Z-score per participant now z-scores each participant once over all their selected trials before splitting the groups, so a participant who read both conditions keeps the difference between them.
- Corpus Analysis stays responsive on large datasets while Study inclusion and exclusions is open: the report is worked out once per filter change instead of on every rerun, and its CSVs are written only when you download them.
- Corpus Analysis keeps its place when you visit another view or open a Help item: the destination, profile and measure you chose are still there when you come back.
- Measure on the stimulus keeps the stimulus version you chose for a text after you visit another view, instead of hiding the figure until you choose again.
- With Aggregate set to Sum, an IQR spread is now drawn as the 95% bootstrap interval of the sum, as SD and SEM already were, instead of the quartiles of the individual values around the total; the recipe and the methods draft say so.
- The "Updated in this session" line under a trial's annotations now appears only in the editor of the trial you changed, and goes once you open another trial, instead of following you to every trial of the dataset.
- While a conflict over a trial's note waits for you to resolve it, the app no longer writes and deletes this tab's unsaved datasets on disk on every click.
- A damaged dataset-citation entry in the saved session no longer throws away every other restored setting: only that entry is left out.
- Large CSV and TSV tables load faster again: a planned read no longer checks every line against the header before reading, only a table that turns out to have a row with a field too many, and that check keeps the loading card live and Cancel working.
- Tables written by R's write.table() with its default row names (a header one column shorter than every row) load again, through the Add-dataset wizard, the API and the CLI, with the row names left out; a table with rows that really have too many fields now says how many and what each has.
- Two tabs or windows that share saved work now merge each other's trial notes, stars and tags as promised, whatever page, trial or plot settings each has open: those are each tab's own, and the last one to save wins them.
- On Windows, a window that opens while another one is still saving large datasets now waits for that save, instead of giving up after about ten seconds, calling the saved work unreadable and pausing saving.
- CSV tables in an export bundle now carry the time they were written instead of 1 January 1980.
- Changing an export setting while a large bundle is still downloading no longer stops the download; the replaced bundle stays available for 30 minutes.
- Preview bundle contents in the Export tab is no longer re-planned on every interaction while it is open, which took seconds on a large corpus with a custom path pattern.
- The read_csv.R reader in CSV bundles now says "Choose a CSV listed in dictionary$csv_files" for a path it does not know, instead of a cryptic R error.
- A figure too large for the raster pixel limit is no longer offered for Retry failed figure files, since retrying with the same settings cannot make it.
- Retrying failed figures in an export bundle larger than 2 GiB now makes a ZIP that macOS Archive Utility and other extractors can open.
- Exported GIFs and MP4s end on the complete scanpath again; most readings had lost their last one or two fixations.
- The bundled demo's raw gaze leaves the pupil area blank where the tracker lost the eye, so a pupil chart shows a gap at each blink instead of dropping to zero.
- Each category now keeps one color in every trial of a dataset, and up to 20 categories get clearly different colors; several used to look almost identical, such as three purples for the demo's saccade types.
- In a right-to-left or mixed-script passage, a word made only of digits or punctuation is drawn in the direction of the words around it, so a period ending an Arabic or Hebrew sentence sits on the left.
- The experimental saccade table (with `SCANPATH_EXPERIMENTAL=1`) leaves the peak speed blank for a saccade that spans a blink or lost signal, instead of reporting thousands of degrees per second.
- In a replay, the first Previous fixation press after pausing or scrubbing goes to the fixation before the one on screen instead of seeming to do nothing, and the fixation buttons work in Safari before 15.4.
- The replay timer has a light background in the light theme again, even when the computer is in dark mode.
- Share links and settings files from before v0.48.0 that open a replay with fixations hidden show the fixations again, as they were drawn when saved, instead of an empty or saccades-only replay; a saccades-only replay linked from v0.48.0 itself also reopens with fixations, while links made from now on keep it saccades-only.
- `render --print-code` and `figure_code` keep scanpath B's fixation window (`--compare-fix-index-range`, `fix_index_range_b=`), so the printed recipe for a comparison or a two-reading replay draws the same B as the command it came from.
- The sample-number axis (`x_field="sample_index"`, `render --x-field sample_index`) draws raw gaze recorded with timestamps too, numbering each reading's samples in recorded order per screen and eye, instead of an empty chart; and a shared link whose chart axis the opened reading lacks falls back to the screen axes, rather than plotting one field against itself.
- The chart axis pickers offer the sample number for gaze samples recorded with timestamps.
- Each visitor to the bundled demo uses about 70 MB less memory: every session now shares one copy of the demo's gaze samples.
- Each interaction on a trial with raw-gaze samples is faster, most on long high-rate recordings: finding the cached figure no longer reads all of the trial's samples.
- Opening a large dataset and changing its trial filters is faster: finding the columns the trial picker can sort by no longer runs Python code for each reading.
- Use this size for batch export now gives the export bundle the width of the prepared artwork, without the page margins, so batch figures print with the same lettering as the proof instead of about 5% larger; the editor also says that the crop, labels and caption are not applied to batch figures.
- Prepare figure no longer fails to make an MP4 when the suggested caption is printed below the replay: every frame of the clip, and its poster, keeps room for the caption's longest reading time.
- A Corpus Analysis chart's Prepare figure for export section stays open, with its draft, when a note or control appears above the chart.
- An emptied caption in Prepare figure no longer leaves a blank caption line below the figure when the caption is set to print with it.
- Preparing a PDF or the offline editor in Prepare figure now shows a loading card with its progress, as the clip does, instead of a page that seems to hang.
- Two Prepare figure sections open at once, such as a Corpus Analysis chart and its text's stimulus, no longer rebuild each other's editor on every rerun.
- Scanpath B's fixation and saccade filters, the exported figure's width and DPI, whether the trial summary shows above the plot, and "keep this range across trials" are kept when the app restarts.
- A renamed built-in dataset that needs a number to stay unique keeps its name within the 80-character limit, as an uploaded dataset's already did.
- Removing a dataset also clears its saved filters, remembered trial and Compare selection, and closes Edit dataset if it was open on it, so a dataset added later under the same name opens unfiltered on its own first trial, and saving the editor cannot rename another dataset.
- Saving a drawn scanpath keeps the participant, trial and text tables attached to the draft, as it already kept the draft's annotations.
- A share link with a value a menu does not offer (a misspelt line style or background, say) now says it ignored that value, as it already did for colours and numbers, instead of quietly using the default. Menu values are matched ignoring capitalisation, and a colour scale may be any Plotly scale, as on the command line.
- Colouring by, hovering, or picking a column that the next dataset you open lacks no longer forgets the choice: it comes back when you return to a dataset that has the column, unless you changed it in between.
- Share → Code for a comparison whose scanpath B comes from a second, hand-mapped dataset now passes B's column mapping on, so the code reads B's files as the app did. `render` takes it as `--compare-word-schema`, `--compare-fix-schema` and `--compare-raw-gaze-schema`, and `figure_code` as `compare_source_options`.
- `compare_scanpaths` and `animate_scanpath` on a dataset recorded as raw gaze alone now say that they need fixations. Before, the comparison failed with a `TypeError` and the replay said no trial existed.
- Splitting a comparison into one file per layer (`render --separable-layers`, `save_figure_layers`) now files its saccades, raw gaze and heatmap colour bar under their own layers; before, all three landed in the fixations file.
- The stimulus image's offset boxes and the fixation-flag threshold boxes now stop at the range a share link carries (±5000 px, 1–60,000 ms). Before, a value past it showed on screen but a share link cut it back to the limit. A settings file holding such a value is now restored at the limit too.
- With Favorites only, a tag filter or a trial-metadata filter on, for the scanpath or for Compare's second one, a click no longer re-filters the whole dataset: the filtered trials are kept until the data, the filter or your stars and tags change (about 0.5 s a click on a full OneStop corpus).
- Compare and the Comparisons grid redraw their figures only when something in them changes, not on every click elsewhere in the app; the static figure already worked this way.
- A long session, or a server shared by many, no longer keeps every scanpath figure it has drawn in memory: the app keeps the 32 most recent.
- Preparing a publication figure no longer waits forever when the browser drawing it stops answering: after two minutes without a reply it stops with an error, and you can try again.
- A closed settings menu no longer brings back a value you changed elsewhere for four controls: undoing the replay's Smoothness or a word highlight now holds, a palette set by a settings file stays on Corpus Analysis, and a new dataset gets its own Stimulus & context fields.
- Editing a dataset's column mapping now keeps the files' own paragraph ids, as adding the files does, and no longer leaves behind a copy of the participant column that a combined Trial ID had used.
- A colour range set by a settings file, a link or *Use this heatmap range for other trials* now stays, instead of going back to Auto or the old range when the menu showing it had been opened before.
- Settings restored from a settings file, and an added dataset's own text size and spacing, no longer revert when a menu you had opened before sends back its old values.
- A stimulus page image replaced on disk at the same path now shows the next time the figure is drawn, instead of the old page until a setting changed.
- A setting changed by a view tile, Undo, Reset or a settings file no longer goes back to its old value when the app reruns itself right after, for example when a dialog closes or a Help page opens.
- Choosing participants no longer brings back readings a condition leaves out: a condition only the Words table carries now still applies when the chosen readers have no Words rows.
- Legends placed at neighbouring spots (along one edge, or round one corner) no longer overlap each other when one is wide or tall for the figure: the later one moves aside, unless that would carry it out of the figure.
- The Plot controls rail stays below the header and inside the window, so its last controls show without scrolling the page.
- Corpus Analysis no longer stops with an error on a screen whose reading-measure flags are all missing.
- On a phone, a trial with several screens names its screen in a line of text beside its ◀ ▶ in place of the dropdown, so the screen steps take a short line and the figure's view choices stay on the first screen in Essentials.
- The screen you picked in a multi-screen trial stays picked after a visit to Corpus Analysis or Data Management, and turning Compare off no longer stops undo from recording your next plot edit.
- Stimulus & context keeps its highlighted spans when you step through a screen with no highlighted words, such as a title, and picks them up even when a trial opens on such a screen.
- On multi-screen trials the experimental per-word reading measures (`compute_word_metrics`, behind `SCANPATH_EXPERIMENTAL=1`) keep each word's screen ID and screen number, so they merge back onto the words one row per word, and the Data page's derived Trial summary, Participant summary and Sentences tables now count every screen's words instead of folding screens that share word IDs together.
- The Data page's Texts table no longer passes off one reader's version of a screen as every reader's: a screen, or a text, that readers saw differently — the demo's answer orders and feedback — is shown once per version with the readers who saw it, and a Differs by reader column names those screens.
- The Data page's checks no longer flag a fixation that a screen's recording end cuts to 0 ms, as in the bundled demo.
- `api.app_link` and `scanpath-studio open` open the bundled demo and the public corpora by the name the dataset list shows, instead of saying the dataset isn't available here.
- The blank band between the header and the dataset and trial pickers is gone.
- The trial summary's chips no longer turn black after the ✏️ menu is opened for the first time in a session.
- Switching subtabs while scrolled to the bottom of a tall one, such as Export, no longer makes the page jump.
- The bundled demo and OneStop draw their word labels in Lucida Sans Typewriter, the font the experiment used, at its size on every screen, so a one-word Feedback screen is no longer drawn too large; where the font isn't installed, labels fall back to the browser's monospace.

[Browse earlier releases on GitHub](https://github.com/lacclab/scanpath-studio/releases)
