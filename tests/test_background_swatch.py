"""The background's colour box shows the colour in use, and a pick applies.

It is not greyed until *Custom…* is picked in the selectbox beside it. The
wire keys (`global_bg_choice` / `global_bg_custom`) keep their meaning, so
links, settings files, the CLI and the API read them the same way.
"""

from __future__ import annotations

import pytest

from scanpath_studio.constants import BACKGROUND_PRESETS, DEFAULT_BACKGROUND_COLOR
from scanpath_studio.controls import BG_CUSTOM_CHOICE, resolved_background_color

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _row():
    import streamlit as st

    from scanpath_studio.controls import BG_CHOICES, background_swatch

    st.session_state.setdefault("global_bg_custom", "#ffffff")
    st.selectbox("Plot background", BG_CHOICES, key="global_bg_choice")
    background_swatch(st, label="Background color")


def _run(**state) -> AppTest:
    at = AppTest.from_function(_row)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at


class TestResolvedColor:
    def test_a_preset_is_its_own_color(self):
        assert (
            resolved_background_color({"global_bg_choice": "Gray"})
            == (BACKGROUND_PRESETS["Gray"])
        )

    def test_custom_is_the_custom_color(self):
        state = {"global_bg_choice": BG_CUSTOM_CHOICE, "global_bg_custom": "#123456"}
        assert resolved_background_color(state) == "#123456"

    def test_nothing_set_is_the_default(self):
        assert resolved_background_color({}) == DEFAULT_BACKGROUND_COLOR


def test_the_box_shows_the_preset_in_use():
    at = _run(global_bg_choice="Black", global_bg_custom="#123456")
    assert at.color_picker[0].value == BACKGROUND_PRESETS["Black"]
    assert not at.color_picker[0].disabled


def test_a_picked_color_applies_without_choosing_custom_first():
    at = _run(global_bg_choice="White")
    at.color_picker[0].set_value("#123456").run(timeout=30)
    assert at.session_state["global_bg_choice"] == BG_CUSTOM_CHOICE
    assert at.session_state["global_bg_custom"] == "#123456"
    assert at.color_picker[0].value == "#123456"


def test_a_preset_color_picked_in_the_box_selects_the_preset():
    at = _run(global_bg_choice=BG_CUSTOM_CHOICE, global_bg_custom="#123456")
    at.color_picker[0].set_value(BACKGROUND_PRESETS["Gray"]).run(timeout=30)
    assert at.session_state["global_bg_choice"] == "Gray"
    # The custom colour is kept for when Custom… is chosen again.
    assert at.session_state["global_bg_custom"] == "#123456"


def test_choosing_a_preset_moves_the_box_and_keeps_the_custom_color():
    at = _run(global_bg_choice=BG_CUSTOM_CHOICE, global_bg_custom="#123456")
    at.selectbox[0].set_value("Gray").run(timeout=30)
    assert at.color_picker[0].value == BACKGROUND_PRESETS["Gray"]
    assert at.session_state["global_bg_custom"] == "#123456"


@pytest.mark.timeout(120)
def test_the_rail_swatch_sets_the_figure_background():
    """In the app: the swatch in 📄 Stimulus → Text is live, and a pick reaches
    the figure's settings."""
    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=60)
    assert not at.exception, at.exception
    swatch = next(
        w for w in at.color_picker if str(w.key).startswith("_rail_bg_swatch__w")
    )
    assert not swatch.disabled
    swatch.set_value("#123456").run(timeout=60)
    assert not at.exception, at.exception
    assert at.session_state["global_bg_choice"] == BG_CUSTOM_CHOICE
    assert at.session_state["global_bg_custom"] == "#123456"


def _shadow_app():
    import streamlit as st

    from scanpath_studio.controls import shadow_widget_key

    keys = st.session_state.setdefault("_keys", [])
    keys.append(shadow_widget_key("probe", st.session_state.get("_value", "a")))


def test_a_shadow_moves_to_a_fresh_key_only_when_its_value_moves():
    """A value changed elsewhere gets a widget the browser never saw,
    so no stale value can come back as a pick; an unchanged one keeps its key."""
    at = AppTest.from_function(_shadow_app).run(timeout=30)
    at.run(timeout=30)
    at.session_state["_value"] = "b"
    at.run(timeout=30)
    first, same, moved = at.session_state["_keys"]
    assert first == same
    assert moved != first
    assert at.session_state[moved] == "b"
    assert first not in at.session_state


class TestTheShadowsCarryTheirOwnDefault:
    """A dataset switch must not turn the background black. A swatch created
    in a closed popover with its colour set through session state never
    receives that colour — a widget the browser has not mounted does not — so
    the browser would mount it at a colour picker's built-in ``#000000`` and
    send that back on the next rerun as a pick, selecting the Black background.
    A shadow widget carries the value as its *own* default, which the element
    itself holds, so it mounts right however late it is opened. The same holds for the Compare
    colour and opacity shadows and the font picker."""

    def test_the_swatch_default_is_the_background_in_use(self):
        at = _run(global_bg_choice="Light gray")
        (picker,) = at.color_picker
        assert picker.proto.default.lower() == BACKGROUND_PRESETS["Light gray"]

    def test_the_compare_colors_default_to_what_is_drawn(self):
        def app():
            import streamlit as st

            from scanpath_studio import controls

            st.session_state.setdefault("cmp1_box_color", "#123456")
            controls._compare_follow_color_picker(
                st, 1, "box", follow="#abcdef", help="", what="word box line"
            )
            controls._compare_follow_color_picker(
                st, 0, "box", follow="#abcdef", help="", what="word box line"
            )

        at = AppTest.from_function(app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        defaults = sorted(p.proto.default.lower() for p in at.color_picker)
        assert defaults == ["#123456", "#abcdef"]

    def test_the_opacity_sliders_default_to_what_is_drawn(self):
        def app():
            import streamlit as st

            from scanpath_studio import controls

            st.session_state.setdefault("global_word_box_fill_opacity", 0.3)
            controls._compare_follow_opacity(
                st, 1, "fill", label="word box fill opacity", help=""
            )

        at = AppTest.from_function(app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        (slider,) = at.slider
        assert list(slider.proto.default) == [pytest.approx(0.3)]
        (box,) = at.number_input
        assert box.proto.default == pytest.approx(0.3)
