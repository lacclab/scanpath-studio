"""Regression coverage for quick-view and full-monitor state transitions."""

from __future__ import annotations

from copy import deepcopy

import pandas as pd
import pytest

from scanpath_studio import controls, tabs
from tests.conftest import APP_SCRIPT

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _viz_store() -> dict:
    return deepcopy(controls._VIZ_WIDGET_DEFAULTS)


def test_illustration_to_scanpath_restores_named_view_defaults(monkeypatch):
    store = _viz_store()
    store.update(
        {
            "global_saccade_render_mode": "Straight",
            "global_fixation_snap_to_line": False,
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
    assert store["global_fixation_snap_to_line"] is True
    assert store["global_saccade_color_mode"] == "One color"
    assert store["global_fixation_opacity"] == 1.0
    assert store["single_animate"] is True

    controls._apply_view_preset("scanpath")

    assert controls._active_quick_view() == "scanpath"
    assert store["global_saccade_render_mode"] == "Straight"
    assert store["global_fixation_snap_to_line"] is False
    assert store["global_saccade_color_mode"] == "One color"
    assert store["global_fixation_opacity"] == 0.7
    assert store["single_animate"] is True
    assert controls._PRE_ILLUSTRATION_STATE not in store


@pytest.mark.parametrize("preset", ["scanpath", "heatmap", "illustration"])
def test_compare_on_and_off_keeps_the_preset(monkeypatch, preset):
    """Compare is a mode, not a design setting — switching it on or
    off leaves the preset highlighted."""
    store = _viz_store()
    store["single_compare_toggle"] = False
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset(preset)
    assert controls._active_quick_view() == preset
    store["single_compare_toggle"] = True
    assert controls._active_quick_view() == preset
    store["single_compare_toggle"] = False
    assert controls._active_quick_view() == preset
    # Back on the preset, a later edit still drifts from it.
    store["global_fixation_opacity"] = 0.33
    assert controls._active_quick_view() == "custom"


def test_leaving_illustration_does_not_leak_an_intervening_edit(monkeypatch):
    store = _viz_store()
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset("illustration")
    store["global_fixation_opacity"] = 0.8
    controls._apply_view_preset("heatmap")

    assert store["global_fixation_opacity"] == 0.7
    assert store["global_saccade_render_mode"] == "Straight"
    assert store["global_fixation_snap_to_line"] is False
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


def test_reset_settings_discards_the_quick_view_selection(monkeypatch):
    store = _viz_store()
    monkeypatch.setattr(controls.st, "session_state", store)
    monkeypatch.setattr(controls.st, "query_params", {})
    controls._apply_view_preset("illustration")
    assert store[controls._QUICK_VIEW_SELECTION_KEY] == "illustration"

    controls.reset_viz_settings()

    assert controls._QUICK_VIEW_SELECTION_KEY not in store


def test_custom_quick_view_remembers_manual_settings(monkeypatch):
    store = _viz_store()
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset("scanpath")
    # The real callback is followed by a rerun, where the rail captures the
    # complete named-view baseline before any manual control can be edited.
    assert controls._active_quick_view() == "scanpath"
    store["global_fixation_opacity"] = 0.42
    assert controls._active_quick_view() == "custom"

    controls._apply_view_preset("heatmap")
    assert controls._active_quick_view() == "heatmap"
    assert store["global_fixation_opacity"] == 0.7
    controls._apply_view_preset("custom")

    assert controls._active_quick_view() == "custom"
    assert store["global_fixation_opacity"] == 0.42


def test_the_custom_tile_keeps_compare_and_the_replay_settings(monkeypatch):
    """Every view tile, Custom included, leaves Compare and the replay as they
    are: Custom brings back its own design, not the viewing it was left in."""
    store = _viz_store()
    store.update({"single_compare_toggle": False, "single_playback_speed": 1.0})
    monkeypatch.setattr(controls.st, "session_state", store)
    controls._choose_plot_view("scanpath", None)
    assert controls._active_quick_view() == "scanpath"
    store["global_fixation_opacity"] = 0.42
    assert controls._active_quick_view() == "custom"
    controls._choose_plot_view("heatmap", "custom")
    assert controls._active_quick_view() == "heatmap"
    viewing = {
        "single_compare_toggle": True,
        "single_playback_speed": 2.0,
        "global_anim_autoplay": False,
        "global_anim_grid_step_ms": 40,
        "global_anim_max_frames": 900,
    }
    store.update(viewing)

    controls._choose_plot_view("custom", "heatmap")

    assert store["global_fixation_opacity"] == 0.42
    assert store["global_show_heatmap"] is False
    assert {key: store[key] for key in viewing} == viewing


def test_view_mode_settings_neither_drift_nor_change_with_a_tile(monkeypatch):
    """The keys every tile keeps are exactly the ones the drift check skips:
    changing the replay leaves the view lit, and no tile changes it back."""
    store = _viz_store()
    store.update({"single_compare_toggle": False, "single_playback_speed": 1.0})
    monkeypatch.setattr(controls.st, "session_state", store)
    controls._choose_plot_view("scanpath", None)
    assert controls._active_quick_view() == "scanpath"
    viewing = {
        "single_compare_toggle": True,
        "single_playback_speed": 2.0,
        "global_anim_autoplay": False,
        "global_anim_quality": "Custom",
        "global_anim_grid_step_ms": 40,
        "global_anim_max_frames": 900,
    }
    assert all(controls._is_view_mode_key(key) for key in viewing)
    store.update(viewing)
    assert controls._active_quick_view() == "scanpath"

    current = "scanpath"
    for tile in ("heatmap", "illustration", "gaze_over_time", "custom", "scanpath"):
        controls._choose_plot_view(tile, current)
        assert controls._active_quick_view() == tile
        assert {key: store[key] for key in viewing} == viewing, tile
        current = tile


def test_a_view_sets_both_readings_marker_size(monkeypatch):
    """A view's marker size reaches Compare's per-reading sizes, and the next
    view puts them back with the rest of its defaults."""
    store = _viz_store()
    store.update({"cmp0_marker_size_range": (10, 30), "cmp1_marker_size_range": (5, 9)})
    monkeypatch.setattr(controls.st, "session_state", store)
    for name, expected in (("gaze_over_time", (4, 4)), ("heatmap", (8, 24))):
        controls._apply_view_preset(name)
        assert store["global_marker_size_range"] == expected
        assert store["cmp0_marker_size_range"] == expected
        assert store["cmp1_marker_size_range"] == expected


def test_scanpath_quick_view_clears_custom_configuration(monkeypatch):
    store = _viz_store()
    store.update(
        {
            "global_fixation_opacity": 0.31,
            "global_fixation_color": "#abcdef",
            "global_show_heatmap": True,
            "global_canvas_width": 999,
            "_canvas_seeded_for": "demo",
        }
    )
    monkeypatch.setattr(controls.st, "session_state", store)
    monkeypatch.setattr(controls.st, "query_params", {"fixation_opacity": "0.31"})

    controls._apply_view_preset("scanpath")

    assert store["global_fixation_opacity"] == 0.7
    assert store["global_fixation_color"] == controls.DEFAULT_FIXATION_COLOR
    assert store["global_show_heatmap"] is False
    assert "global_canvas_width" not in store
    assert "_canvas_seeded_for" not in store
    assert controls.st.query_params == {}


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


@pytest.mark.parametrize("key", ["background_image", "background_image_b"])
def test_a_stimulus_page_replaced_on_disk_misses_the_figure_cache(key, tmp_path):
    """The figure embeds the page's bytes, so its cache key follows the file at
    that path, not only the path: a page re-exported over the old one shows."""
    import os

    words = pd.DataFrame({"word_id": [1], "x": [0.0], "y": [0.0]})
    fixations = pd.DataFrame({"x": [1.0], "y": [1.0], "duration_ms": [200.0]})
    page = tmp_path / "page.png"
    page.write_bytes(b"\x89PNG first")
    first = tabs._figure_input_key(words, fixations, {key: str(page)})
    assert tabs._figure_input_key(words, fixations, {key: str(page)}) == first
    # A copy that keeps the old page's size and modification time (`cp -p`).
    stamp = page.stat()
    page.write_bytes(b"\x89PNG other")
    os.utime(page, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert page.stat().st_size == stamp.st_size
    assert tabs._figure_input_key(words, fixations, {key: str(page)}) != first
    # A missing file and an inline page still make a key.
    page.unlink()
    assert tabs._figure_input_key(words, fixations, {key: str(page)})
    assert tabs._figure_input_key(words, fixations, {key: "data:image/png;base64,AA=="})


def test_every_page_path_the_figure_embeds_is_stamped_in_its_key():
    """The figure settings that name a page file are the ones
    `_figure_input_key` stamps; a new one must be added there."""
    from dataclasses import fields

    from scanpath_studio.plots import FigureSettings

    paths = {
        f.name
        for f in fields(FigureSettings)
        if f.name.startswith("background_image")
        and not f.name.removesuffix("_b").endswith(("_size", "_origin", "_opacity"))
    }
    assert paths == tabs._IMAGE_PATH_INPUTS


# --- narrowing the trial pool is not a design edit ---------------------------


def test_mirror_keys_and_late_defaults_are_not_drift():
    """What the drift check leaves out, without booting the app."""
    applied = {"global_fixation_opacity": 0.7, "global_show_saccades": True}
    late = {
        **applied,
        # A slider's typed twin, registered the first time its popover draws,
        # and the span-highlight mirrors a saved design can still hold.
        "global_fixation_opacity__num": 0.7,
        "global_marker_size_range__num_lo": 8,
        "global_highlight_span_on": True,
        "global_highlight_span_mode": "Mark text",
        # A control registered late, at its widget default.
        "global_saccade_width": controls._VIZ_WIDGET_DEFAULTS["global_saccade_width"],
    }
    assert not controls._design_drifted(applied, late)
    assert controls._design_drifted(applied, {**late, "global_fixation_opacity": 0.4})
    # A key with no default (an explicit colour range) appearing is a choice
    # the user made.
    assert controls._design_drifted(
        applied, {**applied, "global_heatmap_color_range": (0.0, 10.0)}
    )


def test_hover_field_options_read_the_columns_of_an_empty_trial():
    empty = pd.DataFrame(columns=["order_in_trial", "duration_ms", "word_id", "x"])
    assert controls.hover_field_options(empty)[:3] == [
        "order_in_trial",
        "duration_ms",
        "word_id",
    ]


@pytest.fixture()
def booted_app():
    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=120)
    assert not at.exception, at.exception
    assert at.session_state["_quick_view_selection"] == "scanpath"
    return at


class TestTrialFiltersKeepTheDesign:
    """Boot the real app, narrow the pool, and watch the preset highlight."""

    @staticmethod
    def _run(at) -> None:
        at.run(timeout=120)
        assert not at.exception, at.exception

    def test_a_trial_filter_leaves_the_preset_alone(self, booted_app):
        at = booted_app
        hover = list(at.session_state["global_fixation_hover_fields"])
        # A trial with no fixations must not wipe the user's hover picks; the
        # unit test above covers that, since the demo has no such reader, so
        # this narrows by the demo's two readers.
        for participant in (["l37_273"], ["l7_183"], []):
            box = next(m for m in at.multiselect if m.key == "filter_participants")
            box.set_value(participant)
            self._run(at)
            assert at.session_state["_quick_view_selection"] == "scanpath", participant
        assert list(at.session_state["global_fixation_hover_fields"]) == hover
        # Every trial the demo keeps is answered correctly, so a Correct
        # filter does not draw; a condition filter with two values stands in.
        for pick_first in (True, False):
            level = next(
                m for m in at.multiselect if m.key == "filter_difficulty_level"
            )
            picked = [level.options[0]] if pick_first else []
            level.set_value(picked)
            self._run(at)
            assert at.session_state["_quick_view_selection"] == "scanpath", picked

    def test_a_preset_owned_control_still_goes_custom(self, booted_app):
        at = booted_app
        at.session_state["global_show_saccades"] = False
        self._run(at)
        assert at.session_state["_quick_view_selection"] == "custom"


def test_the_heatmap_preset_turns_the_highlight_off(monkeypatch):
    """The Heatmap design is the word colours and nothing else, so a
    highlighted span is switched off with the other layers."""
    store = _viz_store()
    store["global_critical_span_style"] = "Mark text"
    monkeypatch.setattr(controls.st, "session_state", store)

    controls._apply_view_preset("heatmap")
    assert store["global_critical_span_style"] == "None"
    assert controls._active_quick_view() == "heatmap"
    # The Scanpath design leaves it at the app's default, which is off too.
    controls._apply_view_preset("scanpath")
    assert store["global_critical_span_style"] == "None"


@pytest.mark.timeout(180)
def test_animate_says_why_layers_are_greyed():
    """During Animation each disabled layer explains why in its hover text."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at.run()
    greyed = ("global_show_heatmap", "global_show_raw_gaze")
    assert not any(at.toggle(key=key).help for key in greyed)
    at.toggle(key="single_animate").set_value(True).run()
    assert not at.exception
    assert not at.toggle(key="global_show_fix").disabled
    for key in greyed:
        toggle = at.toggle(key=key)
        assert toggle.disabled, key
        assert (
            toggle.help
            == controls._ANIMATE_GREYS[
                {
                    "global_show_heatmap": "heatmap",
                    "global_show_raw_gaze": "rawgaze",
                }[key]
            ]
        )
