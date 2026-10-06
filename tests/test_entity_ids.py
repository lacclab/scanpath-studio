"""The Participants/Trials/Texts tabs without an attached table: the ids the
fixation and AOI rows carry, with counts (`tabs._ids_from_data`)."""

from __future__ import annotations

import pandas as pd

from scanpath_studio.tabs import _ids_from_data


def _frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    words = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3 + ["p2"] * 3,
            "trial_id": ["t1"] * 3 + ["t1"] * 3,
            "text_id": ["a"] * 6,
            "word_id": [1, 2, 3] * 2,
            "line_idx": [0] * 6,
            "text": ["The", "cat", "sat"] * 2,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p2", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t1", "t2"],
            "text_id": ["a", "a", "a", "a", "b"],
        }
    )
    return words, fixations


def test_participants() -> None:
    words, fixations = _frames()
    out = _ids_from_data("participant", words, fixations, cache_key="p")
    assert out.to_dict("list") == {
        "Participant ID": ["p1", "p2"],
        "# Trials": [1, 2],
        "# Texts": [1, 2],
        "# Fixations": [2, 3],
    }


def test_trials() -> None:
    words, fixations = _frames()
    out = _ids_from_data("trial", words, fixations, cache_key="t")
    assert out["Trial ID"].tolist() == ["t1", "t1", "t2"]
    assert out["Text ID"].tolist() == ["a", "a", "b"]
    assert out["# Fixations"].tolist() == [2, 2, 1]
    # A trial with fixations but no AOI rows counts 0, not a gap.
    assert out["# AOIs"].tolist() == [3, 3, 0]


def test_texts() -> None:
    words, fixations = _frames()
    out = _ids_from_data("text", words, fixations, cache_key="x")
    assert out.columns[:2].tolist() == ["Text ID", "# Readers"]
    assert out.set_index("Text ID")["Text"]["a"] == "The cat sat"
    assert out.set_index("Text ID")["# Readers"]["a"] == 2


def test_nothing_to_show() -> None:
    empty = pd.DataFrame()
    for kind in ("participant", "trial", "text"):
        assert _ids_from_data(kind, empty, empty, cache_key=kind).empty


def test_trials_carry_their_constant_columns() -> None:
    words, fixations = _frames()
    fixations = fixations.assign(
        difficulty=["Adv", "Adv", "Ele", "Ele", "Adv"],  # one per trial: kept
        x=[1.0, 2.0, 3.0, 4.0, 5.0],  # varies inside a trial: left out
        eye=["R"] * 5,  # the same in every trial: left out
        unique_text_id=["a", "a", "a", "a", "b"],  # repeats Text ID: left out
        image_path=["/home/me/a.png"] * 4 + ["/home/me/b.png"],  # S4
    )
    out = _ids_from_data("trial", words, fixations, cache_key="c")
    assert out["difficulty"].tolist() == ["Adv", "Ele", "Adv"]
    assert out["image_path"].tolist() == ["a.png", "a.png", "b.png"]
    for gone in ("x", "eye", "unique_text_id"):
        assert gone not in out.columns
