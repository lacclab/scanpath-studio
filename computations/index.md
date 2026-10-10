# Computations & methodology

Register version **2** · 66 entries across 9 categories.

Every operation that derives or semantically changes a value you can see, export, or fetch through the API is listed here with its formula, its units, and how far it has actually been verified. Pure layout and byte-preserving file I/O are out of scope; filtering, precedence and assignment are in, because they change *which observations* a result stands for.

## How to read the status column

| Status                     | Means                                                          |
| -------------------------- | -------------------------------------------------------------- |
| **Verified**               | A hand-calculated oracle or exact invariant exists and passes. |
| **Partially verified**     | Tested, but without an independent reference implementation.   |
| **Unverified**             | Exercised by tests only for execution, not for meaning.        |
| **Intentional convention** | A choice that can only be documented, not proved.              |

Verification tiers: **A** hand-calculated synthetic oracle · **B** independent reference implementation · **C** property/invariant tests · **D** cross-surface parity (UI, API, CLI, export agree).

Tier B is largely absent, on purpose

Comparing against an independent implementation [is planned](https://github.com/lacclab/scanpath-studio/issues/130). Scientific measures therefore read *Partially verified* even where their hand oracle is exact.

Entries marked *experimental* are not in this release. They are listed so that their definitions are on record.

## Summary

| ID                                                        | Name                                     | Category                        | Unit                                                                                             | Status                                |
| --------------------------------------------------------- | ---------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------------------------- |
| [`norm.words`](#norm-words)                               | Word table normalization                 | Normalization / inference       | —                                                                                                | Partially verified                    |
| [`norm.fixations`](#norm-fixations)                       | Fixation table normalization             | Normalization / inference       | —                                                                                                | Partially verified                    |
| [`norm.box_edges`](#norm-box-edges)                       | Word box from edges                      | Normalization / inference       | px (screen coordinates, y increasing downwards)                                                  | Verified                              |
| [`norm.trial_id_composite`](#norm-trial-id-composite)     | Composite trial identity                 | Normalization / inference       | —                                                                                                | Partially verified                    |
| [`norm.flags`](#norm-flags)                               | Flag coercion                            | Normalization / inference       | —                                                                                                | Verified                              |
| [`norm.stimulus_broadcast`](#norm-stimulus-broadcast)     | Stimulus-level word broadcast            | Normalization / inference       | —                                                                                                | Partially verified                    |
| [`norm.aoi_center_placement`](#norm-aoi-center-placement) | AoI-only fixation placement              | Normalization / inference       | px                                                                                               | Verified                              |
| [`norm.participant_metadata`](#norm-participant-metadata) | Participant metadata join                | Normalization / inference       | —                                                                                                | Verified                              |
| [`assign.fixation_to_word`](#assign-fixation-to-word)     | Fixation → word assignment               | Assignment / classification     | —                                                                                                | Partially verified                    |
| [`assign.in_text`](#assign-in-text)                       | Out-of-text flag                         | Assignment / classification     | —                                                                                                | Verified                              |
| [`assign.line_cluster`](#assign-line-cluster)             | Visual line clustering                   | Assignment / classification     | —                                                                                                | Partially verified                    |
| [`assign.runs`](#assign-runs)                             | Runs and passes                          | Assignment / classification     | —                                                                                                | Partially verified                    |
| [`assign.progression`](#assign-progression)               | Progression and regression flags         | Assignment / classification     | —                                                                                                | Verified                              |
| [`assign.saccade_class`](#assign-saccade-class)           | Saccade reading class                    | Assignment / classification     | —                                                                                                | Partially verified                    |
| [`measure.ffd`](#measure-ffd)                             | First fixation duration (FFD)            | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.fprt`](#measure-fprt)                           | First-pass gaze duration (FPRT)          | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.rpd`](#measure-rpd)                             | Regression-path duration (RPD / go-past) | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.tfd`](#measure-tfd)                             | Total fixation duration (TFD)            | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.nfix`](#measure-nfix)                           | Fixations per word                       | Scientific measure              | —                                                                                                | Verified · experimental               |
| [`measure.skip`](#measure-skip)                           | Skip flag / skip rate                    | Scientific measure              | rate when aggregated (0–1)                                                                       | Verified · experimental               |
| [`measure.regressions`](#measure-regressions)             | Regression in/out flags                  | Scientific measure              | rate when aggregated (0–1)                                                                       | Partially verified · experimental     |
| [`measure.landing_position`](#measure-landing-position)   | Initial landing position                 | Scientific measure              | letters                                                                                          | Partially verified · experimental     |
| [`measure.landing_distance`](#measure-landing-distance)   | Centred landing distance                 | Scientific measure              | letters (0 = word center, negative = left of center)                                             | Partially verified · experimental     |
| [`measure.second_pass`](#measure-second-pass)             | Second-pass duration                     | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.single_fix`](#measure-single-fix)               | Single-fixation duration                 | Scientific measure              | ms                                                                                               | Partially verified · experimental     |
| [`measure.reg_in_count`](#measure-reg-in-count)           | Regressions into word                    | Scientific measure              | —                                                                                                | Partially verified · experimental     |
| [`fix.saccade_amplitude`](#fix-saccade-amplitude)         | Saccade amplitude                        | Scientific measure              | px                                                                                               | Verified                              |
| [`fix.angles`](#fix-angles)                               | Saccade angles                           | Scientific measure              | degrees (−180, 180\]                                                                             | Verified                              |
| [`fix.rebased_onsets`](#fix-rebased-onsets)               | Rebased fixation onsets                  | Scientific measure              | ms                                                                                               | Partially verified                    |
| [`pre.merge_short`](#pre-merge-short)                     | Short-fixation merging                   | Preprocessing                   | ms threshold, characters distance                                                                | Partially verified · experimental     |
| [`pre.exclude_short`](#pre-exclude-short)                 | Short/long fixation exclusion            | Preprocessing                   | ms                                                                                               | Partially verified · experimental     |
| [`pre.blink_adjacent`](#pre-blink-adjacent)               | Blink-adjacent exclusion                 | Preprocessing                   | —                                                                                                | Partially verified · experimental     |
| [`pre.cleaning_report`](#pre-cleaning-report)             | Cleaning QA report                       | Preprocessing                   | —                                                                                                | Partially verified · experimental     |
| [`pre.sentence_measures`](#pre-sentence-measures)         | Sentence-level measures                  | Preprocessing                   | ms, counts                                                                                       | Partially verified · experimental     |
| [`pre.saccade_table`](#pre-saccade-table)                 | Saccade table                            | Preprocessing                   | px, deg (when geometry is known), ms                                                             | Partially verified · experimental     |
| [`pre.character_grid`](#pre-character-grid)               | Character grid                           | Preprocessing                   | px                                                                                               | Intentional convention · experimental |
| [`pre.rtl`](#pre-rtl)                                     | Right-to-left detection                  | Preprocessing                   | —                                                                                                | Verified                              |
| [`pre.sensitivity`](#pre-sensitivity)                     | Measure sensitivity                      | Preprocessing                   | —                                                                                                | Partially verified · experimental     |
| [`align.algorithms`](#align-algorithms)                   | Vertical drift correction                | Preprocessing                   | —                                                                                                | Partially verified · experimental     |
| [`agg.measure_values`](#agg-measure-values)               | Measure value extraction                 | Statistical aggregation         | —                                                                                                | Partially verified                    |
| [`agg.aggregate_value`](#agg-aggregate-value)             | Central tendency                         | Statistical aggregation         | —                                                                                                | Verified                              |
| [`agg.spread`](#agg-spread)                               | Spread band                              | Statistical aggregation         | —                                                                                                | Verified                              |
| [`agg.bootstrap_ci`](#agg-bootstrap-ci)                   | Bootstrap confidence interval            | Statistical aggregation         | same as the measure                                                                              | Verified                              |
| [`agg.effect_size`](#agg-effect-size)                     | Group means and difference               | Statistical aggregation         | —                                                                                                | Partially verified                    |
| [`agg.group_mask`](#agg-group-mask)                       | Group definition                         | Statistical aggregation         | —                                                                                                | Verified                              |
| [`agg.word_profile`](#agg-word-profile)                   | Per-word cohort profile                  | Statistical aggregation         | —                                                                                                | Partially verified                    |
| [`agg.word_rates`](#agg-word-rates)                       | Skip / regression rate profile           | Statistical aggregation         | proportion                                                                                       | Partially verified                    |
| [`agg.reader_summary`](#agg-reader-summary)               | Per-participant summary                  | Statistical aggregation         | ms, px, counts, proportions                                                                      | Partially verified · experimental     |
| [`agg.trial_summary`](#agg-trial-summary)                 | Per-trial summary                        | Statistical aggregation         | ms, counts                                                                                       | Partially verified · experimental     |
| [`agg.normalize`](#agg-normalize)                         | Normalized measure column                | Statistical aggregation         | —                                                                                                | Partially verified                    |
| [`agg.landing_curve`](#agg-landing-curve)                 | Landing-position curve                   | Statistical aggregation         | fraction of the interest area (0–1 for a landing inside the box), or px with `as_fraction=False` | Partially verified · experimental     |
| [`agg.over_time`](#agg-over-time)                         | Trend over time                          | Statistical aggregation         | —                                                                                                | Partially verified                    |
| [`sim.nld`](#sim-nld)                                     | Normalized Levenshtein distance          | Similarity                      | dimensionless (0–1)                                                                              | Verified · experimental               |
| [`sim.aoi_sequence`](#sim-aoi-sequence)                   | AoI sequence                             | Similarity                      | —                                                                                                | Verified · experimental               |
| [`sim.windowed`](#sim-windowed)                           | NLD by fixation index / time             | Similarity                      | —                                                                                                | Partially verified · experimental     |
| [`geom.pixels_per_degree`](#geom-pixels-per-degree)       | Pixels per degree of visual angle        | Unit / coordinate conversion    | px / degree                                                                                      | Verified                              |
| [`geom.font_pt_to_px`](#geom-font-pt-to-px)               | Font point size to pixels                | Unit / coordinate conversion    | px                                                                                               | Verified                              |
| [`geom.word_box_bounds`](#geom-word-box-bounds)           | Word interest-area edges                 | Unit / coordinate conversion    | px                                                                                               | Partially verified                    |
| [`geom.word_box_space_px`](#geom-word-box-space-px)       | Inter-word padding baked into each box   | Unit / coordinate conversion    | px                                                                                               | Verified                              |
| [`geom.word_char_advance`](#geom-word-char-advance)       | Character advance within a word          | Unit / coordinate conversion    | px / character                                                                                   | Verified                              |
| [`geom.word_glyph_span`](#geom-word-glyph-span)           | Where a word's glyphs are                | Unit / coordinate conversion    | px                                                                                               | Partially verified                    |
| [`disp.marker_sizes`](#disp-marker-sizes)                 | Fixation marker sizing                   | Display / export transformation | px (marker diameter)                                                                             | Intentional convention                |
| [`disp.axis_ranges`](#disp-axis-ranges)                   | Axis ranges and inversion                | Display / export transformation | px                                                                                               | Intentional convention                |
| [`disp.true_scale`](#disp-true-scale)                     | True-scale text rendering                | Display / export transformation | —                                                                                                | Intentional convention                |
| [`disp.animation_timing`](#disp-animation-timing)         | Animation timing                         | Display / export transformation | ms (recorded) → ms (playback)                                                                    | Intentional convention                |
| [`disp.illustration`](#disp-illustration)                 | Illustration disclosure                  | Display / export transformation | —                                                                                                | Verified                              |

## Normalization / inference

### `norm.words` — Word table normalization

Map an arbitrary word/IA export onto the canonical word columns.

**Formula.** For each canonical field, `pick_column` walks a candidate list and takes the first column that exists; the user's mapping overrides it. Unmapped optional fields are dropped unless listed in `WORD_OPTIONAL_FIELDS`.

|                          |                                                                       |
| ------------------------ | --------------------------------------------------------------------- |
| **Output**               | participant_id, trial_id, text_id, word_id, text, x, y, width, height |
| **Missing & edge cases** | A missing *required* field raises with the columns it looked for.     |
| **Precedence & caveats** | An explicit user mapping always beats auto-detection.                 |
| **Code**                 | `scanpath_studio/data.py:normalize_words`                             |
| **Consumers**            | UI, API, CLI, Export                                                  |
| **Tests**                | `tests/test_data.py`, `tests/test_column_mapping.py`                  |
| **Verification**         | tier C, D — **Partially verified**                                    |

### `norm.fixations` — Fixation table normalization

Map an arbitrary fixation report onto the canonical columns.

**Formula.** As `norm.words`, over the fixation candidate lists. `order_in_trial` is assigned by sorting each trial on `timestamp_ms`; `fixation_id` is synthesized per trial when the export carries none.

|                          |                                                                |
| ------------------------ | -------------------------------------------------------------- |
| **Output**               | participant_id, trial_id, x, y, duration_ms, timestamp_ms, …   |
| **Grouping / ordering**  | (participant_id, trial_id[, screen_id])                        |
| **Missing & edge cases** | Rows with no coordinates survive when a word/AoI id is mapped. |
| **Code**                 | `scanpath_studio/data.py:normalize_fixations`                  |
| **Consumers**            | UI, API, CLI, Export                                           |
| **Tests**                | `tests/test_data.py`                                           |
| **Verification**         | tier C, D — **Partially verified**                             |

### `norm.box_edges` — Word box from edges

Convert EyeLink IA edges to origin+size.

**Formula.** x = IA_LEFT · y = IA_TOP · width = IA_RIGHT − IA_LEFT · height = IA_BOTTOM − IA_TOP.

|                  |                                                 |
| ---------------- | ----------------------------------------------- |
| **Output**       | x, y, width, height                             |
| **Unit**         | px (screen coordinates, y increasing downwards) |
| **Code**         | `scanpath_studio/data.py:normalize_words`       |
| **Consumers**    | UI, API, CLI, Export                            |
| **Tests**        | `tests/test_word_box_geometry.py`               |
| **Verification** | tier A, C — **Verified**                        |

### `norm.trial_id_composite` — Composite trial identity

Build one unique trial id from several columns.

**Formula.** The mapped Trial ID columns are joined in the order given, separated by `_`, after casting each to string. A `_` or `\` inside a part is escaped with a `\` first, so two different tuples never give the same id; parts with neither compose as a plain join.

|                          |                                                                    |
| ------------------------ | ------------------------------------------------------------------ |
| **Output**               | trial_id                                                           |
| **Missing & edge cases** | A row missing any component keeps the literal string of that part. |
| **Code**                 | `scanpath_studio/data.py:trial_id_series`                          |
| **Consumers**            | UI, API, CLI                                                       |
| **Tests**                | `tests/test_trial_identity.py`, `tests/test_composite_ids.py`      |
| **Verification**         | tier C, D — **Partially verified**                                 |

### `norm.flags` — Flag coercion

Read EyeLink's string booleans as booleans.

**Formula.** Numbers go by `!= 0`. Strings are matched case-insensitively against `{'', '.', '0', '0.0', 'false', 'f', 'no', 'n', 'na', 'nan', '-'}` → False; anything else → True.

|                          |                                                                                                                                                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | bool                                                                                                                                                                                                                                              |
| **Missing & edge cases** | NaN → False for an operational flag (blink, excluded). A supplied reading-measure flag (skip, regression in / out) keeps it missing instead — `''`, `'.'`, `'na'`, `'nan'`, `'-'` and NaN read as NA (`coerce_measure_flag`, a nullable boolean). |
| **Reference**            | Guards the `'.'`-as-missing convention in EyeLink IA reports.                                                                                                                                                                                     |
| **Code**                 | `scanpath_studio/data.py:coerce_flag`                                                                                                                                                                                                             |
| **Consumers**            | UI, API, CLI, Export                                                                                                                                                                                                                              |
| **Tests**                | `tests/test_data.py`                                                                                                                                                                                                                              |
| **Verification**         | tier A, C — **Verified**                                                                                                                                                                                                                          |

### `norm.stimulus_broadcast` — Stimulus-level word broadcast

Share one stimulus' word boxes across every participant who read it.

**Formula.** Words with no participant column are copied once per reading (participant × trial [× screen]) in the fixations, stamped with that reading's ids. Per reading, the boxes are those of the first words trial found by its trial ID, then its trial ID before a repeat's \_r2 suffix, then its Text ID (only a Text ID the fixations map, and never one the words give to more than one trial). A trial-ID match always stands; mapped Text IDs that disagree with it are warned about.

|                          |                                                                                                                                                                                                                  |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Missing & edge cases** | No fixations for a text ⇒ its words are not broadcast. Some readings unmatched ⇒ StimulusJoinWarning with the counts; none matched, or any multipart screen unmatched ⇒ StimulusJoinError, never an empty table. |
| **Code**                 | `scanpath_studio/data.py:broadcast_stimulus_words`                                                                                                                                                               |
| **Consumers**            | UI, API, CLI                                                                                                                                                                                                     |
| **Tests**                | `tests/test_stimulus_join.py`, `tests/test_dataset_support.py`                                                                                                                                                   |
| **Verification**         | tier C — **Partially verified**                                                                                                                                                                                  |

### `norm.aoi_center_placement` — AoI-only fixation placement

Place a fixation with no x/y at its word box's center.

**Formula.** x = word.x + width/2 · y = word.y + height/2.

|                          |                                                                                                                                                                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px                                                                                                                                                                                                                                                                  |
| **Missing & edge cases** | No matching word box, or no word id (blank, or not a number) ⇒ the fixation keeps no coordinates — a missing id never matches a box with none. No x/y mapped and a Word/IA ID column with no numbers at all ⇒ UnplacedFixationsError, never an empty figure (#412). |
| **Precedence & caveats** | Only when x/y are absent; recorded coordinates always win.                                                                                                                                                                                                          |
| **Code**                 | `scanpath_studio/data.py:harmonize_frames`                                                                                                                                                                                                                          |
| **Consumers**            | UI, API, CLI                                                                                                                                                                                                                                                        |
| **Tests**                | `tests/test_data.py`                                                                                                                                                                                                                                                |
| **Verification**         | tier A, C — **Verified**                                                                                                                                                                                                                                            |

### `norm.participant_metadata` — Participant metadata join

Attach a participant-level table without broadcasting it.

**Formula.** Left join on string `participant_id`. Duplicate ids that agree are combined field by field (each field keeps the one non-missing value the rows hold); duplicate ids that **disagree** are dropped and reported, so no `groupby.first()` winner is ever invented. A field is projected onto the per-trial frame, never onto word/fixation rows.

|                          |                                                                            |
| ------------------------ | -------------------------------------------------------------------------- |
| **Output**               | One column per registered field, at participant grain                      |
| **Missing & edge cases** | A participant with no row reads as missing everywhere, never as a default. |
| **Precedence & caveats** | A real recorded column of the same name always wins.                       |
| **Code**                 | `scanpath_studio/metadata.py:build_participant_metadata`                   |
| **Consumers**            | UI, API, CLI, Export, Data Management                                      |
| **Tests**                | `tests/test_metadata.py`, `tests/test_metadata_duplicates.py`              |
| **Verification**         | tier A, C, D — **Verified**                                                |

## Assignment / classification

### `assign.fixation_to_word` — Fixation → word assignment

The single highest-risk step: which word a fixation counts for.

**Formula.** 1. Bounding-box containment against the trial's word boxes — the experiment's own rectangles (`geom.word_box_bounds`), so on a tiling corpus a fixation on the space *after* a word is credited to that word, as EyeLink's interest-area report credits it. Boxes are half-open, `x0 ≤ x < x1` and `y0 ≤ y < y1` (`measures.word_box_contains`), so a point on an edge two boxes share goes to the one that starts there — the next word, the line below — as EyeLink assigns it. 2. Otherwise `word_id = NaN` (out of text). There is no snapping to a nearby word.

|                          |                                                                                                                                                                                                                                                                                                                                             |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | word_id                                                                                                                                                                                                                                                                                                                                     |
| **Grouping / ordering**  | (participant_id, trial_id[, screen_id]) — never across screens                                                                                                                                                                                                                                                                              |
| **Missing & edge cases** | Unassignable fixations keep NaN and are excluded from word measures.                                                                                                                                                                                                                                                                        |
| **Precedence & caveats** | Runs only when the fixations carry no word id. A mapped `word_id` (on the bundled demo, EyeLink's `CURRENT_FIX_INTEREST_AREA_ID`) is used exactly as given, blanks included — nothing is computed and no blank is filled — unless `overwrite=True`. Geometry agrees with that column on all 3,208 of the demo's EyeLink-assigned fixations. |
| **Code**                 | `scanpath_studio/measures.py:assign_fixations_to_words`                                                                                                                                                                                                                                                                                     |
| **Consumers**            | UI, API, CLI, Export, Corpus Analysis                                                                                                                                                                                                                                                                                                       |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`                                                                                                                                                                                                                                                                                         |
| **Verification**         | tier A, C — **Partially verified**                                                                                                                                                                                                                                                                                                          |

### `assign.in_text` — Out-of-text flag

Whether a fixation landed on any word of the stimulus.

**Formula.** The fixation falls inside some word box (`word_box_bounds`, tested half-open by `word_box_contains`, as `assign.fixation_to_word` tests it). Box containment only, so a fixation the data's own `word_id` puts on a word but that lies outside every box still counts as out-of-text.

|                  |                                                     |
| ---------------- | --------------------------------------------------- |
| **Output**       | bool mask                                           |
| **Code**         | `scanpath_studio/measures.py:fixation_in_text_mask` |
| **Consumers**    | UI, API, Corpus Analysis                            |
| **Tests**        | `tests/test_synthetic.py`                           |
| **Verification** | tier A, C — **Verified**                            |

### `assign.line_cluster` — Visual line clustering

Derive text lines from word-box geometry, not from `line_idx`.

**Formula.** Word boxes are sorted by `y` and split wherever the gap between consecutive centers exceeds `tol_frac` (0.5) of the median box height. Exists because `line_idx` is a constant in many IA exports.

|                  |                                                     |
| ---------------- | --------------------------------------------------- |
| **Output**       | Line index per word                                 |
| **Code**         | `scanpath_studio/measures.py:cluster_word_lines`    |
| **Consumers**    | UI, API, Corpus Analysis                            |
| **Tests**        | `tests/test_measures.py`, `tests/test_synthetic.py` |
| **Verification** | tier A, C — **Partially verified**                  |

### `assign.runs` — Runs and passes

Trial run, line run, and per-word visit/pass indices.

**Formula.** Consecutive fixations on the same word form one *visit*; the n-th visit to a word is its n-th pass. Line runs break whenever the assigned line changes.

|                          |                                                                                                                                                                                                                               |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | run, linerun, word_runid, word_run (the visit's pass number), word_run_fix, nrun, reread (word_run > 1)                                                                                                                       |
| **Grouping / ordering**  | Ordered by `timestamp_ms` within a trial                                                                                                                                                                                      |
| **Precedence & caveats** | Always recomputed: an imported column under any of these names is replaced. An imported `pass_index` (EyeLink's `reread` is renamed to it on load) is a separate column and is kept as given — nothing computes `pass_index`. |
| **Code**                 | `scanpath_studio/measures.py:materialize_runs`                                                                                                                                                                                |
| **Consumers**            | UI, API, Export, Corpus Analysis                                                                                                                                                                                              |
| **Tests**                | `tests/test_measures.py`                                                                                                                                                                                                      |
| **Verification**         | tier A, C — **Partially verified**                                                                                                                                                                                            |

### `assign.progression` — Progression and regression flags

Whether the *outgoing* saccade moves forward in the text.

**Formula.** `progression = sign(next word_id − word_id)`. `is_regression = word_id < running max word_id in the trial` — i.e. relative to the furthest word reached, not to the previous fixation.

|                          |                                                     |
| ------------------------ | --------------------------------------------------- |
| **Output**               | progression ∈ {−1, 0, 1}, is_regression             |
| **Grouping / ordering**  | Per trial, in timestamp order                       |
| **Missing & edge cases** | Unassigned fixations give progression 0.            |
| **Code**                 | `scanpath_studio/measures.py:enrich_fixations`      |
| **Consumers**            | UI, API, Export, Corpus Analysis                    |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py` |
| **Verification**         | tier A, C — **Verified**                            |

### `assign.saccade_class` — Saccade reading class

Label each outgoing saccade by its reading role.

**Formula.** From the word and text line of the two fixations, in this order: refixation (same word), regression (up to an earlier line, or back within a line), return sweep (down to a later line), forward (the next word on the line), skip (two or more words ahead on the line); `other` when either fixation has no assigned word.

|                          |                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------- |
| **Output**               | (not stored — computed for each figure)                                                       |
| **Precedence & caveats** | Always computed; an imported `saccade_type` / `NEXT_SAC_DIRECTION` (a direction) is not used. |
| **Code**                 | `scanpath_studio/measures.py:classify_saccades`                                               |
| **Consumers**            | UI, API, Export                                                                               |
| **Tests**                | `tests/test_saccade_class_filter.py`                                                          |
| **Verification**         | tier A, C — **Partially verified**                                                            |

## Preprocessing

### `pre.merge_short` — Short-fixation merging

Experimental

Not in this release.

Fold a short fixation into a neighbour within a character distance.

**Formula.** A fixation below the short threshold is merged into the nearer adjacent fixation when that neighbour is within the merge distance, expressed in characters and converted to px via `geom.word_char_advance`. Durations add; position follows the survivor.

|                          |                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------- |
| **Output**               | A reduced fixation frame                                                                            |
| **Unit**                 | ms threshold, characters distance                                                                   |
| **Missing & edge cases** | Off by default; original rows stay available.                                                       |
| **Precedence & caveats** | The conversion reads the shared letter scale, so "within 1 character" means the same on every word. |
| **Reference**            | A common cleaning step; thresholds are the user's choice.                                           |
| **Code**                 | `scanpath_studio/preprocessing.py:merge_short_fixations`                                            |
| **Consumers**            | UI (Preprocessing panel — not in this release), API, CLI, Export                                    |
| **Tests**                | `tests/test_preprocessing.py`                                                                       |
| **Verification**         | tier A, C — **Partially verified**                                                                  |

### `pre.exclude_short` — Short/long fixation exclusion

Experimental

Not in this release.

Soft-exclude fixations outside a duration window.

**Formula.** Drop fixations shorter than / longer than the chosen bounds.

|                          |                                                                  |
| ------------------------ | ---------------------------------------------------------------- |
| **Unit**                 | ms                                                               |
| **Missing & edge cases** | Soft: excluded rows are reported, not deleted from the source.   |
| **Code**                 | `scanpath_studio/preprocessing.py:preprocess_fixations`          |
| **Consumers**            | UI (Preprocessing panel — not in this release), API, CLI, Export |
| **Tests**                | `tests/test_preprocessing.py`                                    |
| **Verification**         | tier C — **Partially verified**                                  |

### `pre.blink_adjacent` — Blink-adjacent exclusion

Experimental

Not in this release.

Drop fixations immediately before/after a blink.

**Formula.** Exclude the fixations neighbouring any row flagged `is_blink`.

|                          |                                                                  |
| ------------------------ | ---------------------------------------------------------------- |
| **Missing & edge cases** | No blink column ⇒ the option has no effect.                      |
| **Code**                 | `scanpath_studio/preprocessing.py:preprocess_fixations`          |
| **Consumers**            | UI (Preprocessing panel — not in this release), API, CLI, Export |
| **Tests**                | `tests/test_preprocessing.py`                                    |
| **Verification**         | tier C — **Partially verified**                                  |

### `pre.cleaning_report` — Cleaning QA report

Experimental

Not in this release.

What the preprocessing pass would remove, and why.

**Formula.** Counts per exclusion reason over the unfiltered frame.

|                  |                                                                                                                          |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Output**       | Cleaning QA table                                                                                                        |
| **Code**         | `scanpath_studio/preprocessing.py:cleaning_report`                                                                       |
| **Consumers**    | UI (Preprocessing panel — not in this release), API, CLI, Export, Data Management (derived tables — not in this release) |
| **Tests**        | `tests/test_preprocessing.py`                                                                                            |
| **Verification** | tier C — **Partially verified**                                                                                          |

### `pre.sentence_measures` — Sentence-level measures

Experimental

Not in this release.

Per-sentence reading time and counts.

**Formula.** Words are grouped into sentences by `infer_sentence_ids` (terminal punctuation). Each sentence's durations, fixation and run counts, go-past times and skip flag are then derived from the fixations on its words; the supplied word measures are not used, so a sentence with no fixations reads as skipped (which is why Corpus Analysis → Per sentence is held back).

|                          |                                                                                           |
| ------------------------ | ----------------------------------------------------------------------------------------- |
| **Output**               | Sentences table                                                                           |
| **Unit**                 | ms, counts                                                                                |
| **Missing & edge cases** | Sentence inference is textual, not annotated — approximate.                               |
| **Code**                 | `scanpath_studio/preprocessing.py:sentence_measures`                                      |
| **Consumers**            | Corpus Analysis, API, CLI, Export, Data Management (derived tables — not in this release) |
| **Tests**                | `tests/test_preprocessing.py`                                                             |
| **Verification**         | tier C — **Partially verified**                                                           |

### `pre.saccade_table` — Saccade table

Experimental

Not in this release.

One row per saccade, with amplitude, angle and class.

**Formula.** Consecutive fixation pairs within a trial; amplitude in px, and in degrees only when `pixels_per_degree` is supplied.

|                          |                                                                          |
| ------------------------ | ------------------------------------------------------------------------ |
| **Output**               | Saccades table                                                           |
| **Unit**                 | px, deg (when geometry is known), ms                                     |
| **Missing & edge cases** | Assumed geometry ⇒ the degree columns inherit that assumption.           |
| **Code**                 | `scanpath_studio/preprocessing.py:saccade_table`                         |
| **Consumers**            | API, CLI, Export, Data Management (derived tables — not in this release) |
| **Tests**                | `tests/test_preprocessing.py`                                            |
| **Verification**         | tier C — **Partially verified**                                          |

### `pre.character_grid` — Character grid

Experimental

Not in this release.

Per-character boxes derived from word boxes.

**Formula.** Character `k` of a word spans `x + (k−1) × advance` to `x + k × advance`, where the advance is `geom.word_char_advance`.

|                          |                                                                                                                                                                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Unit**                 | px                                                                                                                                                                                                                                               |
| **Missing & edge cases** | Proportional fonts make this an approximation.                                                                                                                                                                                                   |
| **Precedence & caveats** | The advance is the shared letter scale, not `width / len(text)` — which on a tiling corpus stretched the glyph row across the trailing inter-word padding, so each character box after the first sat progressively further right than its glyph. |
| **Code**                 | `scanpath_studio/preprocessing.py:character_grid`                                                                                                                                                                                                |
| **Consumers**            | API, CLI, Export, Data Management (derived tables — not in this release)                                                                                                                                                                         |
| **Tests**                | `tests/test_preprocessing.py`                                                                                                                                                                                                                    |
| **Verification**         | tier A, C — **Intentional convention**                                                                                                                                                                                                           |

### `pre.rtl` — Right-to-left detection

Whether a word's script runs right to left.

**Formula.** Unicode range test over the word's characters.

|                  |                                                         |
| ---------------- | ------------------------------------------------------- |
| **Output**       | right_to_left                                           |
| **Code**         | `scanpath_studio/preprocessing.py:detect_right_to_left` |
| **Consumers**    | UI, API, Corpus Analysis                                |
| **Tests**        | `tests/test_preprocessing.py`                           |
| **Verification** | tier A, C — **Verified**                                |

### `pre.sensitivity` — Measure sensitivity

Experimental

Not in this release.

How much the word measures move under different line assignments.

**Formula.** Each trial's fixations are line-assigned by every method in `methods` (default `attach`, `slice`, `consensus`), FFD / FPRT / RPD / TFD are recomputed per method, and each word's spread (max − min across methods) is reported beside a per-trial correction report.

|                  |                                                        |
| ---------------- | ------------------------------------------------------ |
| **Code**         | `scanpath_studio/preprocessing.py:measure_sensitivity` |
| **Consumers**    | API (not in this release)                              |
| **Tests**        | `tests/test_preprocessing.py`                          |
| **Verification** | tier C — **Partially verified**                        |

### `align.algorithms` — Vertical drift correction

Experimental

Not in this release.

Line-assignment algorithms, ported natively.

**Formula.** The ten Carr et al. algorithms — `attach`, `chain`, `cluster`, `compare`, `merge`, `regress`, `segment`, `split`, `stretch`, `warp` — plus `slice` and a `consensus` vote over them. Each reassigns fixation *y* to a text line. Not in this release.

|                          |                                                                                                                                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | Corrected fixation y (display only; exported tables stay raw)                                                                                                                                                                                           |
| **Missing & edge cases** | Off by default; the original coordinates are never overwritten.                                                                                                                                                                                         |
| **Reference**            | Carr, Pescuma, Furlan, Ktori & Crepaldi (2021), *Algorithms for the automated correction of vertical drift in eye-tracking data*, Behavior Research Methods. Ported from the reference implementation — the one entry with a genuine tier-B comparison. |
| **Code**                 | `scanpath_studio/alignment.py:correct`                                                                                                                                                                                                                  |
| **Consumers**            | UI, API, CLI                                                                                                                                                                                                                                            |
| **Tests**                | `tests/test_alignment.py`, `tests/test_cli_drift.py`                                                                                                                                                                                                    |
| **Verification**         | tier B, C — **Partially verified**                                                                                                                                                                                                                      |

## Scientific measure

### `measure.ffd` — First fixation duration (FFD)

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Duration of the first fixation on a word.

**Formula.** Duration of the word's first fixation, whenever it comes — as EyeLink's `IA_FIRST_FIXATION_DURATION`, so a computed and an imported value mean the same. Not conditioned on first pass: a word first reached by a regression has an FFD and `skip_flag = True`; filter on `skip_flag` for first-pass-only analyses.

|                          |                                                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Output**               | first_fixation_ms                                                                                                                                                                                            |
| **Unit**                 | ms                                                                                                                                                                                                           |
| **Grouping / ordering**  | (participant, trial, word)                                                                                                                                                                                   |
| **Missing & edge cases** | Never fixated ⇒ NaN, not 0, so a skipped word is left out of every mean. An imported 0 is blanked too, wherever the word's fixation count is 0 — or, with no count mapped, its total fixation duration is 0. |
| **Precedence & caveats** | A precomputed `IA_FIRST_FIXATION_DURATION` wins.                                                                                                                                                             |
| **Reference**            | Rayner (1998), standard reading-measure definitions.                                                                                                                                                         |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                                                                                                      |
| **Consumers**            | UI, API                                                                                                                                                                                                      |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`                                                                                                                                                          |
| **Verification**         | tier A, D — **Partially verified**                                                                                                                                                                           |

### `measure.fprt` — First-pass gaze duration (FPRT)

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Sum of the fixations in the word's first visit.

**Formula.** Sum of every fixation in the word's **first** run, i.e. before the gaze leaves the word for the first time — whenever that run starts (EyeLink's `IA_FIRST_RUN_DWELL_TIME`; not conditioned on first pass, as `measure.ffd`). A fixation outside every word ends the run, as it does for `measure.second_pass`.

|                          |                                                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Output**               | first_pass_gaze_duration_ms                                                                                                                                                                                  |
| **Unit**                 | ms                                                                                                                                                                                                           |
| **Grouping / ordering**  | (participant, trial, word)                                                                                                                                                                                   |
| **Missing & edge cases** | Never fixated ⇒ NaN, not 0, so a skipped word is left out of every mean. An imported 0 is blanked too, wherever the word's fixation count is 0 — or, with no count mapped, its total fixation duration is 0. |
| **Precedence & caveats** | A precomputed IA gaze duration wins.                                                                                                                                                                         |
| **Reference**            | Rayner (1998).                                                                                                                                                                                               |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                                                                                                      |
| **Consumers**            | UI, API                                                                                                                                                                                                      |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`                                                                                                                                                          |
| **Verification**         | tier A, D — **Partially verified**                                                                                                                                                                           |

### `measure.rpd` — Regression-path duration (RPD / go-past)

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

First entry to the word until the gaze passes it to the right.

**Formula.** Total time from the word's first fixation until the first fixation on a **later** word — every fixation in between, including a first visit to an earlier, skipped word during the regression. Matches EyeLink's `IA_REGRESSION_PATH_DURATION` on 1779 of the bundled demo's 1780 fixated words. Fixations outside every word neither extend nor close the window.

|                          |                                                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Output**               | regression_path_duration_ms                                                                                                                                                                                  |
| **Unit**                 | ms                                                                                                                                                                                                           |
| **Grouping / ordering**  | (participant, trial, word)                                                                                                                                                                                   |
| **Missing & edge cases** | Never fixated ⇒ NaN, not 0, so a skipped word is left out of every mean. An imported 0 is blanked too, wherever the word's fixation count is 0 — or, with no count mapped, its total fixation duration is 0. |
| **Reference**            | Definitions differ across toolkits (go-past vs regression path); `eyekit` is the intended comparison. Unresolved until that cross-validation runs.                                                           |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                                                                                                      |
| **Consumers**            | UI, API                                                                                                                                                                                                      |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`                                                                                                                                                          |
| **Verification**         | tier A — **Partially verified**                                                                                                                                                                              |

### `measure.tfd` — Total fixation duration (TFD)

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

All time spent on a word across the whole trial.

**Formula.** Sum of every fixation assigned to the word, any pass.

|                          |                                                               |
| ------------------------ | ------------------------------------------------------------- |
| **Output**               | total_fixation_duration_ms                                    |
| **Unit**                 | ms                                                            |
| **Missing & edge cases** | Never fixated ⇒ 0 (the word *was* read past; it got no time). |
| **Precedence & caveats** | A precomputed IA dwell time wins.                             |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`       |
| **Consumers**            | UI, API                                                       |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`           |
| **Verification**         | tier A, D — **Partially verified**                            |

### `measure.nfix` — Fixations per word

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Count of fixations assigned to a word.

**Formula.** Row count of the word's assigned fixations.

|                          |                                                         |
| ------------------------ | ------------------------------------------------------- |
| **Output**               | n_fixations                                             |
| **Missing & edge cases** | Never fixated ⇒ 0.                                      |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures` |
| **Consumers**            | UI, API                                                 |
| **Tests**                | `tests/test_synthetic.py`                               |
| **Verification**         | tier A — **Verified**                                   |

### `measure.skip` — Skip flag / skip rate

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Whether a word received no first-pass fixation.

**Formula.** `skip_flag = no fixation in the word's first pass`.

|                          |                                                                 |
| ------------------------ | --------------------------------------------------------------- |
| **Output**               | skip_flag                                                       |
| **Unit**                 | rate when aggregated (0–1)                                      |
| **Missing & edge cases** | A word fixated only after a regression still counts as skipped. |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`         |
| **Consumers**            | UI, API                                                         |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`             |
| **Verification**         | tier A — **Verified**                                           |

### `measure.regressions` — Regression in/out flags

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Whether a word was returned to, or left backwards.

**Formula.** `regression_in_flag` — some later fixation lands on this word after the gaze had moved past it. `regression_out_flag` — a regression to an earlier word is made from this word during first pass, before the eyes first leave it forwards (EyeLink's `IA_REGRESSION_OUT`); a regression from it later in the trial does not count.

|                          |                                                         |
| ------------------------ | ------------------------------------------------------- |
| **Output**               | regression_in_flag, regression_out_flag                 |
| **Unit**                 | rate when aggregated (0–1)                              |
| **Precedence & caveats** | Precomputed IA regression flags win (see `norm.flags`). |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures` |
| **Consumers**            | UI, API                                                 |
| **Tests**                | `tests/test_measures.py`, `tests/test_synthetic.py`     |
| **Verification**         | tier A — **Partially verified**                         |

### `measure.landing_position` — Initial landing position

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Where in the word the first fixation landed, in letters.

**Formula.** `char_width = geom.word_char_advance`; `offset = first_fix_x − word.x` (LTR) or `word.x + n·advance − first_fix_x` (RTL); `landing_position = offset / char_width + 1` — so the first letter starts at 1 and its center is 1.5. Unclipped: on a tiling corpus the box's last cell is the space after the word, which belongs to it, so a first fixation there reads `n + 1` to `n + 2`.

|                          |                                                                                                                                               |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | initial_landing_position                                                                                                                      |
| **Unit**                 | letters                                                                                                                                       |
| **Missing & edge cases** | Never fixated, zero width, or no text ⇒ NaN. Measured from the word's first fixation, first pass or not (as `measure.ffd`).                   |
| **Precedence & caveats** | The scale is `geom.word_char_advance`, not `width / len(text)`, which on a tiling corpus puts every landing ~`(n+1)/n` too far into the word. |
| **Reference**            | Assumes a monospaced advance within the word box — exact for the app's monospace default, approximate for proportional fonts.                 |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                                       |
| **Consumers**            | UI, API                                                                                                                                       |
| **Tests**                | `tests/test_measures.py`                                                                                                                      |
| **Verification**         | tier A — **Partially verified**                                                                                                               |

### `measure.landing_distance` — Centred landing distance

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Landing position relative to the word's center.

**Formula.** `landing_position − (1 + len(text) / 2)` — the glyphs span `[1, n + 1)`, so that is the word's center. The center of the *letters*, not of the box: a tiling box's trailing space would move it half a letter right.

|                          |                                                         |
| ------------------------ | ------------------------------------------------------- |
| **Output**               | initial_landing_distance                                |
| **Unit**                 | letters (0 = word center, negative = left of center)    |
| **Missing & edge cases** | As `measure.landing_position`.                          |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures` |
| **Consumers**            | UI, API                                                 |
| **Tests**                | `tests/test_measures.py`                                |
| **Verification**         | tier A — **Partially verified**                         |

### `measure.second_pass` — Second-pass duration

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

Time spent on the word during its second visit.

**Formula.** Sum of the fixations in the word's second run.

|                          |                                                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| **Output**               | second_pass_duration_ms                                                                                                 |
| **Unit**                 | ms                                                                                                                      |
| **Missing & edge cases** | Fewer than two runs ⇒ 0. An imported blank `IA_SECOND_RUN_DWELL_TIME` becomes 0 too, where the fixation count is known. |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                 |
| **Consumers**            | UI, API                                                                                                                 |
| **Tests**                | `tests/test_measures.py`                                                                                                |
| **Verification**         | tier A — **Partially verified**                                                                                         |

### `measure.single_fix` — Single-fixation duration

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

First-pass duration when the first pass was exactly one fixation.

**Formula.** FFD when the word's first run has length 1, else NaN.

|                          |                                                                                                                                                                                                                                                           |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | single_fixation_duration_ms                                                                                                                                                                                                                               |
| **Unit**                 | ms                                                                                                                                                                                                                                                        |
| **Missing & edge cases** | A first run of more than one fixation ⇒ NaN. Never fixated ⇒ NaN, not 0, so a skipped word is left out of every mean. An imported 0 is blanked too, wherever the word's fixation count is 0 — or, with no count mapped, its total fixation duration is 0. |
| **Reference**            | Rayner (1998).                                                                                                                                                                                                                                            |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures`                                                                                                                                                                                                   |
| **Consumers**            | UI, API                                                                                                                                                                                                                                                   |
| **Tests**                | `tests/test_measures.py`                                                                                                                                                                                                                                  |
| **Verification**         | tier A — **Partially verified**                                                                                                                                                                                                                           |

### `measure.reg_in_count` — Regressions into word

Experimental

Scanpath Studio does not compute this in this release. A value your dataset brings is shown as given, defined by the software that exported it.

How many times the gaze came back to this word.

**Formula.** Number of regressions into the word — entries from a later word (EyeLink's `IA_REGRESSION_IN_COUNT`). A re-entry from an *earlier* word is a new run but not a regression in.

|                          |                                                         |
| ------------------------ | ------------------------------------------------------- |
| **Output**               | number_of_regressions_in                                |
| **Missing & edge cases** | Never regressed into ⇒ 0.                               |
| **Code**                 | `scanpath_studio/measures.py:compute_per_word_measures` |
| **Consumers**            | UI, API                                                 |
| **Tests**                | `tests/test_measures.py`                                |
| **Verification**         | tier A — **Partially verified**                         |

### `fix.saccade_amplitude` — Saccade amplitude

Distance between consecutive fixations — always pixels.

**Formula.** `sqrt(dx² + dy²)` between consecutive fixations in the trial.

|                          |                                                                                                                                                                                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | saccade_amplitude                                                                                                                                                                                                                                                                                       |
| **Unit**                 | px                                                                                                                                                                                                                                                                                                      |
| **Grouping / ordering**  | Per trial, in timestamp order; the first fixation has none.                                                                                                                                                                                                                                             |
| **Missing & edge cases** | First fixation of a trial ⇒ NaN.                                                                                                                                                                                                                                                                        |
| **Precedence & caveats** | A source column literally named `saccade_amplitude` is assumed to be pixels and kept. EyeLink's **degree**-valued `NEXT_SAC_AMPLITUDE` / `PREVIOUS_SAC_AMPLITUDE` normalize to `next_/prev_saccade_amplitude_deg` and never reach this column — they are different quantities *and* different saccades. |
| **Code**                 | `scanpath_studio/measures.py:enrich_fixations`                                                                                                                                                                                                                                                          |
| **Consumers**            | UI, API, Export, Corpus Analysis                                                                                                                                                                                                                                                                        |
| **Tests**                | `tests/test_measures.py`                                                                                                                                                                                                                                                                                |
| **Verification**         | tier A, C — **Verified**                                                                                                                                                                                                                                                                                |

### `fix.angles` — Saccade angles

Incoming and outgoing saccade direction.

**Formula.** `angle_incoming = degrees(atan2(−dy, dx))` from the previous fixation; `angle_outgoing` is the next fixation's incoming angle. `−dy` because screen y grows downwards, so 0° is rightward and positive is up.

|                          |                                                |
| ------------------------ | ---------------------------------------------- |
| **Output**               | angle_incoming, angle_outgoing                 |
| **Unit**                 | degrees (−180, 180\]                           |
| **Missing & edge cases** | Trial edges ⇒ NaN.                             |
| **Code**                 | `scanpath_studio/measures.py:enrich_fixations` |
| **Consumers**            | UI, API, Export                                |
| **Tests**                | `tests/test_measures.py`                       |
| **Verification**         | tier A, C — **Verified**                       |

### `fix.rebased_onsets` — Rebased fixation onsets

Trial-relative onset times for animation and time series.

**Formula.** Cumulative onsets rebased so the trial starts at 0, from `timestamp_ms` where present, else by accumulating durations.

|                          |                                                       |
| ------------------------ | ----------------------------------------------------- |
| **Output**               | Onset array                                           |
| **Unit**                 | ms                                                    |
| **Missing & edge cases** | A backwards clock restarts the accumulation.          |
| **Code**                 | `scanpath_studio/measures.py:rebased_fixation_onsets` |
| **Consumers**            | UI, API, CLI                                          |
| **Tests**                | `tests/test_measures.py`                              |
| **Verification**         | tier A, C — **Partially verified**                    |

## Statistical aggregation

### `agg.measure_values` — Measure value extraction

Pull one registered measure's values out of a frame.

**Formula.** The `aggregation.MEASURES` entry names the frame (words or fixations), the column and the unit; values are coerced numeric and NaNs dropped.

|                          |                                                             |
| ------------------------ | ----------------------------------------------------------- |
| **Missing & edge cases** | Non-numeric entries become NaN and are dropped, not zeroed. |
| **Code**                 | `scanpath_studio/aggregation.py:measure_values`             |
| **Consumers**            | Corpus Analysis, API                                        |
| **Tests**                | `tests/test_aggregation.py`                                 |
| **Verification**         | tier C, D — **Partially verified**                          |

### `agg.aggregate_value` — Central tendency

The Aggregate selector: mean / median / sum.

**Formula.** `np.nanmean` · `np.nanmedian` · `np.nansum` over the values.

|                          |                                                      |
| ------------------------ | ---------------------------------------------------- |
| **Missing & edge cases** | NaN-skipping throughout; an all-NaN input gives NaN. |
| **Code**                 | `scanpath_studio/aggregation.py:aggregate_value`     |
| **Consumers**            | Corpus Analysis, API                                 |
| **Tests**                | `tests/test_aggregation.py`                          |
| **Verification**         | tier A, C — **Verified**                             |

### `agg.spread` — Spread band

The error band drawn around an aggregate.

**Formula.** `SD` → ±1 sample std (ddof=1) · `SEM` → ±std/√n · `IQR` → the 25th and 75th percentiles · `Bootstrap CI` → `agg.bootstrap_ci`. With `agg='sum'`, SD/SEM fall back to the bootstrap: the spread of individual observations does not bracket a total.

|                          |                                                |
| ------------------------ | ---------------------------------------------- |
| **Missing & edge cases** | Empty input or NaN center ⇒ a zero-width band. |
| **Code**                 | `scanpath_studio/aggregation.py:spread_bounds` |
| **Consumers**            | Corpus Analysis, API                           |
| **Tests**                | `tests/test_aggregation.py`                    |
| **Verification**         | tier A, C — **Verified**                       |

### `agg.bootstrap_ci` — Bootstrap confidence interval

Percentile bootstrap CI of the chosen aggregate.

**Formula.** 1000 resamples with replacement; the CI is the 2.5th and 97.5th percentiles of the resampled statistic.

|                          |                                                            |
| ------------------------ | ---------------------------------------------------------- |
| **Unit**                 | same as the measure                                        |
| **Missing & edge cases** | n < 2 ⇒ a degenerate interval at the point estimate.       |
| **Precedence & caveats** | Seeded (`seed=0`) — the same data gives the same interval. |
| **Reference**            | Percentile bootstrap; no bias correction.                  |
| **Code**                 | `scanpath_studio/aggregation.py:bootstrap_ci`              |
| **Consumers**            | Corpus Analysis, API                                       |
| **Tests**                | `tests/test_aggregation.py`                                |
| **Verification**         | tier A, C — **Verified**                                   |

### `agg.effect_size` — Group means and difference

Two groups' means, their difference and Cohen's d.

**Formula.** Each value is one participant's mean of the measure (pooled observations when the data names no participants). `mean_diff = mean(A) − mean(B)`. Cohen's *d* uses the pooled SD `sqrt(((nA−1)·varA + (nB−1)·varB) / (nA+nB−2))` with ddof=1, and is shown only when the groups share no participant.

|                          |                                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | mean_a, mean_b, mean_diff, cohen_d, n_a, n_b                                                                                                    |
| **Grouping / ordering**  | One value per participant in each group                                                                                                         |
| **Missing & edge cases** | n < 2 in either group ⇒ NaN *d*. A zero pooled SD gives **NaN**, not 0.0, so it cannot read as 'no effect' beside a non-zero mean difference.   |
| **Reference**            | **Descriptive only** — no significance test. A participant in both groups contributes to both means, so the groups are not independent samples. |
| **Code**                 | `scanpath_studio/aggregation.py:group_mean_difference`                                                                                          |
| **Consumers**            | Corpus Analysis, API                                                                                                                            |
| **Tests**                | `tests/test_aggregation.py`                                                                                                                     |
| **Verification**         | tier A, C — **Partially verified**                                                                                                              |

### `agg.group_mask` — Group definition

Which rows belong to a cohort.

**Formula.** A spec maps column → allowed values; the mask is the conjunction of membership tests. Two modes: split one field, or two independent filter sets. A key may be a tuple of columns matched as one composite key: a trial-metadata field resolves to the (participant, trial) readings its rows describe, a participant field to participant ids and a text field to text ids — the tables are never joined onto the frames.

|                          |                                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Missing & edge cases** | A column (or any column of a composite key) absent from the frame contributes no constraint; a metadata selection that matches nothing selects no rows. |
| **Code**                 | `scanpath_studio/aggregation.py:group_mask`                                                                                                             |
| **Consumers**            | Corpus Analysis, API                                                                                                                                    |
| **Tests**                | `tests/test_aggregation.py`                                                                                                                             |
| **Verification**         | tier A, C — **Verified**                                                                                                                                |

### `agg.word_profile` — Per-word cohort profile

A measure per word position, aggregated across participants.

**Formula.** Group the word measures by word id and apply `agg.aggregate_value`.

|                          |                                                              |
| ------------------------ | ------------------------------------------------------------ |
| **Missing & edge cases** | A minimum-participants threshold drops thinly-sampled words. |
| **Code**                 | `scanpath_studio/aggregation.py:cohort_word_profile`         |
| **Consumers**            | Corpus Analysis, API                                         |
| **Tests**                | `tests/test_aggregation.py`                                  |
| **Verification**         | tier C — **Partially verified**                              |

### `agg.word_rates` — Skip / regression rate profile

Rate measures per word.

**Formula.** Mean of the 0/1 flag over the participants who reported it — a proportion in [0, 1]. Each rate has its own participant count (`n_skip`, `n_regression_in`) and its own minimum-participants verdict.

|                          |                                                                                                                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Unit**                 | proportion                                                                                                                                                                                             |
| **Missing & edge cases** | A missing flag is no observation: it is left out of that rate and its participant count, never read as 0. A rate below the minimum participants is hidden; the word stays while its other rate stands. |
| **Code**                 | `scanpath_studio/aggregation.py:word_rate_profile`                                                                                                                                                     |
| **Consumers**            | Corpus Analysis, API                                                                                                                                                                                   |
| **Tests**                | `tests/test_aggregation.py`                                                                                                                                                                            |
| **Verification**         | tier A, C — **Partially verified**                                                                                                                                                                     |

### `agg.reader_summary` — Per-participant summary

Experimental

Not in this release.

One row per participant: totals, means and rates.

**Formula.** Counts and NaN-skipping means over that participant's rows. `mean_saccade_px` is the mean of `fix.saccade_amplitude` and is in pixels.

|                  |                                                       |
| ---------------- | ----------------------------------------------------- |
| **Output**       | Readers table                                         |
| **Unit**         | ms, px, counts, proportions                           |
| **Code**         | `scanpath_studio/aggregation.py:reader_summary_table` |
| **Consumers**    | Corpus Analysis, Export, Data Management, API         |
| **Tests**        | `tests/test_aggregation.py`                           |
| **Verification** | tier C, D — **Partially verified**                    |

### `agg.trial_summary` — Per-trial summary

Experimental

Not in this release.

One row per trial: reading time, counts, rates.

**Formula.** Counts and sums over the trial's fixations and word measures. `reading_time_ms` is last fixation end − first fixation start; without recorded fixation onsets it is the summed fixation durations, and `reading_time_source` says it is an estimate. `wpm` = words ÷ reading time.

|                          |                                                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Output**               | Trials table                                                                                                               |
| **Unit**                 | ms, counts                                                                                                                 |
| **Missing & edge cases** | No onset column ⇒ reading time and wpm are duration-based estimates, labeled as such — never the 0, 1, 2, … order numbers. |
| **Code**                 | `scanpath_studio/aggregation.py:trial_summary_table`                                                                       |
| **Consumers**            | Corpus Analysis, Export, Data Management, API                                                                              |
| **Tests**                | `tests/test_aggregation.py`                                                                                                |
| **Verification**         | tier C, D — **Partially verified**                                                                                         |

### `agg.normalize` — Normalized measure column

Rescale a measure for cross-participant comparison.

**Formula.** Per-participant z-score, `(value − participant mean) / participant SD`, when **Z-score per participant** is on.

|                          |                                                                                                             |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **Missing & edge cases** | A participant with zero variance (or one value) ⇒ 0, the participant's own mean; a missing value stays NaN. |
| **Code**                 | `scanpath_studio/aggregation.py:add_normalized_column`                                                      |
| **Consumers**            | Corpus Analysis                                                                                             |
| **Tests**                | `tests/test_aggregation.py`                                                                                 |
| **Verification**         | tier A, C — **Partially verified**                                                                          |

### `agg.landing_curve` — Landing-position curve

Experimental

Not in this release.

Distribution of initial landing positions by word length.

**Formula.** Histogram of the landing position as a *fraction of the word's interest area* — `(first_fix_x − word.x) / width` over the experiment's own box, i.e. `(measure.landing_position − 1)` over the box's `width / geom.word_char_advance` character cells (RTL counted from where the glyphs end, as the letter position is). Unclipped — binned per word length.

|                          |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Unit**                 | fraction of the interest area (0–1 for a landing inside the box), or px with `as_fraction=False`                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Precedence & caveats** | On a glyph-tight corpus the box is the glyph run, so 0 is the first letter's edge and 1 the last's. On a tiling corpus the box's last cell is the space after the word, so the glyphs fill `[0, n / (n + 1))` and a landing on that space reads just below 1, not clipped onto 1.0. A first fixation assigned from outside the box (by an imported `word_id`) reads below 0 or above 1 rather than being clipped onto an edge. The origin is the word's `x` and the scale is `geom.word_char_advance`. |
| **Code**                 | `scanpath_studio/aggregation.py:landing_positions`                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Consumers**            | Corpus Analysis                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **Tests**                | `tests/test_aggregation.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Verification**         | tier C — **Partially verified**                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

### `agg.over_time` — Trend over time

A measure by trial index or fixation index.

**Formula.** Aggregate per index position across the selection.

|                          |                                                   |
| ------------------------ | ------------------------------------------------- |
| **Missing & edge cases** | Index positions with no data are gaps, not zeros. |
| **Code**                 | `scanpath_studio/aggregation.py:metric_over_time` |
| **Consumers**            | Corpus Analysis                                   |
| **Tests**                | `tests/test_aggregation.py`                       |
| **Verification**         | tier C — **Partially verified**                   |

## Similarity

### `sim.nld` — Normalized Levenshtein distance

Experimental

Not in this release.

Scanpath similarity over AoI sequences.

**Formula.** `levenshtein(a, b) / max(len(a), len(b))` ∈ [0, 1]; 0 is identical. Two empty sequences give 0.

|                          |                                                        |
| ------------------------ | ------------------------------------------------------ |
| **Unit**                 | dimensionless (0–1)                                    |
| **Missing & edge cases** | Not in this release.                                   |
| **Reference**            | Standard edit-distance scanpath comparison.            |
| **Code**                 | `scanpath_studio/similarity.py:normalized_levenshtein` |
| **Consumers**            | UI, API                                                |
| **Tests**                | `tests/test_similarity.py`                             |
| **Verification**         | tier A, C — **Verified**                               |

### `sim.aoi_sequence` — AoI sequence

Experimental

Not in this release.

The symbol string an NLD comparison runs on.

**Formula.** Assigned `word_id`s in fixation order, with unassigned fixations dropped and (optionally) immediate repeats collapsed.

|                          |                                                              |
| ------------------------ | ------------------------------------------------------------ |
| **Missing & edge cases** | A trial with no assigned fixations yields an empty sequence. |
| **Code**                 | `scanpath_studio/similarity.py:aoi_sequence`                 |
| **Consumers**            | UI, API                                                      |
| **Tests**                | `tests/test_similarity.py`                                   |
| **Verification**         | tier A, C — **Verified**                                     |

### `sim.windowed` — NLD by fixation index / time

Experimental

Not in this release.

Similarity restricted to a window of the scanpath.

**Formula.** `sim.nld` over the sub-sequence inside the index or time window.

|                  |                                                       |
| ---------------- | ----------------------------------------------------- |
| **Code**         | `scanpath_studio/similarity.py:nld_by_fixation_index` |
| **Consumers**    | UI, API                                               |
| **Tests**        | `tests/test_similarity.py`                            |
| **Verification** | tier C — **Partially verified**                       |

## Unit / coordinate conversion

### `geom.pixels_per_degree` — Pixels per degree of visual angle

The screen-geometry conversion every angular unit depends on.

**Formula.** `px_per_mm = canvas_width_px / monitor_width_mm`; `mm_per_degree = 2 · viewing_distance_mm · tan(0.5°)`; `px_per_degree = px_per_mm · mm_per_degree`.

|                          |                                                                                                                                                                                              |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px / degree                                                                                                                                                                                  |
| **Missing & edge cases** | Any missing geometry ⇒ no conversion is offered at all.                                                                                                                                      |
| **Precedence & caveats** | **Provenance matters more than the number.** Every built-in corpus assumes its monitor size and viewing distance, so a degree-valued result inherits that — see the *Recording setup* panel. |
| **Code**                 | `scanpath_studio/experimental_setup.py:pixels_per_degree`                                                                                                                                    |
| **Consumers**            | UI, API, CLI, Export                                                                                                                                                                         |
| **Tests**                | `tests/test_experimental_setup.py`                                                                                                                                                           |
| **Verification**         | tier A, C — **Verified**                                                                                                                                                                     |

### `geom.font_pt_to_px` — Font point size to pixels

Typography conversion for true-scale text rendering.

**Formula.** `px = pt · dpi / 72`.

|                  |                                                       |
| ---------------- | ----------------------------------------------------- |
| **Unit**         | px                                                    |
| **Code**         | `scanpath_studio/experimental_setup.py:font_pt_to_px` |
| **Consumers**    | UI, API, CLI                                          |
| **Tests**        | `tests/test_experimental_setup.py`                    |
| **Verification** | tier A, C — **Verified**                              |

### `geom.word_box_bounds` — Word interest-area edges

Where one word's interest area ends and the next begins.

**Formula.** `x .. x + width` by `y .. y + height` — the experiment's own rectangles, unmodified. On a tiling corpus each box includes the space after its word.

|                          |                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Precedence & caveats** | The boundary *between* words, for everything that tests a point against a box or draws one: `assign.fixation_to_word`, `assign.in_text`, the drawn outlines, the word heatmaps, the critical-span frame, drift correction and the model scanpaths. A position *inside* a word goes through `geom.word_char_advance` instead, and where its letters are through `geom.word_glyph_span`; the drawn word label is centered in the box. |
| **Code**                 | `scanpath_studio/measures.py:word_box_bounds`                                                                                                                                                                                                                                                                                                                                                                                       |
| **Consumers**            | UI, API, Corpus Analysis                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Tests**                | `tests/test_word_box_geometry.py`, `tests/test_word_id_offset.py`                                                                                                                                                                                                                                                                                                                                                                   |
| **Verification**         | tier A, C — **Partially verified**                                                                                                                                                                                                                                                                                                                                                                                                  |

### `geom.word_box_space_px` — Inter-word padding baked into each box

Detects a tiling layout that carries one trailing space per box.

**Formula.** Median of `width / (len(text) + 1)` across one trial's words — the advance — reported only when the boxes are consistently that wide **and** actually tile (no gaps). Anything else ⇒ `0.0`, i.e. 'these AOIs are glyph-tight — each box is its glyph run'.

|                          |                                                                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px                                                                                                                              |
| **Missing & edge cases** | No usable words ⇒ 0.0 (glyph-tight), never a guess.                                                                             |
| **Precedence & caveats** | Never moves a box edge; it only tells `geom.word_char_advance` and `geom.word_glyph_span` how many character cells a box holds. |
| **Code**                 | `scanpath_studio/measures.py:word_box_space_px`                                                                                 |
| **Consumers**            | UI, API, Export                                                                                                                 |
| **Tests**                | `tests/test_measures.py`                                                                                                        |
| **Verification**         | tier A, C — **Verified**                                                                                                        |

### `geom.word_char_advance` — Character advance within a word

How wide one letter is — the scale for every within-word position.

**Formula.** `width / (len(text) + 1)` when `geom.word_box_space_px` finds trailing padding, else `width / len(text)`.

|                          |                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px / character                                                                                                                                                                                                                                                                                                                                                                                  |
| **Missing & edge cases** | No `text`/`width` ⇒ NaN, and the letter measures report NaN.                                                                                                                                                                                                                                                                                                                                    |
| **Precedence & caveats** | The single accessor for the letter scale, as `geom.word_box_bounds` is for the boundary between words: `measure.landing_position`, `measure.landing_distance`, `agg.landing_curve` and the saccade table's launch/landing letter all read it. Before that each derived its own `width / len(text)`, which is one advance too wide on a tiling corpus, by a factor that varied with word length. |
| **Code**                 | `scanpath_studio/measures.py:word_char_advance`                                                                                                                                                                                                                                                                                                                                                 |
| **Consumers**            | UI, API, Export, Corpus Analysis                                                                                                                                                                                                                                                                                                                                                                |
| **Tests**                | `tests/test_measures.py`                                                                                                                                                                                                                                                                                                                                                                        |
| **Verification**         | tier A, C — **Verified**                                                                                                                                                                                                                                                                                                                                                                        |

### `geom.word_glyph_span` — Where a word's glyphs are

The glyph run inside a word's box — where its letters are.

**Formula.** Starts at `x` and runs `len(text) × geom.word_char_advance`: the whole box on a glyph-tight corpus, one advance short of it on a tiling one. No `text` ⇒ the box width.

|                          |                                                                                                                                                                                                                                                                                                                                                 |
| ------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px                                                                                                                                                                                                                                                                                                                                              |
| **Precedence & caveats** | Not an interest area: `agg.landing_curve` measures a landing across it and mirrors an RTL one. Measured against OneStop's own Experiment Builder screens: each tiling box is centered on its word, half a space either side, so the run's `x` start is half an advance early there; the label uses the box center, the landing measures do not. |
| **Code**                 | `scanpath_studio/measures.py:word_glyph_span`                                                                                                                                                                                                                                                                                                   |
| **Consumers**            | UI, API, Corpus Analysis                                                                                                                                                                                                                                                                                                                        |
| **Tests**                | `tests/test_word_box_geometry.py`                                                                                                                                                                                                                                                                                                               |
| **Verification**         | tier A — **Partially verified**                                                                                                                                                                                                                                                                                                                 |

## Display / export transformation

### `disp.marker_sizes` — Fixation marker sizing

Marker size encodes fixation duration on one fixed scale.

**Formula.** Fixed scales (`marker_size_scale` = `sqrt`, the default; `linear`; `log`): `size = s_min + (s_max − s_min) · (f(d) − f(lo)) / (f(hi) − f(lo))`, with `d` clamped to the duration bounds `[lo, hi]` (`marker_duration_range`, default 50–600 ms) and `f` = √, identity or ln. `relative`: linear between the drawn set's own shortest and longest duration (the scale before the fixed one; older saved configs and Share links keep it). **Display only** — never a recorded value.

|                          |                                                                                                                                                                                    |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | px (marker diameter)                                                                                                                                                               |
| **Missing & edge cases** | A missing duration is treated as 0 ms: the smallest marker.                                                                                                                        |
| **Precedence & caveats** | One scale for single-trial figures, both comparison sides, replays and bulk exports, so a duration draws at one size in all of them; only the px range is per scanpath in Compare. |
| **Code**                 | `scanpath_studio/plots.py:_compute_marker_sizes`                                                                                                                                   |
| **Consumers**            | UI, API, CLI, Export                                                                                                                                                               |
| **Tests**                | `tests/test_duration_scale.py`, `tests/test_plots.py`, `tests/test_builder_parity.py`                                                                                              |
| **Verification**         | tier C, D — **Intentional convention**                                                                                                                                             |

### `disp.axis_ranges` — Axis ranges and inversion

Screen coordinates, drawn the way the screen is.

**Formula.** The y axis is inverted (`y_range = [max, min]`) so the figure matches the display; ranges come from the canvas, not the data, when a canvas size is known.

|                  |                                                 |
| ---------------- | ----------------------------------------------- |
| **Unit**         | px                                              |
| **Code**         | `scanpath_studio/plots.py:_compute_axis_ranges` |
| **Consumers**    | UI, API, CLI, Export                            |
| **Tests**        | `tests/test_plots.py`                           |
| **Verification** | tier C, D — **Intentional convention**          |

### `disp.true_scale` — True-scale text rendering

One line of text fills its share of the recorded line pitch.

**Formula.** A word label's font is `1/line_spacing` of the line pitch (the median line-to-line distance of the word boxes), capped so the words fit their box widths (`plots._width_fit_font`; the smaller wins), in data pixels converted at the figure's display scale. When the boxes are monospace words padded alike — half the gap to each neighbour — the font is read off them instead: one character cell is the slope of box width over word length (`plots._padded_monospace_font`), over the font's advance. The figure is drawn at its exact pixel size and scaled as one block.

|                  |                                                    |
| ---------------- | -------------------------------------------------- |
| **Code**         | `scanpath_studio/tabs.py:_render_true_scale_chart` |
| **Consumers**    | UI                                                 |
| **Tests**        | `tests/test_plots.py`                              |
| **Verification** | tier D — **Intentional convention**                |

### `disp.animation_timing` — Animation timing

How recorded time maps to playback time.

**Formula.** Frames sit on a uniform reading-time grid over `fix.rebased_onsets`; the frame at reading time t is on screen once t / playback speed of wall time has passed, so a replay lasts reading span / speed. The player keeps that clock itself, skipping frames a display is too slow to show, and a GIF/MP4 lasts the same. A multipart replay changes screen at the boundary and draws no connector across canvases.

|                          |                                                                                                                                                                                        |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Unit**                 | ms (recorded) → ms (playback)                                                                                                                                                          |
| **Precedence & caveats** | Plotly's own frame queue is never the clock: it rounds every frame up to whole display ticks and the error accumulates. Without the player (`fig.show()`) the figure falls back to it. |
| **Code**                 | `scanpath_studio/plots.py:make_scanpath_animation`                                                                                                                                     |
| **Consumers**            | UI, API, CLI, Export                                                                                                                                                                   |
| **Tests**                | `tests/test_replay_player.py`, `tests/test_animation_export.py`                                                                                                                        |
| **Verification**         | tier C, D — **Intentional convention**                                                                                                                                                 |

### `disp.illustration` — Illustration disclosure

When a figure stops being a faithful record.

**Formula.** Views that no longer show the data as recorded — snapped fixations, arced saccades, hidden or windowed fixations, a replay not at real time, an authored scanpath — are labeled *Illustration*.

|                  |                                                          |
| ---------------- | -------------------------------------------------------- |
| **Code**         | `scanpath_studio/illustration.py:illustration_reasons`   |
| **Consumers**    | UI, API, CLI, Export                                     |
| **Tests**        | `tests/test_illustration.py`, `tests/test_disclosure.py` |
| **Verification** | tier C, D — **Verified**                                 |
