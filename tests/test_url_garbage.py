"""BUG-69: a hand-edited share link must never crash the app.

Every URL param that feeds a min/max-bounded widget is clamped on the way in
(`url_state._URL_BOUNDED`), and every colour param is read as ``#rrggbb`` or
dropped with the "Ignored bad URL param" warning (`_parse_hex_color`). The audit
found two holes: raw gaze's marker size and opacity rode the link with no bounds
(``?raw_gaze_opacity=5`` crashed the slider), and colours were read as any string
(``?order_font_color=zzz`` crashed Plotly inside the figure builder). This boots
the real app with garbage in *every* such param at once, so a param added later
without a bound or a validator fails here by name.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _bounded_params() -> dict[str, tuple[str, tuple]]:
    """``url param → (session key, (lo, hi))`` for every clamped deep-link param."""
    from scanpath_studio.url_state import _URL_BOUNDED, _URL_PRESETS

    return {
        url_key: (state_key, _URL_BOUNDED[state_key])
        for url_key, (state_key, _coerce) in _URL_PRESETS.items()
        if state_key in _URL_BOUNDED
    }


def _boot(params: dict[str, str]):
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key, value in params.items():
        at.query_params[key] = value
    at.run()
    return at


def test_every_bounded_param_is_a_known_widget_bound():
    """Raw gaze's two sliders are the ones UX-86 put on the link unbounded."""
    params = _bounded_params()
    assert params["raw_gaze_marker_size"][1] == (1.0, 12.0)
    assert params["raw_gaze_opacity"][1] == (0.1, 1.0)


@pytest.mark.parametrize("side", ["above", "below"])
def test_out_of_range_values_are_clamped_not_crashed_on(side):
    params = _bounded_params()
    query = {}
    for url_key, (_state, (lo, hi)) in params.items():
        span = abs(hi - lo) or 1
        value = hi + 10 * span if side == "above" else lo - 10 * span
        ranged = url_key.endswith("_range")
        query[url_key] = f"{value},{value}" if ranged else f"{value}"
    at = _boot(query)

    assert not at.exception, [e.message for e in at.exception]
    for url_key, (state_key, (lo, hi)) in params.items():
        got = at.session_state[state_key]
        want = hi if side == "above" else lo
        assert tuple(got) == (want, want) if isinstance(got, tuple) else got == want, (
            url_key,
            got,
        )


def test_garbage_colours_are_dropped_with_a_warning():
    from scanpath_studio.url_state import _SHARE_COLOR_PARAMS, _URL_PRESETS

    at = _boot({param: "zzz" for param in _SHARE_COLOR_PARAMS})

    assert not at.exception, [e.message for e in at.exception]
    warned = " ".join(w.value for w in at.warning)
    for param in _SHARE_COLOR_PARAMS:
        assert f"?{param}='zzz'" in warned, param
        state_key = _URL_PRESETS[param][0]
        if state_key in at.session_state:
            assert at.session_state[state_key] != "zzz", param


def test_a_valid_colour_still_lands():
    at = _boot({"order_font_color": "#123456", "raw_gaze_color": " #ABCDEF "})

    assert not at.exception
    assert at.session_state["global_order_font_color"] == "#123456"
    assert at.session_state["global_raw_gaze_color"] == "#ABCDEF"
