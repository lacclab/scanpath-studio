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

## Scanpath view

| Feature | Where | Drive it by | Works when |
| --- | --- | --- | --- |
| Pick a reading | Above the plot | `single_participant`, `single_trial_id` | The plot, title and chips follow; a share link reopens the same reading |
| The spatial plot | Centre | — (drawn by `tabs._render_true_scale_chart`) | Word labels keep their px size at any column width; never `st.plotly_chart` |
| Fixations | Rail → **Fixations** | `global_show_fix` + its popover's `global_*` keys | Markers sized by duration; colour-by / scale / range honoured |
| Saccades | Rail → **Saccades** | `global_show_saccades` | One trace with `None` separators; arrows, colour, style, width |
| Stimulus image | Rail → **Stimulus** | `global_show_stimulus` | Page image behind the words at its offset / scale / opacity |
| Word boxes | Rail → **Word boxes** | `global_show_words` | Boxes exactly as the data gave them (`x .. x + width`) |
| Heatmap | Rail → **Heatmap** | `global_show_heatmap` | Word-level shading on its own colour bar |
| Raw gaze | Rail → **Raw gaze** | `global_show_raw_gaze` | Samples drawn; on by default when raw gaze is the only table |
| Filters & highlights | Rail → **Filters & highlights** | its popover's keys | The badge counts active filters; the fixation range slices the trail |
| Figure & canvas | Rail → **Figure & canvas** | its popover's keys (legends: `global_legend_<kind>_*`) | Canvas size, fonts, title / caption, legends, credit |
| Animate | Rail toggle | `single_animate` | The replay player draws its own toolbar row; the plot keeps the static figure's size |
| Compare | Rail toggle | `single_compare_toggle`, `single_compare_layout`, `?compare=` | Overlay / side by side / stacked; B from another dataset resolves to side by side on unequal canvases |
| Fixation index | Rail → Fixations popover | `global_show_order`, `global_order_label_position` | Numbers above / inside / below each fixation, on every builder |

### Subtabs under the plot

Annotations, Stimulus & context and Comparisons are absent in Essentials.

| Subtab | Works when |
| --- | --- |
| Annotations | Favourite / tag / note a reading; it survives a dataset switch and comes back |
| Stimulus & context | The text and its metadata for the reading |
| Comparisons | Full only; NLD similarity scores only with `SCANPATH_EXPERIMENTAL=1` |
| Line assignment | Experimental only |
| Export | Figures + tables for the filtered trials; every file carries the citation |
| Share → Link / Code / File | The link reopens both readings from uploads or locally available public corpora. Missing B leaves A open with recovery instructions. The code reproduces the figure (`test_render_every_option`) and the settings file restores it |

## Corpus Analysis

| Feature | Works when |
| --- | --- |
| Measures from the dataset | Only the measures the dataset brought (`measure_*` fields); a notice and greyed sections without one |
| Recipe download | The JSON beside each table re-creates it |

## Data Management

| Feature | Works when |
| --- | --- |
| ➕ Add dataset wizard | Upload → map columns → validate → the dataset opens; `*` fields block only when missing |
| ✏️ Edit dataset | A change re-normalizes and keeps the column-name map |
| 📂 Available datasets | Lists every dataset; renaming an upload preserves its annotations, saved selection and comparison identity |
| Metadata tables | Their columns appear as trial filters, chips and in the export bundle |
| Data checks | Each check that found rows says how many, where, and what happens to them |

## Headless surfaces

| Surface | Smoke check |
| --- | --- |
| Cohort recipe | `recipe profile.recipe.json --sample -o profile.csv` reproduces the CSV downloaded for a demo Per text cohort profile |
| CLI | `scanpath-studio render --sample -o out.html` writes a figure; `--list-trials` lists 24 |
| API | `load_sample_data()` → `plot_scanpath(..., participant=, trial=)` → `save_figure` |
