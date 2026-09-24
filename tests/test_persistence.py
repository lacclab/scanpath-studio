from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pytest

from scanpath_studio import persistence
from scanpath_studio.annotations import ANNOTATIONS_STATE_KEY
from scanpath_studio.persistence import (
    cache_status,
    clear_local_state,
    forget_state,
    human_size,
    is_loopback_url,
    persistence_enabled,
    persistence_paused,
    rename_cached_dataset,
    restore_local_state,
    restore_state,
    restored_from_cache,
    restored_summary,
    save_local_state,
    save_state,
    set_persistence_paused,
    skip_next_local_save,
)
from scanpath_studio.session_keys import DESIGN_PRESETS


def _dataset():
    return {
        "words": pd.DataFrame({"trial_id": ["t1"], "text": ["hello"]}),
        "fixations": pd.DataFrame({"trial_id": ["t1"], "duration_ms": [120]}),
        "raw_gaze": pd.DataFrame(),
        "filter_fields": ["condition"],
        "composite_trial_columns": ["participant", "item"],
        "schemas": {"words": {"trial": "trial_id"}},
    }


def test_enabled_only_for_loopback_without_override():
    assert persistence_enabled("http://localhost:8501", {})
    assert persistence_enabled("http://127.0.0.1:8501/path", {})
    assert not persistence_enabled("https://scanpath-studio.example", {})
    assert persistence_enabled(
        "https://public.example", {"SCANPATH_STUDIO_PERSIST": "1"}
    )
    assert not persistence_enabled(
        "http://localhost:8501", {"SCANPATH_STUDIO_PERSIST": "0"}
    )


class TestTheGateTrustsTheServerNotTheBrowser:
    """ENG-56 — inside a Streamlit server the gate reads ``server.address``.

    It used to read ``st.context.url``, which Streamlit copies from the browser's
    own message, so a peer on the network could connect to an all-interfaces
    server claiming ``http://localhost/`` and get the owner's cached datasets.
    """

    @pytest.fixture
    def serving(self, monkeypatch):
        from streamlit import config, runtime

        monkeypatch.setattr(runtime, "exists", lambda: True)
        before = config.get_option("server.address")
        yield lambda address: config.set_option("server.address", address)
        config.set_option("server.address", before)

    def test_a_claimed_localhost_url_is_not_enough(self, serving):
        serving(None)  # Streamlit's default: every interface
        assert not persistence_enabled("http://localhost:8501", {})
        serving("0.0.0.0")
        assert not persistence_enabled("http://127.0.0.1:8501", {})

    @pytest.mark.parametrize("address", ["127.0.0.1", "::1", "[::1]", "localhost"])
    def test_a_loopback_bound_server_persists(self, serving, address):
        serving(address)
        assert persistence_enabled("https://any.example", {})
        assert persistence.server_bound_to_loopback()

    def test_the_environment_still_wins_both_ways(self, serving):
        serving(None)
        assert persistence_enabled("", {"SCANPATH_STUDIO_PERSIST": "1"})
        serving("127.0.0.1")
        assert not persistence_enabled("", {"SCANPATH_STUDIO_PERSIST": "0"})

    def test_cache_status_reports_the_same_gate(self, serving, tmp_path):
        serving(None)
        assert not cache_status(tmp_path, url="http://localhost", environ={})["enabled"]
        serving("127.0.0.1")
        assert cache_status(tmp_path, url="", environ={})["enabled"]


def test_the_desktop_app_binds_loopback_so_it_keeps_its_cache():
    """ENG-56 made the cache follow the bind address, so the launcher's is load-bearing."""
    import re
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "desktop" / "launcher.py"
    ).read_text(encoding="utf-8")
    bound = re.findall(r'"--server\.address=([^"]+)"', source)
    assert bound, "desktop/launcher.py no longer passes --server.address"
    assert all(persistence._is_loopback_host(address) for address in bound), bound


def test_is_loopback_url_is_independent_of_persistence_overrides():
    assert is_loopback_url("http://localhost:8501")
    assert is_loopback_url("http://127.0.0.1:8501/path")
    assert is_loopback_url("http://[::1]:8501")
    assert not is_loopback_url("https://scanpath-studio.example")


def test_round_trip_datasets_settings_mappings_and_annotations(tmp_path):
    source = {
        "_datasets": {"My corpus": _dataset()},
        "data_source_choice": "My corpus",
        "global_show_heatmap": False,
        "global_word_hover_fields": ["text", "surprisal"],
        "col_map_fix_x": "gaze_x",
        "trial_annotations": {
            ("p1", "t1"): {"star": True, "tags": ["Review"], "note": "check"}
        },
    }
    assert save_state(source, tmp_path)
    restored = {}
    assert restore_state(restored, tmp_path)
    pd.testing.assert_frame_equal(
        restored["_datasets"]["My corpus"]["words"],
        source["_datasets"]["My corpus"]["words"],
    )
    assert restored["data_source_choice"] == "My corpus"
    assert restored["global_show_heatmap"] is False
    assert restored["global_word_hover_fields"] == ["text", "surprisal"]
    assert restored["col_map_fix_x"] == "gaze_x"
    assert restored["trial_annotations"][("p1", "t1")]["note"] == "check"


def test_restore_is_once_only_and_does_not_overwrite_seeded_values(tmp_path):
    source = {"global_show_heatmap": True}
    save_state(source, tmp_path)
    restored = {"global_show_heatmap": False}
    assert restore_state(restored, tmp_path)
    assert restored["global_show_heatmap"] is False
    assert not restore_state(restored, tmp_path)


def test_setting_change_reuses_persisted_dataset_files(tmp_path):
    source = {
        "_datasets": {"Corpus": _dataset()},
        "global_show_heatmap": True,
    }
    assert save_state(source, tmp_path)
    frame_path = next((tmp_path / "datasets").glob("*-words.parquet"))
    before = frame_path.stat().st_mtime_ns

    source["global_show_heatmap"] = False

    assert save_state(source, tmp_path)
    assert frame_path.stat().st_mtime_ns == before


def test_concurrent_sessions_leave_a_valid_cache(tmp_path):
    sessions = [
        {
            "_datasets": {f"Corpus {index}": _dataset()},
            "global_show_heatmap": bool(index % 2),
        }
        for index in range(4)
    ]

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(pool.map(lambda session: save_state(session, tmp_path), sessions))

    restored = {}
    assert restore_state(restored, tmp_path)
    assert restored["_datasets"]


def test_local_save_failure_does_not_escape_into_the_app(tmp_path, monkeypatch):
    invalid_root = tmp_path / "not-a-directory"
    invalid_root.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr(persistence, "state_directory", lambda: invalid_root)

    assert not save_local_state({}, "http://localhost:8501")


def test_forget_removes_only_known_cache_files(tmp_path):
    source = {"_datasets": {"Corpus": _dataset()}}
    save_state(source, tmp_path)
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    forget_state(tmp_path)
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "manifest.json").exists()


# ENG-30 — the cache is inspectable and controllable from outside itself. These
# pin the read-only status dict (app panel / CLI / api.cache_status all render
# it) and the two controls: pause saving, and forget what was saved.


def test_cache_status_describes_what_is_stored(tmp_path):
    session = {
        "_datasets": {"Corpus": _dataset()},
        "global_show_heatmap": True,
        "trial_annotations": {("p1", "t1"): {"star": True, "tags": [], "note": ""}},
    }
    save_state(session, tmp_path)

    # Explicit environ: the ambient one may carry SCANPATH_STUDIO_PERSIST from
    # another test or the developer's shell.
    status = cache_status(tmp_path, url="http://localhost:8501", environ={})

    assert status["enabled"] and status["exists"] and status["readable"]
    assert status["directory"] == str(tmp_path)
    assert [entry["name"] for entry in status["datasets"]] == ["Corpus"]
    # 1 word row + 1 fixation row + an empty raw-gaze frame.
    assert status["datasets"][0]["rows"] == {"words": 1, "fixations": 1, "raw_gaze": 0}
    assert status["rows"] == 2
    assert status["annotations"] == 1
    assert status["settings"] >= 1
    assert status["bytes"] > 0
    assert status["saved_at"]


def test_cache_status_on_an_empty_and_a_hosted_deployment(tmp_path):
    empty = cache_status(tmp_path, url="http://localhost:8501", environ={})
    assert not empty["exists"] and not empty["readable"]
    assert empty["datasets"] == [] and empty["bytes"] == 0 and empty["rows"] == 0

    hosted = cache_status(tmp_path, url="https://scanpath-studio.example", environ={})
    assert not hosted["enabled"] and hosted["override"] == ""

    forced_off = cache_status(
        tmp_path,
        url="http://localhost:8501",
        environ={"SCANPATH_STUDIO_PERSIST": "0"},
    )
    assert not forced_off["enabled"] and forced_off["override"] == "off"


def test_cache_status_flags_an_unreadable_manifest(tmp_path):
    (tmp_path / "manifest.json").write_text("{ not json", encoding="utf-8")
    status = cache_status(tmp_path, url="http://localhost:8501", environ={})
    assert status["exists"] and not status["readable"]

    (tmp_path / "manifest.json").write_text('{"schema": 99}', encoding="utf-8")
    newer = cache_status(tmp_path, url="http://localhost:8501", environ={})
    # A newer schema is present but restore_state refuses it, so the panel must
    # not claim the session is safely stored.
    assert newer["exists"] and not newer["readable"] and newer["schema"] == 99


def test_pausing_stops_saving_and_resuming_writes_again(tmp_path, monkeypatch):
    import scanpath_studio.persistence as module

    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr(module, "state_directory", lambda *a, **k: tmp_path)
    session = {"_datasets": {"Corpus": _dataset()}}

    assert save_local_state(session, "http://localhost:8501")
    set_persistence_paused(session, True)
    assert persistence_paused(session)
    session["global_show_heatmap"] = False  # a change that would otherwise save
    assert not save_local_state(session, "http://localhost:8501")

    set_persistence_paused(session, False)
    assert save_local_state(session, "http://localhost:8501")


def test_clear_local_state_deletes_files_and_session_bookkeeping(tmp_path, monkeypatch):
    import scanpath_studio.persistence as module

    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr(module, "state_directory", lambda *a, **k: tmp_path)
    session = {"_datasets": {"Corpus": _dataset()}}
    save_local_state(session, "http://localhost:8501")

    clear_local_state(session)

    assert not (tmp_path / "manifest.json").exists()
    assert not cache_status(tmp_path, url="http://localhost:8501", environ={})["exists"]
    # The loaded data is untouched, and the next save rewrites from scratch.
    assert session["_datasets"]
    assert save_local_state(session, "http://localhost:8501")


def test_clear_local_state_survives_an_undeletable_cache(tmp_path, monkeypatch):
    """A locked cache file must not wedge Clear recovery / Reset everything.

    Those two actions are what a user reaches for when the session is already
    broken, so the disk half is best-effort: it reports ``False`` and the
    in-session bookkeeping is forgotten either way.
    """
    import scanpath_studio.persistence as module

    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr(module, "state_directory", lambda *a, **k: tmp_path)
    session = {"_datasets": {"Corpus": _dataset()}}
    save_local_state(session, "http://localhost:8501")
    assert module._LAST_FINGERPRINT_KEY in session

    def _refuse(root):
        raise PermissionError(f"{root}/manifest.json is read-only")

    monkeypatch.setattr(module, "forget_state", _refuse)

    assert clear_local_state(session) is False
    assert module._LAST_FINGERPRINT_KEY not in session
    assert session["_datasets"]


def test_clear_can_skip_one_rewrite_without_pausing_future_saves(tmp_path, monkeypatch):
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
    session = {"_datasets": {"Corpus": _dataset()}}
    assert save_local_state(session, "http://localhost:8501")

    clear_local_state(session)
    skip_next_local_save(session)

    assert not save_local_state(session, "http://localhost:8501")
    assert not (tmp_path / "manifest.json").exists()
    assert not persistence_paused(session)
    session["global_show_heatmap"] = True
    assert save_local_state(session, "http://localhost:8501")


def test_restored_flag_marks_only_a_session_that_got_data_back(tmp_path):
    source = {"_datasets": {"Corpus": _dataset()}}
    save_state(source, tmp_path)

    restored = {}
    assert restore_state(restored, tmp_path)
    assert restored_from_cache(restored)
    assert restored_summary(restored)["datasets"] == 1

    empty_cache = {}
    assert not restore_state(empty_cache, tmp_path / "elsewhere")
    assert not restored_from_cache(empty_cache)
    assert restored_summary(empty_cache) == {}


class TestOnlyARealRecoveryIsAnnounced:
    """UX-136 — every rerun writes the cache, so a session that has only ever
    changed view settings still leaves a manifest behind. Restoring one is not
    "recovering your last session", and saying so was worst in exactly the case
    the user hit: right after clearing the cache by hand, where the toast reads
    as "clearing it did nothing"."""

    def test_settings_alone_restore_silently(self, tmp_path, monkeypatch):
        monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
        save_state({"global_show_heatmap": True}, tmp_path)
        restored = {}

        # The mechanism ran — silence is about the announcement, not the data …
        assert restore_state(restored, tmp_path)
        assert restored["global_show_heatmap"] is True
        # … and it is the app-facing wrapper that decides whether to say so.
        assert not restored_from_cache(restored)
        assert not restore_local_state({}, "http://localhost:8501")
        assert restored_summary(restored) == {
            "datasets": 0,
            "annotations": 0,
            "designs": 0,
            "metadata": 0,
        }

    def test_an_annotation_is_worth_announcing(self, tmp_path):
        save_state(
            {ANNOTATIONS_STATE_KEY: {("p1", "t1"): {"favorite": True, "tags": ["a"]}}},
            tmp_path,
        )
        restored = {}

        assert restore_state(restored, tmp_path)
        assert restored_from_cache(restored)
        assert restored_summary(restored)["annotations"] == 1

    def test_a_saved_design_is_worth_announcing(self, tmp_path):
        save_state({DESIGN_PRESETS: {"Mine": {"global_show_heatmap": True}}}, tmp_path)
        restored = {}

        assert restore_state(restored, tmp_path)
        assert restored_from_cache(restored)
        assert restored_summary(restored)["designs"] == 1

    def test_what_this_session_already_had_is_not_counted_as_recovered(self, tmp_path):
        """Restoring is a `setdefault`, so a dataset, annotation store or design
        library already in the session keeps its own — nothing came back."""
        save_state(
            {
                "_datasets": {"Corpus": _dataset()},
                DESIGN_PRESETS: {"Mine": {}},
                ANNOTATIONS_STATE_KEY: {("p1", "t1"): {"favorite": True}},
            },
            tmp_path,
        )
        live = {
            "_datasets": {"Corpus": _dataset()},
            DESIGN_PRESETS: {"Mine": {}},
            ANNOTATIONS_STATE_KEY: {},
        }

        assert restore_state(live, tmp_path)
        assert not restored_from_cache(live)

    def test_clearing_the_cache_takes_the_announcement_with_it(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
        save_state({"_datasets": {"Corpus": _dataset()}}, tmp_path)
        restored = {}
        assert restore_state(restored, tmp_path)

        clear_local_state(restored)
        assert not restored_from_cache(restored)
        assert restored_summary(restored) == {}


def test_human_size_reads_as_a_file_size():
    assert human_size(0) == "0 B"
    assert human_size(900) == "900 B"
    assert human_size(2048) == "2.0 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"


def test_upgrade_from_a_manifest_without_row_counts(tmp_path):
    """A cache written before ``rows`` existed must not report 0 rows.

    ``restore_state`` seeds ``_LAST_DATASET_ENTRIES_KEY`` from the manifest and
    ``save_state`` re-emits those entries verbatim whenever the frames are
    unchanged — so a row-less entry would otherwise survive every later save and
    the panel would read "1 dataset · 0 rows · <size> on disk" forever.
    """
    session = {"_datasets": {"Corpus": _dataset()}, "global_show_heatmap": True}
    save_state(session, tmp_path)

    # Rewrite the manifest the way the pre-ENG-30 writer did.
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest["datasets"].values():
        entry.pop("rows", None)
    path.write_text(json.dumps(manifest), encoding="utf-8")

    legacy = cache_status(tmp_path, url="http://localhost:8501", environ={})
    assert legacy["readable"]
    # Unknown, NOT zero — the size is real, so a 0 would contradict it.
    assert legacy["rows"] is None

    restored = {}
    assert restore_state(restored, tmp_path)
    restored["global_show_heatmap"] = False  # a settings-only change → reuse path
    assert save_state(restored, tmp_path)

    healed = cache_status(tmp_path, url="http://localhost:8501", environ={})
    assert healed["rows"] == 2
    assert healed["datasets"][0]["rows"] == {"words": 1, "fixations": 1, "raw_gaze": 0}
    # The backfill must not have rewritten the frames — it only counts them.
    assert (tmp_path / "datasets").is_dir()


def test_setup_snapshot_survives_a_cache_round_trip(tmp_path):
    """CMP-8 §1: the per-dataset `setup` key must ride the recovery cache.

    Without it a restored session would reopen an uploaded corpus with no
    geometry — the exact hole the snapshot exists to close — and the compare
    figure would have nothing to draw B's panel to scale with.
    """
    from scanpath_studio.experimental_setup import Provenance, SetupSnapshot

    snapshot = SetupSnapshot(
        canvas_width=1680,
        canvas_height=1050,
        monitor_width_mm=474.0,
        screen_provenance=Provenance.MEASURED,
        geometry_provenance=Provenance.SKIPPED,
        text_provenance=Provenance.ASSUMED,
    )
    payload = _dataset()
    payload["setup"] = snapshot.to_dict()
    assert save_state({"_datasets": {"Corpus": payload}}, tmp_path)

    restored = {}
    assert restore_state(restored, tmp_path)
    stored = restored["_datasets"]["Corpus"]["setup"]
    assert SetupSnapshot.from_dict(stored) == snapshot


def test_a_cache_written_before_the_setup_key_still_restores(tmp_path):
    """An older cache has no `setup` at all; it must degrade, not raise."""
    from scanpath_studio.experimental_setup import SetupSnapshot

    assert save_state({"_datasets": {"Corpus": _dataset()}}, tmp_path)
    restored = {}
    assert restore_state(restored, tmp_path)
    entry = restored["_datasets"]["Corpus"]
    assert "setup" not in entry
    fallback = SetupSnapshot(canvas_width=999)
    assert SetupSnapshot.from_dict(entry.get("setup"), fallback=fallback) == fallback


# DATA-23 — a rename moves the cached Parquet files instead of re-encoding them,
# so the cache never accumulates orphans under the old name's slug.


def test_rename_moves_the_cached_frames_and_keeps_the_restore(tmp_path):
    session = {"_datasets": {"Corpus": _dataset()}, "data_source_choice": "Corpus"}
    assert save_state(session, tmp_path)
    before = sorted(path.name for path in (tmp_path / "datasets").glob("*.parquet"))

    session["_datasets"] = {"Renamed": session["_datasets"].pop("Corpus")}
    session["data_source_choice"] = "Renamed"
    assert rename_cached_dataset(session, "Corpus", "Renamed", tmp_path)

    after = sorted(path.name for path in (tmp_path / "datasets").glob("*.parquet"))
    assert len(after) == len(before) and after != before, (
        "the frames should have been renamed in place, not duplicated or rewritten"
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["datasets"]) == {"Renamed"}
    assert manifest["session"]["data_source_choice"] == "Renamed"

    restored = {}
    assert restore_state(restored, tmp_path)
    assert set(restored["_datasets"]) == {"Renamed"}
    pd.testing.assert_frame_equal(
        restored["_datasets"]["Renamed"]["words"],
        _dataset()["words"],
    )


def test_the_save_after_a_rename_does_not_rewrite_the_frames(tmp_path):
    """The whole point of moving the files: the next save is manifest-only."""
    session = {"_datasets": {"Corpus": _dataset()}}
    assert save_state(session, tmp_path)

    session["_datasets"] = {"Renamed": session["_datasets"].pop("Corpus")}
    assert rename_cached_dataset(session, "Corpus", "Renamed", tmp_path)
    frame_path = next((tmp_path / "datasets").glob("*-words.parquet"))
    before = frame_path.stat().st_mtime_ns

    assert save_state(session, tmp_path)
    assert frame_path.stat().st_mtime_ns == before
    assert len(list((tmp_path / "datasets").glob("*.parquet"))) == 3


def test_rename_without_a_cache_on_disk_is_a_no_op_not_an_error(tmp_path):
    session = {"_datasets": {"Renamed": _dataset()}}
    assert rename_cached_dataset(session, "Corpus", "Renamed", tmp_path)
    assert not (tmp_path / "manifest.json").exists()


def test_a_failed_rename_forces_a_full_rewrite_next_save(tmp_path):
    """A half-moved cache must never be trusted — drop the reuse bookkeeping."""
    session = {"_datasets": {"Corpus": _dataset()}}
    assert save_state(session, tmp_path)
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")

    session["_datasets"] = {"Renamed": session["_datasets"].pop("Corpus")}
    assert not rename_cached_dataset(session, "Corpus", "Renamed", tmp_path)
    assert persistence._LAST_DATASET_ENTRIES_KEY not in session

    assert save_state(session, tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["datasets"]) == {"Renamed"}
    restored = {}
    assert restore_state(restored, tmp_path)
    assert set(restored["_datasets"]) == {"Renamed"}


class TestRememberedDatasetCounts:
    """DATA-32 — a dataset's headline counts are computed once and remembered.

    The point of the item is the *invalidation*, not the store: a remembered
    count is a number on screen that claims to describe the data, so it must
    never outlive the rows it was taken from.
    """

    @staticmethod
    def _frames():
        import pandas as pd

        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t1", "t2"],
                "word_id": [0, 1, 0],
                "text": ["the", "cat", "sat"],
                "x": [10.0, 60.0, 10.0],
                "y": [10.0, 10.0, 50.0],
                "width": [40.0, 40.0, 40.0],
                "height": [20.0, 20.0, 20.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t1", "t2"],
                "x": [20.0, 70.0, 20.0],
                "y": [15.0, 15.0, 55.0],
                "duration_ms": [200.0, 180.0, 220.0],
            }
        )
        return words, fixations

    def test_counted_once_then_reused(self, monkeypatch):
        import streamlit as st

        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_COUNTS_STORE_KEY

        st.session_state.pop(DATASET_COUNTS_STORE_KEY, None)
        words, fixations = self._frames()
        calls = []
        real = app._dataset_counts

        def _counting(_words, _fixations, _raw_gaze, _key):
            calls.append(_key)
            return real(_words, _fixations, _raw_gaze, _key)

        monkeypatch.setattr(app, "_dataset_counts", _counting)
        first = app.remembered_dataset_counts("corpus", words, fixations)
        second = app.remembered_dataset_counts("corpus", words, fixations)
        assert first == second
        assert first["Participants"] == 2
        assert first["Trials"] == 2
        assert first["Words"] == 3
        assert len(calls) == 1, "the second listing recomputed the counts"

    def test_an_unloaded_dataset_shows_what_was_remembered(self):
        import streamlit as st

        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_COUNTS_STORE_KEY

        st.session_state.pop(DATASET_COUNTS_STORE_KEY, None)
        words, fixations = self._frames()
        app.remembered_dataset_counts("corpus", words, fixations)
        # The payoff: a corpus opened earlier keeps its row without being read.
        assert app.remembered_dataset_counts("corpus", None, None)["Trials"] == 2
        # …and one never opened stays blank rather than guessed at.
        assert app.remembered_dataset_counts("never-opened", None, None) == {}

    def test_changed_rows_are_recounted(self):
        """The staleness guard: same name, different data — recount."""
        import streamlit as st

        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_COUNTS_STORE_KEY

        st.session_state.pop(DATASET_COUNTS_STORE_KEY, None)
        words, fixations = self._frames()
        app.remembered_dataset_counts("corpus", words, fixations)
        trimmed = fixations.iloc[:2]
        assert app.remembered_dataset_counts("corpus", words, trimmed)["Fixations"] == 2

    def test_a_removed_dataset_loses_its_row(self):
        import streamlit as st

        from scanpath_studio import app
        from scanpath_studio.constants import DATASET_COUNTS_STORE_KEY

        st.session_state.pop(DATASET_COUNTS_STORE_KEY, None)
        words, fixations = self._frames()
        app.remembered_dataset_counts("corpus", words, fixations)
        app.remembered_dataset_counts("other", words, fixations)
        app.forget_dataset_counts(keep={"other"})
        assert app.remembered_dataset_counts("corpus", None, None) == {}
        assert app.remembered_dataset_counts("other", None, None)["Trials"] == 2
        app.forget_dataset_counts()
        assert app.remembered_dataset_counts("other", None, None) == {}

    def test_they_round_trip_through_the_recovery_cache(self, tmp_path):
        from scanpath_studio import persistence
        from scanpath_studio.constants import DATASET_COUNTS_STORE_KEY

        remembered = {"corpus": {"key": ["a", "b"], "counts": {"Trials": 2}}}
        session = {
            "data_source_choice": "corpus",
            DATASET_COUNTS_STORE_KEY: dict(remembered),
        }
        persistence.save_state(session, tmp_path)
        restored: dict = {}
        assert persistence.restore_state(restored, tmp_path)
        assert restored[DATASET_COUNTS_STORE_KEY] == remembered
        # …and forgetting the cache forgets them, which is what the ask named.
        persistence.clear_local_state(restored, tmp_path)
        assert DATASET_COUNTS_STORE_KEY not in restored


class TestTheRecoveryToastPhrase:
    """UX-136 — the toast names what came back, so the claim can be checked
    against the 🗄️ Automatic recovery panel it points at."""

    @staticmethod
    def _recap(**counts):
        from scanpath_studio.app import _restored_recap

        return _restored_recap({persistence._RESTORED_PAYLOAD_KEY: counts})

    def test_one_kind_reads_as_a_count(self):
        assert self._recap(datasets=1) == "1 dataset"
        assert self._recap(datasets=3) == "3 datasets"

    def test_zero_counts_are_left_out_rather_than_padded(self):
        """The panel legitimately shows "0 designs"; a sentence should not."""
        assert self._recap(datasets=2, annotations=0, designs=0) == "2 datasets"

    def test_several_kinds_read_as_a_list(self):
        assert (
            self._recap(datasets=2, annotations=1, designs=4)
            == "2 datasets, 1 annotation and 4 designs"
        )

    def test_nothing_to_report_still_reads_as_a_sentence(self):
        assert self._recap() == "your last session"


class TestAMalformedCacheNeverStopsTheApp:
    """BUG-71 — the manifest is a file on disk, so any JSON can be in it.

    Wrong shapes used to escape as an ``AttributeError`` the restore did not
    catch, and restored values were seeded unchecked into widgets that refuse
    them — both before the 💾 Session dialog that could reset them, on every
    launch. Each case below crashed the app in the pre-beta audit.
    """

    @staticmethod
    def _write(root, manifest) -> None:
        (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    @staticmethod
    def _manifest(**sections):
        return {
            "schema": 1,
            "datasets": {},
            "session": {},
            "annotations": [],
            **sections,
        }

    def test_a_manifest_that_is_not_an_object_is_ignored(self, tmp_path):
        for manifest in ([], None, "x", 3):
            self._write(tmp_path, manifest)
            session = {}
            assert not restore_state(session, tmp_path)
            assert "_datasets" not in session

    def test_a_malformed_dataset_entry_abandons_the_restore_untouched(self, tmp_path):
        self._write(
            tmp_path,
            self._manifest(
                datasets={"x": "str"}, session={"global_show_heatmap": True}
            ),
        )
        session = {}
        assert not restore_state(session, tmp_path)
        # Checked before anything is applied, so nothing is half-restored.
        assert session == {persistence._RESTORED_KEY: True}

    def test_malformed_annotation_records_are_skipped(self, tmp_path):
        good = {"participant_id": "p1", "trial_id": "t1", "star": True}
        self._write(tmp_path, self._manifest(annotations=["x", 5, good]))
        session = {}
        assert restore_state(session, tmp_path)
        assert list(session[ANNOTATIONS_STATE_KEY]) == [("p1", "t1")]

        self._write(tmp_path, self._manifest(annotations={"a": 1}))
        session = {}
        assert restore_state(session, tmp_path)
        assert session[ANNOTATIONS_STATE_KEY] == {}

    def test_values_a_widget_refuses_are_clamped_or_dropped(self, tmp_path):
        self._write(
            tmp_path,
            self._manifest(
                session={
                    "global_fixation_opacity": 7,
                    "global_stimulus_image_opacity": -1,
                    "global_marker_size_range": "abc",
                    "global_order_font_color": "zzz",
                    "global_canvas_width": "wide",
                    "global_show_heatmap": "yes",
                    "global_heatmap_style": "Bogus",
                    "global_line_spacing": float("nan"),
                    "global_text_color": "#123456",
                    "col_map_fix_x": "gaze_x",
                    # Not a key this module writes — a foreign manifest must not
                    # be able to seed arbitrary session state.
                    "_show_upload_wizard": True,
                }
            ),
        )
        session = {}
        assert restore_state(session, tmp_path)
        assert session["global_fixation_opacity"] == 1.0
        assert session["global_stimulus_image_opacity"] == 0.1
        for dropped in (
            "global_marker_size_range",
            "global_order_font_color",
            "global_canvas_width",
            "global_show_heatmap",
            "global_heatmap_style",
            "global_line_spacing",
            "_show_upload_wizard",
        ):
            assert dropped not in session, dropped
        assert session["global_text_color"] == "#123456"
        assert session["col_map_fix_x"] == "gaze_x"

    def test_a_range_comes_back_as_the_tuple_the_widget_writes(self, tmp_path):
        save_state({"global_marker_size_range": (30, 8)}, tmp_path)
        session = {}
        assert restore_state(session, tmp_path)
        assert session["global_marker_size_range"] == (8, 30)

    def test_a_malformed_design_library_keeps_its_good_designs(self, tmp_path):
        self._write(
            tmp_path,
            self._manifest(session={DESIGN_PRESETS: {"ok": {"a": 1}, "bad": "x"}}),
        )
        session = {}
        assert restore_state(session, tmp_path)
        assert session[DESIGN_PRESETS] == {"ok": {"a": 1}}


class TestTheRestoreCrashLoopBreaker:
    """BUG-71 — a restore that breaks the app must not break every launch.

    Its marker is written before the cache is applied and cleared when a run
    that applied it reaches the epilogue (`save_local_state`). A session that
    finds it opens without the cache, keeps the files, pauses saving so they
    stay, and clears the marker so the next reload tries again.
    """

    @pytest.fixture
    def cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
        monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
        save_state({"_datasets": {"Corpus": _dataset()}}, tmp_path)
        return tmp_path

    def test_a_run_that_finishes_clears_the_marker(self, cache):
        marker = cache / persistence.RESTORE_MARKER_NAME
        session = {}
        assert restore_local_state(session, "http://localhost:8501")
        assert marker.is_file()  # applied, not yet known to render
        save_local_state(session, "http://localhost:8501")
        assert not marker.exists()

    def test_nothing_to_restore_leaves_no_marker(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
        monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
        assert not restore_local_state({}, "http://localhost:8501")
        assert not (tmp_path / persistence.RESTORE_MARKER_NAME).exists()

    def test_a_launch_after_one_that_never_finished_skips_the_restore(self, cache):
        manifest = (cache / "manifest.json").read_text(encoding="utf-8")
        crashed = {}
        restore_local_state(crashed, "http://localhost:8501")  # …and never saved

        session = {}
        assert not restore_local_state(session, "http://localhost:8501")
        assert "_datasets" not in session
        assert persistence_paused(session)
        assert persistence.consume_restore_skipped(session)
        assert not persistence.consume_restore_skipped(session)  # said once
        # The stored copy is untouched, and this session cannot overwrite it.
        session["global_show_heatmap"] = True
        assert not save_local_state(session, "http://localhost:8501")
        assert (cache / "manifest.json").read_text(encoding="utf-8") == manifest

        # One strike: the marker went with the skip, so a reload tries again.
        again = {}
        assert restore_local_state(again, "http://localhost:8501")
        assert again["_datasets"]

    def test_clearing_the_cache_takes_the_marker_with_it(self, cache):
        restore_local_state({}, "http://localhost:8501")
        clear_local_state({}, cache)
        assert not (cache / persistence.RESTORE_MARKER_NAME).exists()


def test_a_restore_that_crashes_the_app_does_not_crash_the_next_launch(
    tmp_path, monkeypatch
):
    """End to end (BUG-71): launch one dies after restoring; launch two opens."""
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from scanpath_studio import app
    from tests.conftest import APP_SCRIPT

    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
    save_state({"global_show_heatmap": True}, tmp_path)
    manifest = (tmp_path / "manifest.json").read_text(encoding="utf-8")

    real = app.render_top_menu

    def broken(*args, **kwargs):
        raise RuntimeError("a restored value this build cannot draw")

    monkeypatch.setattr(app, "render_top_menu", broken)
    first = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    first.run()
    assert first.exception  # the crash the breaker exists for

    monkeypatch.setattr(app, "render_top_menu", real)
    second = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=180)
    second.run()
    assert not second.exception, [e.message for e in second.exception]
    assert any("didn't finish opening" in t.value for t in second.toast)
    assert (tmp_path / "manifest.json").read_text(encoding="utf-8") == manifest

    def test_metadata_tables_are_named_in_the_toast(self):
        """DATA-38 — a restored participant table is something a user would
        recognise coming back, so the toast says so."""
        assert self._recap(datasets=1, metadata=2) == "1 dataset and 2 metadata tables"


class TestMetadataTablesInTheRecoveryCache:
    """DATA-38 — attached participant / trial / text tables survive a refresh.

    They were in neither list the cache writes, so a refresh brought the
    dataset back and silently dropped every table attached to it — and with
    them every metadata field in the filter funnel, the chip picker and the
    trial-sort popover.

    DATA-47: the tables belong to a dataset — the session keys hold the
    selected one's (``OWNER_KEY``), the cache files them under its name, and a
    restore returns them to that dataset, reaching the session keys once it is
    selected (``activate_dataset``, which ``app.main`` runs every run)."""

    @staticmethod
    def _attached():
        from scanpath_studio import metadata as md

        return {
            md.OWNER_KEY: "study",
            md.SESSION_KEY: md.build_participant_metadata(
                pd.DataFrame(
                    {
                        "participant_id": ["p1", "p2"],
                        "age": [30, 41],
                        "L1": ["he", "en"],
                    }
                ),
                "participant_id",
                source_name="readers.csv",
            ),
            md.TRIAL_SESSION_KEY: md.build_trial_metadata(
                pd.DataFrame({"trial_id": ["t1", "t2"], "condition": ["easy", "hard"]}),
                "trial_id",
                source_name="trials.csv",
            ),
            md.TEXT_SESSION_KEY: md.build_text_metadata(
                pd.DataFrame({"text_id": ["x1"], "genre": ["news"]}),
                "text_id",
                source_name="texts.csv",
            ),
        }

    def test_all_three_grains_round_trip(self, tmp_path):
        from scanpath_studio import metadata as md

        session = {"_datasets": {"study": _dataset()}, **self._attached()}
        assert save_state(session, tmp_path)
        restored = {}
        assert restore_state(restored, tmp_path)
        md.activate_dataset(restored, "study")

        for key, source in (
            (md.SESSION_KEY, "readers.csv"),
            (md.TRIAL_SESSION_KEY, "trials.csv"),
            (md.TEXT_SESSION_KEY, "texts.csv"),
        ):
            assert restored[key].names == session[key].names
            assert restored[key].source_name == source
        assert list(restored[md.SESSION_KEY].frame["age"]) == [30, 41]
        assert list(restored[md.TRIAL_SESSION_KEY].frame["condition"]) == [
            "easy",
            "hard",
        ]
        assert restored_summary(restored)["metadata"] == 3
        assert restored_from_cache(restored)

    def test_restored_tables_are_marked_so_the_empty_uploader_keeps_them(
        self, tmp_path
    ):
        """The Data page reads an empty uploader as "detach"; a restored table
        has no file in it, so it has to be told apart."""
        from scanpath_studio import metadata as md

        save_state(self._attached(), tmp_path)
        restored = {}
        restore_state(restored, tmp_path)
        md.activate_dataset(restored, "study")
        for grain in ("participant", "trial", "text"):
            assert md.is_restored(restored, grain)
        assert restored[md.RAW_SESSION_KEY] is restored[md.SESSION_KEY].frame

    def test_a_table_already_attached_is_not_overwritten(self, tmp_path):
        from scanpath_studio import metadata as md

        save_state(self._attached(), tmp_path)
        own = md.build_participant_metadata(
            pd.DataFrame({"participant_id": ["p9"], "hand": ["left"]}),
            "participant_id",
            source_name="mine.csv",
        )
        restored = {md.OWNER_KEY: "study", md.SESSION_KEY: own}
        restore_state(restored, tmp_path)
        assert restored[md.SESSION_KEY] is own
        assert not md.is_restored(restored, "participant")
        assert restored_summary(restored)["metadata"] == 2

    def test_attaching_or_changing_a_table_is_a_change_worth_saving(self, tmp_path):
        from scanpath_studio import metadata as md

        session = {"global_show_heatmap": True, md.OWNER_KEY: "study"}
        assert save_state(session, tmp_path)
        assert not save_state(session, tmp_path)
        session.update(self._attached())
        assert save_state(session, tmp_path)
        # Rebuilt from the same rows — what the Data page does on every render,
        # and the participant re-join on every run — is *not* a change …
        session[md.SESSION_KEY] = md.build_participant_metadata(
            session[md.SESSION_KEY].frame, "participant_id", source_name="readers.csv"
        )
        assert not save_state(session, tmp_path)
        # … but a different row is.
        session[md.TEXT_SESSION_KEY] = md.build_text_metadata(
            pd.DataFrame({"text_id": ["x1"], "genre": ["fiction"]}),
            "text_id",
            source_name="texts.csv",
        )
        assert save_state(session, tmp_path)
        restored = {}
        restore_state(restored, tmp_path)
        md.activate_dataset(restored, "study")
        assert list(restored[md.TEXT_SESSION_KEY].frame["genre"]) == ["fiction"]

    def test_a_manifest_without_metadata_still_restores(self, tmp_path):
        """Every manifest written before DATA-38 lacks the key."""
        from scanpath_studio import metadata as md

        save_state({"_datasets": {"study": _dataset()}}, tmp_path)
        manifest = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
        assert "metadata" not in manifest
        restored = {}
        assert restore_state(restored, tmp_path)
        assert md.SESSION_KEY not in restored
        assert restored_summary(restored)["metadata"] == 0

    def test_a_payload_that_no_longer_builds_is_skipped(self, tmp_path):
        from scanpath_studio import metadata as md

        save_state(self._attached(), tmp_path)
        path = tmp_path / persistence.METADATA_FILE
        payloads = json.loads(path.read_text("utf-8"))
        payloads["datasets"]["study"]["participant"]["records"] = [{"no_id": 1}]
        path.write_text(json.dumps(payloads), "utf-8")
        restored = {}
        assert restore_state(restored, tmp_path)
        md.activate_dataset(restored, "study")
        assert md.SESSION_KEY not in restored
        assert md.TRIAL_SESSION_KEY in restored

    def test_the_tables_are_not_rewritten_on_every_settings_change(self, tmp_path):
        """The manifest is rewritten on every layer toggle and trial switch; a
        trial table can run to tens of thousands of rows, so it lives beside the
        manifest and is written only when its content changes."""
        session = {"global_show_heatmap": True, **self._attached()}
        assert save_state(session, tmp_path)
        sidecar = tmp_path / persistence.METADATA_FILE
        manifest = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
        assert manifest["metadata"] == {
            "file": persistence.METADATA_FILE,
            "tables": ["study:participant", "study:trial", "study:text"],
        }
        # Mark the file (trailing whitespace is still valid JSON): a rewrite
        # would drop the mark.
        sidecar.write_text(sidecar.read_text("utf-8") + " ", "utf-8")
        session["global_show_heatmap"] = False
        assert save_state(session, tmp_path)
        assert sidecar.read_text("utf-8").endswith(" ")

    def test_a_reordered_table_is_a_change(self, tmp_path):
        from scanpath_studio import metadata as md

        session = self._attached()
        save_state(session, tmp_path)
        frame = session[md.TRIAL_SESSION_KEY].frame.iloc[::-1]
        session[md.TRIAL_SESSION_KEY] = md.build_trial_metadata(
            frame.reset_index(drop=True), "trial_id", source_name="trials.csv"
        )
        assert save_state(session, tmp_path)

    def test_detaching_every_table_removes_the_file(self, tmp_path):
        session = self._attached()
        save_state(session, tmp_path)
        assert (tmp_path / persistence.METADATA_FILE).is_file()
        for key in list(session):
            session.pop(key)
        session["global_show_heatmap"] = True
        assert save_state(session, tmp_path)
        assert not (tmp_path / persistence.METADATA_FILE).exists()
        manifest = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
        assert "metadata" not in manifest

    def test_a_missing_file_costs_the_tables_not_the_datasets(self, tmp_path):
        from scanpath_studio import metadata as md

        save_state({"_datasets": {"study": _dataset()}, **self._attached()}, tmp_path)
        (tmp_path / persistence.METADATA_FILE).unlink()
        restored = {}
        assert restore_state(restored, tmp_path)
        assert "study" in restored["_datasets"]
        assert md.SESSION_KEY not in restored
        assert restored_summary(restored)["metadata"] == 0

    def test_clearing_the_cache_removes_the_file(self, tmp_path):
        save_state(self._attached(), tmp_path)
        forget_state(tmp_path)
        assert not (tmp_path / persistence.METADATA_FILE).exists()

    def test_cache_status_counts_the_tables(self, tmp_path):
        save_state(self._attached(), tmp_path)
        assert cache_status(tmp_path, environ={})["metadata"] == 3
