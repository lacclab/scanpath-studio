"""The rail's number controls hold the range a link or settings file is held to.

`url_state._URL_BOUNDED` clamps each number a link or a settings file carries.
A slider or number box that lets the user go further makes a figure the link
cannot carry: Share would hand on the clamped value, and the recipient would
see a different figure. Here the rail is drawn with every layer on, alone and
in Compare, and each control on a clamped key must have exactly that range.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import url_state
from tests.conftest import APP_SCRIPT

_EVERY_LAYER = (
    "global_show_fix",
    "global_show_saccades",
    "global_show_heatmap",
    "global_show_raw_gaze",
    "global_show_order",
    "global_show_stimulus_image",
    "global_show_coordinate_grid",
)


def _ranges(**state) -> dict[str, tuple[float, float]]:
    """Each drawn slider and number box on a clamped key, by key: its range."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key in _EVERY_LAYER:
        at.session_state[key] = True
    for key, value in state.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception, at.exception
    ranges = {}
    for kind in ("slider", "number_input"):
        for element in at.get(kind):
            # A typed box beside a slider is a stand-in (`<key>__num`) that
            # writes the key itself, so it holds the key's range too.
            key = str(getattr(element, "key", None) or "").removesuffix("__num")
            if key in url_state._URL_BOUNDED:
                ranges[key] = (float(element.proto.min), float(element.proto.max))
    return ranges


_SHADOW = "drawn on a stand-in key of another name that writes this one"
_SETUP = "a recording-setup field, on the Data page"
_PRINT = "the Export subtab's print size"

#: Clamped keys the test's runs do not draw as a slider or number box, with why.
_NOT_DRAWN_HERE: dict[str, str] = {
    "cmp0_box_fill_opacity": _SHADOW,
    "cmp0_box_line_opacity": _SHADOW,
    "cmp1_box_fill_opacity": _SHADOW,
    "cmp1_box_line_opacity": _SHADOW,
    "global_heatmap_sigma_px": _SHADOW,
    "export_figure_dpi": _PRINT,
    "export_figure_width": _PRINT,
    "global_canvas_height": _SETUP,
    "global_canvas_width": _SETUP,
    "global_display_dpi": _SETUP,
    "global_monitor_width_mm": _SETUP,
    "global_stimulus_font_pt": _SETUP,
    "global_viewing_distance_mm": _SETUP,
}


@pytest.mark.timeout(300)
def test_each_number_control_holds_the_links_range():
    ranges: dict[str, tuple[float, float]] = {}
    for state in ({}, {"single_compare_toggle": True}, {"single_animate": True}):
        ranges.update(_ranges(**state))
    wrong = {
        key: (drawn, url_state._URL_BOUNDED[key])
        for key, drawn in ranges.items()
        if drawn != tuple(map(float, url_state._URL_BOUNDED[key]))
    }
    assert not wrong, (
        "these controls' ranges differ from what a link or settings file is "
        f"held to, (control, link): {wrong}"
    )
    unseen = set(url_state._URL_BOUNDED) - set(ranges)
    assert unseen == set(_NOT_DRAWN_HERE), (
        "every clamped key is drawn here or listed in _NOT_DRAWN_HERE with why: "
        f"newly unseen {sorted(unseen - set(_NOT_DRAWN_HERE))}, "
        f"now drawn {sorted(set(_NOT_DRAWN_HERE) - unseen)}"
    )


def test_a_settings_file_past_a_controls_range_is_held_to_it(monkeypatch):
    """A file saved before a control had its maximum can carry a value past
    it. Restored as it is, Streamlit resets the control to its minimum without
    a word: a 1 ms "long" threshold, which flags every fixation. The reader
    clamps every clamped key, A's and B's, whichever section holds it."""
    import pandas as pd
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {})
    flags = {"long": {"mode": "Highlight", "threshold_ms": 100_000}}
    config = {
        "highlighting": {"fixation_flags": flags},
        "compare": [{}, {"fixation_flags": flags}],
        "coloring": {"stimulus_image_offset_x": 9000},
    }
    combos = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
    fixations = combos.assign(x=1.0, y=2.0, duration_ms=100.0)
    url_state._restore_plot_config(config, combos, fixations)
    top = url_state._URL_BOUNDED["global_fixclass_long_threshold_ms"][1]
    assert st.session_state["global_fixclass_long_threshold_ms"] == top
    assert st.session_state["cmp1_fixclass_long_threshold_ms"] == top
    assert st.session_state["global_stimulus_image_offset_x"] == 5000.0
