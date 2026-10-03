# DATA-66 phase 4: the API and CLI speak the dataset's own column names

**Goal:** a script works in the names its files use. The user decided (2026-10-03) that `load_scanpath_data()` returns frames under the dataset's own names by default, with `names="canonical"` for the internal ones. Every API function takes either kind of frame.

**Spec:** [`plans/data-66-original-column-names.md`](data-66-original-column-names.md) §4, with the user's call above.

## Design

- **The map rides on the frame.** `column_names.attach(frame, table, names)` writes the frame as `as_written` does (the user's names, a redundant `unique_*` alias left out). It records in `frame.attrs["scanpath_studio.columns"]` the table, the map and what was renamed. pandas 3 carries `attrs` through filtering, `loc`, `copy`, `assign`, `merge`, `concat` and `groupby` (checked), so a script can slice a loaded frame and hand it back.
- **Every API function takes either kind** through `column_names.to_canonical_frame(frame)`. It renames back, restores the alias and drops the attrs key. A frame without the key is taken as canonical, as today; a raw table still fails `_require_normalized`.
- **Outputs follow the input.** When a function's input frames carried names, its output frames are written in them: a table that *is* the dataset's (word metrics, preprocessed fixations) under its full map, a derived one (trial or reader summaries, `list_trials`, `list_parts`, the analysis family's derived tables) with only its ids renamed. This uses phase 3's rules.
- **Column options accept either name:**
  - one column each: `color_by`, `highlight_column`, `heatmap_metric`, `word_hover_measure`, `word_heatmap_col`, `x_field`, `y_field`;
  - lists: `word_hover_fields`, `fixation_hover_fields`.
  
  Each is translated with `ColumnNames.to_canonical` before validation.
- **Headless figures match the app's text.** `plot_scanpath`, `animate_scanpath` and `compare_scanpaths` set `FigureSettings.column_labels` from the frames' map.
- **`ScanpathData`** is a tuple of `(words, fixations)`, so `words, fixations = load_scanpath_data(…)` still works. It also has `.words`, `.fixations` and `.column_names` (a table → `ColumnNames` dict).
- **CLI:**
  - `render` reads the user's names, and its column flags accept either name; `--heatmap-metric` loses its fixed `choices`, and the API validates it.
  - `--list-trials` prints the dataset's names.
  - `analyze` writes them, plus a `columns.json`.
- **The app and every internal caller stay canonical.** They pass `names="canonical"`: `compare_source`, `datasets`/`eyegenbench` loaders called by the app, `cli` internals that index columns, and the docs gallery builder. The canonical names stay the internal contract.
- **The code snippet** keeps canonical option values, which every dataset accepts. It selects trials through the API's own trial arguments, never by indexing a column, so it runs whichever names the frames carry.
- **Public-corpus loaders** (`load_potec`, `load_onestop`, `load_multipleye`) route through `load_scanpath_data`, so they return maps too. The app's Compare B uses them for a public-corpus B (the phase 2b gap).

## Not changed

Share links, saved configs, designs and the recovery cache keep canonical values.
