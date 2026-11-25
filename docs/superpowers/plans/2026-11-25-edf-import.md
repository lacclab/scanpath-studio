# EyeLink EDF Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a study's EyeLink `.edf` files into a Scanpath Studio dataset (fixations, word boxes, stimulus images, trial metadata; raw gaze on request) with no Data Viewer step.

**Architecture:** A new `scanpath_studio/eyelink.py` wraps SR Research's `edf2asc`, parses the ASC with pymovements (plus a small line scan for what pymovements drops), reads the Experiment Builder session files the EDF points to (`.ias`, `.vcl`, runtime images), and writes a per-participant Parquet **study folder** in parallel and resumably. `api.add_eyelink_dataset` loads that folder into a saved dataset through the existing `api.add_dataset`. The CLI gets `import-eyelink`. All of it is experimental.

**Tech Stack:** Python ≥3.11, pandas 3, pymovements 0.28 (optional extra `edf`), Pillow, pyarrow, `concurrent.futures.ProcessPoolExecutor`.

**Spec:** `docs/superpowers/specs/2026-11-25-edf-import-design.md`

## Global Constraints

- Off unless `SCANPATH_EXPERIMENTAL=1`: gate `constants.eyelink_import_enabled()` (returns `experimental_features_enabled()`); every public entry raises `ValueError` naming `SCANPATH_EXPERIMENTAL` when off; CLI flags/commands hidden from `--help` when off.
- `edf2asc` is never bundled or downloaded. Lookup order: `SCANPATH_EDF2ASC` env var → `PATH` → known install folders (macOS `/Applications/EyeLink/`, `/usr/local/bin/edf2asc`; Windows `C:\Program Files (x86)\SR Research\EyeLink\bin\edf2asc.exe` and `C:\Program Files\SR Research\EyeLink\bin\edf2asc.exe`; Linux `/usr/bin/edf2asc`).
- Conversion command (argument list, no shell): `edf2asc <edf> -t -c -y -utf8 -e -p <tmp_dir>`; drop `-e` when raw gaze is requested.
- pymovements is an optional extra: `edf = ["pymovements>=0.28.0"]` in `pyproject.toml`; without it, entries raise `ImportError` naming `pip install "scanpath-studio[edf]"`. Never imported at module top level.
- Fixations are EyeLink's own `EFIX` events, positions taken from the `EFIX` line's average x/y, never recomputed.
- Never write into the user's experiment folder. ASCs are temporary unless `keep_asc=True`.
- Message time correction: an event's time is `msg_time - offset` (`MSG 896475 -13 …` → 896488). A `.vcl` / `.ias` line's leading number is an offset applied the same way to the `DRAW_LIST` / `IAREA FILE` message's corrected time.
- Clock: `timestamp_ms` is tracker ms minus the trial's `START` line time (as the bundled demo's `TRIAL_START_TIME`).
- House rules (CLAUDE.md): `from __future__ import annotations`; ruff via `uv run --extra lint`; changelog fragment, never `CHANGELOG.md`; no issue numbers or history in comments; `Verified:` trailer; no AI co-author trailer; commits on a branch, landed by PR.

## Review Focus

1. **Session folder missing or partial** (ASC kept apart from `results/<session>/`, an `.ias` deleted) → fixations still load; `notes` names each missing file; no exception. Test in Task 4.
2. **Aborted trial** (no `TRIAL_RESULT`, or no `END` before the next `TRIALID`) → the trial ends at the next `TRIALID` / `END` / end of file, and its fixations are kept. Test in Task 3.
3. **Binocular recording** → both eyes' fixations kept with `eye` = `L`/`R`; screens and words are not duplicated. Test in Task 2 and Task 4.
4. **Non-UTF-8 ASC** (latin-1 bytes in a message, as OneStop's) → parses. Test in Task 2.
5. **Re-running after one EDF changed or a new EDF added** → only those sessions are redone; a failed session is retried and others are untouched. Test in Task 5.

---

### Task 0: Branch, issue, spec

- [ ] **Step 1:** `git switch -c eyelink-edf-import` from an up-to-date `main`.
- [ ] **Step 2:** Open the issue with `/track` (type Feature, `area:data`, Status *In progress*, assigned to `@me`); body summarises the spec and links it. Use its number `#N` in every commit subject below.
- [ ] **Step 3:** Commit the spec, this plan and the `mkdocs.yml` `exclude_docs` line for `superpowers/`: `git commit -m "Design and plan EyeLink EDF import (#N)"` with `Verified: none (docs only)`.

### Task 1: Gate, extra, and the `edf2asc` wrapper

**Files:**
- Modify: `scanpath_studio/constants.py` (add `eyelink_import_enabled` beside `multipleye_format_enabled`)
- Modify: `pyproject.toml` (extra `edf`)
- Create: `scanpath_studio/eyelink.py`
- Modify: `AGENTS.md` (module map line under *Data*; *Experimental features* bullet)
- Test: `tests/test_eyelink_convert.py`

**Interfaces:**
- Produces:
  - `class Edf2AscNotFoundError(FileNotFoundError)`; `class Edf2AscError(RuntimeError)`
  - `find_edf2asc() -> Path`
  - `convert_edf(edf: Path, out_dir: Path, *, samples: bool = False) -> Path` (returns the `.asc` path)
  - `_require_enabled(entry: str) -> None` (raises the gate's `ValueError`)

- [ ] **Step 1: Write failing tests** — a fake `edf2asc` is a `tmp_path` shell script that writes `<stem>.asc` into the `-p` folder and echoes its argv to a file; set `SCANPATH_EDF2ASC` to it.
  - `test_find_uses_env_var` → `find_edf2asc() == fake`.
  - `test_find_missing_names_where_to_get_it`: env var unset, `PATH` empty, known folders patched to `tmp_path` → `Edf2AscNotFoundError`, message contains `"EyeLink Developers Kit"` and `"SCANPATH_EDF2ASC"`.
  - `test_convert_events_only_args`: argv == `[<edf>, "-t", "-c", "-y", "-utf8", "-e", "-p", <out>]`; returns `out / "s1.asc"`.
  - `test_convert_with_samples_drops_e`.
  - `test_bad_cpu_type_explains_rosetta`: monkeypatch `subprocess.run` to raise `OSError(86, "Bad CPU type in executable")` → `Edf2AscError` whose message contains `"softwareupdate --install-rosetta"`.
  - `test_nonzero_exit_reports_output`: fake script exits 1 printing `boom` → `Edf2AscError` containing `boom`.
  - `test_gate_off_raises`: without `SCANPATH_EXPERIMENTAL`, `convert_edf` → `ValueError` mentioning `SCANPATH_EXPERIMENTAL`.
- [ ] **Step 2:** `uv run --extra test pytest tests/test_eyelink_convert.py -v` → FAIL (module missing).
- [ ] **Step 3:** Implement. `convert_edf` calls `subprocess.run(args, capture_output=True, text=True, check=False)`; success means exit 0 **and** the `.asc` exists. Add the `edf` extra and the AGENTS.md lines.
- [ ] **Step 4:** Tests PASS; `uv run --extra lint ruff check . && uv run --extra lint ruff format .`.
- [ ] **Step 5:** Commit `Add the edf2asc wrapper behind the experimental gate (#N)`.

### Task 2: ASC reading

**Files:**
- Modify: `scanpath_studio/eyelink.py`
- Create: `tests/eyelink_fixtures.py` (builders for a small experiment on disk)
- Test: `tests/test_eyelink_asc.py`

**Interfaces:**
- Consumes: `_require_enabled`.
- Produces:
  - `@dataclass(frozen=True) class AscRecording`: `fixations: pd.DataFrame` (`eye`, `onset`, `offset`, `duration_ms`, `x`, `y`), `messages: pd.DataFrame` (`time`, `text`; time already offset-corrected, offset stripped from `text`), `blocks: pd.DataFrame` (`start`, `end` from `START`/`END` lines), `samples: pd.DataFrame | None` (`time`, `x`, `y`, `pupil`, `eye`), `display: tuple[int, int] | None` (from `DISPLAY_COORDS l t r b` → `(r-l+1, b-t+1)`).
  - `read_asc(path: Path, *, samples: bool = False) -> AscRecording`
  - `tests/eyelink_fixtures.py`: `write_experiment(root: Path, *, binocular=False, with_session_files=True, aborted_trial=False, latin1=False) -> Path` returns the `.asc` path at `root/exp/results/p01/p01.asc`, plus `EXPECTED` dict of hand-traced values (fixation counts/positions per trial and screen, word boxes, trial vars). Layout: `exp/results/p01/{p01.asc, aoi/IA_1.ias, aoi/IA_2.ias, graphics/VC_1.vcl, graphics/VC_2.vcl}`, `exp/runtime/images/{bg.png, text1.png, text2.png}` (Pillow-generated solid colours). Two trials; trial 1 has two displays (a text screen with boxes, then a question screen without); `DISPLAY_COORDS 0 0 1279 1023`.

- [ ] **Step 1: Failing tests:**
  - `test_read_fixations_positions`: fixations equal `EXPECTED["fixations"]` (onset, duration, x, y, eye) exactly.
  - `test_messages_offset_corrected`: `MSG 1000 -13 !V DRAW_LIST graphics/VC_1.vcl` → row `(1013, "!V DRAW_LIST graphics/VC_1.vcl")`.
  - `test_display_size` → `(1280, 1024)`.
  - `test_blocks`: `START`/`END` times per trial.
  - `test_binocular_keeps_both_eyes` (Review Focus 3).
  - `test_latin1_asc_parses` (Review Focus 4): fixture with `latin1=True` writes a message with `é` in latin-1.
  - `test_events_only_has_no_samples`: `samples=False` → `rec.samples is None`.
  - `test_missing_pymovements_names_extra`: monkeypatch import to fail → `ImportError` containing `scanpath-studio[edf]`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement `read_asc`: `pymovements.gaze.from_asc(path, events=True, messages=True, encoding=enc)` with `enc` `"utf-8"` then `"latin-1"` on `UnicodeDecodeError`; take event onsets/offsets for `fixation_eyelink`; one pass over the file's lines (same encoding) collects `EFIX` average x/y (fields 5–6) keyed by `(eye, onset)`, `START`/`END` times and the `MSG` offset field (pymovements' message text keeps `-13 …`; strip and apply it). Samples come from pymovements' `samples` frame only when `samples=True`.
- [ ] **Step 4:** PASS; ruff.
- [ ] **Step 5:** Commit `Read EyeLink ASC recordings with pymovements (#N)`.

### Task 3: Trials, screens and session files

**Files:**
- Modify: `scanpath_studio/eyelink.py`
- Test: `tests/test_eyelink_screens.py`

**Interfaces:**
- Consumes: `AscRecording`.
- Produces:
  - `resolve_session_dir(source: Path, *, session_dir: Path | None, experiment_dir: Path | None) -> Path | None` — first of `session_dir`, `source.parent`, `experiment_dir / "results" / source.stem` that contains any file a `!V IAREA FILE` / `!V DRAW_LIST` message names; else `None`.
  - `parse_ias(path: Path) -> pd.DataFrame` (`offset`, `word_id`, `x`, `y`, `width`, `height`, `text`), `RECTANGLE id left top right bottom label` → `width = right-left`, `height = bottom-top`; other shapes skipped and reported.
  - `parse_vcl(path: Path) -> list[Display]`, `@dataclass Display: offset: int; background: tuple[int,int,int]; images: list[tuple[Path, int, int, int | None, int | None]]` — a new `Display` at each `CLEAR`; `IMGLOAD TOP_LEFT <path> x y [w h]` (path relative to the `.vcl`'s folder); other commands collected into `skipped: list[str]`.
  - `trial_table(rec: AscRecording) -> pd.DataFrame` (`trial_id`, `start` (the `START` time), `begin` (TRIALID time), `end`), and `trial_vars(rec) -> pd.DataFrame` (`trial_id` + one column per `!V TRIAL_VAR name value`, values as strings).
  - `screen_table(rec, trials, session: Path | None) -> tuple[pd.DataFrame, list[str]]` — rows `trial_id`, `screen_index` (1-based), `screen_id` (`f"screen_{i}"`), `begin`, `end`, `display: Display | None`, `ias: Path | None`; plus notes.
- [ ] **Step 1: Failing tests:**
  - `test_trial_bounds` and `test_aborted_trial_ends_at_next_trialid` (Review Focus 2).
  - `test_trial_vars_table`: `EXPECTED["trial_vars"]`.
  - `test_vcl_displays_and_times`: trial 1 has 2 screens; screen 2 `begin == draw_list_time - (-6620)`… use the fixture's offsets; `end` of screen 1 == `begin` of screen 2; last screen ends at the trial's `end`.
  - `test_ias_boxes`: `RECTANGLE 1 358 154 453 261 Food` → `x=358, y=154, width=95, height=107, text="Food"`.
  - `test_ias_bound_to_screen_by_time`: the `.ias` attaches to the display whose begin is within 2 ms of its corrected time; a question screen gets `ias=None`.
  - `test_resolve_session_dir_order`: explicit beats sibling beats `experiment_dir/results/<stem>`; none → `None`.
  - `test_inline_iarea_and_imgload` — `!V IAREA RECTANGLE …` and `!V IMGLOAD …` messages without files produce the same tables.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; ruff.
- [ ] **Step 5:** Commit `Split EyeLink recordings into trials and screens (#N)`.

### Task 4: One session's tables and images

**Files:**
- Modify: `scanpath_studio/eyelink.py`
- Test: `tests/test_eyelink_session.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces:
  - `compose_display(display: Display, out_dir: Path, size: tuple[int, int]) -> Path` — Pillow canvas of `size` in the background colour, each image pasted at `(x, y)`, resized to `(w, h)` when given; saved as `out_dir / f"{sha256(png bytes)[:16]}.png"` (identical screens share one file).
  - `@dataclass class SessionTables: words, fixations, trial_metadata: pd.DataFrame; raw_gaze: pd.DataFrame | None; display: tuple[int, int] | None; notes: list[str]`
  - `session_tables(source: Path, *, image_dir: Path, session_dir: Path | None = None, experiment_dir: Path | None = None, raw_gaze: bool = False, asc_dir: Path | None = None) -> SessionTables` — `.edf` goes through `convert_edf` into `asc_dir` (a temp dir when `None`); `.asc` read directly.
  - Columns. **fixations:** `participant_id` (= `source.stem`), `trial_id` (str of the TRIALID value), `text_id`, `screen_id`, `screen_index`, `fixation_id` (1-based per trial, by onset), `x`, `y`, `duration_ms`, `timestamp_ms` (`onset - start`), `eye`, `image_path`. **words:** `participant_id`, `trial_id`, `text_id`, `screen_id`, `screen_index`, `word_id`, `text`, `x`, `y`, `width`, `height`, `image_path`. `text_id` = the `.ias` path relative to the session folder without suffix (`aoi/IA_1`), else `f"trial_{trial_id}"`. **trial_metadata:** `participant_id`, `trial_id`, then the trial vars.
- [ ] **Step 1: Failing tests:**
  - `test_session_fixations_match_expected` (counts and positions per trial and screen).
  - `test_fixation_assigned_by_onset_across_screen_change`: a fixation starting 5 ms before screen 2 begins belongs to screen 1.
  - `test_fixations_outside_trials_dropped` (calibration-period `EFIX` lines).
  - `test_words_from_ias` and `test_question_screen_has_no_words`.
  - `test_image_composed_once_per_identical_display`: two trials with the same `.vcl` content → one PNG; pixel at a pasted image's origin equals that image's colour.
  - `test_missing_session_files_still_loads` (Review Focus 1): `with_session_files=False` → fixations present, `words` empty, `image_path` all missing, `notes` names `aoi/IA_1.ias` and `graphics/VC_1.vcl`.
  - `test_binocular_words_not_duplicated` (Review Focus 3).
  - `test_frames_load_in_the_app_pipeline`: `api.load_scanpath_data(t.words, t.fixations)` succeeds and `plot_scanpath(..., show_stimulus_image=True)` builds a figure for trial 1, screen `screen_1`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; ruff.
- [ ] **Step 5:** Commit `Build fixations, word boxes and stimulus images from one EyeLink session (#N)`.

### Task 5: The study folder — parallel, resumable

**Files:**
- Modify: `scanpath_studio/eyelink.py`
- Test: `tests/test_eyelink_study.py`

**Interfaces:**
- Consumes: `session_tables`.
- Produces:
  - `PARSER_VERSION: int = 1` (bump when output for the same input changes).
  - `import_eyelink(paths: str | Path | Iterable[str | Path], study_dir: str | Path, *, session_dir=None, experiment_dir=None, raw_gaze: bool = False, workers: int | None = None, rebuild: bool = False, keep_asc: bool = False, progress: Callable[[int, int, str], None] | None = None) -> StudyReport`
  - `@dataclass class StudyReport: study_dir: Path; imported: list[str]; skipped: list[str]; failed: dict[str, str]; notes: dict[str, list[str]]`
  - `load_eyelink(study_dir, *, participants: Iterable[str] | None = None) -> EyeLinkData`; `@dataclass class EyeLinkData: words, fixations, trial_metadata: pd.DataFrame; raw_gaze: pd.DataFrame | None; display: tuple[int, int] | None; notes: dict[str, list[str]]`
  - Layout: `study_dir/{manifest.json, fixations/<pid>.parquet, words/<pid>.parquet, trial_metadata/<pid>.parquet, raw_gaze/<pid>.parquet, images/<hash>.png, asc/ (keep_asc only)}`. `image_path` stored relative to `study_dir`, made absolute by `load_eyelink`. Manifest: `{"version": 1, "display": [w, h], "sessions": {pid: {"source": str, "size": int, "mtime_ns": int, "parser_version": int, "raw_gaze": bool, "status": "ok" | "failed", "error": str | None, "notes": [...]}}}`, written atomically after each session.
- `paths`: files (`.edf`/`.asc`) and folders (searched with `rglob` for `*.edf`, then `*.asc` whose stem has no `.edf`). Two sources with the same stem → `ValueError` before any work.
- Skip rule: `status == "ok"` and `(size, mtime_ns, parser_version)` equal and `raw_gaze` not newly requested; `rebuild=True` redoes all. Workers default `max(1, os.cpu_count() - 1)`; `workers=1` runs in-process (tests). Each worker returns its `SessionTables`; the parent writes files and the manifest. Different displays across sessions → `display` is `None` and a note says so.
- Progress: `progress(done, total, pid)` and `progress_mod.report(done, total, unit="sessions", detail=pid)` per finished session.
- [ ] **Step 1: Failing tests** (fixture writes 3 sessions, `workers=1` unless stated):
  - `test_import_writes_layout_and_manifest`.
  - `test_rerun_skips_unchanged`, `test_rerun_redoes_changed_and_new` (touch one ASC's mtime; add a fourth) (Review Focus 5).
  - `test_failed_session_reported_and_retried`: one corrupt ASC → `failed` has it, others `imported`; fixing it and re-running imports only it.
  - `test_duplicate_stems_refused`.
  - `test_load_eyelink_round_trip_and_participants_filter`.
  - `test_parallel_matches_serial`: `workers=2` output frames equal `workers=1`'s.
  - `test_progress_callback_counts`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; ruff.
- [ ] **Step 5:** Commit `Import a study's EyeLink sessions into a resumable study folder (#N)`.

### Task 6: API and saved dataset (with trial metadata)

**Files:**
- Modify: `scanpath_studio/api.py` (re-export `import_eyelink`, `load_eyelink`; new `add_eyelink_dataset`; `add_dataset` gains `trial_metadata=`)
- Modify: `scanpath_studio/persistence.py` (`store_dataset` writes a dataset's trial metadata table into the metadata sidecar the app restores, under this dataset's store key)
- Modify: `scanpath_studio/__init__.py` (lazy exports)
- Create: `changelog.d/<N>.added.md`
- Test: `tests/test_eyelink_api.py`

**Interfaces:**
- Consumes: `import_eyelink`, `load_eyelink`, `EyeLinkData`.
- Produces:
  - `add_dataset(..., trial_metadata: TrialMetadata | pd.DataFrame | None = None)` — a frame is loaded with `load_trial_metadata(frame, id_column="trial_id", participant_column="participant_id")`; stored so the app's `metadata.activate_dataset` restores it for this dataset (follow the sidecar format `_save_metadata` writes). With `replace=True` and no `trial_metadata`, the stored one is kept.
  - `add_eyelink_dataset(name: str, study_dir: str | Path, *, raw_gaze_participants: Iterable[str] | None = None, description: str | None = None, select: bool = True, replace: bool = False) -> str` → `load_eyelink`, then `add_dataset(name, words, fixations, raw_gaze=<only the named participants'>, canvas_size=data.display, trial_metadata=data.trial_metadata, keep_columns=["image_path", "screen_id", "screen_index"], …)`. Default description: `"EyeLink import of N sessions from <study_dir>"`.
- [ ] **Step 1: Failing tests** (`tmp_path` state dir via the env var the persistence tests use):
  - `test_add_eyelink_dataset_round_trip`: after it, `persistence` restores a dataset with the fixture's fixation count, `screen_id`s, absolute `image_path`s, and `canvas` 1280×1024.
  - `test_trial_metadata_restored_in_app`: `AppTest.from_file("streamlit_app.py")` with the state dir opens on the dataset and the trial filter offers a `TRIAL_VAR` column (e.g. `condition`).
  - `test_add_dataset_trial_metadata_replace_keeps_it`.
  - `test_gate_off_refuses`.
  - Add the new API names to whatever `tests/test_api*.py` pins the public surface.
- [ ] **Step 2:** FAIL. **Step 3:** Implement; changelog fragment `changelog.d/<N>.added.md`: `Experimental: import EyeLink EDF recordings (fixations, word boxes, stimulus images and trial variables) without Data Viewer, through api.import_eyelink and scanpath-studio import-eyelink; needs SR Research's edf2asc.` **Step 4:** PASS; run `tests/test_eyelink_*.py`, `tests/test_persistence*.py`, `tests/test_session_key_contract.py`; ruff.
- [ ] **Step 5:** Commit `Add an EyeLink study as a saved dataset, with its trial variables (#N)`.

### Task 7: CLI

**Files:**
- Modify: `scanpath_studio/cli.py` (`import-eyelink` command in `_COMMANDS` only when `eyelink_import_enabled()`; `render --eyelink-study DIR`, hidden like `--multipleye`)
- Modify: `.claude/skills/verify/feature-map.md` (a row for EyeLink import)
- Test: `tests/test_eyelink_cli.py`

**Interfaces:**
- Consumes: `import_eyelink`, `add_eyelink_dataset`, `load_eyelink`.
- Produces: `scanpath-studio import-eyelink PATH... --study-dir DIR [--session-dir DIR] [--experiment-dir DIR] [--raw-gaze] [--workers N] [--rebuild] [--keep-asc] [--add NAME [--raw-gaze-participants P ...]]`. Prints `[n/N] <pid> ok|skipped|failed: <reason>`, then a summary line `Imported A, skipped S, failed F → DIR`; exit 1 when any failed. `render --eyelink-study DIR --participant P --trial T [--screen S]` renders from `load_eyelink`.
- [ ] **Step 1: Failing tests:** `test_import_eyelink_cli_summary_and_exit_code`, `test_import_eyelink_cli_add`, `test_render_eyelink_study_writes_png_or_html`, `test_hidden_when_gate_off` (not in `--help`, command refused with the gate message).
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; ruff; `tests/test_cli*.py`.
- [ ] **Step 5:** Commit `Add scanpath-studio import-eyelink (#N)`.

### Task 8: Raw gaze, opt-in

**Files:**
- Modify: `scanpath_studio/eyelink.py`
- Test: `tests/test_eyelink_raw_gaze.py`

**Interfaces:**
- Consumes: `read_asc(samples=True)`, `session_tables(raw_gaze=True)`, `import_eyelink(raw_gaze=True)`.
- Produces: `raw_gaze` frame columns `participant_id`, `trial_id`, `screen_id`, `screen_index`, `x`, `y`, `timestamp_ms`, `pupil_area` or `pupil_diameter` (from the ASC's `PUPIL` line), `eye`; only samples inside a screen span; pupil missing where x or y is missing (`update_sample_data.without_lost_pupil`); `raw_gaze/<pid>.parquet` sorted by `trial_id`, `timestamp_ms`, written with one row group per trial.
- [ ] **Step 1: Failing tests:** `test_samples_on_fixation_clock`, `test_lost_eye_pupil_missing`, `test_samples_between_screens_dropped`, `test_raw_gaze_parquet_row_groups_per_trial`, `test_rerun_with_raw_gaze_redoes_sessions_without_it`, `test_add_eyelink_dataset_raw_gaze_participants_only`.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS; ruff.
- [ ] **Step 5:** Commit `Import EyeLink raw gaze on request (#N)`.

### Task 9: OneStop checks and verification

**Files:**
- Create: `scripts/eyelink_onestop_check.py` (maintainer script, not run in CI)
- Modify: `docs/superpowers/specs/2026-11-25-edf-import-design.md` (a *Results* section)

- [ ] **Step 1:** Script compares `import_eyelink` output for one session with Data Viewer's reports for the same session (the OneStop Full per-part fixation and IA reports that `update_sample_data --source-dir` reads): per trial, fixation count, onset and position differences (max/median), and word-box equality; prints a table. Run it on `l42_2070.asc` with `--experiment-dir "/Users/shubi/Data/OneStop Full Experiment Folders Backup 17122024/ose_3p_l1_l60_tower_st_mit_l1_latest_widthfix"`. Expected: word boxes equal; fixation differences reported, not tuned.
- [ ] **Step 2:** Full run on the 360 ASCs (`--workers` default): record wall time, peak import memory, study folder size; re-run and confirm everything is skipped. Then `add_eyelink_dataset` and record the app's memory and time to open and draw one trial. If fixations + words do not fit comfortably, write that down as the next round's work (on-demand loading), do not build it here.
- [ ] **Step 3:** Raw gaze timing on 3 sessions with `--raw-gaze`.
- [ ] **Step 4:** `/verify`: boot the app on the imported dataset, screenshot a OneStop paragraph with stimulus, boxes and fixations; render it through the CLI and the API.
- [ ] **Step 5:** Write the numbers into the spec's *Results*; run `diff-reviewer` (and `perf-reviewer`, since it loads large data) over the branch; fix findings; commit `Record the EyeLink import's OneStop results (#N)` with `Verified: harness, apptest, browser`; open the PR; set the issue to *Review*.
