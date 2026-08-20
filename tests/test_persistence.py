from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from scanpath_studio import persistence
from scanpath_studio.persistence import (
    cache_status,
    clear_local_state,
    forget_state,
    human_size,
    is_loopback_url,
    persistence_enabled,
    persistence_paused,
    rename_cached_dataset,
    restore_state,
    restored_from_cache,
    save_local_state,
    save_state,
    set_persistence_paused,
    skip_next_local_save,
)


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
    source = {"global_show_heatmap": True}
    save_state(source, tmp_path)

    restored = {}
    assert restore_state(restored, tmp_path)
    assert restored_from_cache(restored)

    empty_cache = {}
    assert not restore_state(empty_cache, tmp_path / "elsewhere")
    assert not restored_from_cache(empty_cache)


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
