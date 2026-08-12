"""MultiplEYE trials as ordered screens — reading pages **and** questions (DATA-24).

A MultiplEYE trial used to be one ``(stimulus, page)`` pseudo-trial, and the
comprehension-question screens were dropped. Now one reading of one stimulus is
one trial (``trial_id == text_id``) whose screens are the corpus's own ``page``
values, ordered by ``screen_index``.

Three joins carry the weight, and each has a way of failing silently that these
tests pin:

* **``screen_index`` comes from the reader's own fixation onsets**, never from
  the screen name — reading pages are presented in page order but the *question
  order is shuffled per reader*, so a name-derived index would quietly reorder
  the trial.
* **Question AOI rows match on ``int(question_id)``** — the AOI file zero-pads
  the stimulus id (``question_01111``) while the fixations do not
  (``question_1111``), so a string match finds nothing and the screens vanish.
* **Word boxes are inner-joined to the screens the reader actually fixated** —
  ``multipart.validate_matching_parts`` rejects a screen present in one report
  and absent from the other, so a skipped page must degrade, not crash.

The tree below is deliberately adversarial about all three: the question AOI
rows are written out of reading order, two readers get different answer layouts,
one reader's question onsets run backwards against the ids, and one reader skips
a page.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import api, datasets

# --- The synthetic corpus ----------------------------------------------------

READER_A = "001_ZH_CH_1_ET1"  # bare pid 1 → answer layout version 71
READER_B = "014_ZH_CH_1_ET2"  # bare pid 14 → answer layout version 22
LIT = "Lit_Demo_1"
Q1, Q2 = 1111, 1112  # question ids as the FIXATIONS spell them (unpadded)

OFF_X, OFF_Y = 305.0, 44.5  # the centered-stimulus offset, spelled out

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

_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
    "00000049454e44ae426082"
)

# Where each answer block's first character sits, per layout version. Version 71
# reads stem → target → distractor_b → distractor_c → distractor_a; version 22
# swaps the target and distractor_a rows, so the SAME question yields a
# different word order for a reader on that layout.
_BLOCK_GEOMETRY = {
    71: {
        "stem": (80, 80),
        "target": (200, 240),
        "distractor_b": (80, 400),
        "distractor_c": (600, 400),
        "distractor_a": (200, 560),
    },
    22: {
        "stem": (80, 80),
        "distractor_a": (200, 240),
        "distractor_b": (80, 400),
        "distractor_c": (600, 400),
        "target": (200, 560),
    },
}
# Written to the file in an order that matches NEITHER layout's reading order,
# so an implementation that keeps file order fails both readers.
_BLOCK_FILE_ORDER = ("distractor_a", "distractor_b", "distractor_c", "target", "stem")


def _char_rows(page: str, word_idx: int, word: str, x0: int, y0: int) -> list[dict]:
    """Two character-AOI rows (20x30 px each) for one two-letter word."""
    return [
        {
            "char_idx": word_idx * 2 + i,
            "char": word[i],
            "top_left_x": x0 + word_idx * 60 + i * 20,
            "top_left_y": y0,
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


def _question_aoi_rows() -> pd.DataFrame:
    """The ``*_aoi_questions.csv`` frame: 5 blocks x 2 words x 2 versions x 2 qs.

    ``word_idx`` restarts at 0 in every block — which is exactly why it cannot be
    the word id — and the stimulus id is **zero-padded** in the page name."""
    rows = []
    for question_id in (Q1, Q2):
        padded = f"{question_id:05d}"
        for version, geometry in _BLOCK_GEOMETRY.items():
            for block in _BLOCK_FILE_ORDER:
                x0, y0 = geometry[block]
                page = (
                    f"question_{padded}"
                    if block == "stem"
                    else f"{LIT}_question_{padded}_{block}"
                )
                # Two words per block, so a screen-unique word id has to run a
                # single counter across the blocks rather than reuse word_idx.
                for word_idx, word in enumerate(
                    (block[:2].upper(), block[-2:].upper())
                ):
                    for row in _char_rows(page, word_idx, word, x0, y0):
                        rows.append(
                            {
                                **row,
                                "question_image_version": f"question_images_version_{version}",
                            }
                        )
    return pd.DataFrame(rows)


def _fix_row(onset: int, page: str, x: int = 90, y: int = 65) -> dict:
    return {
        "onset": onset,
        "duration": 200,
        "location_x": x,
        "location_y": y,
        "page": page,
    }


def _scan_row(onset: int, page: str, word_idx: int) -> dict:
    return {**_fix_row(onset, page), "name": "fixation", "word_idx": word_idx}


# Reader A reads both pages; their question onsets run 1112 BEFORE 1111, so the
# onset order and the id order disagree. Reader B skips page_2 entirely.
_READING = {
    READER_A: [
        _scan_row(1000, "page_1", 0),
        _scan_row(1200, "page_1", 1),
        _scan_row(2000, "page_2", 0),
    ],
    READER_B: [_scan_row(1000, "page_1", 0)],
}
_QUESTIONS = {
    READER_A: [
        _fix_row(3000, f"question_{Q2}"),
        _fix_row(4000, f"question_{Q1}"),
        # A rating screen: no AOI file ships for it, so it is never a screen.
        _fix_row(2500, "familiarity_rating_screen_1"),
        _fix_row(2700, "subject_difficulty_screen"),
    ],
    READER_B: [
        _fix_row(3000, f"question_{Q1}"),
        _fix_row(4000, f"question_{Q2}"),
    ],
}


def build_screens_tree(
    root: Path, *, versions: bool = True, images: bool = True
) -> Path:
    """Write a MultiplEYE tree with reading pages **and** question screens."""
    stimuli = root / "stimuli_Demo"
    aoi_dir = stimuli / "aoi_stimuli_demo"
    aoi_dir.mkdir(parents=True)
    pd.DataFrame(
        _char_rows("page_1", 0, "AA", 80, 50)
        + _char_rows("page_1", 1, "BB", 80, 50)
        # page_2 reuses page_1's coordinates, as the real corpus does.
        + _char_rows("page_2", 0, "CC", 80, 50)
        + _char_rows("page_2", 1, "DD", 80, 50),
        columns=_AOI_COLUMNS,
    ).to_csv(aoi_dir / "lit_demo_1_aoi.csv", index=False)
    _question_aoi_rows().to_csv(aoi_dir / "lit_demo_1_aoi_questions.csv", index=False)

    for reader in (READER_A, READER_B):
        scan_dir = root / "scanpaths" / reader
        fix_dir = root / "fixations" / reader
        scan_dir.mkdir(parents=True)
        fix_dir.mkdir(parents=True)
        name = f"{reader}_trial_1_{LIT}"
        # The scanpath export is pre-filtered to reading pages, as it is in the
        # corpus — the question screens only exist in the raw fixation file.
        pd.DataFrame(_READING[reader]).to_csv(
            scan_dir / f"{name}_scanpath.csv", index=False
        )
        raw = [
            {k: v for k, v in row.items() if k not in ("name", "word_idx")}
            for row in _READING[reader]
        ] + _QUESTIONS[reader]
        pd.DataFrame(raw).to_csv(fix_dir / f"{name}_fixation.csv", index=False)

    if versions:
        write_versions(root)
    if images:
        image_dir = stimuli / "question_images_zh_ch_1"
        for version in _BLOCK_GEOMETRY:
            folder = image_dir / f"question_images_version_{version}"
            folder.mkdir(parents=True)
            for question_id in (Q1, Q2):
                name = f"Lit_Demo_id1_question_{question_id:05d}_zh.png"
                (folder / name).write_bytes(_PNG_1X1)
    return root


def write_versions(root: Path, frame: pd.DataFrame | None = None) -> Path:
    """``stimulus_order_versions_*.csv``: pid → answer-layout version number."""
    if frame is None:
        frame = pd.DataFrame(
            {
                # Unassigned versions (blank pid) sit alongside the real ones, and
                # the pid is a float here but zero-padded text in the file names.
                "version_number": [1, 71, 22, 225],
                "participant_id": [None, 1.0, 14.0, 46.0],
            }
        )
    config = root / "stimuli_Demo" / "config"
    config.mkdir(parents=True, exist_ok=True)
    path = config / "stimulus_order_versions_demo.csv"
    frame.to_csv(path, index=False)
    return path


@pytest.fixture
def screens_root(tmp_path) -> Path:
    return build_screens_tree(tmp_path)


def _screens(frame: pd.DataFrame, reader: str) -> pd.DataFrame:
    """One ordered row per screen of ``reader``'s single trial."""
    rows = frame[frame["participant_id"] == reader]
    columns = [c for c in ("screen_index", "screen_id", "screen_kind") if c in rows]
    return rows[columns].drop_duplicates().sort_values("screen_index")


# --- 1. Identity: one trial, ordered screens ---------------------------------


def test_a_stimulus_is_one_trial_with_its_pages_as_screens(screens_root):
    words, fixations = datasets.load_multipleye(
        screens_root, include_question_screens=False
    )

    # trial_id == text_id == the stimulus; the pages live inside it as screens.
    assert set(words["trial_id"]) == {LIT}
    assert set(words["text_id"]) == {LIT}
    assert (words["trial_id"] == words["text_id"]).all()
    screens = _screens(words, READER_A)
    assert list(screens["screen_id"]) == ["page_1", "page_2"]
    assert list(screens["screen_index"]) == [1, 2]
    assert set(screens["screen_kind"]) == {"reading"}
    # page_2 reuses page_1's coordinates but is its own screen with its own text.
    page_1 = words[
        (words["participant_id"] == READER_A) & (words["screen_id"] == "page_1")
    ]
    page_2 = words[
        (words["participant_id"] == READER_A) & (words["screen_id"] == "page_2")
    ]
    assert set(page_1["text"]) == {"AA", "BB"}
    assert set(page_2["text"]) == {"CC", "DD"}
    assert sorted(page_1["x"]) == sorted(page_2["x"])
    # The presentation monitor rides along, so a screen reports its real canvas.
    from scanpath_studio.multipart import screen_canvas_size

    reader_fix = fixations[
        (fixations["participant_id"] == READER_A) & (fixations["screen_id"] == "page_1")
    ]
    assert screen_canvas_size(reader_fix) == datasets.MULTIPLEYE_MONITOR


# --- 2. Ordering comes from the onsets, not the names ------------------------


def test_screen_index_follows_the_readers_onsets_not_the_screen_names(screens_root):
    """The question order is shuffled per reader, so only the onsets can order it."""
    _, fixations = datasets.load_multipleye(screens_root)

    # Reader A fixated question_1112 BEFORE question_1111 …
    assert list(_screens(fixations, READER_A)["screen_id"]) == [
        "page_1",
        "page_2",
        f"question_{Q2}",
        f"question_{Q1}",
    ]
    # … while reader B saw them the other way round — same names, same file, and
    # a name-derived index would have given both readers the same order.
    assert list(_screens(fixations, READER_B)["screen_id"]) == [
        "page_1",
        f"question_{Q1}",
        f"question_{Q2}",
    ]
    # Indices stay a contiguous 1..N over the INCLUDED screens: the rating and
    # difficulty screens are gone and leave no gap behind them.
    assert list(_screens(fixations, READER_A)["screen_index"]) == [1, 2, 3, 4]
    assert list(_screens(fixations, READER_B)["screen_index"]) == [1, 2, 3]
    assert not fixations["screen_id"].str.contains("rating|difficulty").any()
    # `onset` stays the parent-global clock; the per-screen clock is re-zeroed.
    question = fixations[
        (fixations["participant_id"] == READER_A)
        & (fixations["screen_id"] == f"question_{Q1}")
    ]
    assert float(question["timestamp_ms"].min()) == 4000.0
    assert float(question["screen_timestamp_ms"].min()) == 0.0


# --- 3. The question-AOI join is on int(question_id) -------------------------


def test_question_aoi_matches_on_the_int_id_and_the_readers_version(screens_root):
    aoi = pd.read_csv(
        screens_root
        / "stimuli_Demo"
        / "aoi_stimuli_demo"
        / "lit_demo_1_aoi_questions.csv"
    )
    # The trap: the AOI file zero-pads, the fixations do not. A string match on
    # the fixations' own screen name finds NOTHING in the AOI file.
    assert (
        not aoi["page"].astype(str).str.contains(f"question_{Q1}\\b", regex=True).any()
    )
    assert aoi["page"].astype(str).str.contains(f"question_{Q1:05d}").any()

    words, fixations = datasets.load_multipleye(screens_root)
    for reader in (READER_A, READER_B):
        assert f"question_{Q1}" in set(
            words[words["participant_id"] == reader]["screen_id"]
        )

    # Each reader's boxes come from THEIR layout version: 71 reads
    # stem → target → …, 22 reads stem → distractor_a → …, so the same screen
    # gives the two readers a different second block.
    def second_block(reader):
        rows = words[
            (words["participant_id"] == reader)
            & (words["screen_id"] == f"question_{Q1}")
        ]
        return rows.sort_values("word_id")["aoi_block"].iloc[2]

    assert second_block(READER_A) == "target"
    assert second_block(READER_B) == "distractor_a"
    # The reader's question image comes from that same version directory.
    path = words[
        (words["participant_id"] == READER_A) & (words["screen_id"] == f"question_{Q1}")
    ]["image_path"].iloc[0]
    assert path.endswith(
        f"question_images_version_71/Lit_Demo_id1_question_{Q1:05d}_zh.png"
    )
    assert Path(path).is_file()


# --- 4. Word ids are screen-unique and follow the block geometry --------------


def test_question_word_ids_are_screen_unique_and_in_reading_order(screens_root):
    words, _ = datasets.load_multipleye(screens_root)
    screen = words[
        (words["participant_id"] == READER_A) & (words["screen_id"] == f"question_{Q1}")
    ].sort_values("word_id")

    # 5 blocks x 2 words. word_idx restarted at 0 in every block in the source,
    # so a screen-unique id can only come from re-numbering across the blocks.
    assert list(screen["word_id"]) == list(range(10))
    assert list(screen["aoi_block"]) == [
        "stem",
        "stem",
        "target",
        "target",
        "distractor_b",
        "distractor_b",
        "distractor_c",
        "distractor_c",
        "distractor_a",
        "distractor_a",
    ]
    # That is the geometric reading order (top, then left) — NOT the order the
    # blocks appear in the AOI file.
    assert list(screen["y"]) == sorted(screen["y"])
    assert list(screen["line_idx"]) == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
    # Reading-page words keep the corpus's own word_idx and carry no block.
    page = words[
        (words["participant_id"] == READER_A) & (words["screen_id"] == "page_1")
    ]
    assert sorted(page["word_id"]) == [0, 1]
    assert page["aoi_block"].isna().all()
    # Every word id is unique inside its screen — the identity measures key on.
    key = ["participant_id", "trial_id", "screen_id", "word_id"]
    assert words.groupby(key).size().max() == 1


# --- 5. A skipped page degrades instead of crashing --------------------------


def test_a_reader_who_skipped_a_page_produces_no_orphan_screen(screens_root):
    """`harmonize_frames` rejects orphan screens, so the boxes must be scoped."""
    words, fixations = datasets.load_multipleye(screens_root)

    # Reader B never fixated page_2, so it is simply absent for them — and its
    # word boxes are absent too, rather than orphaning the screen.
    assert "page_2" in set(_screens(words, READER_A)["screen_id"])
    assert "page_2" not in set(_screens(words, READER_B)["screen_id"])
    assert "page_2" not in set(_screens(fixations, READER_B)["screen_id"])

    from scanpath_studio.multipart import validate_matching_parts

    validate_matching_parts(words, fixations)  # would raise on an orphan


# --- 6/7. Degradation: no versions file, and the opt-out ---------------------


def test_uploads_without_a_versions_file_yield_reading_screens_only(
    screens_root, caplog
):
    """The layout is reader-specific, so it is never guessed — only skipped."""
    from scanpath_studio.data import read_tables

    fixation_files = sorted(str(p) for p in (screens_root / "fixations").rglob("*.csv"))
    aoi_files = [
        str(screens_root / "stimuli_Demo" / "aoi_stimuli_demo" / name)
        for name in ("lit_demo_1_aoi.csv", "lit_demo_1_aoi_questions.csv")
    ]
    fix_df = read_tables(fixation_files)
    aoi_df = read_tables(aoi_files)

    with caplog.at_level(logging.WARNING, logger="scanpath_studio.datasets"):
        words, fixations = datasets.load_multipleye_uploads(fix_df, aoi_df)
    assert set(fixations["screen_id"]) == {"page_1", "page_2"}
    assert set(words["screen_id"]) == {"page_1", "page_2"}
    assert "answer-layout version table" in caplog.text

    # Hand the recipe the versions table and the question screens come back.
    versions = pd.read_csv(write_versions(screens_root))
    words, fixations = datasets.load_multipleye_uploads(
        fix_df, aoi_df, versions_df=versions
    )
    assert f"question_{Q1}" in set(fixations["screen_id"])
    assert f"question_{Q1}" in set(words["screen_id"])
    # Uploading the versions table alongside the AOI CSVs works the same way.
    combined = read_tables(aoi_files + [str(write_versions(screens_root))])
    words, _ = datasets.load_multipleye_uploads(fix_df, combined)
    assert f"question_{Q2}" in set(words["screen_id"])


def test_include_question_screens_false_yields_reading_screens_only(screens_root):
    words, fixations = datasets.load_multipleye(
        screens_root, include_question_screens=False
    )

    assert set(words["screen_kind"]) == {"reading"}
    assert set(fixations["screen_kind"]) == {"reading"}
    assert set(fixations["screen_id"]) == {"page_1", "page_2"}
    assert "aoi_block" not in words.columns or words["aoi_block"].isna().all()
    # Reading pages alone need no per-reader layout, so the boxes stay
    # stimulus-level and the page number is the (reader-independent) order.
    raw_words, _ = datasets.multipleye_raw_frames(
        screens_root, include_question_screens=False
    )
    assert "participant_id" not in raw_words.columns
    assert dict(zip(raw_words["page"], raw_words["screen_index"])) == {
        "page_1": 1,
        "page_2": 2,
    }


# --- 8. The screen-aware surfaces round-trip ---------------------------------


def test_the_headless_api_lists_and_plots_a_question_screen(screens_root):
    words, fixations = datasets.load_multipleye(screens_root)

    catalog = api.list_parts(words, fixations, READER_A, LIT)
    assert list(catalog["screen_id"]) == [
        "page_1",
        "page_2",
        f"question_{Q2}",
        f"question_{Q1}",
    ]
    assert list(catalog["screen_index"]) == [1, 2, 3, 4]

    fig = api.plot_scanpath(
        words,
        fixations,
        READER_A,
        LIT,
        screen=f"question_{Q1}",
        canvas_size=datasets.MULTIPLEYE_MONITOR,
    )
    assert len(fig.data) > 0
    # Only that screen's five answer blocks are drawn — no page-1 word boxes.
    labels = [t for t in fig.data if getattr(t, "name", "") == "words"]
    assert labels, "no word-label trace"
    assert set(labels[0].text) == {"ST", "EM", "TA", "ET", "DI", "_A", "_B", "_C"}


def test_the_cli_resolves_a_stimulus_trial_id_and_can_drop_the_questions(screens_root):
    """`render --source multipleye` loads from a corpus ROOT, so it resolves
    ``--trial`` itself — and that resolver has to know the trial is the stimulus
    now, not a ``<stim>__page_NN`` id."""
    from scanpath_studio.cli import _load_multipleye_render

    _, fixations, pid, tid = _load_multipleye_render(str(screens_root), READER_A, LIT)
    assert (pid, tid) == (READER_A, LIT)
    assert f"question_{Q1}" in set(fixations["screen_id"])

    # The review app's integer trial number still resolves, to the same trial.
    _, _, _, by_number = _load_multipleye_render(str(screens_root), READER_A, "1")
    assert by_number == LIT

    # …and the opt-out reaches the loader (`--no-question-screens`).
    _, reading_only, _, _ = _load_multipleye_render(
        str(screens_root), READER_A, LIT, include_question_screens=False
    )
    assert set(reading_only["screen_id"]) == {"page_1", "page_2"}

    with pytest.raises(ValueError, match="neither a MultiplEYE trial id"):
        _load_multipleye_render(str(screens_root), READER_A, "Lit_Demo_1__page_01")
