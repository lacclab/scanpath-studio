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
            key = getattr(element, "key", None)
            if key in url_state._URL_BOUNDED:
                ranges[key] = (float(element.proto.min), float(element.proto.max))
    return ranges


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    "state",
    [{}, {"single_compare_toggle": True}],
    ids=["alone", "compare"],
)
def test_each_number_control_holds_the_links_range(state):
    ranges = _ranges(**state)
    assert len(ranges) > 30, f"only {len(ranges)} clamped controls drawn"
    wrong = {
        key: (drawn, url_state._URL_BOUNDED[key])
        for key, drawn in ranges.items()
        if drawn != tuple(map(float, url_state._URL_BOUNDED[key]))
    }
    assert not wrong, (
        "these controls' ranges differ from what a link or settings file is "
        f"held to, (control, link): {wrong}"
    )
