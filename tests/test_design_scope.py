"""A saved design records every plot control, not just the rail's `global_*` keys.

A design used to snapshot only `global_*` session keys. That is scanpath A's
filters and styling, but the Compare view keeps its own — each scanpath's styling
(`cmp{0,1}_*`), scanpath B's filters (`cmp1_fixclass_*`, `cmp1_saccade_classes`),
the layout and stimulus — and the fixation-index window is a `single_*` key. All
of them silently survived a design switch instead of being replaced by it.

The second half is a guard rather than a behaviour test: it renders the real
rail and fails on any plot-control key that is neither recorded by a design nor
named below as deliberately left out, so the next control added under a new
prefix has to be decided about instead of forgotten.
"""

from __future__ import annotations

import pytest

from scanpath_studio import controls
from scanpath_studio import session_keys as sk

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

#: What a design does not record, and why.
NOT_A_DESIGN_SETTING = {
    # An uploaded file is not a setting, and Streamlit refuses to assign a value
    # to an uploader's key (see `controls._is_restorable_global`).
    "global_stimulus_image_upload",
    # The Compare box-outline / fill pickers are shadows: they show the colour
    # drawn and write the real `cmp{idx}_box_color` / `cmp{idx}_box_fill_color`
    # (and the raw-gaze one `cmp{idx}_raw_gaze_color`),
    # which a design does record.
    "cmp0_box_color__pick",
    "cmp1_box_color__pick",
    "cmp0_box_fill_color__pick",
    "cmp1_box_fill_color__pick",
    "cmp0_raw_gaze_color__pick",
    "cmp1_raw_gaze_color__pick",
}

B_FILTERS = {
    "cmp1_fixclass_short_mode": "Discard",
    "cmp1_fixclass_short_threshold_ms": 120,
    "cmp1_fixclass_long_mode": "Highlight",
    "cmp1_fixclass_oob_mode": "Discard",
    "cmp1_fixclass_blink_mode": "Discard",
    "cmp1_saccade_classes": ["regression"],
}
STYLES = {"cmp0_fix_color": "#123456", "cmp1_saccade_width": 5.5}
MODES = {"single_compare_toggle": True, "single_playback_speed": 2.0}
A_FILTERS = {
    "global_fixclass_short_mode": "Discard",
    "global_saccade_classes": ["forward", "regression"],
}


def _app():
    """Take the queued design action (a button `on_click` runs first), then
    render the real rail for the first demo trial and publish its keys."""
    import streamlit as st

    from scanpath_studio import api, controls

    action = st.session_state.pop("_action", None)
    if action:
        verb, _, name = action.partition(":")
        if verb == "save":
            controls.save_design_preset(name)
        else:
            controls._apply_view_preset(name)
    words, fixations = api.load_sample_data(names="canonical")
    first = fixations[["participant_id", "trial_id"]].iloc[0]
    trial = fixations[
        (fixations["participant_id"] == first["participant_id"])
        & (fixations["trial_id"] == first["trial_id"])
    ]
    st.session_state["_viz"] = controls.render_plot_controls(
        fixations, 16, words=words, fix_range_fixations=trial
    )
    st.session_state["_keys"] = sorted(str(k) for k in st.session_state)


def _run(at: AppTest) -> AppTest:
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


@pytest.fixture()
def at() -> AppTest:
    return _run(AppTest.from_function(_app, default_timeout=90))


def _do(at: AppTest, action: str) -> AppTest:
    at.session_state["_action"] = action
    return _run(at)


class TestADesignRecordsTheFilters:
    def test_scanpath_b_filters_and_the_compare_styles_come_back(self, at):
        for key, value in {**B_FILTERS, **STYLES, **A_FILTERS}.items():
            at.session_state[key] = value
        _do(at, "save:mine")
        at.session_state["cmp1_fixclass_short_mode"] = "Off"
        at.session_state["cmp1_saccade_classes"] = ["forward"]
        at.session_state["cmp0_fix_color"] = "#abcdef"
        at.session_state["cmp1_saccade_width"] = 1.0
        at.session_state["global_fixclass_short_mode"] = "Off"
        at.session_state["global_saccade_classes"] = ["forward"]
        _do(at, "apply:mine")
        for key, value in {**B_FILTERS, **STYLES, **A_FILTERS}.items():
            assert at.session_state[key] == value, key

    def test_a_design_replaces_the_filters_it_does_not_hold(self, at):
        """Applying a design starts from defaults, like the built-ins: a filter
        left over from before must not survive into a design saved without one."""
        _do(at, "save:plain")
        for key, value in {**B_FILTERS, **A_FILTERS}.items():
            at.session_state[key] = value
        _do(at, "apply:plain")
        assert at.session_state["cmp1_fixclass_short_mode"] == "Off"
        assert at.session_state["global_fixclass_short_mode"] == "Off"

    def test_a_built_in_view_leaves_them_alone(self, at):
        """Built-in views are global-only: they never owned Compare's keys."""
        for key, value in B_FILTERS.items():
            at.session_state[key] = value
        _do(at, "apply:scanpath")
        assert at.session_state["cmp1_fixclass_long_mode"] == "Highlight"

    def test_compare_on_and_the_replay_speed_come_back(self, at):
        for key, value in MODES.items():
            at.session_state[key] = value
        _do(at, "save:mine")
        at.session_state["single_compare_toggle"] = False
        at.session_state["single_playback_speed"] = 1.0
        _do(at, "apply:mine")
        for key, value in MODES.items():
            assert at.session_state[key] == value, key

    def test_editing_a_b_filter_drops_the_design_highlight(self, at):
        _do(at, "save:mine")
        _do(at, "apply:mine")
        assert at.session_state["_quick_view_selection"] == "design:mine"
        at.session_state["cmp1_fixclass_short_mode"] = "Discard"
        _run(at)
        assert at.session_state["_quick_view_selection"] == "custom"


class TestComingBackToTheDesign:
    """Settings that return to the design that was left put its highlight back:
    switching Compare on reads Custom, and switching it off again must not.

    The app draws the Compare switch on every run, so its key is in the
    baseline from the start; this harness has no switch, so it seeds it."""

    @pytest.fixture()
    def at(self, at):
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = False
        return _run(at)

    def test_compare_on_then_off_keeps_a_saved_design(self, at):
        """#374 F25: Compare is a mode, so a saved design stays highlighted.
        The built-ins are covered in test_viz_state_transitions: this harness
        renders the rail without the app's palette sync, which a built-in needs."""
        _do(at, "save:mine")
        _do(at, "apply:mine")
        _run(at)
        assert at.session_state["_quick_view_selection"] == "design:mine"
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = True
        _run(at)
        assert at.session_state["_quick_view_selection"] == "design:mine"
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = False
        _run(at)
        assert at.session_state["_quick_view_selection"] == "design:mine"

    def test_a_setting_still_changed_stays_custom(self, at):
        _do(at, "save:mine")
        _do(at, "apply:mine")
        _run(at)
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = True
        at.session_state["global_fixclass_short_mode"] = "Discard"
        _run(at)
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = False
        _run(at)
        assert at.session_state["_quick_view_selection"] == "custom"

    def test_picking_custom_forgets_the_design_left(self, at):
        _do(at, "save:mine")
        _do(at, "apply:mine")
        _run(at)
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = True
        _run(at)
        _do(at, "apply:custom")
        at.session_state[sk.SINGLE_COMPARE_TOGGLE] = False
        _run(at)
        assert at.session_state["_quick_view_selection"] == "custom"


class TestTheFixationWindows:
    WINDOW = (2, 4)

    @pytest.mark.parametrize(
        "key", ["single_fix_range", "single_compare_fix_range"], ids=["A", "B"]
    )
    @pytest.mark.parametrize("all_trials", [True, False])
    def test_a_chosen_window_is_part_of_the_design(self, at, key, all_trials):
        at.session_state[key] = self.WINDOW
        at.session_state[f"{key}_user_set"] = True
        at.session_state["single_fix_range_all_trials"] = all_trials
        _run(at)
        _do(at, "save:head")
        at.session_state[key] = (1, 1)
        at.session_state["single_fix_range_all_trials"] = not all_trials
        _do(at, "apply:head")
        assert tuple(at.session_state[key]) == self.WINDOW
        assert at.session_state["single_fix_range_all_trials"] is all_trials

    def test_an_untouched_window_is_not_recorded(self, at):
        """The slider rewrites its auto-default each render; a design saved with
        no chosen window must not pin whatever the last trial's full range was."""
        _do(at, "save:plain")
        at.session_state["single_fix_range"] = (2, 3)
        at.session_state["single_fix_range_user_set"] = True
        _do(at, "apply:plain")
        assert at.session_state["single_fix_range_user_set"] is False
        assert tuple(at.session_state["single_fix_range"]) != (2, 3)

    def test_an_untouched_window_does_not_fire_the_drift_check(self, at):
        _do(at, "save:mine")
        _do(at, "apply:mine")
        _run(at)
        _run(at)
        assert at.session_state["_quick_view_selection"] == "design:mine"


class TestEveryPlotControlIsAccountedFor:
    def test_no_rail_key_is_forgotten(self, at):
        at.session_state["single_compare_toggle"] = True
        at.session_state["_resolved_comparing"] = True
        _run(at)
        forgotten = [
            key
            for key in at.session_state["_keys"]
            if not key.startswith("_")
            and not key.endswith("__num")
            and not key.endswith(("__num_lo", "__num_hi"))
            and not controls._is_design_key(key)
            and key not in NOT_A_DESIGN_SETTING
            and not key.startswith(("viz_view_", "design_", "quick_view"))
        ]
        assert forgotten == [], (
            "These session keys are set by the rail but a saved design would "
            "neither record nor restore them. Add them to "
            "`controls._DESIGN_EXTRA_KEYS`, or to NOT_A_DESIGN_SETTING here with "
            f"the reason: {forgotten}"
        )

    def test_everything_reset_clears_is_a_design_key_or_named_here(self):
        """`reset_viz_settings` is the other list of "all the plot controls"; the
        two must not drift."""
        source = {
            *sk.PLOT_CONFIG_STATE_KEYS,
            *sk.compare_state_keys(0),
            *sk.compare_state_keys(1),
            *sk.COMPARE_B_FILTER_STATE_KEYS,
            sk.SINGLE_COMPARE_TOGGLE,
            sk.SINGLE_PLAYBACK_SPEED,
            sk.SINGLE_COMPARE_FIX_RANGE,
            "single_fix_range",
            "single_fix_range_all_trials",
        }
        missing = {
            key
            for key in source
            if not controls._is_design_key(key) and key not in NOT_A_DESIGN_SETTING
        }
        assert missing == set()
