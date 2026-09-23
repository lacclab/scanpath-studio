"""EXP-18: a share link reopens the figure the sender was looking at.

The pre-beta audit round-tripped a link from a sender with non-default settings
and found figure-changing settings that never rode it: the stimulus-image layer
and *Show full monitor* (which `session_keys` claimed round-tripped), the PRE-2
fixation flags (with *Discard* the recipient saw different fixations, and no
Illustration label), the replay speed (a non-1× speed stamps one), the colour-bar
styling, the span border colour and Compare's A/B legend. These drive the writer
into the reader, then the whole app from a sender to a recipient.

Canvas size, base font size and Compare's per-scanpath styles are deliberately
still off the link — pending a maintainer decision — and the Share panel says so.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

#: Every setting EXP-18 put on the link, at a value that differs from its default.
SENT = {
    "global_show_stimulus_image": True,
    "global_fit_to_monitor": False,
    "global_show_compare_legend": True,
    "global_colorbar_orientation": "Horizontal",
    "global_colorbar_tickangle": 45,
    "global_colorbar_tickfont_size": 16,
    "global_span_border_color": "#00AAAA",
    "global_fixclass_short_mode": "Discard",
    "global_fixclass_short_threshold_ms": 120,
    "global_fixclass_short_symbol": "x",
    "global_fixclass_short_color": "#FF0000",
    "global_fixclass_long_mode": "Highlight",
    "global_fixclass_long_threshold_ms": 900,
    "global_fixclass_long_symbol": "star",
    "global_fixclass_long_color": "#00FF00",
    "global_fixclass_oob_mode": "Highlight",
    "global_fixclass_oob_symbol": "circle-open",
    "global_fixclass_oob_color": "#0000FF",
    "global_fixclass_blink_mode": "Discard",
    "global_fixclass_blink_symbol": "square-open",
    "global_fixclass_blink_color": "#123456",
    "single_playback_speed": 2.0,
}


def _round_trip_app():
    """Build a link from `_sent`, clear the state, read the link back."""
    from urllib.parse import parse_qs as _parse_qs

    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    sent = st.session_state["_sent"]
    for key, value in sent.items():
        st.session_state[key] = value
    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    query, _ = _build_share_query(DEMO_CHOICE)
    st.session_state["_query"] = query
    for key in sent:
        del st.session_state[key]

    st.query_params.clear()
    for key, values in _parse_qs(query).items():
        st.query_params[key] = values[0]
    _apply_url_preset()
    st.session_state["_got"] = {key: st.session_state.get(key) for key in sent}


def test_every_figure_setting_survives_the_link():
    at = AppTest.from_function(_round_trip_app)
    at.session_state["_sent"] = SENT
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert [w.value for w in at.warning] == []
    assert at.session_state["_got"] == SENT


def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    st.session_state["_seeded"] = {
        key: st.session_state.get(key)
        for key in (
            "single_playback_speed",
            "global_colorbar_orientation",
            "global_colorbar_tickangle",
            "global_fixclass_short_mode",
            "global_fixclass_short_symbol",
            "global_fixclass_short_threshold_ms",
        )
    }


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("playback_speed", "3.3"),  # not one of the slider's options
        ("colorbar_orientation", "Diagonal"),
        ("fixclass_short_mode", "Bogus"),
        ("fixclass_short_symbol", "bogus"),
        ("fixclass_short_color", "zzz"),
    ],
)
def test_a_value_the_widget_refuses_is_ignored_with_a_warning(param, value):
    at = AppTest.from_function(_link_app)
    at.query_params[param] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert any(f"?{param}=" in w.value for w in at.warning), [
        w.value for w in at.warning
    ]


def test_numbers_are_clamped_to_their_widgets():
    at = AppTest.from_function(_link_app)
    at.query_params["colorbar_tickangle"] = "500"
    at.query_params["fixclass_short_threshold_ms"] = "0"
    at.query_params["playback_speed"] = "2"  # the writer's own spelling is "2.0"
    at.query_params["colorbar_orientation"] = "horizontal"
    at.run(timeout=30)
    assert not at.exception, at.exception
    seeded = at.session_state["_seeded"]
    assert seeded["global_colorbar_tickangle"] == 90
    assert seeded["global_fixclass_short_threshold_ms"] == 1
    assert seeded["single_playback_speed"] == 2.0
    assert seeded["global_colorbar_orientation"] == "Horizontal"


def test_the_whole_app_reopens_the_senders_figure():
    """Sender → Share link → recipient, through every widget on the way."""
    sender = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    sender.run()
    for key, value in SENT.items():
        sender.session_state[key] = value
    sender.run()
    assert not sender.exception, [e.message for e in sender.exception]
    query, _caveats = sender.session_state["_share_query_current"]

    recipient = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key, values in parse_qs(query).items():
        recipient.query_params[key] = values[0]
    recipient.run()
    assert not recipient.exception, [e.message for e in recipient.exception]
    got = {key: recipient.session_state[key] for key in SENT}
    assert got == SENT
    # *Discard* changes which fixations are drawn — the reason this mattered.
    flags = recipient.session_state["_snippet_state"].settings["fixation_flags"]
    assert flags["short"]["mode"] == "Discard"


def test_the_share_panel_says_what_the_link_leaves_out():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.run()
    captions = " ".join(c.value for c in at.caption)
    assert "aren't in the link" in captions
