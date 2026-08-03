from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

import scanpath_studio.persistence as persistence

from scanpath_studio.persistence import (
    forget_state,
    persistence_enabled,
    restore_state,
    save_local_state,
    save_state,
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
