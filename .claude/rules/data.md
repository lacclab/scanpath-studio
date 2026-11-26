---
paths:
  - "scanpath_studio/data.py"
  - "scanpath_studio/column_names.py"
  - "scanpath_studio/multipart.py"
  - "scanpath_studio/metadata.py"
  - "scanpath_studio/measures.py"
  - "scanpath_studio/datasets.py"
  - "scanpath_studio/eyelink.py"
  - "scanpath_studio/annotations.py"
  - "scanpath_studio/dataset_identity.py"
  - "scanpath_studio/persistence.py"
  - "scanpath_studio/experimental_setup.py"
  - "scanpath_studio/update_sample_data.py"
  - "scanpath_studio/synthetic.py"
  - "scanpath_studio/api.py"
  - "scanpath_studio/utils.py"
  - "scanpath_studio/data_health.py"
  - "scanpath_studio/study_checks.py"
  - "tests/synthetic_data.py"
  - "scanpath_studio/constants.py"
  - "scanpath_studio/app.py"
  - "scanpath_studio/tabs.py"
  - "scanpath_studio/url_state.py"
  - "scanpath_studio/controls.py"
  - "scanpath_studio/wizard.py"
  - "scanpath_studio/compare_source.py"
---

# Data

- **Carry `column_names` through every rewrite of `_datasets[name]`**, and show
  column names through the map. The API's frames use the dataset's own names;
  package code reading them passes `names="canonical"`.
- **A trial filter decides readings, never rows of one table** — see AGENTS.md → *Trial
  annotations & filtering*.
- **One trial pool, the union, on every surface**: a trial is listed when any
  table has it, and a table that lacks it draws as an empty layer
  (`data.trial_pool`; `utils.combo_source` in the app).
- **Raw gaze can be a dataset's only table**; nothing derives fixations from
  samples, and the Raw gaze layer then turns on by default.
- **Column auto-detection** (`data.pick_column`) ignores case and separators
  and one trailing unit block (`Fixation Duration [ms]` == `fixation_duration`),
  so `*_CANDIDATES` lists hold only distinct conventions. A whole-token match
  (`AOI_LEFT`) is taken only when exactly one column survives it.
- **`*` on a mapping field means exactly "validation blocks without it."**
  Without X/Y, fixations whose Word IDs name no word of their trial are refused
  (`harmonize_frames` → `UnplacedFixationsError`).
- **pandas joins NaN to NaN** in `merge` and `Series.map(dict)`: drop missing
  keys before any lookup keyed on a word id.
- **Repeated readings** get `_r2` on `trial_id` (ranked on `TRIAL_INDEX`) unless
  the Trial ID maps to several columns, which builds a composite id
  (`data.compose_id`). Any mapping beats a literal `unique_trial_id` column.
- **A built-in dataset's recording setup is an override, never an edit of the
  corpus** (`constants.DATASET_SETUP_OVERRIDES_KEY`); a share link elides it
  against the source's screen.
- **Every fingerprint is exact** — a frame hashed in full or named by its source
  (`data.stamp_source` / `adopt_source`, `frame_cache`, `assign_derived`), never
  sampled. A new large per-rerun frame needs one, or it is hashed every run.
- The bundled `raw_gaze.parquet` (Parquet only: no CSV copy in the wheel)
  carries the two L1 readers' recorded EyeLink gaze positions for every screen
  of all 24 readings. Extract samples within each screen's interest period in
  its fixation report and subtract the trial start time to share the fixation
  clock; the samples carry the screen's `part` and `screen_index`. Keep
  every recorded tick, including missing x/y values, pupil area in tracker
  units and the tracked eye. A sample without a position has a missing pupil
  value, not EyeLink's 0 (`update_sample_data.without_lost_pupil`).

The checklist form of these rules — the diff that triggers each, the check, and
the bug behind it — is in [`REVIEW.md`](../../REVIEW.md).
