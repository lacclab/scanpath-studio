"""Duplicate metadata rows that do not disagree are one record, combined.

Two ``p1`` rows — one giving a language and no age, the other an age and no
language — used to keep whichever came first, so the table lost age in one row
order and language in the other. Each field now takes the one value its rows
hold, at all three grains; rows that hold two *different* values for a field
are still refused.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import metadata as md

ROWS = [
    {"id": "a", "language": "English", "age": None},
    {"id": "a", "language": None, "age": 20},
    {"id": "b", "language": "Hebrew", "age": 30},
]


def _build(grain: str, rows: list[dict]):
    frame = pd.DataFrame(rows)
    if grain == "participant":
        return md.build_participant_metadata(frame, "id", participants=["a", "b"])
    if grain == "trial":
        return md.build_trial_metadata(frame, "id", keys={("p1", "a"), ("p1", "b")})
    if grain == "trial_by_reader":
        frame = frame.assign(reader="p1")
        return md.build_trial_metadata(
            frame, "id", "reader", keys={("p1", "a"), ("p1", "b")}
        )
    return md.build_text_metadata(frame, "id", keys=["a", "b"])


def _row(table, grain: str) -> dict:
    if grain == "participant":
        return table.values_for("a")
    if grain in ("trial", "trial_by_reader"):
        return table.values_for("p1", "a")
    return table.values_for("a")


GRAINS = ("participant", "trial", "trial_by_reader", "text")


@pytest.mark.parametrize("grain", GRAINS)
@pytest.mark.parametrize("order", ["as_written", "reversed"])
def test_compatible_duplicates_keep_every_value(grain, order):
    rows = ROWS if order == "as_written" else [ROWS[1], ROWS[0], ROWS[2]]
    table = _build(grain, rows)
    assert len(table.frame) == 2
    values = _row(table, grain)
    assert values["language"] == "English"
    assert values["age"] == 20
    assert table.report.conflicting == ()
    assert table.report.combined_rows == 2
    # The other key is untouched.
    assert table.field("age").n_missing == 0
    assert table.field("language").n_missing == 0


@pytest.mark.parametrize("grain", GRAINS)
def test_rows_that_disagree_are_still_refused(grain):
    rows = [*ROWS, {"id": "b", "language": "Arabic", "age": 30}]
    table = _build(grain, rows)
    conflicting = {
        k[-1] if isinstance(k, tuple) else k for k in table.report.conflicting
    }
    assert conflicting == {"b"}
    assert table.report.combined_rows == 2
    assert _row(table, grain)["age"] == 20


def test_the_count_survives_a_rejoin():
    table = _build("participant", ROWS)
    assert md.rejoin(table, ["a", "b", "c"]).report.combined_rows == 2
    trials = _build("trial", ROWS)
    assert md.rejoin_trials(trials, {("p1", "a")}).report.combined_rows == 2


def test_a_repeated_index_label_does_not_spread_a_value():
    """A user's frame may carry repeated index labels (a concatenation)."""
    frame = pd.DataFrame(ROWS, index=[0, 0, 0])
    table = md.build_participant_metadata(frame, "id", participants=["a", "b"])
    assert table.values_for("b") == {"language": "Hebrew", "age": 30}
    assert table.values_for("a") == {"language": "English", "age": 20}


def test_the_status_line_names_the_combined_rows():
    from scanpath_studio.tabs import _combined_rows_note

    assert _combined_rows_note(_build("text", ROWS).report) == (
        "combined 2 compatible duplicate rows"
    )
    assert _combined_rows_note(_build("text", ROWS[1:]).report) is None
