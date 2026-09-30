"""Tests for the pure (non-Streamlit) core of the annotations module."""

from __future__ import annotations

from scanpath_studio import annotations as annotations_mod
from scanpath_studio.annotations import (
    deserialize,
    is_empty_entry,
    records_to_store,
    select_keys,
    serialize,
    store_to_records,
)


def test_records_store_roundtrip():
    records = [
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "star": True,
            "tags": ["a"],
            "note": "hi",
        },
        {
            "participant_id": "p2",
            "trial_id": "t9",
            "star": False,
            "tags": [],
            "note": "x",
        },
    ]
    store = records_to_store(records)
    assert store[("p1", "t1")] == {"star": True, "tags": ["a"], "note": "hi"}
    # Re-flattening yields the same logical content.
    again = records_to_store(store_to_records(store))
    assert again == store


def test_empty_entries_are_pruned():
    records = [
        {
            "participant_id": "p1",
            "trial_id": "t1",
            "star": False,
            "tags": [],
            "note": "  ",
        },
        {
            "participant_id": "p1",
            "trial_id": "t2",
            "star": True,
            "tags": [],
            "note": "",
        },
    ]
    store = records_to_store(records)
    assert ("p1", "t1") not in store  # all-empty entry dropped
    assert ("p1", "t2") in store
    assert is_empty_entry({"star": False, "tags": [], "note": ""}) is True


def test_normalize_dedups_sorts_tags_and_strips_note():
    store = records_to_store(
        [
            {
                "participant_id": "p",
                "trial_id": "t",
                "star": 1,
                "tags": ["b", "a", "a", " c "],
                "note": "  keep  ",
            }
        ]
    )
    entry = store[("p", "t")]
    assert entry["star"] is True
    assert entry["tags"] == ["a", "b", "c"]
    assert entry["note"] == "keep"


def test_serialize_deserialize_roundtrip():
    store = records_to_store(
        [
            {
                "participant_id": "p",
                "trial_id": "t",
                "star": True,
                "tags": ["x"],
                "note": "n",
            }
        ]
    )
    text = serialize(store)
    assert deserialize(text) == store


def test_deserialize_accepts_bare_list():
    text = '[{"participant_id": "p", "trial_id": "t", "star": true, "tags": [], "note": ""}]'
    store = deserialize(text)
    assert store[("p", "t")]["star"] is True


def test_select_keys_filters():
    store = records_to_store(
        [
            {
                "participant_id": "p",
                "trial_id": "fav",
                "star": True,
                "tags": ["keep"],
                "note": "",
            },
            {
                "participant_id": "p",
                "trial_id": "exc",
                "star": False,
                "tags": ["To exclude"],
                "note": "",
            },
            {
                "participant_id": "p",
                "trial_id": "plain",
                "star": False,
                "tags": [],
                "note": "",
            },
        ]
    )
    keys = [("p", "fav"), ("p", "exc"), ("p", "plain")]

    assert select_keys(store, keys, favorites_only=True) == [("p", "fav")]
    assert select_keys(store, keys, required_tags=["keep"]) == [("p", "fav")]
    assert ("p", "exc") not in select_keys(store, keys, excluded_tags=["To exclude"])
    # No filters -> everything passes.
    assert select_keys(store, keys) == keys


# --- 🗂️ Data → Annotations (UX-174 r2) ---------------------------------------


def _store_of_two_datasets():
    return {
        ("p1", "t1"): {"star": True, "tags": ["Review"], "note": ""},
        ("p1", "t1", "s2"): {"star": False, "tags": [], "note": "Screen two."},
        ("p9", "t9"): {"star": True, "tags": [], "note": "Another dataset."},
    }


def test_records_in_keeps_this_datasets_trials_and_their_screens():
    records = annotations_mod.records_in(_store_of_two_datasets(), {("p1", "t1")})
    assert [(r["participant_id"], r["trial_id"]) for r in records] == [
        ("p1", "t1"),
        ("p1", "t1"),
    ]
    assert {r.get("screen_id") for r in records} == {None, "s2"}


def test_merge_records_adds_matches_replaces_and_skips_the_rest():
    store = _store_of_two_datasets()
    applied, skipped = annotations_mod.merge_records(
        store,
        [
            {"participant_id": "p1", "trial_id": "t1", "note": "Newer."},
            {"participant_id": "p1", "trial_id": "t2", "star": True},
            {"participant_id": "elsewhere", "trial_id": "t1", "star": True},
        ],
        {("p1", "t1"), ("p1", "t2")},
    )
    assert (applied, skipped) == (2, 1)
    assert store[("p1", "t1")] == {"star": False, "tags": [], "note": "Newer."}
    assert store[("p1", "t2")]["star"] is True
    assert ("elsewhere", "t1") not in store


def test_drop_records_removes_exactly_the_named_entries():
    store = _store_of_two_datasets()
    removed = annotations_mod.drop_records(
        store,
        [{"participant_id": "p1", "trial_id": "t1", "screen_id": "s2"}],
    )
    assert removed == 1
    assert set(store) == {("p1", "t1"), ("p9", "t9")}
