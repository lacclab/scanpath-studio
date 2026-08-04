import json

import pandas as pd

import scanpath_studio as sps
from scanpath_studio.authoring import authoring_json, default_events, layout_text


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
