"""A hand-edited share link must never crash the app.

Every URL param that feeds a min/max-bounded widget is clamped on the way in
(`url_state._URL_BOUNDED`), and every colour param is read as ``#rrggbb`` or
dropped with the "Ignored bad URL param" warning (`_parse_hex_color`). Without
a bound, ``?raw_gaze_opacity=5`` would crash the slider; read as any string,
``?order_font_color=zzz`` would crash Plotly inside the figure builder. This boots
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
    """Raw gaze's two sliders, marker size and opacity, are bounded on the link."""
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
    # The source it names, as every Share link does: a link's canvas and font
    # are held against the source snap only for that source.
    query["source"] = "demo"
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
        assert f"invalid {param}=zzz" in warned, param
        state_key = _URL_PRESETS[param][0]
        if state_key in at.session_state:
            assert at.session_state[state_key] != "zzz", param


def test_a_valid_colour_still_lands():
    at = _boot({"order_font_color": "#123456", "raw_gaze_color": " #ABCDEF "})

    assert not at.exception
    assert at.session_state["global_order_font_color"] == "#123456"
    assert at.session_state["global_raw_gaze_color"] == "#ABCDEF"


def test_a_non_finite_or_garbage_link_opens_the_app_with_notices():
    """``1e309`` overflows to infinity; it and the rest are reported, never drawn.

    Before, ``marker_size_range=1,1e309`` raised ``OverflowError`` out of the
    reader and replaced the whole page with the crash note on every reload.
    """
    title = "x" * 20_000
    at = _boot(
        {
            "source": "demo",
            "marker_size_range": "1,1e309",
            "marker_duration_range": "1,1e309",
            "fixation_opacity": "NaN",
            "saccade_width": "inf",
            "canvas_width": "1e309",
            "show_heatmap": "maybe",
            "redact_text": "-1",
            "show_fixations": "maybe",
            "title_pattern": title,
        }
    )

    assert not at.exception, [e.message for e in at.exception]
    warned = [w.value for w in at.warning]
    for shown in (
        "marker_size_range=1,1e309",
        "marker_duration_range=1,1e309",
        "fixation_opacity=NaN",
        "saccade_width=inf",
        "canvas_width=1e309",
        "show_heatmap=maybe",
        "redact_text=-1",
        "show_fixations=maybe",
    ):
        assert any(f"Ignored the link's invalid {shown}." in w for w in warned), (
            shown,
            warned,
        )
    # The notice echoes the start of an overlong value, not all of it.
    (long_notice,) = [w for w in warned if "title_pattern=" in w]
    assert "(20,000 characters)" in long_notice
    assert len(long_notice) < 200
    # None of them reached session state; the controls kept their defaults.
    assert at.session_state["global_title_pattern"] != title
    assert at.session_state["global_marker_size_range"] != (1, float("inf"))
    assert at.session_state["global_show_heatmap"] is False
    assert at.session_state["global_redact_text"] is False
    # The scanpath still drew.
    assert at.session_state["global_show_fix"] is True


def test_an_out_of_range_number_is_clamped_with_a_notice():
    at = _boot({"source": "demo", "marker_size_range": "-5,10"})

    assert not at.exception, [e.message for e in at.exception]
    assert at.session_state["global_marker_size_range"] == (4, 10)
    assert [w.value for w in at.warning] == [
        "The link's marker_size_range=-5,10 is outside the control's range; used 4,10."
    ]


class TestTheParsers:
    @pytest.mark.parametrize(
        "raw", ["1", "true", "TRUE", "Yes", "on", " On ", "0", "false", "No", "OFF"]
    )
    def test_a_real_on_off_spelling_reads(self, raw):
        from scanpath_studio.url_state import _coerce_bool

        assert _coerce_bool(raw) is (raw.strip().lower() in {"1", "true", "yes", "on"})

    @pytest.mark.parametrize("raw", ["maybe", "-1", "2", "", "y", "enabled"])
    def test_anything_else_raises(self, raw):
        from scanpath_studio.url_state import _coerce_bool

        with pytest.raises(ValueError):
            _coerce_bool(raw)

    def test_share_writes_only_spellings_the_reader_accepts(self):
        from scanpath_studio.url_state import _coerce_bool

        assert _coerce_bool("1") is True
        assert _coerce_bool("0") is False

    @pytest.mark.parametrize("raw", ["nan", "NaN", "inf", "-inf", "1e309", "x"])
    def test_numbers_must_be_finite(self, raw):
        from scanpath_studio.url_state import (
            _parse_finite_float,
            _parse_float_range,
            _parse_int,
            _parse_int_range,
        )

        for parse in (_parse_finite_float, _parse_int):
            with pytest.raises(ValueError):
                parse(raw)
        for parse in (_parse_int_range, _parse_float_range):
            with pytest.raises(ValueError):
                parse(f"1,{raw}")

    def test_whole_numbers_and_pairs_still_read(self):
        from scanpath_studio.url_state import (
            _parse_float_range,
            _parse_int,
            _parse_int_range,
        )

        assert _parse_int("12") == 12
        assert _parse_int("12.0") == 12
        with pytest.raises(ValueError):
            _parse_int("12.5")
        assert _parse_int_range("20,5") == (5, 20)
        assert _parse_float_range("0.5,-1") == (-1.0, 0.5)
        with pytest.raises(ValueError):
            _parse_int_range("1,2,3")

    def test_figure_text_is_capped(self):
        from scanpath_studio.url_state import _MAX_LINK_TEXT_CHARS, _parse_figure_text

        fits = "a" * _MAX_LINK_TEXT_CHARS
        assert _parse_figure_text(fits) == fits
        assert _parse_figure_text("<b>{trial_id}</b>") == "{trial_id}"
        with pytest.raises(ValueError):
            _parse_figure_text(fits + "a")
