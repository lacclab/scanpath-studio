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
| ❓ Help actions | Header ❓ menu | — | The dialog opens and the view stays where it was |
| Stable / Dev | Help menu | Open Documentation and What’s new | Both open the matching docs edition in another tab. Only Dev lists unreleased changes. |

## Scanpath view

| Feature | Where | Drive it by | Works when |
| --- | --- | --- | --- |
| Pick a reading | Above the plot | `single_participant`, `single_trial_id` | The plot, title and chips follow; a share link reopens the same reading |
| Keyboard shortcuts | Scanpath page, trial arrows, replay timeline | Left / Right, Shift + Left / Right, Space, Home / End | Page arrows step trials, Shift + arrows step B, and the replay timeline steps frames and toggles playback. Typing in the picker leaves the trial alone. |
| Fixation charts | Full → Figure & canvas → Axis preset | `global_x_field`, `global_y_field` | Index ticks are integers. Elapsed seconds stay relative to the complete reading. Screen Y increases downward. Raw samples appear only on supported coordinates. |
| The spatial plot | Centre | — (drawn by `tabs._render_true_scale_chart`) | Word labels keep their px size at any column width; never `st.plotly_chart` |
| Fixations | Rail → **Fixations** | `global_show_fix` + its popover's `global_*` keys | Markers sized by duration; colour-by / scale / range honoured |
| Saccades | Rail → **Saccades** | `global_show_saccades` | One trace with `None` separators; arrows, colour, style, width |
| Stimulus image | Rail → **Stimulus** | `global_show_stimulus` | Page image behind the words at its offset / scale / opacity |
| Word boxes | Rail → **Word boxes** | `global_show_words` | Boxes exactly as the data gave them (`x .. x + width`) |
| Heatmap | Rail → **Heatmap** | `global_show_heatmap` | Word-level shading on its own colour bar |
| Raw gaze | Rail → **Raw gaze** | `global_show_raw_gaze` | Samples drawn; on by default when raw gaze is the only table |
| Filters & highlights | Rail → **Filters & highlights** | its popover's keys | The badge counts active filters; the fixation range slices the trail |
| Figure & canvas | Rail → **Figure & canvas** | its popover's keys (legends: `global_legend_<kind>_*`) | Canvas size, fonts, title / caption, legends, credit |
| Animation | Shared View tile | `single_animate` | The replay player draws its own toolbar row; the plot keeps the static figure's size |
| Four views and Palette | Top of Plot controls | `viz_view_*`, `global_palette` | Both modes show the same grid and keep the figure, palette and comparison when switching |
| Compare readings | Below Palette | `single_compare_toggle`, `single_compare_layout`, `?compare=` | Overlay / side by side / stacked; B from another dataset resolves to side by side on unequal canvases |
| Fixation index | Rail → Fixations popover | `global_show_order`, `global_order_label_position` | Numbers above / inside / below each fixation, on every builder |
| Undo and Redo | Full → foot of Plot controls, beside Reset visualization | `viz_undo`, `viz_redo` | Undo a confirmed reset, redo it, then undo and edit again on the current reading |

### Subtabs under the plot

Annotations, Stimulus & context and Comparisons are absent in Essentials.

| Subtab | Works when |
| --- | --- |
| Annotations | Favourite / tag / note a reading; it survives a dataset switch and comes back |
| Stimulus & context | The text and its metadata for the reading |
| Comparisons | Full only; NLD similarity scores only with `SCANPATH_EXPERIMENTAL=1` |
| Line assignment | Experimental only |
| Export | Figures + tables for the filtered trials; every file carries the citation |
| Export retry | Fail one layer format and one whole layer set in a multi-reading bundle. Retry lists just the remaining failures in `index.csv` and preserves the contents and names of every successful file. |
| Share → Link / Code / File | The link reopens both readings from uploads or locally available public corpora. Missing B leaves A open with recovery instructions. The code reproduces the figure (`test_render_every_option`) and the settings file restores it |

## Corpus Analysis

| Feature | Works when |
| --- | --- |
| Corpus overview | Switch between text and participant means, inspect a point and open its profile. The selected ID and measure carry through, and the recipe reproduces the full summary CSV. |
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
| 📂 Available datasets | Lists every dataset; renaming an upload preserves its annotations, saved selection and comparison identity |
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
| API | `load_sample_data()` → `plot_scanpath(..., participant=, trial=)` → `save_figure` |
