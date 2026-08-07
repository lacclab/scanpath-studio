import json

import pandas as pd

import scanpath_studio as sps
from scanpath_studio.authoring import (
    authored_fixations,
    authoring_json,
    default_events,
    layout_text,
    parse_authoring_json,
    unusable_event_rows,
)


def test_authored_geometry_uses_word_top_left_and_fixation_centres():
    words = layout_text("alpha beta", margin=70, character_width=10, word_height=20)
    assert words.iloc[0]["x"] == 70
    assert words.iloc[0]["y"] == 70
    events = default_events(words)
    assert events.iloc[0]["x"] == words.iloc[0]["x"] + words.iloc[0]["width"] / 2
    assert events.iloc[0]["y"] == words.iloc[0]["y"] + words.iloc[0]["height"] / 2


def test_public_authoring_build_and_json_load_round_trip(tmp_path):
    words, fixations = sps.build_authored_scanpath("alpha beta")
    payload = authoring_json("alpha beta", default_events(words))
    path = tmp_path / "authored.json"
    path.write_text(payload, encoding="utf-8")
    loaded_words, loaded_fixations = sps.load_authored_scanpath(path)
    pd.testing.assert_frame_equal(loaded_words, words)
    pd.testing.assert_frame_equal(loaded_fixations, fixations)
    assert json.loads(payload)["schema"] == 1


# --- BUG-19: rows that can't be drawn, and the index the editor needs ---------


def test_a_row_targeting_a_word_that_is_not_there_is_reported_not_silent():
    """The whole "my edit didn't take" report: a bad target vanished quietly."""
    words = layout_text("alpha beta")
    events = default_events(words)
    events.loc[1, "word_id"] = 99  # only two words exist

    assert unusable_event_rows(words, events) == [2]  # 1-based, as shown in the UI
    # …and that is exactly the row the builder drops, so the two never disagree.
    assert len(authored_fixations(words, events)) == len(events) - 1


def test_a_blank_target_word_counts_as_unusable():
    words = layout_text("alpha beta")
    events = default_events(words)
    events["word_id"] = events["word_id"].astype(object)
    events.loc[0, "word_id"] = None

    assert unusable_event_rows(words, events) == [1]


def test_every_default_row_is_usable():
    words = layout_text("alpha beta gamma delta")
    assert unusable_event_rows(words, default_events(words)) == []


def test_a_restored_file_comes_back_range_indexed():
    """``st.data_editor(num_rows="dynamic")`` cannot add rows to a gapped index,
    and its edits then land on the wrong rows (BUG-19)."""
    words = layout_text("alpha beta gamma")
    events = default_events(words).drop(index=1)  # a deleted middle row
    assert list(events.index) == [0, 2]

    _, restored = parse_authoring_json(authoring_json("alpha beta gamma", events))

    assert list(restored.index) == [0, 1]
