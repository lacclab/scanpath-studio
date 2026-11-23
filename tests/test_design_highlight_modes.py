"""The design-preset highlight follows the design, not the mode.

Compare and Animate are ways of viewing a design, so switching one on keeps the
highlight on Scanpath rather than moving it to Custom. A new dataset re-seeds
its own canvas and fields, which is not a hand edit either. And a link built
from a customized view opens on Custom, while one from a stock view — which
carries the whole design — opens on that design.
"""

from __future__ import annotations

import json
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
    from scanpath_studio.constants import SUBTAB_SHARE
    from scanpath_studio.url_state import SHARE_LINK, SHARE_SECTION_KEY

    at.session_state["single_subtab"] = SUBTAB_SHARE
    at.session_state[SHARE_SECTION_KEY] = SHARE_LINK
    at.run()
    query, _ = at.session_state["_share_query_current"]
    return dict(parse_qsl(query.lstrip("?")))


@pytest.mark.parametrize("mode", ["single_compare_toggle", "single_animate"])
def test_a_mode_does_not_move_the_highlight(mode):
    at = _app()
    assert _highlight(at) == "scanpath"
    for enabled in (True, False):
        at.toggle(key=mode).set_value(enabled).run()
        assert _highlight(at) == "scanpath"


def test_another_dataset_keeps_the_design():
    at = _app()
    picker = at.selectbox(key="data_source_picker")
    other = next(i for i, o in enumerate(picker.options) if "Hand-drawn" in o)
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


def test_time_chart_with_a_palette_reopens_from_share_link_and_file(monkeypatch):
    from scanpath_studio import tabs
    from scanpath_studio.constants import SUBTAB_SHARE
    from scanpath_studio.url_state import SHARE_SECTION_KEY

    at = _app()
    at.button(key="viz_view_gaze_over_time").click().run()
    at.button(key="viz_palette_high_contrast").click().run()
    assert _highlight(_app(_share_query(at))) == "gaze_over_time"

    exported = {}
    build = tabs._current_figure_config

    def capture(*args, **kwargs):
        value = build(*args, **kwargs)
        exported.update(value)
        return value

    monkeypatch.setattr(tabs, "_current_figure_config", capture)
    at.session_state["single_subtab"] = SUBTAB_SHARE
    at.session_state[SHARE_SECTION_KEY] = "Settings file"
    at.run()
    contents = json.dumps(exported).encode()
    at.button(key="viz_view_scanpath").click().run()
    at.file_uploader(key="plot_config_upload").upload(
        "time.json", contents, "application/json"
    ).run()
    assert not at.exception
    assert _highlight(at) == "gaze_over_time"
    assert at.session_state["global_palette"] == "High contrast"

    at.selectbox(key="global_color_by").set_value("duration_ms").run()
    received = _app(_share_query(at))
    assert _highlight(received) == "custom"
    received.button(key="viz_view_gaze_over_time").click().run()
    assert (
        received.selectbox(key="global_color_by").value == controls.UNIFORM_COLOR_FIELD
    )
