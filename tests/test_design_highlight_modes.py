"""#374 F25 — the design-preset highlight follows the design, not the mode.

Compare and Animate are ways of viewing a design: switching one on used to move
the highlight from Scanpath to Custom. A new dataset re-seeds its own canvas and
fields, which also read as a hand edit. And a link built from a customized view
opened on Scanpath, because only the design's own few keys were checked.
"""

from __future__ import annotations

from urllib.parse import parse_qsl

import pytest

from scanpath_studio import controls
from tests.conftest import APP_SCRIPT

pytestmark = pytest.mark.timeout(240)


def _app(query: dict | None = None):
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_file(APP_SCRIPT, default_timeout=90)
    for key, value in (query or {}).items():
        at.query_params[key] = value
    at.run()
    assert not at.exception
    return at


def _highlight(at) -> str:
    return at.session_state[controls._QUICK_VIEW_SELECTION_KEY]


def _share_query(at) -> dict:
    """The Share link the app would hand out right now."""
    at.session_state["single_share_choice"] = "Link"
    at.run()
    query, _ = at.session_state["_share_query_current"]
    return dict(parse_qsl(query.lstrip("?")))


@pytest.mark.parametrize("mode", ["single_compare_toggle", "single_animate"])
def test_a_mode_does_not_move_the_highlight(mode):
    at = _app()
    assert _highlight(at) == "scanpath"
    at.toggle(key=mode).set_value(True).run()
    assert _highlight(at) == "scanpath"
    at.toggle(key=mode).set_value(False).run()
    assert _highlight(at) == "scanpath"


def test_another_dataset_keeps_the_design():
    at = _app()
    picker = at.selectbox(key="data_source_picker")
    other = next(i for i, o in enumerate(picker.options) if "Synthetic" in o)
    picker.select_index(other).run()
    assert not at.exception
    assert _highlight(at) == "scanpath"


def test_a_link_from_a_custom_view_opens_on_custom():
    received = _app({"fixation_color": "#0072b2", "saccade_color": "#123456"})
    assert _highlight(received) == controls._CUSTOM_VIEW


def test_a_link_from_a_stock_view_opens_on_its_design():
    query = _share_query(_app())
    assert len(query) > 20  # the link carries the whole design
    received = _app(query)
    assert _highlight(received) == "scanpath"
