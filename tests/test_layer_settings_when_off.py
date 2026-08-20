"""UX-97: a layer's settings stay reachable while the layer toggle is off.

Each layer section on the Scanpath rail is a `toggle → ⚙️ style → 🧹 filter`
row. The ▾ that opens the style popover is always clickable, but the popover's
*body* used to be gated `if show_<layer>:` — so turning a layer off left an
affordance that opened onto nothing. The controls now always render and are
greyed instead, which is also what lets a user prepare a layer's styling before
switching it on.

Two halves are pinned here: the mechanism (`_layer_off` greys whatever renders
inside it, and folds the reason into each control's help) and the four layers
that use it (fixations, saccades, heatmap, raw gaze), which must still expose
their wire-format keys with the layer off.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _off_app():
    """One `_labeled` row and one slider, both inside an off layer."""
    import streamlit as st

    from scanpath_studio.controls import _labeled, _layer_off, _numeric_slider

    with _layer_off("↗️ Saccades", off=True):
        _labeled(
            st,
            "selectbox",
            "Line style",
            options=["solid", "dash"],
            key="global_saccade_style",
            help="Saccade line style.",
        )
        _numeric_slider(
            st,
            "Line width",
            label_left=True,
            key="global_saccade_width",
            min_value=0.5,
            max_value=6.0,
            step=0.5,
        )


def _on_app():
    """The same row with the layer on — nothing is greyed."""
    import streamlit as st

    from scanpath_studio.controls import _labeled, _layer_off

    with _layer_off("↗️ Saccades", off=False):
        _labeled(
            st,
            "selectbox",
            "Line style",
            options=["solid", "dash"],
            key="global_saccade_style",
            help="Saccade line style.",
        )


class TestTheLayerOffGate:
    def test_it_greys_every_control_and_says_why(self):
        at = AppTest.from_function(_off_app)
        at.run(timeout=30)
        assert not at.exception, at.exception

        style = at.selectbox(key="global_saccade_style")
        assert style.proto.disabled
        # The reason rides the control's own help, so the tooltip explains the
        # greying rather than leaving the user guessing (as `_mode_gate` does).
        assert "Saccades" in style.proto.help
        assert "Saccade line style." in style.proto.help
        # The slider *and* its typed box (UX-9) both grey.
        assert at.slider(key="global_saccade_width").proto.disabled
        assert at.number_input(key="global_saccade_width__num").proto.disabled
        # Plus one caption at the head of the popover, for the case where the
        # user never hovers a control.
        assert any("turn the layer on" in (c.value or "") for c in at.caption)

    def test_the_stored_value_is_untouched(self):
        """A disabled widget keeps its key — greying must not rewrite settings.

        Same contract as `_mode_gate`: these are share-link and saved-config
        wire format, so a layer toggle may not clobber them.
        """
        at = AppTest.from_function(_off_app)
        at.session_state["global_saccade_style"] = "dash"
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["global_saccade_style"] == "dash"

    def test_an_on_layer_greys_nothing(self):
        at = AppTest.from_function(_on_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        style = at.selectbox(key="global_saccade_style")
        assert not style.proto.disabled
        assert style.proto.help == "Saccade line style."


#: One control per layer, named by the widget method that finds it: with the
#: layer off it must still RENDER (`in at.session_state` proves nothing — the
#: `global_*` defaults are seeded whether or not the widget draws) and be greyed.
_LAYER_CONTROLS = [
    ("global_show_saccades", "slider", "global_saccade_width"),
    ("global_show_heatmap", "selectbox", "global_heatmap_metric"),
    ("global_show_raw_gaze", "color_picker", "global_raw_gaze_color"),
]


@pytest.mark.timeout(180)
@pytest.mark.parametrize("toggle_key, kind, setting_key", _LAYER_CONTROLS)
def test_the_rail_still_renders_a_layers_settings_with_the_layer_off(
    toggle_key, kind, setting_key
):
    """The real rail, not the helper: the popover body is no longer gated away."""
    at = AppTest.from_file(str(APP_SCRIPT), default_timeout=180)
    at.session_state[toggle_key] = False
    at.run()
    assert not at.exception, at.exception

    control = getattr(at, kind)(key=setting_key)
    assert control.proto.disabled
    assert "turn the layer on" in control.proto.help


@pytest.mark.timeout(180)
@pytest.mark.parametrize("toggle_key, kind, setting_key", _LAYER_CONTROLS)
def test_the_same_controls_are_live_with_the_layer_on(toggle_key, kind, setting_key):
    """The other half: greying is the layer's doing, not a permanent state."""
    at = AppTest.from_file(str(APP_SCRIPT), default_timeout=180)
    at.session_state[toggle_key] = True
    at.run()
    assert not at.exception, at.exception
    assert not getattr(at, kind)(key=setting_key).proto.disabled
