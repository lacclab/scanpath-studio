"""EXP-19: a share link carries the recording setup and Compare's styles.

Until EXP-19 the canvas, the base font, the physical monitor geometry and the
per-scanpath Compare styles travelled in the 💾 saved config alone, and the
Share panel said so. They ride the link now — but only when they say something
the recipient's own session would not, so a link to the demo does not restate
the demo's 2560x1440, and the styles only beside the comparison they describe.

Two things make that more than a table entry, and both are pinned here: the
elision (``url_state._link_defaults``), and the source snap in
``app.seed_canvas_state``, which on a recipient's first run used to overwrite a
linked canvas with the corpus' own monitor before a widget ever showed it.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from scanpath_studio import session_keys as sk
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

#: The recording setup, every value off its default (and the DPI off the value
#: the canvas and physical width would derive: 1920 / (520 / 25.4) = 93.78).
SETUP_SENT = {
    "global_canvas_width": 1920,
    "global_canvas_height": 1080,
    "global_base_font_size": 20,
    "global_monitor_width_mm": 520.0,
    "global_viewing_distance_mm": 650.0,
    "global_display_dpi": 110.0,
    "global_stimulus_font_pt": 14.0,
    "global_use_stimulus_font_pt": True,
}

#: Both scanpaths' styles, every value off its default.
STYLES_SENT = {
    "cmp0_fix_color": "#aa0000",
    "cmp0_saccade_color": "#00aa00",
    "cmp0_saccade_style": "Dash-dot",
    "cmp0_saccade_width": 3.5,
    "cmp0_marker_size_range": (6, 18),
    "cmp0_opacity": 0.4,
    "cmp0_hollow": True,
    "cmp0_label_pattern": "A: {trial_id}",
    "cmp1_fix_color": "#0000aa",
    "cmp1_saccade_color": "#aa00aa",
    "cmp1_saccade_style": "Dotted",
    "cmp1_saccade_width": 1.5,
    "cmp1_marker_size_range": (5, 30),
    "cmp1_opacity": 0.9,
    "cmp1_hollow": True,
    "cmp1_label_pattern": "B: {participant_id}",
}

SENT = {**SETUP_SENT, **STYLES_SENT}


def test_the_new_params_are_exactly_the_saved_config_only_keys():
    """Nothing that used to be config-only is left behind, and nothing else
    got the default-elision treatment by accident."""
    assert set(sk.SETUP_PARAMS.values()) == set(SETUP_SENT)
    assert set(sk.COMPARE_STYLE_PARAMS.values()) == set(STYLES_SENT)
    assert set(sk.COMPARE_STYLE_PARAMS.values()) == (
        sk.compare_state_keys(0) | sk.compare_state_keys(1)
    )


def test_the_snap_protected_keys_are_the_ones_the_snap_writes():
    """The reader names these to `seed_canvas_state`; a snap key it does not
    know would still overwrite a linked value on the recipient's first run."""
    from scanpath_studio import app, url_state

    assert url_state._SOURCE_SNAPPED_KEYS == {
        "global_canvas_width",
        "global_canvas_height",
        *app._FONT_SNAP_KEYS,
    }


# ---------------------------------------------------------------------------
# The writer into the reader
# ---------------------------------------------------------------------------
def _round_trip_app():
    """Build a link from `_sent`, clear the state, read the link back."""
    from urllib.parse import parse_qs as _parse_qs

    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    sent = st.session_state["_sent"]
    for key, value in sent.items():
        st.session_state[key] = value
    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": {"participant_id": "p2", "trial_id": "t2"},
    }
    query, _ = _build_share_query(st.session_state["_choice"])
    st.session_state["_query"] = query
    for key in sent:
        del st.session_state[key]

    st.query_params.clear()
    for key, values in _parse_qs(query).items():
        st.query_params[key] = values[0]
    _apply_url_preset()
    st.session_state["_got"] = {key: st.session_state.get(key) for key in sent}


def _round_trip(sent: dict, choice: str | None = None):
    from scanpath_studio.constants import DEMO_CHOICE

    at = AppTest.from_function(_round_trip_app)
    at.session_state["_sent"] = sent
    at.session_state["_choice"] = choice or DEMO_CHOICE
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert [w.value for w in at.warning] == []
    return at


def test_every_setting_survives_the_link():
    at = _round_trip(SENT)
    assert at.session_state["_got"] == SENT
    emitted = set(parse_qs(at.session_state["_query"]))
    assert set(sk.SETUP_PARAMS) | set(sk.COMPARE_STYLE_PARAMS) <= emitted


def test_the_params_are_spelled_by_side():
    """`cmp_a_*` is the first scanpath and `cmp_b_*` the second, as `style_a` /
    `--label-a` / `cmp_stimulus=A` name them everywhere else."""
    at = _round_trip(SENT)
    emitted = parse_qs(at.session_state["_query"])
    assert emitted["cmp_a_fix_color"] == ["#aa0000"]
    assert emitted["cmp_b_fix_color"] == ["#0000aa"]
    assert emitted["canvas_width"] == ["1920"]
    assert emitted["cmp_a_marker_size_range"] == ["6,18"]


def _defaults_app():
    """Seed the setup + styles exactly as a fresh demo session does, then link."""
    import streamlit as st

    from scanpath_studio.app import SETUP_DEFAULTS
    from scanpath_studio.controls import compare_style_defaults
    from scanpath_studio.url_state import _build_share_query

    for key, value in {**SETUP_DEFAULTS, **compare_style_defaults()}.items():
        st.session_state[key] = value
    st.session_state["global_canvas_width"] = 2560
    st.session_state["global_canvas_height"] = 1440
    # What `seed_canvas_state` pins: the DPI the canvas and width imply.
    st.session_state["global_display_dpi"] = round(2560 / (597.0 / 25.4), 2)
    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": st.session_state.get("_compare"),
    }
    query, _ = _build_share_query(st.session_state["_choice"])
    st.session_state["_query"] = query


def _emitted_defaults(choice: str, compare: dict | None = None) -> set:
    at = AppTest.from_function(_defaults_app)
    at.session_state["_choice"] = choice
    at.session_state["_compare"] = compare
    at.run(timeout=60)
    assert not at.exception, at.exception
    emitted = set(parse_qs(at.session_state["_query"]))
    return emitted & (set(sk.SETUP_PARAMS) | set(sk.COMPARE_STYLE_PARAMS))


def test_a_setting_at_its_default_stays_off_the_link():
    from scanpath_studio.constants import DEMO_CHOICE

    compare = {"participant_id": "p2", "trial_id": "t2"}
    assert _emitted_defaults(DEMO_CHOICE, compare) == set()


def test_a_source_that_declares_no_screen_always_carries_its_canvas():
    """The synthetic trial's canvas is estimated from the data, which the link
    writer does not have — so there is no default to leave off against."""
    from scanpath_studio.constants import SYNTHETIC_CHOICE

    assert _emitted_defaults(SYNTHETIC_CHOICE) == {"canvas_width", "canvas_height"}


def _no_compare_app():
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    for key, value in st.session_state["_sent"].items():
        st.session_state[key] = value
    st.session_state["_share_selection"] = {"participant_id": "p1"}
    st.session_state["_query"] = _build_share_query(DEMO_CHOICE)[0]


def test_the_styles_travel_only_with_a_comparison():
    """Like `cmp_layout`: without `compare=` they restore nothing, and the
    widgets keep them in session state long after Compare was switched off."""
    from scanpath_studio.constants import DEMO_CHOICE

    at = AppTest.from_function(_round_trip_app)
    at.session_state["_sent"] = STYLES_SENT
    at.session_state["_choice"] = DEMO_CHOICE
    at.run(timeout=60)
    assert set(sk.COMPARE_STYLE_PARAMS) <= set(parse_qs(at.session_state["_query"]))

    at = AppTest.from_function(_no_compare_app)
    at.session_state["_sent"] = STYLES_SENT
    at.run(timeout=60)
    assert not at.exception, at.exception
    emitted = set(parse_qs(at.session_state["_query"]))
    assert not emitted & set(sk.COMPARE_STYLE_PARAMS)


# ---------------------------------------------------------------------------
# A hand-edited link
# ---------------------------------------------------------------------------
def _link_app():
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    _apply_url_preset()
    keys = st.session_state["_keys"]
    st.session_state["_seeded"] = {key: st.session_state.get(key) for key in keys}


def _open_link(**params):
    at = AppTest.from_function(_link_app)
    at.session_state["_keys"] = list(SENT)
    for key, value in params.items():
        at.query_params[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


def test_numbers_are_clamped_to_their_widgets():
    from scanpath_studio.constants import SACCADE_WIDTH_BOUNDS

    at = _open_link(
        canvas_width="50",
        canvas_height="99999",
        base_font_size="200",
        monitor_width_mm="5",
        viewing_distance_mm="99999",
        display_dpi="5000",
        stimulus_font_pt="1",
        cmp_a_opacity="3",
        cmp_a_saccade_width="99",
        cmp_b_marker_size_range="1,99",
    )
    assert [w.value for w in at.warning] == []
    seeded = at.session_state["_seeded"]
    assert seeded["global_canvas_width"] == 100
    assert seeded["global_canvas_height"] == 10000
    assert seeded["global_base_font_size"] == 72
    assert seeded["global_monitor_width_mm"] == 100.0
    assert seeded["global_viewing_distance_mm"] == 3000.0
    assert seeded["global_display_dpi"] == 1000.0
    assert seeded["global_stimulus_font_pt"] == 4.0
    assert seeded["cmp0_opacity"] == 1.0
    assert seeded["cmp0_saccade_width"] == SACCADE_WIDTH_BOUNDS[1]
    assert seeded["cmp1_marker_size_range"] == (4, 40)


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("cmp_a_saccade_style", "Wavy"),  # not one of the selectbox's labels
        ("cmp_b_fix_color", "zzz"),
        ("cmp_a_saccade_color", "red"),  # the pickers only ever hold #rrggbb
        ("canvas_width", "wide"),
    ],
)
def test_a_value_the_widget_refuses_is_ignored_with_a_warning(param, value):
    at = _open_link(**{param: value})
    assert any(f"?{param}=" in w.value for w in at.warning), [
        w.value for w in at.warning
    ]


def test_a_line_style_is_matched_case_blind():
    at = _open_link(cmp_a_saccade_style="dash-dot", cmp_b_saccade_style="DOTTED")
    seeded = at.session_state["_seeded"]
    assert seeded["cmp0_saccade_style"] == "Dash-dot"
    assert seeded["cmp1_saccade_style"] == "Dotted"


def test_a_linked_legend_label_is_text_not_markup():
    """BUG-75's rule for the title and caption, applied to the legend label."""
    at = _open_link(cmp_a_label_pattern='<a href="https://x.example">A</a> {trial_id}')
    assert at.session_state["_seeded"]["cmp0_label_pattern"] == "A {trial_id}"


# ---------------------------------------------------------------------------
# The source snap
# ---------------------------------------------------------------------------
def _seed_app():
    """Run `seed_canvas_state` for the demo over words that declare a font."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.app import seed_canvas_state
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.session_keys import LINK_SETUP_STATE_KEY

    words = pd.DataFrame(
        {"x": [10.0], "y": [10.0], "stimulus_font_px": [30.0]},
    )
    st.session_state["_resolved"] = seed_canvas_state(
        words, pd.DataFrame(), DEMO_CHOICE
    )
    st.session_state["_marker_left"] = LINK_SETUP_STATE_KEY in st.session_state


def _seed(**session):
    at = AppTest.from_function(_seed_app)
    for key, value in session.items():
        at.session_state[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


def test_the_source_snap_overwrites_an_unlinked_canvas_and_font():
    """The control: without the link's word, the demo's monitor and a declared
    typeface win — which is the snap doing its job for a source switch."""
    at = _seed(
        global_canvas_width=1920, global_canvas_height=1080, global_base_font_size=20
    )
    width, height, font = at.session_state["_resolved"][:3]
    assert (width, height, font) == (2560, 1440, 30)


def test_a_linked_canvas_and_font_survive_the_source_snap():
    """A demo link that carries 1920x1080 used to open at 2560x1440: the canvas
    was seeded from the link, then snapped to the demo's monitor on the first
    run, before any widget showed it."""
    at = _seed(
        global_canvas_width=1920,
        global_canvas_height=1080,
        global_base_font_size=20,
        **{
            sk.LINK_SETUP_STATE_KEY: [
                "global_base_font_size",
                "global_canvas_height",
                "global_canvas_width",
            ]
        },
    )
    width, height, font = at.session_state["_resolved"][:3]
    assert (width, height, font) == (1920, 1080, 20)
    # One-shot: consumed by the first seeding, so a later source switch snaps.
    assert at.session_state["_marker_left"] is False
    # And the snap's restore stash records the linked font as *absent*, so
    # leaving the corpus restores the factory size rather than keeping this one.
    assert at.session_state["_font_snap_restore"]["global_base_font_size"] is None


def test_the_reader_names_what_it_seeded_for_the_snap():
    at = _open_link(canvas_width="1920", base_font_size="20", show_words="1")
    assert sorted(at.session_state[sk.LINK_SETUP_STATE_KEY]) == [
        "global_base_font_size",
        "global_canvas_width",
    ]


# ---------------------------------------------------------------------------
# The whole app, sender to recipient
# ---------------------------------------------------------------------------
#: What the app test sends: the setup (the point-size font switch left alone —
#: with the text scaled to its boxes it changes nothing on screen, and the rail
#: derives the base font from it otherwise) and both scanpaths' styles.
APP_SENT = {
    **{k: v for k, v in SETUP_SENT.items() if k != "global_use_stimulus_font_pt"},
    **STYLES_SENT,
}


@pytest.mark.timeout(600)
def test_the_whole_app_reopens_the_senders_comparison():
    """Sender → Share link → recipient, through every widget on the way: the
    same session values, the same figure input — and no "not in the link"."""
    sender = AppTest.from_file(APP_SCRIPT, default_timeout=250)
    sender.session_state["single_compare_toggle"] = True
    sender.run()
    for key, value in APP_SENT.items():
        sender.session_state[key] = value
    sender.run()
    assert not sender.exception, [e.message for e in sender.exception]
    query, _caveats = sender.session_state["_share_query_current"]
    captions = " ".join(c.value for c in sender.caption)
    assert "aren't in the link" not in captions
    assert "Session → JSON backup" not in captions
    sent_state = sender.session_state["_snippet_state"]
    assert sent_state.kind == "comparison"

    recipient = AppTest.from_file(APP_SCRIPT, default_timeout=250)
    for key, values in parse_qs(query).items():
        recipient.query_params[key] = values[0]
    recipient.run()
    assert not recipient.exception, [e.message for e in recipient.exception]
    got = {key: recipient.session_state[key] for key in APP_SENT}
    assert got == APP_SENT
    got_state = recipient.session_state["_snippet_state"]
    # The demo declares 2560x1440; the snap must not have undone the link.
    assert got_state.canvas == (1920, 1080)
    assert got_state.base_font_size == 20
    assert got_state.kind == "comparison"
    assert got_state.compare.labels == sent_state.compare.labels
    for key in ("style_a", "style_b", "show_legend", "marker_size_range"):
        assert got_state.settings[key] == sent_state.settings[key], key
    assert got_state == sent_state
