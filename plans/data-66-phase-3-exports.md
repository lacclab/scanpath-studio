# DATA-66 phase 3: exported tables under the dataset's own names

**Goal:** the files a user downloads name their columns as the dataset's own files do, and say where every column came from.

**Spec:** [`plans/data-66-original-column-names.md`](data-66-original-column-names.md) §3.

## Design

- **One choke point:** `export._write_table(…, names)` runs `column_names.as_written`. It drops a `unique_*` alias that only repeats its partner, then renames by `ColumnNames.export_headers`.
- **What gets renamed:** a column read from **one** column of the file is written under that column's name. A composite, converted, generated or computed column keeps its internal name, because its values are not what the file held under any one name. A header that would repeat another column's name is skipped.
- **Per-table maps:** `bulk_export(column_names={"fixations": …, "words": …, "raw_gaze": …})`. `_ARTIFACT_TABLE` routes each artifact to its table's map, so a word box's `x` is written as `IA_LEFT` while a fixation's `x` is `CURRENT_FIX_X`. Summaries across tables (trial or reader summaries, sentences, cleaning QA) take the identity names from `across_tables`.
- **Provenance:**
  - `columns.json` (`COLUMNS_FILE_SCHEMA = 1`) lists, per table, every column the map records: the header written, its canonical name, its kind, its sources and its note.
  - The README's data dictionary is generated from the same maps by `dictionary_lines`.
- **Patterns** accept either name. `pattern_fields(column_names=…)` adds each file name as an alias of its canonical field.
- **Pair export** applies the names only when both scanpaths come from the open dataset. A pair across two datasets shares no file names, so it keeps the internal ones, which both datasets understand.
- **Corpus Analysis tidy CSVs** go through `as_written` with the across-tables map, matching their on-screen headers.
- **Bulk-export cache:** its signature includes the maps, so a rename rebuilds the bundle.

## Not in phase 3

- `analyze` and every headless caller: they have no map until the API's loaders return one (phase 4). Without a map, every exporter writes the internal names exactly as before.
- Metadata tables are the user's own tables and are written as attached.
