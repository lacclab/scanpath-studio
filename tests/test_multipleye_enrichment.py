"""MultiplEYE side-data enrichment, end to end over a synthetic corpus tree (ENG-3).

Beyond the fixation / AOI tables, ``datasets.multipleye_raw_frames`` enriches the
loaded frames from four kinds of side data, each gated on its file or folder
existing:

* ``participant_data.csv`` → ``pp_*`` reader metadata, merged onto the fixations
  by ``(int(participant), session)``;
* ``stimuli_*/multipleye_comprehension_questions_*.xlsx`` → a per-stimulus
  ``comprehension_questions`` JSON column on both frames;
* ``reading_measures/`` → the corpus' pre-aggregated measures as ``IA_*`` columns
  on **per-reader** word boxes, joined by ``(participant, stimulus, page,
  word_idx)``;
* ``stimuli_*/stimuli_images_*/`` → a per-``(stimulus, page)`` ``image_path`` plus
  the centered-image origin.

Each test builds a MultiplEYE-shaped tree in ``tmp_path`` holding only the files
the enrichment reads. The tree is deliberately asymmetric — reader B reads one
stimulus more than reader A, and that extra stimulus ships no reading measures
and no questions — so a merge that lands on the wrong rows, or multiplies them,
shows up as a wrong value rather than a wrong column list.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import datasets

# --- The synthetic corpus ----------------------------------------------------

READER_A = "001_ZH_CH_1_ET1"  # reads Lit_Demo_1 (2 pages)
READER_B = "014_ZH_CH_1_ET2"  # reads Lit_Demo_1 (2 pages) + Arg_Other_2 (1 page)
LIT = "Lit_Demo_1"
ARG = "Arg_Other_2"
# DATA-24: a trial is one *reading of a stimulus*; its pages are screens inside
# it. Each constant below is the (trial_id, screen_id) pair that names one page.
LIT_P1 = (LIT, "page_1")
LIT_P2 = (LIT, "page_2")
ARG_P1 = (ARG, "page_1")

# The stimulus image (1310x991) was shown centered on a 1920x1080 monitor, so the
# loader shifts the image-relative AOI / fixation coordinates by (1920-1310)/2 and
# (1080-991)/2 onto their true on-screen position. Spelled out rather than
# imported from datasets.py so the expectation is independent of the code.
OFF_X, OFF_Y = 305.0, 44.5

_AOI_COLUMNS = [
    "char_idx",
    "char",
    "top_left_x",
    "top_left_y",
    "width",
    "height",
    "char_idx_in_line",
    "line_idx",
    "page",
    "word_idx",
    "word_idx_in_line",
    "word",
]

# A valid 1x1 PNG — the app reads the stimulus image's pixel size from the PNG
# header, so the bytes have to parse even though nothing renders them here.
_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)

_HAS_OPENPYXL = importlib.util.find_spec("openpyxl") is not None
requires_openpyxl = pytest.mark.skipif(
    not _HAS_OPENPYXL, reason="openpyxl is needed to write a real .xlsx workbook"
)


def _char_aoi_rows(page: str, word_idx: int, word: str, x0: int) -> list[dict]:
    """Two character-AOI rows (20x30 px each) for one two-letter word at ``x0``."""
    return [
        {
            "char_idx": word_idx * 2 + i,
            "char": word[i],
            "top_left_x": x0 + i * 20,
            "top_left_y": 50,
            "width": 20,
            "height": 30,
            "char_idx_in_line": word_idx * 2 + i,
            "line_idx": 0,
            "page": page,
            "word_idx": word_idx,
            "word_idx_in_line": word_idx,
            "word": word,
        }
        for i in range(2)
    ]


def _scanpath_row(onset: int, duration: int, x: int, y: int, page: str, word: int):
    return {
        "onset": onset,
        "duration": duration,
        "name": "fixation",
        "location_x": x,
        "location_y": y,
        "page": page,
        "word_idx": word,
    }


# Three fixations per Lit page-pair: two on page_1 (words 0 and 1), one on page_2.
_LIT_SCANPATH = [
    _scanpath_row(1000, 200, 90, 65, "page_1", 0),
    _scanpath_row(1300, 180, 150, 65, "page_1", 1),
    _scanpath_row(2000, 210, 90, 65, "page_2", 0),
]
_ARG_SCANPATH = [_scanpath_row(500, 150, 90, 65, "page_1", 0)]

# Per-reader reading measures for Lit_Demo (one row per page x word). word_idx
# restarts per page, so page_1 word 0 and page_2 word 0 carry different values —
# a page-blind join would silently pick the wrong one.
_READING_MEASURES = {
    READER_A: {
        "page": ["page_1", "page_1", "page_2", "page_2"],
        "word_idx": [0, 1, 0, 1],
        "FFD": [210, 180, 240, 0],
        "FPRT": [210, 180, 240, 0],
        "TFT": [430, 180, 240, 0],
        "TFC": [2, 1, 1, 0],
        "RPD_inc": [430, 180, 240, 0],
        "TRC_in": [0, 2, 0, 0],
        "TRC_out": [1, 0, 0, 0],
        "RR": [0, 1, 0, 0],  # re-reading: deliberately NOT mapped to a regression
        "skipped": [0, 0, 0, 1],
    },
    READER_B: {
        "page": ["page_1", "page_1", "page_2", "page_2"],
        "word_idx": [0, 1, 0, 1],
        "FFD": [111, 112, 113, 114],
        "FPRT": [111, 112, 113, 114],
        "TFT": [111, 112, 113, 114],
        "TFC": [1, 1, 1, 1],
        "RPD_inc": [111, 112, 113, 114],
        "TRC_in": [0, 0, 0, 0],
        "TRC_out": [0, 0, 0, 0],
        "RR": [0, 0, 0, 0],
        "skipped": [0, 0, 0, 0],
    },
}

# The comprehension workbook: only Lit_Demo_1 has questions, Arg_Other_2 has none.
# Rows are stored out of order — the loader sorts by (condition_no, question_no).
_QUESTIONS_FRAME = pd.DataFrame(
    {
        "stimulus_name": ["Lit_Demo", "Lit_Demo"],
        "stimulus_id": [1, 1],
        "condition_no": [1, 1],
        "question_no": [2, 1],
        "question": ["Who?", "Why?"],
        "target": ["The alchemist", "Because"],
        "distractor_a": ["The boy", "Despite"],
        "distractor_b": ["nan", "Although"],  # a literal 'nan' is dropped
        "condition_name": ["local", "local"],
    }
)
_QUESTIONS_NAME = "multipleye_comprehension_questions_demo.xlsx"


def build_multipleye_tree(
    root: Path,
    *,
    reader_metadata: bool = True,
    reading_measures: bool = True,
    images: bool = True,
) -> Path:
    """Write a minimal MultiplEYE session set under ``root``; return ``root``.

    Only the files the loader + its enrichment actually read are written. Each
    side-data kind can be left out to exercise the "file absent" path. The
    comprehension workbook is installed separately (:func:`install_questions`),
    since writing a real ``.xlsx`` needs an optional dependency.
    """
    aoi_dir = root / "stimuli_Demo" / "aoi_stimuli_demo"
    aoi_dir.mkdir(parents=True)
    lit_chars = (
        _char_aoi_rows("page_1", 0, "AA", 80)
        + _char_aoi_rows("page_1", 1, "BB", 140)
        # page_2 reuses page_1's coordinates, as the real corpus does.
        + _char_aoi_rows("page_2", 0, "CC", 80)
        + _char_aoi_rows("page_2", 1, "DD", 140)
    )
    pd.DataFrame(lit_chars, columns=_AOI_COLUMNS).to_csv(
        aoi_dir / "lit_demo_1_aoi.csv", index=False
    )
    pd.DataFrame(_char_aoi_rows("page_1", 0, "EE", 80), columns=_AOI_COLUMNS).to_csv(
        aoi_dir / "arg_other_2_aoi.csv", index=False
    )

    for reader, stimuli in ((READER_A, [LIT]), (READER_B, [LIT, ARG])):
        session_dir = root / "scanpaths" / reader
        session_dir.mkdir(parents=True)
        for stimulus in stimuli:
            rows = _LIT_SCANPATH if stimulus == LIT else _ARG_SCANPATH
            trial_num = stimuli.index(stimulus) + 1
            pd.DataFrame(rows).to_csv(
                session_dir / f"{reader}_trial_{trial_num}_{stimulus}_scanpath.csv",
                index=False,
            )

    if reader_metadata:
        write_participant_data(root)
    if reading_measures:
        for reader, measures in _READING_MEASURES.items():
            write_reading_measures(root, reader, measures)
    if images:
        write_stimulus_images(root)
    return root


def write_participant_data(root: Path, frame: pd.DataFrame | None = None) -> Path:
    """``participant_data.csv``: integer pids, one duplicated row, one stranger."""
    if frame is None:
        frame = pd.DataFrame(
            {
                # The bare pid is an integer here but zero-padded text in the
                # filenames ("001"), and reader A's row is duplicated.
                "participant_id": [1, 1, 14, 77],
                "session": ["ET1", "ET1", "ET2", "ET1"],
                "age": [25, 25, 31, 40],
                "gender": ["F", "F", "M", "X"],
                "native_language_1": ["Mandarin", "Mandarin", "Cantonese", "German"],
                "years_education": [16, 16, 18, 12],
                "level_education": ["BA", "BA", "MA", "HS"],
                "unused_column": ["a", "a", "b", "c"],
            }
        )
    path = root / "participant_data.csv"
    frame.to_csv(path, index=False)
    return path


def install_questions(
    root: Path, monkeypatch, frame: pd.DataFrame | None = None
) -> Path:
    """Put the comprehension workbook where the loader globs for it.

    With ``openpyxl`` installed the frame is written as a real ``.xlsx``. Without
    it those bytes can't be produced, so a placeholder is written at the same
    path and ``pd.read_excel`` is stubbed to return the frame: what is under test
    is the per-stimulus join + stamping, not pandas' Excel parsing, and that
    coverage must not hinge on an optional dependency being present in CI.
    :func:`test_real_workbook_round_trips_through_the_reader` covers the actual
    file format wherever openpyxl *is* installed.
    """
    frame = _QUESTIONS_FRAME.copy() if frame is None else frame
    path = root / "stimuli_Demo" / _QUESTIONS_NAME
    if _HAS_OPENPYXL:
        frame.to_excel(path, index=False)
    else:
        path.write_bytes(b"")
        monkeypatch.setattr(pd, "read_excel", lambda *a, **k: frame.copy())
    return path


def write_reading_measures(root: Path, reader: str, measures) -> Path:
    """One ``reading_measures/`` file. The stimulus in the name carries no id."""
    session_dir = root / "reading_measures" / reader
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{reader}_trial_1_Lit_Demo_reading_measures.csv"
    pd.DataFrame(measures).to_csv(path, index=False)
    return path


def write_stimulus_images(root: Path) -> Path:
    """Per-``(stimulus, page)`` page images, named as the loader expects."""
    image_dir = root / "stimuli_Demo" / "stimuli_images_zh_ch_1"
    image_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "lit_demo_id1_page_1_zh.png",
        "lit_demo_id1_page_2_zh.png",
        "arg_other_id2_page_1_zh.png",
    ):
        (image_dir / name).write_bytes(_PNG_1X1)
    return image_dir


@pytest.fixture
def full_tree(tmp_path, monkeypatch) -> Path:
    """A tree with every side-data kind present."""
    root = build_multipleye_tree(tmp_path)
    install_questions(root, monkeypatch)
    return root


@pytest.fixture
def bare_tree(tmp_path) -> Path:
    """Fixations + AOI boxes only — no side data at all."""
    return build_multipleye_tree(
        tmp_path, reader_metadata=False, reading_measures=False, images=False
    )


# --- Assertion helpers -------------------------------------------------------


def _screen_rows(frame: pd.DataFrame, reader: str, screen: tuple) -> pd.DataFrame:
    """Every row of one ``(reader, trial, screen)`` in a normalized frame."""
    trial, screen_id = screen
    return frame[
        (frame["participant_id"] == reader)
        & (frame["trial_id"] == trial)
        & (frame["screen_id"] == screen_id)
    ]


def _word_row(words: pd.DataFrame, reader: str, screen: tuple, word_id: int):
    """The single word row for ``(reader, screen, word_id)`` — a merge that
    multiplied rows fails here rather than silently averaging later."""
    rows = _screen_rows(words, reader, screen)
    rows = rows[rows["word_id"] == word_id]
    assert len(rows) == 1, f"{reader}/{screen}/word {word_id}: {len(rows)} rows, want 1"
    return rows.iloc[0]


def _reader_value(frame: pd.DataFrame, reader: str, column: str):
    """The one value ``column`` takes across all of ``reader``'s rows."""
    values = set(frame[frame["participant_id"] == reader][column])
    assert len(values) == 1, f"{reader}/{column}: {values}"
    return values.pop()


def _assert_canonical_intact(words: pd.DataFrame, fixations: pd.DataFrame) -> None:
    """The canonical geometry / identity columns, whatever side data was merged.

    Word boxes: two 20px characters at image x=80..120, y=50..80, shifted by the
    centering offset. Fixations: reader A's page_1 pair and page_2 single.
    """
    assert set(words["trial_id"]) == {LIT, ARG}
    assert set(zip(words["trial_id"], words["screen_id"])) == {LIT_P1, LIT_P2, ARG_P1}
    assert set(fixations["participant_id"]) == {READER_A, READER_B}

    aa = _word_row(words, READER_A, LIT_P1, 0)
    assert aa["text"] == "AA"
    assert (aa["x"], aa["width"]) == (80 + OFF_X, 40.0)
    assert (aa["y"], aa["height"]) == (50 + OFF_Y, 30.0)
    bb = _word_row(words, READER_A, LIT_P1, 1)
    assert bb["text"] == "BB" and bb["x"] == 140 + OFF_X
    # page_2 reuses page_1's coordinates but is its own screen with its own words.
    cc = _word_row(words, READER_A, LIT_P2, 0)
    assert cc["text"] == "CC" and cc["x"] == 80 + OFF_X
    # Reader B alone read Arg_Other_2 — reader A must not inherit its box.
    ee = _word_row(words, READER_B, ARG_P1, 0)
    assert ee["text"] == "EE"
    assert words[(words["participant_id"] == READER_A)]["trial_id"].eq(LIT).all()

    # 3 fixations per reader on Lit_Demo_1, plus reader B's single Arg fixation.
    assert len(fixations) == 7
    first = _screen_rows(fixations, READER_A, LIT_P1).sort_values("timestamp_ms")
    assert list(first["x"]) == [90 + OFF_X, 150 + OFF_X]
    assert list(first["y"]) == [65 + OFF_Y, 65 + OFF_Y]
    assert list(first["duration_ms"]) == [200, 180]
    assert list(first["timestamp_ms"]) == [1000, 1300]
    assert list(first["word_id"]) == [0, 1]


# --- Reader metadata (participant_data.csv) ----------------------------------


def test_reader_metadata_merges_by_int_pid_and_session(full_tree):
    """``participant_data`` joins on the int-coerced pid + session, not the text."""
    words, fixations = datasets.load_multipleye(full_tree)
    _assert_canonical_intact(words, fixations)

    # The filename pid is zero-padded text ("001"); participant_data stores 1.
    assert _reader_value(fixations, READER_A, "pp_age") == 25
    assert _reader_value(fixations, READER_B, "pp_age") == 31
    assert _reader_value(fixations, READER_A, "pp_gender") == "F"
    assert _reader_value(fixations, READER_B, "pp_native_language") == "Cantonese"
    assert _reader_value(fixations, READER_A, "pp_years_education") == 16
    assert _reader_value(fixations, READER_B, "pp_education_level") == "MA"

    # Reader 77 (ET1) is in participant_data but read nothing here, and reader A's
    # row is duplicated there — neither adds a fixation row (len == 7 above).
    assert 40 not in set(fixations["pp_age"])
    # Only the namespaced columns are carried; the join keys aren't leaked.
    assert "unused_column" not in fixations.columns
    assert "session" in fixations.columns and "age" not in fixations.columns
    # The metadata rides on the fixations only — the word boxes stay geometry +
    # reading measures (the chips and grouping facets read the fixation frame).
    assert not [c for c in words.columns if c.startswith("pp_")]


def test_reader_metadata_without_session_column_is_skipped(tmp_path):
    """A participant_data table missing a join key adds no columns and no rows."""
    root = build_multipleye_tree(tmp_path)
    write_participant_data(
        root, pd.DataFrame({"participant_id": [1, 14], "age": [25, 31]})
    )
    words, fixations = datasets.load_multipleye(root)

    assert not [c for c in fixations.columns if c.startswith("pp_")]
    _assert_canonical_intact(words, fixations)


def test_partial_reader_metadata_carries_only_the_columns_present(tmp_path):
    """A participant_data table with a subset of the fields adds only those."""
    root = build_multipleye_tree(tmp_path)
    write_participant_data(
        root,
        pd.DataFrame(
            {  # no gender / native_language_1 / education columns at all
                "participant_id": [1, 14],
                "session": ["ET1", "ET2"],
                "age": [25, 31],
            }
        ),
    )
    words, fixations = datasets.load_multipleye(root)
    _assert_canonical_intact(words, fixations)

    assert [c for c in fixations.columns if c.startswith("pp_")] == ["pp_age"]
    assert _reader_value(fixations, READER_A, "pp_age") == 25
    assert _reader_value(fixations, READER_B, "pp_age") == 31


def test_missing_participant_data_leaves_no_reader_columns(tmp_path):
    """No participant_data.csv → the pp_* columns are simply absent."""
    root = build_multipleye_tree(tmp_path, reader_metadata=False)
    words, fixations = datasets.load_multipleye(root)

    assert "pp_age" not in fixations.columns
    _assert_canonical_intact(words, fixations)


# --- Comprehension questions (the .xlsx workbook) ----------------------------


def test_questions_join_by_stimulus_not_by_trial(full_tree):
    """The questions JSON lands on every row of its stimulus — and only there."""
    words, fixations = datasets.load_multipleye(full_tree)
    _assert_canonical_intact(words, fixations)

    lit_json = set(
        words[words["text_id"] == LIT]["comprehension_questions"].dropna().unique()
    )
    assert len(lit_json) == 1  # one JSON payload, shared by both pages + readers
    items = json.loads(lit_json.pop())
    # Sorted by (condition_no, question_no) regardless of workbook row order.
    assert [q["question_no"] for q in items] == [1, 2]
    assert items[0]["question"] == "Why?"
    assert items[0]["target"] == "Because"
    assert items[0]["distractors"] == ["Despite", "Although"]
    assert items[0]["condition"] == "local"
    # A literal 'nan' distractor is dropped, not carried through as text.
    assert items[1]["question"] == "Who?"
    assert items[1]["distractors"] == ["The boy"]

    # Arg_Other_2 ships no questions → NaN, not another stimulus' questions.
    arg = words[words["text_id"] == ARG]["comprehension_questions"]
    assert arg.isna().all()
    # The same payload rides along on the fixations (the panel reads either frame).
    fix_lit = fixations[fixations["text_id"] == LIT]["comprehension_questions"]
    assert fix_lit.notna().all()
    assert (
        fixations[fixations["text_id"] == ARG]["comprehension_questions"].isna().all()
    )


@requires_openpyxl
def test_real_workbook_round_trips_through_the_reader(tmp_path):
    """A genuinely written .xlsx yields the same map the stubbed reader does."""
    root = build_multipleye_tree(tmp_path)
    path = root / "stimuli_Demo" / _QUESTIONS_NAME
    _QUESTIONS_FRAME.to_excel(path, index=False)

    assert datasets._multipleye_questions_path(root) == path
    qmap = datasets._multipleye_questions_by_stimulus(path)
    assert set(qmap) == {LIT}  # "Lit_Demo" + "_" + stimulus_id 1
    items = json.loads(qmap[LIT])
    assert [q["question"] for q in items] == ["Why?", "Who?"]
    assert [q["target"] for q in items] == ["Because", "The alchemist"]


def test_questions_workbook_without_join_keys_is_skipped(tmp_path, monkeypatch):
    """A workbook missing ``stimulus_id`` adds no column and breaks nothing."""
    root = build_multipleye_tree(tmp_path)
    install_questions(
        root,
        monkeypatch,
        pd.DataFrame({"stimulus_name": ["Lit_Demo"], "question": ["Why?"]}),
    )
    words, fixations = datasets.load_multipleye(root)

    assert "comprehension_questions" not in words.columns
    assert "comprehension_questions" not in fixations.columns
    _assert_canonical_intact(words, fixations)


def test_questions_skipped_when_the_excel_reader_is_missing(full_tree, monkeypatch):
    """Reading the workbook needs openpyxl; without it the load still succeeds."""

    def _no_openpyxl(*args, **kwargs):
        raise ImportError("Missing optional dependency 'openpyxl'")

    monkeypatch.setattr(pd, "read_excel", _no_openpyxl)
    words, fixations = datasets.load_multipleye(full_tree)

    assert "comprehension_questions" not in words.columns
    _assert_canonical_intact(words, fixations)


def test_missing_questions_workbook_leaves_no_question_column(bare_tree):
    words, fixations = datasets.load_multipleye(bare_tree)

    assert datasets._multipleye_questions_path(bare_tree) is None
    assert "comprehension_questions" not in words.columns
    assert "comprehension_questions" not in fixations.columns
    _assert_canonical_intact(words, fixations)


# --- Pre-computed reading measures (reading_measures/) -----------------------


def test_reading_measures_attach_per_reader_page_and_word(full_tree):
    """Each reader's measures land on that reader's boxes, keyed by page + word."""
    words, fixations = datasets.load_multipleye(full_tree)
    _assert_canonical_intact(words, fixations)

    # 4 Lit boxes for reader A + 4 Lit and 1 Arg box for reader B. The stimulus
    # boxes are replicated per reader, not multiplied by the measures rows.
    assert len(words) == 9
    # word_id is unique within a SCREEN (it restarts on the next page), which is
    # exactly the identity multipart.grouping_columns keys measures on.
    key = ["participant_id", "trial_id", "screen_id", "word_id"]
    assert words.groupby(key).size().max() == 1

    # FFD → IA_FIRST_FIXATION_DURATION → first_fixation_ms, per reader.
    assert _word_row(words, READER_A, LIT_P1, 0)["first_fixation_ms"] == 210
    assert _word_row(words, READER_B, LIT_P1, 0)["first_fixation_ms"] == 111
    # word_idx restarts per page: page_2 word 0 keeps page_2's own value.
    assert _word_row(words, READER_A, LIT_P2, 0)["first_fixation_ms"] == 240
    assert _word_row(words, READER_B, LIT_P2, 1)["first_fixation_ms"] == 114

    a_p1_w0 = _word_row(words, READER_A, LIT_P1, 0)
    assert a_p1_w0["total_fixation_duration_ms"] == 430  # TFT → IA_DWELL_TIME
    assert a_p1_w0["first_pass_gaze_duration_ms"] == 210  # FPRT
    assert a_p1_w0["regression_path_duration_ms"] == 430  # RPD_inc
    assert a_p1_w0["n_fixations"] == 2  # TFC
    # Regression flags are derived from the counts (TRC_out=1 → out, in=0).
    assert a_p1_w0["regression_out_count"] == 1
    assert bool(a_p1_w0["regression_out_flag"]) is True
    assert bool(a_p1_w0["regression_in_flag"]) is False
    a_p1_w1 = _word_row(words, READER_A, LIT_P1, 1)
    assert a_p1_w1["regression_in_count"] == 2
    assert bool(a_p1_w1["regression_in_flag"]) is True
    # skipped → IA_SKIP → skip_flag, on that word only.
    assert bool(_word_row(words, READER_A, LIT_P2, 1)["skip_flag"]) is True
    assert bool(_word_row(words, READER_A, LIT_P2, 0)["skip_flag"]) is False

    # Arg_Other_2 ships no reading-measures file: the box survives, unmeasured.
    assert pd.isna(_word_row(words, READER_B, ARG_P1, 0)["first_fixation_ms"])


def test_reading_measures_rr_column_is_not_a_regression_flag(full_tree):
    """RR is re-reading, not a regression — it must not reach the word frame."""
    raw_words, _ = datasets.multipleye_raw_frames(full_tree)

    assert "RR" not in raw_words.columns
    assert "RR" not in datasets.MULTIPLEYE_RM_MAP
    # Reader A's RR=1 word is not flagged as a regression in/out by the mapping.
    row = raw_words[
        (raw_words["participant_id"] == READER_A)
        & (raw_words["page"] == "page_1")
        & (raw_words["word_idx"] == 1)
    ].iloc[0]
    assert row["IA_REGRESSION_OUT"] == 0
    # That word did have regressions *in* (TRC_in=2) — the flags aren't constant.
    assert row["IA_REGRESSION_IN"] == 1


def test_partial_reading_measures_only_map_the_columns_present(tmp_path):
    """A file with a subset of measures adds only those; strays merge nowhere."""
    root = build_multipleye_tree(tmp_path, reading_measures=False)
    write_reading_measures(
        root,
        READER_B,
        {
            "page": ["page_1", "page_1"],
            "word_idx": [0, 99],  # word 99 exists in no box → left-merges nowhere
            "FFD": [777, 888],
        },
    )
    words, fixations = datasets.load_multipleye(root)
    _assert_canonical_intact(words, fixations)

    assert len(words) == 9  # the stray word_idx=99 row added nothing
    assert _word_row(words, READER_B, LIT_P1, 0)["first_fixation_ms"] == 777
    assert pd.isna(_word_row(words, READER_B, LIT_P2, 0)["first_fixation_ms"])
    # No TFT/TFC column in the file → no such canonical column at all.
    assert "total_fixation_duration_ms" not in words.columns
    assert "n_fixations" not in words.columns
    # Reader A shipped no file: their boxes are present and unmeasured.
    assert pd.isna(_word_row(words, READER_A, LIT_P1, 0)["first_fixation_ms"])


def test_reading_measures_file_without_word_idx_is_skipped(tmp_path):
    """An unjoinable measures file is dropped, not merged on page alone."""
    root = build_multipleye_tree(tmp_path, reading_measures=False)
    write_reading_measures(
        root, READER_A, {"page": ["page_1", "page_2"], "FFD": [42, 43]}
    )
    words, fixations = datasets.load_multipleye(root)
    _assert_canonical_intact(words, fixations)

    assert len(words) == 9
    assert "first_fixation_ms" not in words.columns


def test_word_boxes_stay_stimulus_level_without_reading_measures(bare_tree):
    """No reading_measures/ → stimulus-level boxes, broadcast across readers."""
    raw_words, _ = datasets.multipleye_raw_frames(bare_tree)
    assert "participant_id" not in raw_words.columns  # no per-reader replication
    assert not [c for c in raw_words.columns if c.startswith("IA_")]
    assert len(raw_words) == 5  # 4 Lit boxes + 1 Arg box, once each

    words, fixations = datasets.load_multipleye(bare_tree)
    # normalize_words broadcasts the participant-less boxes onto the readers who
    # read each trial — same 9 rows as the per-reader path, no measures.
    assert len(words) == 9
    assert "first_fixation_ms" not in words.columns
    _assert_canonical_intact(words, fixations)


def test_attach_reading_measures_off_keeps_boxes_stimulus_level(full_tree):
    """The opt-out skips the per-reader replication but keeps the other side data."""
    raw_words, raw_fixations = datasets.multipleye_raw_frames(
        full_tree, attach_reading_measures=False
    )

    assert len(raw_words) == 5
    assert "participant_id" not in raw_words.columns
    assert not [c for c in raw_words.columns if c.startswith("IA_")]
    # Images + questions still enrich the stimulus-level boxes, keyed the same way.
    lit_p2 = raw_words[(raw_words["stimulus"] == LIT) & (raw_words["page"] == "page_2")]
    assert set(lit_p2["image_path"]) == {
        str(
            full_tree / "stimuli_Demo/stimuli_images_zh_ch_1/lit_demo_id1_page_2_zh.png"
        )
    }
    lit_questions = json.loads(lit_p2["comprehension_questions"].iloc[0])
    assert [q["target"] for q in lit_questions] == ["Because", "The alchemist"]
    assert (
        raw_words[raw_words["stimulus"] == ARG]["comprehension_questions"].isna().all()
    )
    assert set(raw_fixations["pp_age"]) == {25, 31}


# --- Stimulus page images ----------------------------------------------------


def test_stimulus_image_path_resolves_per_stimulus_and_page(full_tree):
    """Each trial's image path points at that page's file, at the centered origin."""
    words, fixations = datasets.load_multipleye(full_tree)
    image_dir = full_tree / "stimuli_Demo" / "stimuli_images_zh_ch_1"

    for (trial, screen), filename in (
        (LIT_P1, "lit_demo_id1_page_1_zh.png"),
        (LIT_P2, "lit_demo_id1_page_2_zh.png"),
        (ARG_P1, "arg_other_id2_page_1_zh.png"),
    ):
        rows = words[(words["trial_id"] == trial) & (words["screen_id"] == screen)]
        paths = set(rows["image_path"])
        assert paths == {str(image_dir / filename)}
        assert os.path.exists(paths.pop())

    # The origin matches the offset applied to the boxes/fixations, so the image
    # lines up with the data underneath it.
    assert set(words["image_x"]) == {OFF_X}
    assert set(fixations["image_y"]) == {OFF_Y}


def test_app_resolves_the_trial_image_from_the_loaded_frames(full_tree):
    """The app's per-trial lookup finds a readable image for a trial."""
    from scanpath_studio.plots import _png_pixel_size
    from scanpath_studio.tabs import _first_str

    words, _ = datasets.load_multipleye(full_tree)
    path = _first_str(_screen_rows(words, READER_A, LIT_P2), "image_path")

    assert path is not None and path.endswith("lit_demo_id1_page_2_zh.png")
    assert _png_pixel_size(path) == (1, 1)


def test_missing_image_folder_yields_no_image_columns(bare_tree):
    """No stimuli_images_* folder → no image columns, and the load still works."""
    words, fixations = datasets.load_multipleye(bare_tree)

    assert datasets._multipleye_image_dir(bare_tree) is None
    for frame in (words, fixations):
        assert "image_path" not in frame.columns
        assert "image_x" not in frame.columns
    _assert_canonical_intact(words, fixations)


def test_image_path_for_a_page_with_no_file_draws_nothing(full_tree):
    """A stamped path whose file is gone resolves to no image layer, not a crash."""
    from scanpath_studio.plots import _image_to_data_uri
    from scanpath_studio.tabs import _first_str

    (
        full_tree
        / "stimuli_Demo"
        / "stimuli_images_zh_ch_1"
        / "arg_other_id2_page_1_zh.png"
    ).unlink()
    words, _ = datasets.load_multipleye(full_tree)
    path = _first_str(_screen_rows(words, READER_B, ARG_P1), "image_path")

    assert path is not None and not os.path.exists(path)
    assert _image_to_data_uri(path) is None


# --- Narrowed loads ----------------------------------------------------------


def test_side_data_is_scoped_to_the_narrowed_load(full_tree):
    """A ``stimuli=`` narrowed load keeps that stimulus' side data and no other's."""
    words, fixations = datasets.load_multipleye(full_tree, stimuli=[ARG])

    assert set(zip(words["trial_id"], words["screen_id"])) == {ARG_P1}
    assert set(fixations["participant_id"]) == {READER_B}  # only B read Arg_Other_2
    assert len(fixations) == 1
    assert _word_row(words, READER_B, ARG_P1, 0)["text"] == "EE"

    # participant_data is read whole, so the reader's metadata still merges.
    assert _reader_value(fixations, READER_B, "pp_age") == 31
    # Lit_Demo's reading-measures files resolve to a stimulus outside this load,
    # so they are skipped entirely — no IA_* column is created at all.
    assert "first_fixation_ms" not in words.columns
    # Arg_Other_2 has no questions: the column exists (Lit's payload was parsed)
    # but stays empty here rather than picking up another stimulus' questions.
    assert words["comprehension_questions"].isna().all()
    assert set(words["image_path"]) == {
        str(
            full_tree
            / "stimuli_Demo/stimuli_images_zh_ch_1/arg_other_id2_page_1_zh.png"
        )
    }


# --- Known gaps in the loader (documented, not yet fixed) --------------------
# These pin the behaviour the enrichment *should* have. They xfail today; when
# the guard lands in datasets.py they xpass — delete the marker at that point.


@pytest.mark.xfail(
    strict=False,
    reason="_multipleye_words_per_reader merges the reading measures with no "
    "uniqueness guard, so two reading_measures files whose id-stripped stimulus "
    "resolves to the same stimulus (a repeated reading, or a PRACTICE trial of a "
    "stimulus also read for real) duplicate that reader's word boxes. Fix: "
    "de-duplicate the RM frame on (participant_id, stimulus, page, word_idx).",
)
def test_duplicate_reading_measures_files_do_not_multiply_word_rows(tmp_path):
    root = build_multipleye_tree(tmp_path)
    # A second file for the SAME stimulus — the file-name id strip maps
    # "Lit_Demo" to Lit_Demo_1 for both.
    session_dir = root / "reading_measures" / READER_A
    pd.DataFrame(dict(_READING_MEASURES[READER_A], FFD=[999] * 4)).to_csv(
        session_dir / f"{READER_A}_trial_7_Lit_Demo_reading_measures.csv", index=False
    )
    words, fixations = datasets.load_multipleye(root)

    assert len(words) == 9  # 13 today: reader A's 4 Lit boxes are doubled
    _assert_canonical_intact(words, fixations)


@pytest.mark.xfail(
    strict=False,
    reason="_multipleye_participant_meta calls pd.read_csv unguarded, so an "
    "empty / truncated participant_data.csv raises EmptyDataError out of "
    "multipleye_raw_frames instead of skipping an optional enrichment. Fix: "
    "catch (pd.errors.ParserError, pd.errors.EmptyDataError, OSError, "
    "UnicodeDecodeError) and return None.",
)
def test_unreadable_participant_data_degrades_to_no_metadata(tmp_path):
    root = build_multipleye_tree(tmp_path)
    (root / "participant_data.csv").write_text("")  # truncated export
    words, fixations = datasets.load_multipleye(root)

    assert not [c for c in fixations.columns if c.startswith("pp_")]
    _assert_canonical_intact(words, fixations)


@pytest.mark.xfail(
    strict=False,
    reason="_multipleye_questions_by_stimulus catches only ImportError around "
    "pd.read_excel, so an unreadable workbook raises ValueError out of "
    "multipleye_raw_frames and kills the whole load. Fix: widen the except to "
    "(ImportError, ValueError, OSError).",
)
def test_corrupt_questions_workbook_degrades_to_no_questions(tmp_path):
    root = build_multipleye_tree(tmp_path)
    (root / "stimuli_Demo" / _QUESTIONS_NAME).write_bytes(b"not a workbook")
    words, fixations = datasets.load_multipleye(root)

    assert "comprehension_questions" not in words.columns
    _assert_canonical_intact(words, fixations)
