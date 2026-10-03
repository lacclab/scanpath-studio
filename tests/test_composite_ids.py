"""A composite id keeps different source tuples apart.

Joining the parts with a bare ``_`` made ``("block_A", "B")`` and
``("block", "A_B")`` the same trial, ``block_A_B``. ``data.compose_id`` escapes
a ``_`` or backslash inside a part, so the two stay distinct, while parts with
neither — almost every id — compose exactly as before. Ids saved under the old
spelling (a stored dataset, an annotations file, a link) still find their trial
when the old spelling is unambiguous.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio import metadata as md
from scanpath_studio.annotations import merge_records
from scanpath_studio.data import (
    compose_id,
    composite_respelling_map,
    harmonize_frames,
    legacy_composite_id,
    mapping_value_preview,
    normalize_fixations,
    normalize_words,
    respell_reading,
    split_composite_id,
    trial_id_series,
)

TUPLES = [("block_A", "B"), ("block", "A_B")]


def _source(rows=TUPLES) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["session", "item"])


def test_the_two_tuples_stay_distinct():
    ids = trial_id_series(_source(), ["session", "item"])
    assert ids.nunique() == 2
    assert list(ids) == ["block\\_A_B", "block_A\\_B"]


def test_parts_without_underscores_compose_as_before():
    frame = pd.DataFrame({"p": ["p1", "7.0"], "t": ["t3", "x"]})
    assert list(trial_id_series(frame, ["p", "t"])) == ["p1_t3", "7_x"]
    assert compose_id(["p1", "t3"]) == "p1_t3"


@pytest.mark.parametrize(
    "parts",
    [
        ["block_A", "B"],
        ["block", "A_B"],
        ["a\\", "_b"],
        ["a\\_", ""],
        ["", "", "x"],
        ["back\\slash", "under_score_"],
    ],
)
def test_the_encoding_reads_back(parts):
    assert split_composite_id(compose_id(parts)) == parts
    assert legacy_composite_id(compose_id(parts)) == "_".join(parts)


def test_vector_and_scalar_forms_agree():
    rows = [("a\\", "_b"), ("x_", "y"), ("p", "q")]
    frame = pd.DataFrame(rows, columns=["a", "b"])
    assert list(trial_id_series(frame, ["a", "b"])) == [compose_id(r) for r in rows]


def test_repeated_rows_of_one_tuple_are_one_trial():
    ids = trial_id_series(_source([*TUPLES, TUPLES[0], TUPLES[0]]), ["session", "item"])
    assert ids.nunique() == 2


def _tables():
    rows = []
    fixations = []
    for (session, item), x in zip(TUPLES, (100, 400), strict=True):
        rows.append(
            {
                "participant_id": "r1",
                "session": session,
                "item": item,
                "word_id": 1,
                "text": "word",
                "x": x,
                "y": 100,
                "width": 50,
                "height": 20,
            }
        )
        fixations.append(
            {
                "participant_id": "r1",
                "session": session,
                "item": item,
                "word_id": 1,
                "x": x + 10,
                "y": 110,
                "duration_ms": 200,
                "timestamp_ms": 0,
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(fixations)


def test_words_and_fixations_join_per_reading():
    words, fixations = _tables()
    schema = {"trial": ["session", "item"]}
    word_schema = api.propose_schema(words, "words") | schema
    fix_schema = api.propose_schema(fixations, "fixations") | schema
    words_n, fix_n = api.load_scanpath_data(
        words, fixations, word_schema=word_schema, fix_schema=fix_schema
    )
    assert sorted(fix_n["trial_id"].unique()) == sorted(
        trial_id_series(_source(), ["session", "item"])
    )
    assert set(words_n["trial_id"]) == set(fix_n["trial_id"])
    for trial in fix_n["trial_id"].unique():
        boxes = words_n[words_n["trial_id"] == trial]
        assert len(boxes) == 1  # each reading keeps its own box


def test_trial_metadata_joins_the_composed_ids():
    keys = {("r1", tid) for tid in trial_id_series(_source(), ["session", "item"])}
    table = pd.DataFrame(
        {"session": ["block_A", "block"], "item": ["B", "A_B"], "level": [1, 2]}
    )
    built = md.build_trial_metadata(table, ["session", "item"], keys=keys)
    assert len(built.report.matched) == 2
    assert not built.report.only_in_data


def test_old_spellings_find_their_trial_when_unambiguous():
    current = ["x\\_1_2", "p_q"]
    assert composite_respelling_map(["x_1_2"], current) == {"x_1_2": "x\\_1_2"}
    # and the reverse: a table composed today against ids stored before
    assert composite_respelling_map(["x\\_1_2"], ["x_1_2"]) == {"x\\_1_2": "x_1_2"}
    # an old id the two readings shared stays unresolved — it named both
    both = trial_id_series(_source(), ["session", "item"])
    assert composite_respelling_map(["block_A_B"], both) == {}
    # an id that is already right is left alone
    assert composite_respelling_map(["p_q"], current) == {}


def test_a_restored_dataset_joins_a_table_composed_today():
    """Stored frames keep the ids they were saved with; a trial table attached
    to them now composes the new spelling and still matches."""
    keys = {("r1", "lab_A_7")}  # stored before the escape
    table = pd.DataFrame({"lab": ["lab_A"], "n": ["7"], "level": [3]})
    built = md.build_trial_metadata(table, ["lab", "n"], keys=keys)
    assert built.report.matched == ("lab_A_7",)
    texts = md.build_text_metadata(
        table.rename(columns={"level": "genre"}), ["lab", "n"], keys={"lab_A_7"}
    )
    assert texts.report.matched == ("lab_A_7",)


def test_harmonize_matches_an_old_and_a_new_spelling():
    words, fixations = _tables()
    words = words.iloc[[0]]
    fixations = fixations.iloc[[0]]
    schema = {"trial": ["session", "item"]}
    words_n = normalize_words(words, api.propose_schema(words, "words") | schema)
    fix_n = normalize_fixations(
        fixations, api.propose_schema(fixations, "fixations") | schema
    )
    # the words half stored before the escape (a recovery-cache dataset)
    words_n = words_n.assign(trial_id="block_A_B")
    words_h, fix_h = harmonize_frames(words_n, fix_n)
    assert set(words_h["trial_id"]) == set(fix_h["trial_id"])


def test_annotations_file_from_before_lands_on_its_trial():
    store: dict = {}
    records = [{"participant_id": "r1", "trial_id": "x_1_2", "star": True}]
    applied, skipped = merge_records(store, records, [("r1", "x\\_1_2")])
    assert (applied, skipped) == (1, 0)
    assert ("r1", "x\\_1_2") in store


def test_api_accepts_the_old_spelling():
    words, fixations = _tables()
    words, fixations = words.iloc[[0]], fixations.iloc[[0]]
    schema = {"trial": ["session", "item"]}
    words_n, fix_n = api.load_scanpath_data(
        words,
        fixations,
        word_schema=api.propose_schema(words, "words") | schema,
        fix_schema=api.propose_schema(fixations, "fixations") | schema,
    )
    fig = api.plot_scanpath(words_n, fix_n, participant="r1", trial="block_A_B")
    assert fig is not None


def test_the_mapping_preview_shows_the_escape():
    preview = mapping_value_preview(_source(), "trial", ["session", "item"])
    assert "block_A + B → block\\_A_B" in preview
    assert "block + A_B → block_A\\_B" in preview


def _one_reading():
    words, fixations = _tables()
    words, fixations = words.iloc[[0]], fixations.iloc[[0]]
    schema = {"trial": ["session", "item"]}
    return api.load_scanpath_data(
        words,
        fixations,
        word_schema=api.propose_schema(words, "words") | schema,
        fix_schema=api.propose_schema(fixations, "fixations") | schema,
    )


def test_compare_accepts_the_old_spelling():
    words_n, fix_n = _one_reading()
    old = ("r1", "block_A_B")
    assert api.compare_scanpaths(words_n, fix_n, old, old) is not None


def test_a_composite_participant_finds_its_old_spelling():
    readings = [("lab\\_A_7", "t1")]
    assert respell_reading("lab_A_7", "t1", readings) == ("lab\\_A_7", "t1")
    store: dict = {}
    records = [{"participant_id": "lab_A_7", "trial_id": "t1", "star": True}]
    assert merge_records(store, records, readings) == (1, 0)
