"""Tests for the pure (non-Streamlit) core of the annotations module."""

from __future__ import annotations

import json

import scanpath_studio.annotations as annotations_mod
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


# --- DATA-48: the annotations belong to a dataset ------------------------------

KEY = annotations_mod.ANNOTATIONS_STATE_KEY
STAR = {"star": True, "tags": ["A tag"], "note": "A's note."}
NOTE = {"star": False, "tags": [], "note": "B's note."}


def _live(session):
    return session[KEY]


class TestPerDatasetStore:
    """Two datasets that reuse ``(participant, trial)`` ids keep their own."""

    def test_colliding_ids_do_not_share_a_star_a_tag_or_a_note(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        # The repro: the same ids on another dataset show nothing.
        assert _live(session) == {}
        assert select_keys(_live(session), [("p1", "t1")], favorites_only=True) == []
        session[KEY][("p1", "t1")] = dict(NOTE)
        annotations_mod.activate_dataset(session, "A")
        assert _live(session) == {("p1", "t1"): STAR}
        annotations_mod.activate_dataset(session, "B")
        assert _live(session) == {("p1", "t1"): NOTE}

    def test_a_switch_round_trips_and_only_a_change_swaps(self):
        session: dict = {}
        assert annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        assert not annotations_mod.activate_dataset(session, "A")
        assert annotations_mod.activate_dataset(session, "B")
        assert annotations_mod.activate_dataset(session, "A")
        assert _live(session) == {("p1", "t1"): STAR}
        # The selected dataset is never also in the store.
        assert "A" not in session[annotations_mod.DATASET_STORE_KEY]

    def test_a_swap_drops_the_trial_editors_widget_state(self):
        """Their keys carry the trial ids only, so a trial B shares would seed
        from A's values and write them into B's store."""
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session["annotrial_star_p1__t1__parent"] = True
        session["annotrial_note_p1__t1__parent"] = "A's note."
        annotations_mod.activate_dataset(session, "B")
        assert not [k for k in session if str(k).startswith("annotrial_")]

    def test_the_first_activation_adopts_what_the_store_holds(self):
        """A session with no owner yet — its first run, or a restored cache
        from before DATA-48 — hands what it has to the dataset it opens on."""
        session = {KEY: {("p1", "t1"): dict(STAR)}}
        annotations_mod.activate_dataset(session, "A")
        assert _live(session) == {("p1", "t1"): STAR}
        annotations_mod.activate_dataset(session, "B")
        assert _live(session) == {}

    def test_forget_drops_a_dataset_whether_or_not_it_is_selected(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        session[KEY][("p1", "t1")] = dict(NOTE)
        annotations_mod.forget_dataset(session, "A")
        assert "A" not in annotations_mod.dataset_records(session)
        annotations_mod.forget_dataset(session, "B")
        assert _live(session) == {}
        assert annotations_mod.dataset_records(session) == {}
        # Nothing of either comes back when a dataset of that name is opened.
        annotations_mod.activate_dataset(session, "A")
        assert _live(session) == {}

    def test_rename_keeps_the_annotations(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        annotations_mod.rename_dataset(session, "A", "A2")
        annotations_mod.rename_dataset(session, "B", "B2")
        assert session[annotations_mod.OWNER_KEY] == "B2"
        annotations_mod.activate_dataset(session, "A2")
        assert _live(session) == {("p1", "t1"): STAR}

    def test_the_wizards_dataset_starts_empty_and_is_adopted_by_its_name(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.begin_pending_dataset(session)
        annotations_mod.activate_dataset(session, annotations_mod.PENDING_DATASET)
        assert _live(session) == {}
        annotations_mod.adopt_pending_dataset(session, "New")
        assert session[annotations_mod.OWNER_KEY] == "New"
        assert not annotations_mod.activate_dataset(session, "New")
        annotations_mod.activate_dataset(session, "A")
        assert _live(session) == {("p1", "t1"): STAR}

    def test_adopt_pending_never_relabels_another_datasets_store(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.adopt_pending_dataset(session, "New")
        assert session[annotations_mod.OWNER_KEY] == "A"

    def test_pending_token_matches_metadata(self):
        from scanpath_studio import metadata

        assert annotations_mod.PENDING_DATASET == metadata.PENDING_DATASET

    def test_store_for_reads_a_dataset_that_is_not_selected(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        assert annotations_mod.store_for(session, "A") == {("p1", "t1"): STAR}
        assert annotations_mod.store_for(session, "B") == {}
        assert annotations_mod.store_for(session, "never opened") == {}

    def test_compare_b_reads_its_own_datasets_store(self, monkeypatch):
        """CMP-8's B filters (the ``cmp`` prefix) narrow by B's dataset."""
        from types import SimpleNamespace

        from scanpath_studio.session_keys import COMPARE_SOURCE_STATE_KEY

        session: dict = {}
        annotations_mod.activate_dataset(session, "B")
        session[KEY][("p1", "t1")] = {"star": False, "tags": ["B tag"], "note": ""}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        monkeypatch.setattr(
            annotations_mod, "st", SimpleNamespace(session_state=session)
        )

        session[COMPARE_SOURCE_STATE_KEY] = "B"
        assert "B tag" in annotations_mod.known_tags("cmp")
        assert "A tag" not in annotations_mod.known_tags("cmp")
        assert annotations_mod.filter_keys([("p1", "t1")], favorites_only=True) == [
            ("p1", "t1")
        ]
        assert (
            annotations_mod.filter_keys(
                [("p1", "t1")], favorites_only=True, prefix="cmp"
            )
            == []
        )
        session[COMPARE_SOURCE_STATE_KEY] = "This dataset"
        assert "A tag" in annotations_mod.known_tags("cmp")

    def test_compare_constants_match_their_owners(self):
        """Not imported (both owners import this module), so pinned here."""
        from scanpath_studio import compare_source, tabs

        assert annotations_mod._COMPARE_SAME_DATASET == compare_source.THIS_DATASET
        assert annotations_mod._COMPARE_PREFIX == tabs._COMPARE_FILTER_PREFIX

    def test_rename_refuses_to_overwrite_another_datasets_store(self):
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        session[KEY][("p1", "t1")] = dict(NOTE)
        annotations_mod.activate_dataset(session, "C")
        assert not annotations_mod.rename_dataset(session, "A", "B")
        assert annotations_mod.store_for(session, "A") == {("p1", "t1"): STAR}
        assert annotations_mod.store_for(session, "B") == {("p1", "t1"): NOTE}
        # Nor onto the selected dataset's name.
        assert not annotations_mod.rename_dataset(session, "A", "C")
        assert annotations_mod.dataset_names(session) == {"A", "B", "C"}

    def test_a_new_dataset_starts_clean_under_a_stale_name(self):
        """A store left under the name the wizard's dataset takes is dropped,
        not merged into the new dataset."""
        session: dict = {
            annotations_mod.DATASET_STORE_KEY: {"New": {("p1", "t1"): dict(STAR)}}
        }
        annotations_mod.activate_dataset(session, annotations_mod.PENDING_DATASET)
        annotations_mod.adopt_pending_dataset(session, "New")
        assert session[annotations_mod.OWNER_KEY] == "New"
        assert _live(session) == {}
        assert "New" not in annotations_mod.dataset_records(session)

    def test_a_note_typed_before_a_switch_is_saved_by_its_callback(self, monkeypatch):
        """The editor's fields save on change: the switch's `activate_dataset`
        drops their widget state before any editor renders again."""
        from types import SimpleNamespace

        session: dict = {}
        monkeypatch.setattr(
            annotations_mod, "st", SimpleNamespace(session_state=session)
        )
        annotations_mod.activate_dataset(session, "A")
        keys = ("annotrial_star_s", "annotrial_tags_s", "annotrial_note_s")
        session.update({keys[0]: False, keys[1]: ["Review"], keys[2]: "Typed."})
        annotations_mod._save_entry_callback("p1", "t1", None, *keys)
        session["annotrial_newtag_s"] = "Mine"
        annotations_mod._add_tag_callback(
            keys[1], "annotrial_newtag_s", ("p1", "t1", None, *keys)
        )
        annotations_mod.activate_dataset(session, "B")
        assert annotations_mod.store_for(session, "A") == {
            ("p1", "t1"): {"star": False, "tags": ["Mine", "Review"], "note": "Typed."}
        }
        assert not [k for k in session if str(k).startswith("annotrial_")]


class TestCachePayload:
    """What the recovery cache writes and reads back (``persistence``)."""

    def _two_datasets(self) -> dict:
        session: dict = {}
        annotations_mod.activate_dataset(session, "A")
        session[KEY][("p1", "t1")] = dict(STAR)
        annotations_mod.activate_dataset(session, "B")
        session[KEY][("p1", "t1")] = dict(NOTE)
        return session

    def test_round_trip_keeps_each_datasets_own(self):
        payload = annotations_mod.cache_payload(self._two_datasets())
        assert set(payload["datasets"]) == {"A", "B"}
        assert "unassigned" not in payload
        restored: dict = {}
        assert annotations_mod.restore_payload(restored, payload) == 2
        assert annotations_mod.payload_count(payload) == 2
        annotations_mod.activate_dataset(restored, "B")
        assert _live(restored) == {("p1", "t1"): NOTE}
        annotations_mod.activate_dataset(restored, "A")
        assert _live(restored) == {("p1", "t1"): STAR}

    def test_the_wizards_dataset_is_never_cached(self):
        session = self._two_datasets()
        annotations_mod.activate_dataset(session, annotations_mod.PENDING_DATASET)
        session[KEY][("p1", "t1")] = dict(STAR)
        assert set(annotations_mod.dataset_records(session)) == {"A", "B"}

    def test_a_pre_data48_flat_list_is_adopted_by_the_dataset_opened_first(self):
        """The one-time migration: the old manifest's records name no dataset."""
        legacy = [
            {"participant_id": "p1", "trial_id": "t1", "star": True},
            "not a record",
        ]
        assert annotations_mod.payload_count(legacy) == 2
        session: dict = {}
        assert annotations_mod.restore_payload(session, legacy) == 1
        # Before any dataset opens, a save keeps them unassigned — not lost.
        assert annotations_mod.cache_payload(session)["unassigned"]
        annotations_mod.activate_dataset(session, "The one it had selected")
        payload = annotations_mod.cache_payload(session)
        assert payload == {
            "datasets": {
                "The one it had selected": [
                    {
                        "participant_id": "p1",
                        "trial_id": "t1",
                        "star": True,
                        "tags": [],
                        "note": "",
                    }
                ]
            }
        }

    def test_the_add_wizard_never_adopts_unassigned_entries(self):
        """A session that opens on the add wizard (a `?source=upload` link)
        must not take an old cache's entries into its uncached store — the
        first save would then write none of them."""
        legacy = [{"participant_id": "p1", "trial_id": "t1", "star": True}]
        session: dict = {}
        annotations_mod.restore_payload(session, legacy)
        annotations_mod.activate_dataset(session, annotations_mod.PENDING_DATASET)
        assert _live(session) == {}
        assert annotations_mod.cache_payload(session)["unassigned"] == [
            {
                "participant_id": "p1",
                "trial_id": "t1",
                "star": True,
                "tags": [],
                "note": "",
            }
        ]
        annotations_mod.activate_dataset(session, "Bundled Demo")
        assert set(_live(session)) == {("p1", "t1")}
        assert "unassigned" not in annotations_mod.cache_payload(session)

    @staticmethod
    def _restored_with_upload() -> dict:
        """A pre-DATA-48 cache restored beside upload ``U``, whose trials do
        not include the old star — so it is the demo's (or a corpus')."""
        import pandas as pd

        session: dict = {
            "_datasets": {
                "U": {
                    "fixations": pd.DataFrame(
                        {"participant_id": ["p2"], "trial_id": ["t2"]}
                    ),
                    "words": pd.DataFrame(),
                }
            }
        }
        legacy = [{"participant_id": "p1", "trial_id": "t1", "star": True}]
        annotations_mod.restore_payload(session, legacy)
        return session

    def test_an_upload_opened_first_does_not_swallow_unassigned_entries(self):
        """Every restored upload was asked in the claim pass; one opened first
        must not take the entries it said no to."""
        session = self._restored_with_upload()
        annotations_mod.activate_dataset(session, "U")
        assert _live(session) == {}
        assert annotations_mod.cache_payload(session)["unassigned"]
        annotations_mod.activate_dataset(session, "Bundled Demo")
        assert set(_live(session)) == {("p1", "t1")}
        assert annotations_mod.store_for(session, "U") == {}

    def test_after_the_add_wizard_the_new_upload_does_not_take_them(self):
        """A `?source=upload` first run, then ✅ Add dataset: the new upload is
        an upload too, so the entries wait for the first built-in or corpus."""
        session = self._restored_with_upload()
        annotations_mod.activate_dataset(session, annotations_mod.PENDING_DATASET)
        session["_datasets"]["New"] = session["_datasets"]["U"]
        annotations_mod.adopt_pending_dataset(session, "New")
        assert not annotations_mod.activate_dataset(session, "New")
        assert _live(session) == {}
        annotations_mod.activate_dataset(session, "Bundled Demo")
        assert set(_live(session)) == {("p1", "t1")}

    def test_adoption_can_wait_for_the_load(self):
        """`app.main` activates with ``adopt=False`` and adopts once the load
        says which dataset is shown."""
        session = self._restored_with_upload()
        annotations_mod.activate_dataset(session, "Some corpus", adopt=False)
        assert _live(session) == {}
        assert annotations_mod.adopt_unassigned(session) == 1
        assert set(_live(session)) == {("p1", "t1")}
        assert annotations_mod.adopt_unassigned(session) == 0

    def test_the_migration_gives_an_entry_to_the_uploads_whose_trials_have_it(self):
        """Old entries go by trial membership: to every upload that has the
        trial, and only the unclaimed rest to the first dataset opened."""
        import pandas as pd

        def upload(*pairs, trial_column="trial_id"):
            return {
                "fixations": pd.DataFrame(
                    {
                        "participant_id": [p for p, _ in pairs],
                        trial_column: [t for _, t in pairs],
                    }
                ),
                "words": pd.DataFrame(),
            }

        note = {"star": False, "tags": [], "note": "n"}
        legacy = [
            {"participant_id": "p1", "trial_id": "t1", **note},
            {"participant_id": "p1", "trial_id": "t1", "screen_id": "s2", **note},
            {"participant_id": "p2", "trial_id": "t2", **note},
            {"participant_id": "p3", "trial_id": "shared", **note},
            {"participant_id": "p9", "trial_id": "t9", **note},
        ]
        session: dict = {
            "_datasets": {
                "U1": upload(("p1", "t1"), ("p3", "shared")),
                "U2": upload(
                    ("p2", "t2"), ("p3", "shared"), trial_column="unique_trial_id"
                ),
            }
        }
        assert annotations_mod.restore_payload(session, legacy) == 5
        assert set(annotations_mod.store_for(session, "U1")) == {
            ("p1", "t1"),
            ("p1", "t1", "s2"),
            ("p3", "shared"),
        }
        assert set(annotations_mod.store_for(session, "U2")) == {
            ("p2", "t2"),
            ("p3", "shared"),
        }
        annotations_mod.activate_dataset(session, "Bundled Demo")
        assert set(_live(session)) == {("p9", "t9")}
        assert set(annotations_mod.dataset_records(session)) == {
            "Bundled Demo",
            "U1",
            "U2",
        }

    def test_the_cache_signature_skips_stored_stores_but_sees_every_change(self):
        session = self._two_datasets()  # B selected, A in the store
        before = annotations_mod.store_signature(session)
        assert not annotations_mod.activate_dataset(session, "B")
        assert annotations_mod.store_signature(session) == before
        # The stored store is not serialized — only its revision is there.
        assert NOTE["note"] in str(before) and STAR["note"] not in str(before)
        session[KEY][("p2", "t2")] = dict(STAR)  # an edit to the live store
        edited = annotations_mod.store_signature(session)
        assert edited != before
        for change in (
            lambda s: annotations_mod.activate_dataset(s, "A"),
            lambda s: annotations_mod.rename_dataset(s, "B", "B2"),
            lambda s: annotations_mod.forget_dataset(s, "B2"),
            lambda s: annotations_mod.restore_payload(s, {"datasets": {}}),
        ):
            last = annotations_mod.store_signature(session)
            change(session)
            assert annotations_mod.store_signature(session) != last

    def test_a_dataset_this_session_already_holds_keeps_its_own(self):
        session = self._two_datasets()  # B selected, A in the store
        other = {
            "datasets": {"A": [{"participant_id": "x", "trial_id": "y", "star": True}]}
        }
        assert annotations_mod.restore_payload(session, other) == 0
        assert annotations_mod.store_for(session, "A") == {("p1", "t1"): STAR}

    def test_malformed_payloads_restore_nothing(self):
        for payload in (None, 5, "x", {"datasets": [1]}, {"datasets": {"A": "x"}}):
            session: dict = {}
            assert annotations_mod.restore_payload(session, payload) == 0
            assert session[KEY] == {}


class TestAnnotationsFile:
    """🗂️ Data → Annotations' JSON file, schema 3."""

    def test_the_file_names_its_dataset_and_imports_without_it(self):
        store = {("p1", "t1"): dict(STAR)}
        text = serialize(store, dataset="Pilot")
        assert json.loads(text)["schema"] == annotations_mod.SCHEMA_VERSION == 3
        assert annotations_mod.file_dataset(text) == "Pilot"
        assert deserialize(text) == store

    def test_an_old_file_names_no_dataset_and_still_imports(self):
        old = json.dumps(
            {
                "schema": 2,
                "annotations": [
                    {"participant_id": "p1", "trial_id": "t1", "star": True}
                ],
            }
        )
        assert annotations_mod.file_dataset(old) is None
        store: dict = {}
        applied, skipped = annotations_mod.merge_records(
            store, store_to_records(deserialize(old)), {("p1", "t1")}
        )
        assert (applied, skipped) == (1, 0)
        assert annotations_mod.file_dataset("not json") is None
