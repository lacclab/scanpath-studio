# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changes not yet released are one file each in [`changelog.d/`](changelog.d/);
`scripts/changelog_fragments.py release` writes them in here.

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
