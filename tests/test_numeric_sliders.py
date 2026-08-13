"""UX-9: sliders paired with a typed number box.

The contract that matters is that the *slider* still owns the canonical session
key (deep links, Share, Save & restore and ``_collect_viz_settings`` read it
unchanged) while the box stays in step in both directions.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _scalar_app():
    import streamlit as st

    from scanpath_studio.controls import _numeric_slider

    st.session_state.setdefault("global_fixation_opacity", 0.7)
    _numeric_slider(
        st,
        "Opacity",
        key="global_fixation_opacity",
        min_value=0.1,
        max_value=1.0,
        step=0.05,
        slider_format="%.2f",
    )


def _range_app():
    import streamlit as st

    from scanpath_studio.controls import _range_slider

    st.session_state.setdefault("global_marker_size_range", (8, 24))
    _range_slider(
        st,
        "Size",
        key="global_marker_size_range",
        min_value=4,
        max_value=40,
    )


def _float_range_with_int_format_app():
    """The colour-range shape: whole numbers on screen, float bounds underneath.

    The bounds are floats on purpose (a restored config clamps into another
    dataset's range), so a bare ``"%d"`` made ``st.number_input`` print a yellow
    type-mismatch warning above each box in the rail.
    """
    import streamlit as st

    from scanpath_studio.controls import _range_slider

    st.session_state.setdefault("global_fixation_color_range", (100.0, 1058.0))
    _range_slider(
        st,
        "Fixation color range",
        key="global_fixation_color_range",
        min_value=100.0,
        max_value=1058.0,
        step=1.0,
        slider_format="%d",
    )


def _float_scalar_with_int_format_app():
    import streamlit as st

    from scanpath_studio.controls import _numeric_slider

    st.session_state.setdefault("some_float_setting", 12.0)
    _numeric_slider(
        st,
        "Whole number",
        key="some_float_setting",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        slider_format="%d",
    )


class TestIntFormatOnFloatValues:
    def test_range_boxes_do_not_warn(self):
        at = AppTest.from_function(_float_range_with_int_format_app)
        at.run()
        assert not at.exception, at.exception
        assert not at.warning, [w.value for w in at.warning]
        assert at.number_input(key="global_fixation_color_range__num_lo").value == 100.0

    def test_scalar_box_does_not_warn(self):
        at = AppTest.from_function(_float_scalar_with_int_format_app)
        at.run()
        assert not at.exception, at.exception
        assert not at.warning, [w.value for w in at.warning]

    def test_the_slider_keeps_the_integer_format(self):
        """Only the box's format is adapted — the slider ticks stay whole."""
        at = AppTest.from_function(_float_range_with_int_format_app)
        at.run()
        assert at.slider(key="global_fixation_color_range").value == (100.0, 1058.0)


class TestNumericSlider:
    def test_box_mirrors_the_canonical_value(self):
        at = AppTest.from_function(_scalar_app)
        at.run()
        assert not at.exception, at.exception
        assert at.number_input(key="global_fixation_opacity__num").value == 0.7

    def test_typing_a_value_writes_the_canonical_key(self):
        at = AppTest.from_function(_scalar_app)
        at.run()
        at.number_input(key="global_fixation_opacity__num").set_value(0.35).run()
        assert at.session_state["global_fixation_opacity"] == pytest.approx(0.35)
        assert at.slider(key="global_fixation_opacity").value == pytest.approx(0.35)

    def test_dragging_the_slider_moves_the_box(self):
        at = AppTest.from_function(_scalar_app)
        at.run()
        at.slider(key="global_fixation_opacity").set_value(0.5).run()
        assert at.number_input(
            key="global_fixation_opacity__num"
        ).value == pytest.approx(0.5)

    def test_an_external_write_moves_both(self):
        """A deep link / restored config sets the canonical key between runs."""
        at = AppTest.from_function(_scalar_app)
        at.run()
        at.session_state["global_fixation_opacity"] = 0.9
        at.run()
        assert at.slider(key="global_fixation_opacity").value == pytest.approx(0.9)
        assert at.number_input(
            key="global_fixation_opacity__num"
        ).value == pytest.approx(0.9)


class TestRangeSlider:
    def test_boxes_mirror_the_canonical_pair(self):
        at = AppTest.from_function(_range_app)
        at.run()
        assert not at.exception, at.exception
        assert at.number_input(key="global_marker_size_range__num_lo").value == 8
        assert at.number_input(key="global_marker_size_range__num_hi").value == 24

    def test_typing_writes_the_canonical_tuple(self):
        at = AppTest.from_function(_range_app)
        at.run()
        at.number_input(key="global_marker_size_range__num_hi").set_value(30).run()
        assert at.session_state["global_marker_size_range"] == (8, 30)

    def test_an_inverted_pair_is_swapped_not_rejected(self):
        at = AppTest.from_function(_range_app)
        at.run()
        at.number_input(key="global_marker_size_range__num_lo").set_value(30).run()
        assert at.session_state["global_marker_size_range"] == (24, 30)

    def test_dragging_the_slider_moves_the_boxes(self):
        at = AppTest.from_function(_range_app)
        at.run()
        at.slider(key="global_marker_size_range").set_range(10, 20).run()
        assert at.number_input(key="global_marker_size_range__num_lo").value == 10
        assert at.number_input(key="global_marker_size_range__num_hi").value == 20
