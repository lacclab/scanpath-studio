# Feature map — what a user does, and what they should see

The `/verify` skill's guide and rubric: each feature from the user's side, where
it lives, the key a test or a link drives it by, and what counts as working.
Keys are the wire format (`session_keys.py`); don't rename them. Add a row when
a feature lands; fix a row when a check here turned out to be wrong.

## Header and views

| Feature | Where | Drive it by | Works when |
| --- | --- | --- | --- |
| Three views | Header: 🗺️ Scanpath · 📊 Corpus Analysis · 🗂️ Data Management | `main_nav` session key (`constants._VIEW_*`) | Each draws with no exception and no "this is a bug" note |
| Essentials / Full | Header switch | `?ui=essentials\|full` (first run only) | Full shows every rail section; Essentials hides Full-only containers by CSS but keeps their widgets' values. Share never writes `ui` |
| Task guides | Help → Task guides | Expand a task, then start or exit the walkthrough | The written steps open with any data. Eligible actions respect the current mode or offer Open in Full. Exit restores the starting view and mode. |
| First visit and import | Scanpath · import wizard | Replay this reading, Import my data, Setup help → Show setup guide | The figure and import fields work immediately. The replay and setup guide start on request. |
| Troubleshooting & feedback | Help menu or a feedback bookmark | Open an answer, then Report a bug | Short answers work offline. Questions open Q&A, suggestions open Ideas, and the bug report offers copyable diagnostics. |
| About & citation | Help menu | Open Citation and App details | Citation gives APA and BibTeX. App details identifies local or server storage and opens support and Debug. |
| Stable / Dev | Help → Documentation · About & citation → App details | Follow Documentation or What's new | Both open the matching docs edition. Dev includes unreleased changes. |

## Scanpath view

| Feature | Where | Drive it by | Works when |
| --- | --- | --- | --- |
| Prepare publication figure | Scanpath → Export → Prepare figure for export | `?prepare=1`, `render --sample -o reading.publication.json`, `publication_figure` | Download the current PNG, then open Label events, pin a fixation, save and reopen the editable file. Under Print settings, choose 85 mm and 300 dpi. The PNG and TIFF are 1,004 px wide and the SVG declares 85 mm. |
| Pick a reading | Above the plot | `single_participant`, `single_trial_id` | The plot, title and chips follow; a share link reopens the same reading |
| Keyboard shortcuts | Scanpath page, trial arrows, replay timeline | Left / Right, Shift + Left / Right, Space, Home / End | Page arrows step trials, Shift + arrows step B, and the replay timeline steps frames and toggles playback. Typing in the picker leaves the trial alone. |
| Fixation charts | Full → Axes → Axis preset | `global_x_field`, `global_y_field` | Index ticks are integers. Elapsed seconds stay relative to the complete reading. Screen Y increases downward. Raw samples appear only on supported coordinates. |
| The spatial plot | Centre | — (drawn by `tabs._render_true_scale_chart`) | Word labels keep their px size at any column width; never `st.plotly_chart` |
| Fixations | Full → Layers → **Fixations** | `global_show_fix` + its popover's `global_*` keys | Markers sized by duration; colour-by / scale / range honoured |
| Saccades | Full → Layers → **Saccades** | `global_show_saccades` | One trace with `None` separators; arrows, colour, style, width |
| Stimulus image | Full → Layers → **Stimulus** | `global_show_stimulus` | Page image behind the words at its offset / scale / opacity |
| Word underlines | Full → Layers → Stimulus → Word highlights → Style → Underline | `global_critical_span_style` | Each flagged word has its own underline in the text color. |
| Word boxes | Full → Layers → **Word boxes** | `global_show_words` | Boxes exactly as the data gave them (`x .. x + width`) |
| Heatmap | Full → Layers → **Heatmap** | `global_show_heatmap` | Word-level shading on its own colour bar |
| Raw gaze | Full → Layers → **Raw gaze** | `global_show_raw_gaze` | Samples drawn; on by default when raw gaze is the only table |
| Filters & highlights | Full → Layers → **Filters & highlights** | its popover's keys | Active marks a filtered or highlighted reading; the fixation range slices the trail |
| Figure | Full → Figure | `global_legend_<kind>_*`, title and framing keys | Open each named menu. A title, framing change and legend position reach the plot. |
| Sample charts | Full → Axes → Axis preset | `global_x_field`, `global_y_field`, `global_show_raw_gaze` | Pupil and position presets draw samples against the recorded clock or sample number. A screen covered only by samples is selectable and exportable. |
| Saccades-only replay | Animation → Full → **Fixations** off, **Saccades** on | `global_show_fix`, `global_show_saccades` | Lines appear as the reading reaches each fixation. Direction arrows follow their lines. |
| Animation | Animation tile or the switch beside Animation settings | `single_animate` | Switch from a custom figure to the replay and back in either mode. Its axes and layers come back. |
| Gaze over time and Custom | Third row of Plot controls | `viz_view_gaze_over_time`, `viz_view_custom`, `global_x_field`, `global_y_field` | Plot elapsed seconds against horizontal position, visit another view, then restore the last manual design with Custom. |
| Views and Palette | Top of Plot controls | `viz_view_*`, `global_palette` | Both modes show view and palette tiles. Full has My views between them. The replay tile and Animation switch control the same replay. |
| Find a setting | Full → Find a setting | `plot_setting_finder` | Search for a legend position, axis field or frame limit and reach its editable controls. The current figure and Undo history stay in place. |
| Comparison charts and span borders | Full → Figure & canvas → Axis preset, Stimulus → Highlight words | `global_x_field`, `global_show_fix`, `single_fix_range`, `single_compare_stimulus` | Hiding markers keeps an index–position sequence visible within its window. Panels share their ranges. A co-replay with stimulus B outlines B’s selected words. |
| Compare readings | Below the palette tiles | `single_compare_toggle`, `single_compare_layout`, `?compare=` | Overlay / side by side / stacked; B from another dataset resolves to side by side on unequal canvases |
| Fixation index | Rail → Fixations popover | `global_show_order`, `global_order_label_position` | Numbers above / inside / below each fixation, on every builder |
| Undo and Redo | Full → foot of Plot controls, beside Reset | `viz_undo`, `viz_redo` | Undo a confirmed reset, redo it, then undo and edit again on the current reading |
| Fold Presets / Palette / Modes / Customize | Chevron beside each rail label | `rail_view_fold`, `rail_palette_fold`, `rail_modes_fold`, `rail_customize_fold` (`_rail_folded_sections`, kept in the `sps_rail_folded` cookie) | Fold, reload the page: still folded; tiles hidden, the label names the current pick (a saved design by name); unfold restores them |

### Subtabs under the plot

Annotations, Stimulus & context and Comparisons are absent in Essentials.

| Subtab | Works when |
| --- | --- |
| Annotations | Favourite / tag / note a reading; it survives a dataset switch and comes back |
| Stimulus & context | The text and its metadata for the reading |
| Comparisons | Full only; NLD similarity scores only with `SCANPATH_EXPERIMENTAL=1` |
| Line assignment | Experimental only |
| Export | Figures + tables for the filtered trials; every file carries the citation |
| Smaller PNG files | Build a PNG bundle with separate layers at the same scale with the toggle off and on, and run `render -o a.png --separable-layers` with and without `--compact-png` (`save_figure` / `save_figure_layers` take `compact_png=True`). The compact files preserve the decoded pixels, dpi and embedded citation. |
| Large export download | Download a bundle over 32 MiB, open the ZIP and check its figures against `index.csv`. A browser with service workers disabled offers numbered parts that join into the same ZIP. |
| Export retry | Fail one layer format and one whole layer set in a multi-reading bundle. Retry lists just the remaining failures in `index.csv` and preserves the contents and names of every successful file. |
| Share → Link / Code / File | The link reopens both readings from uploads or locally available public corpora. Missing B leaves A open with recovery instructions. The code reproduces the figure (`test_render_every_option`) and the settings file restores it |

## Corpus Analysis

| Feature | Works when |
| --- | --- |
| Corpus overview | Check the landing chart has no preselected record. Switch between Texts, Participants and Groups. Select a participant outside the top 12 and find their marked point. Open a skip-rate profile to see its percentage and word counts. Return with Back to participants. Open Table and downloads and check that the recipe reproduces the full summary CSV in its original units. |
| Group comparisons | Open Groups to see both group means. Turn comparison off, edit the first group, then turn it on and check that group A carries over. Clear either side of a field split to get a prompt, then choose a new value to restore the results. |
| Measures from the dataset | Only the measures the dataset brought (`measure_*` fields); a notice and greyed sections without one |
| Recipe download | The Cohort profile and Difference word profile recipes reproduce the downloaded CSV with the original source files and selections |
| Study revision | Inspect a word with an unmeasured reading, compare two snapshots after a source correction, and find the participant and reading that changed |
| Participant contrast | An unpaired reader appears in the CSV and the mean difference uses only complete pairs |

## Data Management

| Feature | Works when |
| --- | --- |
| ➕ Add dataset wizard | Upload → map columns → validate → the dataset opens; `*` fields block only when missing |
| Draw a scanpath | Draw word 1 → word 3 → word 1, change the last duration, preview, save and reopen by name. The draft and Share code reproduce the three visits. |
| ✏️ Edit dataset | A change re-normalizes and keeps the column-name map |
| Current dataset | Overview counts the filtered trials. Averages and table coverage describe the same selection. A recording row jumps to its table on a page with all six tables. Data checks cover the whole dataset even when the filters leave zero trials. |
| Dataset library | Search or filter by source, sort, and open a dataset. Opening another dataset with unsaved edits offers to keep or discard the draft. Renaming an upload preserves its annotations, saved selection and comparison identity. |
| Saved work | Local recovery and downloaded corpora are accessible even when the current dataset fails to load. |
| Mapping recovery | Upload a Fixations table with an unrecognized duration, press Add dataset, activate the blocker with Enter, and map a seconds column. The duration picker receives focus and shows two converted values. |
| Dataset credit | Credit an unpublished lab dataset and a second comparison dataset. The saved README identifies which supplies the exported trials and BibTeX contains both references. |
| Metadata tables | Their columns appear as trial filters, chips and in the export bundle |
| Data checks | Each check that found rows says how many, where, and what happens to them |
| Run sheet | A missing planned reading, a raw-gaze-only reading and a planned omission have separate outcomes |
| Reviewer notes | A disputed screen note can be inspected before import and independent edits in two local sessions survive reopening |

## Headless surfaces

| Surface | Smoke check |
| --- | --- |
| Coauthor handoff | Copy the packaged Canal example into an empty folder. Its documented commands reproduce a specific reading and the original two-reader result CSV checksum. |
| Input counts | Check a header-only and an all-unkeyed fixation file with `--json-report`. The findings-only `--json` still returns a list. |
| Cohort recipe | `recipe profile.recipe.json --sample -o profile.csv` reproduces the CSV downloaded for a demo Per text cohort profile |
| CLI | `scanpath-studio render --sample -o out.html` writes a figure; `--list-trials` lists 24 |
| Add a dataset from a script | With `SCANPATH_STUDIO_STATE_DIR` set to a scratch folder, `add_dataset("Pilot 3", words, fixations)` or `scanpath-studio add`, then launch the app on that folder: it opens on *Pilot 3* and draws its first reading. Adding the same name again fails unless `--replace`, which keeps its annotations and setup. `remove_dataset` / `scanpath-studio remove` then takes it off the list, and the next launch opens on the default dataset with no saved key naming it. |
| Open the app on a reading from a script | `api.app_link("Pilot 3", p, t, show_heatmap=True)` returns `http://localhost:8501/?dataset=Pilot+3&participant=…&trial_id=…&show_heatmap=1…`; `scanpath-studio open "Pilot 3" -p P -t T --heatmap --print` prints the same link, and without `--print` opens it in a running app or starts one. Opened (with the dataset added on a scratch `SCANPATH_STUDIO_STATE_DIR`), the app shows *Pilot 3* at that reading with the heatmap on. A render-only flag (`--sample`, `--stimulus-image`) or `background_image=` is refused by name. |
| API | `load_sample_data()` → `plot_scanpath(..., participant=, trial=)` → `save_figure` |
