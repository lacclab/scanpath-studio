"""A bundle's metadata tables describe only the readers, trials and texts it
exports — never the rest of the attached table."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.export import ExportOptions, _rows_in_scope, bulk_export


def _reading(participant: str, trial: str, text: str):
    words, fixations = api.build_authored_scanpath("A small trial")
    ids = {"participant_id": participant, "trial_id": trial, "text_id": text}
    return words.assign(**ids), fixations.assign(**ids)


def _corpus():
    """Two readings: p1 reads x1 in t1, p2 reads x2 in t2."""
    w1, f1 = _reading("p1", "t1", "x1")
    w2, f2 = _reading("p2", "t2", "x2")
    words = pd.concat([w1, w2], ignore_index=True)
    fixations = pd.concat([f1, f2], ignore_index=True)
    combos = pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "trial_id": ["t1", "t2"],
            "text_id": ["x1", "x2"],
        }
    )
    return combos, words, fixations


def _metadata(trial_keyed_by_participant: bool) -> dict:
    trials = {"trial_id": ["t1", "t2"], "block": ["A", "B"]}
    if trial_keyed_by_participant:
        trials = {"participant_id": ["p1", "p2"], **trials}
    return {
        "participant_metadata": pd.DataFrame(
            {"participant_id": ["p1", "p2"], "age": [20, 50]}
        ),
        "trial_metadata": pd.DataFrame(trials),
        "text_metadata": pd.DataFrame(
            {"text_id": ["x1", "x2"], "genre": ["news", "opinion"]}
        ),
    }


def _bundle_metadata(settings: dict, **options) -> dict[str, pd.DataFrame]:
    combos, words, fixations = _corpus()
    data, progress = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=1200,
        canvas_height=800,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings=settings,
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=True,
            **options,
        ),
    )
    assert not progress.errors, progress.errors
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {
            name: pd.read_csv(io.BytesIO(zf.read(name)), dtype=str)
            for name in zf.namelist()
            if name.startswith("metadata/")
        }


@pytest.mark.parametrize("combine", [False, True])
@pytest.mark.parametrize("keyed_by_participant", [False, True])
def test_one_trial_bundle_holds_only_its_own_metadata(combine, keyed_by_participant):
    tables = _bundle_metadata(
        _metadata(keyed_by_participant),
        scope="trial",
        scope_participant="p1",
        scope_trial="t1",
        combine_trials=combine,
    )
    assert tables["metadata/participants.csv"].to_dict("records") == [
        {"participant_id": "p1", "age": "20"}
    ]
    trials = tables["metadata/trials.csv"]
    assert trials["trial_id"].tolist() == ["t1"]
    assert trials["block"].tolist() == ["A"]
    assert tables["metadata/texts.csv"].to_dict("records") == [
        {"text_id": "x1", "genre": "news"}
    ]


def test_the_whole_pool_keeps_every_row():
    tables = _bundle_metadata(_metadata(True))
    assert sorted(tables["metadata/participants.csv"]["participant_id"]) == [
        "p1",
        "p2",
    ]
    assert sorted(tables["metadata/texts.csv"]["text_id"]) == ["x1", "x2"]


def test_column_opt_outs_still_apply_to_the_scoped_rows():
    tables = _bundle_metadata(
        _metadata(False),
        scope="trial",
        scope_participant="p2",
        scope_trial="t2",
        metadata_fields=(),
        text_metadata_fields=("genre",),
    )
    assert "metadata/participants.csv" not in tables
    assert tables["metadata/texts.csv"].to_dict("records") == [
        {"text_id": "x2", "genre": "opinion"}
    ]


def test_a_table_with_no_matching_row_is_left_out_not_shipped_whole():
    settings = {
        "participant_metadata": pd.DataFrame(
            {"participant_id": ["someone_else"], "age": [33]}
        )
    }
    assert "metadata/participants.csv" not in _bundle_metadata(settings)


def test_a_reader_scoped_trial_row_needs_the_whole_pair():
    """p2's t1 is a different reading from p1's t1."""
    frame = pd.DataFrame(
        {"participant_id": ["p1", "p2"], "trial_id": ["t1", "t1"], "block": [1, 2]}
    )
    kept = _rows_in_scope(frame, pairs={("p1", "t1")}, texts=set(), grain="trial")
    assert kept["block"].tolist() == [1]


def test_ids_compare_as_text():
    frame = pd.DataFrame({"participant_id": [1, 2], "age": [20, 50]})
    kept = _rows_in_scope(frame, pairs={("1", "t")}, texts=set(), grain="participant")
    assert kept["age"].tolist() == [20]
