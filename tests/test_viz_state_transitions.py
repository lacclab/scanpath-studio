"""Regression coverage for quick-view and full-monitor state transitions."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd

from scanpath_studio import controls, tabs


def _viz_store() -> dict:
    return deepcopy(controls._VIZ_WIDGET_DEFAULTS)


def test_illustration_to_scanpath_restores_shared_style(monkeypatch):
    store = _viz_store()
    store.update(
        {
            "global_saccade_render_mode": "Straight",
            "global_fixation_snap_to_word": False,
            "global_saccade_color_mode": "By type",
            "global_fixation_opacity": 0.45,
            # Animate is a render mode, not a quick-view owner. It must survive
            # both preset callbacks without changing their semantics.
            "single_animate": True,
        }
    )
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset("illustration")

    assert controls._active_quick_view() == "illustration"
    assert store["global_saccade_render_mode"] == "Arc"
    assert store["global_fixation_snap_to_word"] is True
    assert store["global_saccade_color_mode"] == "Uniform"
    assert store["global_fixation_opacity"] == 1.0
    assert store["single_animate"] is True

    controls._apply_view_preset("scanpath")

    assert controls._active_quick_view() == "scanpath"
    assert store["global_saccade_render_mode"] == "Straight"
    assert store["global_fixation_snap_to_word"] is False
    assert store["global_saccade_color_mode"] == "By type"
    assert store["global_fixation_opacity"] == 0.45
    assert store["single_animate"] is True
    assert controls._PRE_ILLUSTRATION_STATE not in store


def test_leaving_illustration_keeps_an_explicit_intervening_edit(monkeypatch):
    store = _viz_store()
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset("illustration")
    store["global_fixation_opacity"] = 0.8
    controls._apply_view_preset("heatmap")

    assert store["global_fixation_opacity"] == 0.8
    assert store["global_saccade_render_mode"] == "Straight"
    assert store["global_fixation_snap_to_word"] is False
    assert controls._active_quick_view() == "heatmap"


def test_restored_illustration_without_snapshot_can_exit_to_scanpath(monkeypatch):
    store = _viz_store()
    store.update(controls._VIEW_PRESETS["illustration"])
    monkeypatch.setattr(controls.st, "session_state", store)
    assert controls._PRE_ILLUSTRATION_STATE not in store

    controls._apply_view_preset("scanpath")

    assert controls._active_quick_view() == "scanpath"
    for key in controls._ILLUSTRATION_OVERRIDE_KEYS:
        assert store[key] == controls._VIZ_WIDGET_DEFAULTS[key]


def test_reset_settings_discards_the_illustration_restore_snapshot(monkeypatch):
    store = _viz_store()
    monkeypatch.setattr(controls.st, "session_state", store)
    monkeypatch.setattr(controls.st, "query_params", {})
    controls._apply_view_preset("illustration")
    assert controls._PRE_ILLUSTRATION_STATE in store

    controls.reset_viz_settings()

    assert controls._PRE_ILLUSTRATION_STATE not in store


def test_full_monitor_changes_only_framing_state_and_cache_input(monkeypatch):
    store = _viz_store()
    store.update(
        {
            "global_show_words": True,
            "global_show_heatmap": True,
            "global_fixation_opacity": 0.55,
            "global_saccade_color": "#123456",
            "global_bg_choice": "Gray",
        }
    )
    monkeypatch.setattr(controls.st, "session_state", store)
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "x": [100.0, 180.0],
            "y": [120.0, 120.0],
            "duration_ms": [100.0, 200.0],
            "order_in_trial": [1, 2],
        }
    )
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "text": ["one", "two"],
            "x_start": [80.0, 160.0],
            "x_end": [140.0, 220.0],
            "y_start": [100.0, 100.0],
            "y_end": [140.0, 140.0],
        }
    )

    on = controls.viz_settings_from_state(fixations, 18, words=words)
    wire_before = {
        key: deepcopy(value)
        for key, value in store.items()
        if key.startswith(("global_", "single_", "cmp"))
    }
    store["global_fit_to_monitor"] = False
    off = controls.viz_settings_from_state(fixations, 18, words=words)
    wire_after = {
        key: deepcopy(value)
        for key, value in store.items()
        if key.startswith(("global_", "single_", "cmp"))
    }

    changed = {
        key
        for key in wire_before | wire_after
        if wire_before.get(key) != wire_after.get(key)
    }
    assert changed == {"global_fit_to_monitor"}
    assert on["fit_to_monitor"] is True
    assert off["fit_to_monitor"] is False
    assert {k: v for k, v in on.items() if k != "fit_to_monitor"} == {
        k: v for k, v in off.items() if k != "fit_to_monitor"
    }

    # The static figure cache must miss for the framing transition while every
    # other build input stays identical.
    key_on = tabs._figure_input_key(words, fixations, on)
    key_off = tabs._figure_input_key(words, fixations, off)
    assert key_on != key_off
    assert dict(key_on)["fit_to_monitor"] is True
    assert dict(key_off)["fit_to_monitor"] is False
