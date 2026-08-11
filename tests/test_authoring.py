from __future__ import annotations

import json

import pandas as pd

import scanpath_studio as sps
from scanpath_studio.authoring import (
    apply_authoring_event,
    authored_fixations,
    authoring_json,
    default_events,
    event_problems,
    layout_text,
    parse_authoring_document,
    parse_authoring_json,
    reconcile_event_table,
    unusable_event_rows,
)


def test_authored_geometry_uses_word_top_left_and_fixation_centres():
    words = layout_text("alpha beta", margin=70, character_width=10, word_height=20)
    assert words.iloc[0]["x"] == 70
    assert words.iloc[0]["y"] == 70
    events = default_events(words)
    assert events.iloc[0]["x"] == words.iloc[0]["x"] + words.iloc[0]["width"] / 2
    assert events.iloc[0]["y"] == words.iloc[0]["y"] + words.iloc[0]["height"] / 2
    assert events["fixation_id"].tolist() == [1, 2]
    assert events["order_in_trial"].tolist() == [1, 2]


def test_explicit_and_blank_lines_are_preserved_before_automatic_wrap():
    words = layout_text(
        "alpha beta\n\ngamma delta",
        canvas_width=115,
        margin=10,
        character_width=10,
        line_height=40,
    )
    # beta wraps within source line 0; the blank source line then consumes its
    # own index before gamma, and delta wraps within source line 2.
    assert words["text"].tolist() == ["alpha", "beta", "gamma", "delta"]
    assert words["line_idx"].astype(int).tolist() == [0, 1, 3, 4]
    assert words["y"].tolist() == [10.0, 50.0, 130.0, 170.0]


def test_punctuation_stays_with_its_token_and_empty_stimulus_has_canonical_columns():
    words = layout_text("Hello, world!")
    assert words["text"].tolist() == ["Hello,", "world!"]
    empty = layout_text("")
    assert empty.empty
    assert list(empty.columns) == [
        "participant_id",
        "trial_id",
        "text_id",
        "word_id",
        "text",
        "line_idx",
        "x",
        "y",
        "width",
        "height",
    ]


def test_public_authoring_build_and_schema_2_json_load_round_trip(tmp_path):
    words, fixations = sps.build_authored_scanpath("alpha beta")
    payload = authoring_json("alpha beta", default_events(words))
    path = tmp_path / "authored.json"
    path.write_text(payload, encoding="utf-8")
    loaded_words, loaded_fixations = sps.load_authored_scanpath(path)
    pd.testing.assert_frame_equal(loaded_words, words)
    pd.testing.assert_frame_equal(loaded_fixations, fixations)
    assert json.loads(payload)["schema"] == 2


def test_schema_1_migrates_without_changing_canonical_output():
    words = layout_text("alpha beta")
    legacy_events = default_events(words)[["word_id", "x", "y", "duration_ms"]]
    schema_1 = json.dumps(
        {
            "schema": 1,
            "text": "alpha beta",
            "fixations": legacy_events.to_dict("records"),
        }
    )
    document = parse_authoring_document(schema_1)
    assert document.schema == 2
    assert document.events["fixation_id"].tolist() == [1, 2]
    expected = authored_fixations(words, legacy_events)
    migrated = authored_fixations(words, document.events)
    pd.testing.assert_frame_equal(migrated, expected)


def test_schema_2_keeps_layout_settings_and_stable_ids():
    words = layout_text("alpha beta", canvas_width=500)
    events = default_events(words)
    events.loc[1, "fixation_id"] = 42
    payload = authoring_json("alpha beta", events, layout={"canvas_width": 500})
    document = parse_authoring_document(payload)
    assert document.layout["canvas_width"] == 500
    assert document.events["fixation_id"].tolist() == [1, 42]
    _, restored = parse_authoring_json(payload)
    assert list(restored.index) == [0, 1]


def test_xy_is_primary_and_target_word_is_optional():
    words = layout_text("alpha beta")
    events = default_events(words)
    events.loc[0, "word_id"] = None
    events.loc[0, ["x", "y"]] = [999.0, 777.0]
    fixations = authored_fixations(words, events)
    assert fixations.loc[0, ["x", "y"]].tolist() == [999.0, 777.0]
    assert pd.isna(fixations.loc[0, "word_id"])
    assert unusable_event_rows(words, events) == []


def test_blank_xy_uses_the_optional_target_word_centre():
    words = layout_text("alpha beta")
    events = default_events(words)
    events.loc[0, ["x", "y"]] = [None, None]
    fixation = authored_fixations(words, events).iloc[0]
    assert fixation["x"] == words.iloc[0]["x"] + words.iloc[0]["width"] / 2
    assert fixation["y"] == words.iloc[0]["y"] + words.iloc[0]["height"] / 2


def test_only_a_row_without_xy_or_valid_target_is_unusable():
    words = layout_text("alpha beta")
    events = default_events(words)
    events.loc[1, ["word_id", "x", "y"]] = [99, None, None]
    assert unusable_event_rows(words, events) == [2]
    assert "Row 2" in " ".join(event_problems(words, events))
    assert len(authored_fixations(words, events)) == 1


def test_canvas_add_move_reorder_and_delete_use_stable_identity():
    words = layout_text("alpha beta")
    events = default_events(words)
    events, selected = apply_authoring_event(
        events, {"type": "add", "x": 500, "y": 300}
    )
    added_id = selected
    assert added_id == 3
    assert events.loc[2, "word_id"] is None

    events, selected = apply_authoring_event(
        events,
        {"type": "move", "fixation_id": added_id, "x": 510, "y": 305},
        selected_fixation_id=selected,
    )
    row = events[events["fixation_id"] == added_id].iloc[0]
    assert row[["x", "y"]].tolist() == [510, 305]

    # A table reorder changes sequence, not identity or selection.
    events.loc[events["fixation_id"] == added_id, "order_in_trial"] = 1
    events.loc[events["fixation_id"] == 1, "order_in_trial"] = 3
    events, selected = reconcile_event_table(events, selected)
    assert selected == added_id
    ordered = authored_fixations(words, events)
    assert int(ordered.iloc[0]["fixation_id"]) == added_id

    events, selected = apply_authoring_event(
        events,
        {"type": "delete", "fixation_id": added_id},
        selected_fixation_id=selected,
    )
    assert added_id not in events["fixation_id"].tolist()
    assert selected is None


def test_duplicate_ids_and_orders_are_rejected_with_actionable_messages():
    words = layout_text("alpha beta")
    events = default_events(words)
    events.loc[1, "fixation_id"] = 1
    events.loc[1, "order_in_trial"] = 1
    problems = event_problems(words, events)
    assert any("Fixation id must be unique" in problem for problem in problems)
    assert any("Order must be unique" in problem for problem in problems)
    try:
        reconcile_event_table(events)
    except ValueError as exc:
        assert "duplicate: 1" in str(exc)
    else:  # pragma: no cover - a regression would make the assertion explain itself
        raise AssertionError("duplicate stable ids/orders were silently accepted")


def test_a_restored_file_comes_back_range_indexed():
    words = layout_text("alpha beta gamma")
    events = default_events(words).drop(index=1)
    _, restored = parse_authoring_json(authoring_json("alpha beta gamma", events))
    assert list(restored.index) == [0, 1]
