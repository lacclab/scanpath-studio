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


def test_nested_extra_columns_leave_the_recording_and_its_entity_summaries_accessible():
    words, fixations = _frames()
    fixations["spans"] = [[1, 2]] * len(fixations)
    fixations["condition"] = ["first", "first", "second", "second", "second"]
    for kind in ("participant", "trial"):
        result = _ids_from_data(kind, words, fixations, cache_key=("nested", kind))
        assert set(result["condition"]) == {"first", "second"}
        assert "spans" not in result
    assert fixations["spans"].iloc[0] == [1, 2]


def test_trials() -> None:
    words, fixations = _frames()
    out = _ids_from_data("trial", words, fixations, cache_key="t")
    assert out["Trial ID"].tolist() == ["t1", "t1", "t2"]
    assert out["Text ID"].tolist() == ["a", "a", "b"]
    assert out["# Fixations"].tolist() == [2, 2, 1]
    # A trial with fixations but no AOI rows counts 0, not a gap.
    assert out["# Words"].tolist() == [3, 3, 0]


def test_texts() -> None:
    words, fixations = _frames()
    out = _ids_from_data("text", words, fixations, cache_key="x")
    assert out.columns[:2].tolist() == ["Text ID", "# Participants"]
    assert out.set_index("Text ID")["Text"]["a"] == "The cat sat"
    assert out.set_index("Text ID")["# Participants"]["a"] == 2


def test_gaze_only_readings_supply_participants_trials_and_texts() -> None:
    words, fixations = _frames()
    samples = pd.DataFrame(
        {
            "participant_id": ["p3", "p3"],
            "trial_id": ["t3", "t3"],
            "text_id": ["c", "c"],
        }
    )

    def ids(kind):
        return _ids_from_data(
            kind, words, fixations, cache_key=("gaze", kind), _raw_gaze=samples
        )

    participant = ids("participant").set_index("Participant ID").loc["p3"]
    assert participant[
        ["# Trials", "# Texts", "# Fixations", "# Gaze points"]
    ].tolist() == [1, 1, 0, 2]
    trial = ids("trial").set_index("Trial ID").loc["t3"]
    assert trial[["Text ID", "# Words", "# Fixations", "# Gaze points"]].tolist() == [
        "c",
        0,
        0,
        2,
    ]
    texts = ids("text").set_index("Text ID")
    assert set(texts.index) == {"a", "b", "c"}
    assert texts.loc["c", "# Participants"] == 1


def test_recorded_text_outranks_the_gaze_fallback_in_all_tables() -> None:
    from scanpath_studio import data

    words, fixations = _frames()
    words = words.assign(unique_text_id="story")
    samples = fixations.iloc[:1].assign(text_id="t1", **{data.TEXT_ID_MAPPED: False})
    fixations = fixations.assign(**{data.TEXT_ID_MAPPED: True})

    def table(kind):
        return _ids_from_data(
            kind, words, fixations, cache_key=("mapped-text", kind), _raw_gaze=samples
        )

    assert data.text_ids(words, fixations, samples) == {"story", "b"}
    assert table("participant").set_index("Participant ID").loc["p1", "# Texts"] == 1
    assert (
        table("trial")
        .set_index(["Participant ID", "Trial ID"])
        .loc[("p1", "t1"), "Text ID"]
        == "story"
    )
    texts = table("text").set_index("Text ID")
    assert set(texts.index) == {"story", "b"}
    assert texts.loc["story", "Text"] == "The cat sat"


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
        image_path=["/home/me/a.png"] * 4 + ["/home/me/b.png"],  # shown by name
    )
    out = _ids_from_data("trial", words, fixations, cache_key="c")
    assert out["difficulty"].tolist() == ["Adv", "Ele", "Adv"]
    assert out["image_path"].tolist() == ["a.png", "a.png", "b.png"]
    for gone in ("x", "eye", "unique_text_id"):
        assert gone not in out.columns


def test_participants_carry_their_constant_columns() -> None:
    words, fixations = _frames()
    fixations = fixations.assign(
        group=["L1", "L1", "L2", "L2", "L2"],  # one per reader: kept
        difficulty=["Adv", "Adv", "Ele", "Ele", "Adv"],  # varies per reader
        lab=["TAU"] * 5,  # the same for every reader: left out
    )
    out = _ids_from_data("participant", words, fixations, cache_key="pc")
    assert out["group"].tolist() == ["L1", "L2"]
    assert "difficulty" not in out.columns and "lab" not in out.columns
