"""A hand-edited share link must never crash the app.

Every URL param that feeds a min/max-bounded widget is clamped on the way in
(`url_state._URL_BOUNDED`), every colour param is read as ``#rrggbb`` or
dropped with the "Ignored the link's invalid …" notice (`_parse_hex_color`), and
every param whose control offers a closed set of options is checked against
that set (`_CHOICE_STATE_PARSERS`, the recovery cache's rule too). Without
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


def _choice_params() -> dict[str, str]:
    """``url param → session key`` for every link param whose control offers a
    closed set of options (`url_state._CHOICE_STATE_PARSERS`). A param of a
    feature this build has off is ignored silently, by design, so it is left
    out."""
    from scanpath_studio.url_state import (
        _CHOICE_STATE_PARSERS,
        _GATED_URL_PARAMS,
        _URL_PRESETS,
    )

    return {
        url_key: state_key
        for url_key, (state_key, _coerce) in _URL_PRESETS.items()
        if state_key in _CHOICE_STATE_PARSERS
        and (url_key not in _GATED_URL_PARAMS or _GATED_URL_PARAMS[url_key]())
    }


def test_garbage_choices_are_dropped_with_a_warning():
    """A value a control does not offer is reported and dropped, as a colour
    is — not stored for the widget to reset silently."""
    params = _choice_params()
    assert len(params) > 30
    at = _boot({param: "zzz-not-an-option" for param in params})

    assert not at.exception, [e.message for e in at.exception]
    warned = " ".join(w.value for w in at.warning)
    for param, state_key in params.items():
        assert f"invalid {param}=zzz-not-an-option" in warned, param
        if state_key in at.session_state:
            assert at.session_state[state_key] != "zzz-not-an-option", param


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


_COLORSCALE_PICKER = "the colour-scale picker draws on a `<key>_pick` key"
_LEGEND_OFF = "drawn only while that legend is shown"

#: Checked menus the test's runs do not draw, each with why.
_MENUS_NOT_DRAWN_HERE: dict[str, str] = {
    "global_fixation_colorscale": _COLORSCALE_PICKER,
    "global_heatmap_colorscale": _COLORSCALE_PICKER,
    "cmp0_heatmap_colorscale": _COLORSCALE_PICKER,
    "cmp1_heatmap_colorscale": _COLORSCALE_PICKER,
    "global_palette": "the palette is a row of tiles (buttons), not a menu",
    "global_marker_size_scale": "its control writes the key from a callback",
    "global_critical_span_style": "drawn only while a highlight column is on",
    "export_figure_width_unit": "the Export subtab's print size",
    "global_legend_colors_size": _LEGEND_OFF,
    "global_legend_compare_size": _LEGEND_OFF,
    "global_legend_highlight_arrangement": _LEGEND_OFF,
    "global_legend_highlight_position": _LEGEND_OFF,
    "global_legend_highlight_size": _LEGEND_OFF,
    "global_legend_saccades_arrangement": _LEGEND_OFF,
    "global_legend_saccades_position": _LEGEND_OFF,
    "global_legend_saccades_size": _LEGEND_OFF,
    "global_legend_size_key_size": _LEGEND_OFF,
}


@pytest.mark.timeout(300)
def test_every_value_a_menu_offers_survives_a_link(monkeypatch):
    """The other side of the garbage check: a link reads back every value the
    rail's menus offer, as they offer it. A choice check narrower than its menu
    would drop a real choice from every link that carries it."""
    from functools import partial

    import streamlit
    from streamlit.delta_generator import DeltaGenerator
    from streamlit.testing.v1 import AppTest

    from scanpath_studio import url_state

    offered: dict[str, list] = {}
    menus = ("selectbox", "radio", "segmented_control", "pills", "multiselect")
    for name in (*menus, "select_slider"):
        real = getattr(DeltaGenerator, name)

        def recording(self, label, options=(), *args, _real=real, **kwargs):
            if kwargs.get("key") in url_state._CHOICE_STATE_PARSERS:
                seen = offered.setdefault(kwargs["key"], [])
                seen += [option for option in options if option not in seen]
            return _real(self, label, options, *args, **kwargs)

        # A container's `col.selectbox` and the module's `st.selectbox`,
        # which is bound to the main container when Streamlit is imported.
        monkeypatch.setattr(DeltaGenerator, name, recording)
        monkeypatch.setattr(streamlit, name, partial(recording, streamlit._main))
    for state in ({}, {"single_compare_toggle": True}, {"single_animate": True}):
        at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        for key in ("global_show_heatmap", "global_show_raw_gaze", "global_show_order"):
            at.session_state[key] = True
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        assert not at.exception, at.exception
    unseen = set(url_state._CHOICE_STATE_PARSERS) - set(offered)
    assert unseen == set(_MENUS_NOT_DRAWN_HERE), (
        "every checked menu is drawn here or listed in _MENUS_NOT_DRAWN_HERE "
        f"with why: newly unseen {sorted(unseen - set(_MENUS_NOT_DRAWN_HERE))}, "
        f"now drawn {sorted(set(_MENUS_NOT_DRAWN_HERE) - unseen)}"
    )

    def reads_back(parse, value) -> bool:
        try:
            return parse(value) == value
        except ValueError:  # the link reader's "not one of the options"
            return False

    refused = {}
    for key, options in offered.items():
        parse = url_state._CHOICE_STATE_PARSERS[key]
        values = (
            [[option] for option in options] if key.endswith("_classes") else options
        )
        dropped = [value for value in values if not reads_back(parse, value)]
        if dropped:
            refused[key] = dropped
    assert not refused, f"a link would drop these menu values: {refused}"
