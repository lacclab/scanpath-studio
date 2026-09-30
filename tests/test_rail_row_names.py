"""UX-153: a split row's name is a click target.

On a row with a switch the name is the switch's own label, so clicking the word
flips the switch, as it always did on 🎬 Animate and ⚖️ Compare. Every such
toggle takes ``wrap=True``: that switches off Streamlit's one-line "truncate"
label mode, and with it the native ``title=`` tooltip that mode stamps (which
repeated the label, icon ligature included: "compare Compare"). Avoiding that
tooltip is why UX-103 had drawn the rail's switches without their names.

On a name-only row (🧹 Filter, 📐 Figure & canvas) the name stays markdown,
and CSS stretches the ▾ trigger's click target over it.

The click itself happens in the browser, where AppTest cannot follow it. What
is pinned here is the widget tree and the CSS that carries the behaviour.
"""

from __future__ import annotations

import re

import pytest
from streamlit.proto.LabelVisibility_pb2 import LabelVisibility

from scanpath_studio.styles import get_app_css
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

VISIBLE = LabelVisibility.LabelVisibilityOptions.VISIBLE

#: Every toggle that sits in a `split_mode_*` row once the app has booted.
SPLIT_ROW_TOGGLES = (
    "single_animate",
    "single_compare_toggle",
    "global_show_fix",
    "global_show_saccades",
    "global_show_stimulus",
    "global_show_heatmap",
    "global_show_raw_gaze",
)


def _switch_row_app():
    import streamlit as st

    from scanpath_studio.controls import _rail_section

    _rail_section(st, "**Fixations**", slug="fix", key="global_show_fix")


def _name_only_row_app():
    import streamlit as st

    from scanpath_studio.controls import _rail_section

    _rail_section(st, "**Filter**", slug="filter")


def test_a_switch_row_names_its_switch():
    at = AppTest.from_function(_switch_row_app)
    at.run()
    assert not at.exception

    toggle = at.toggle(key="global_show_fix")
    assert toggle.label == "**Fixations**"
    assert toggle.proto.label_visibility.value == VISIBLE
    assert toggle.proto.wrap is True
    # The name is not written a second time beside the switch.
    assert "**Fixations**" not in [m.value for m in at.markdown]


def test_a_name_only_row_keeps_its_name_as_text():
    at = AppTest.from_function(_name_only_row_app)
    at.run()
    assert not at.exception

    assert len(at.toggle) == 0
    assert [m.value for m in at.markdown] == ["**Filter**"]


def test_every_split_row_toggle_opts_out_of_the_title_tooltip():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception

    for key in SPLIT_ROW_TOGGLES:
        toggle = at.toggle(key=key)
        assert toggle.proto.label_visibility.value == VISIBLE, key
        assert toggle.proto.wrap is True, key


def _css() -> str:
    return re.sub(r"\s+", " ", get_app_css())


def test_the_name_only_rows_stretch_the_trigger_over_the_name():
    css = _css()
    name_only = (
        '[data-testid="stHorizontalBlock"][class*="st-key-split_mode_rail_"]:not( '
        ':has([data-testid="stCheckbox"]) )'
    )
    assert f"{name_only} {{ position: relative; }}" in css
    assert f'{name_only} [data-testid="stPopover"] button::after {{' in css


def test_the_switch_slot_is_flexible_again():
    # UX-103 had pinned the switch to its own width because the name was a
    # separate flexible child; with the name back inside the toggle, that rule
    # would leave no room for the label.
    css = _css()
    assert (
        '[class*="st-key-split_mode_rail_"] > div:has([data-testid="stCheckbox"])'
        not in css
    )
