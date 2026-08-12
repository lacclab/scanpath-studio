"""UX-51: the Scanpath rail's controls read `label | field`, not label-above.

Moving a control's title into a column of its own changes the widget tree, and
almost all of what the change must NOT break is invisible in the rendered page:

* the widget keeps its **key** — every `global_*` / `single_*` / `filter_*` key
  is share-link and saved-config wire format, so a layout change that renamed or
  dropped one would silently break users' old links;
* it keeps its **label**, merely collapsed, so the accessible name (and every
  `AppTest` lookup by label) survives the move;
* the `?` help icon folds into the title as its own hover tooltip, with the
  title text repeated at the head of it — that repetition is the escape hatch
  for a label the shared-width column had to truncate.

These pin all four, plus the escaping that keeps a label or a help string from
injecting markup into the page.
"""

from __future__ import annotations

import pytest
from streamlit.proto.LabelVisibility_pb2 import LabelVisibility

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

#: A widget whose title moved into the label column hides its own label rather
#: than losing it — the accessible name (and every AppTest label lookup) stays.
COLLAPSED = LabelVisibility.LabelVisibilityOptions.COLLAPSED


def _row_app():
    """One converted control, standing in for every rail row."""
    import streamlit as st

    from scanpath_studio.controls import _labeled

    _labeled(
        st,
        "selectbox",
        "Color fixations by",
        options=["(uniform)", "duration_ms"],
        key="global_color_by",
        persist_state="session",
        help="The metric mapped to fixation marker **hue**.",
    )


def _plain_row_app():
    """A control with no help — no tooltip affordance to add."""
    import streamlit as st

    from scanpath_studio.controls import _labeled

    _labeled(st, "selectbox", "Marker shape", options=["circle"], key="global_x")


def _unsafe_row_app():
    """A label and a help string that would be markup if left unescaped."""
    import streamlit as st

    from scanpath_studio.controls import _labeled

    _labeled(
        st,
        "selectbox",
        '<b>Size</b> & "shape"',
        options=["a"],
        key="global_x",
        help='</span><script>alert("x")</script>',
    )


def _slider_app():
    """The UX-9 slider + typed box, in its UX-51 `label | slider | box` form."""
    import streamlit as st

    from scanpath_studio.controls import _numeric_slider

    _numeric_slider(
        st,
        "Opacity",
        label_left=True,
        key="global_fixation_opacity",
        min_value=0.1,
        max_value=1.0,
        step=0.05,
        slider_format="%.2f",
        help="Fixation marker opacity.",
    )


def _label_markup(at) -> list[str]:
    """Every UX-51 row label rendered this run, as raw markdown."""
    return [m.value for m in at.markdown if "sps-flabel" in (m.value or "")]


class TestOneRow:
    def test_the_widget_keeps_its_key_label_and_help(self):
        """Only where the title is DRAWN moves — not the wire format."""
        at = AppTest.from_function(_row_app)
        at.run(timeout=30)
        assert not at.exception, at.exception

        box = at.selectbox(key="global_color_by")
        assert box.label == "Color fixations by"
        assert box.proto.help == "The metric mapped to fixation marker **hue**."
        # Collapsed, not removed: the accessible name is still the real label.
        assert box.proto.label_visibility.value == COLLAPSED

    def test_the_title_renders_in_its_own_column(self):
        at = AppTest.from_function(_row_app)
        at.run(timeout=30)
        labels = _label_markup(at)
        assert len(labels) == 1, labels
        assert ">Color fixations by</span>" in labels[0]

    def test_the_help_folds_into_the_title_tooltip(self):
        """The `?` icon's replacement — hovering the title shows the help.

        The markdown emphasis is stripped: a `title=` attribute is plain text, so
        `**hue**` would otherwise reach the user as literal asterisks.
        """
        at = AppTest.from_function(_row_app)
        at.run(timeout=30)
        (label,) = _label_markup(at)
        assert (
            'title="Color fixations by — The metric mapped to fixation marker hue."'
            in label
        )
        assert "sps-flabel-help" in label, (
            "a title carrying help needs the hover affordance class — it is the "
            "only hint left that there is something to hover"
        )

    def test_the_tooltip_repeats_the_title(self):
        """What makes a truncated label recoverable.

        The label column is one shared width per section, so an over-long title
        ellipsises. It must still be readable in full from the tooltip.
        """
        at = AppTest.from_function(_row_app)
        at.run(timeout=30)
        (label,) = _label_markup(at)
        assert 'title="Color fixations by' in label

    def test_a_title_without_help_gets_no_hover_affordance(self):
        at = AppTest.from_function(_plain_row_app)
        at.run(timeout=30)
        (label,) = _label_markup(at)
        assert "sps-flabel-help" not in label
        assert 'title="Marker shape"' in label

    def test_markup_in_a_title_or_help_is_escaped(self):
        """The label is rendered with `unsafe_allow_html`, so it must escape."""
        at = AppTest.from_function(_unsafe_row_app)
        at.run(timeout=30)
        assert not at.exception, at.exception
        (label,) = _label_markup(at)
        assert "<b>" not in label and "<script>" not in label
        assert "&lt;b&gt;Size&lt;/b&gt;" in label


class TestSliderRow:
    def test_the_slider_still_owns_the_canonical_key(self):
        """UX-9's contract survives the extra column (the box keeps the shadow)."""
        at = AppTest.from_function(_slider_app)
        at.session_state["global_fixation_opacity"] = 0.7
        at.run(timeout=30)
        assert not at.exception, at.exception

        assert at.slider(key="global_fixation_opacity").value == pytest.approx(0.7)
        assert at.number_input(
            key="global_fixation_opacity__num"
        ).value == pytest.approx(0.7)
        # Typing an exact value still writes the canonical key.
        at.number_input(key="global_fixation_opacity__num").set_value(0.35).run(
            timeout=30
        )
        assert at.session_state["global_fixation_opacity"] == pytest.approx(0.35)

    def test_the_slider_label_moves_to_the_column(self):
        at = AppTest.from_function(_slider_app)
        at.run(timeout=30)
        (label,) = _label_markup(at)
        assert ">Opacity</span>" in label
        slider = at.slider(key="global_fixation_opacity")
        assert slider.label == "Opacity"
        assert slider.proto.label_visibility.value == COLLAPSED


@pytest.mark.timeout(180)
class TestTheRealRail:
    """The whole rail, through the app, not one control in isolation."""

    def test_rail_controls_keep_their_wire_format_keys(self):
        at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        at.run()
        assert not at.exception, at.exception

        keys = (
            {s.key for s in at.selectbox}
            | {s.key for s in at.slider}
            | {m.key for m in at.multiselect}
        )
        # One converted control per widget kind that the Fixations section opens
        # with: a selectbox, a range slider and a multiselect.
        for key in (
            "global_color_by",
            "global_align_algorithm",
            "global_marker_size_range",
            "global_fixation_hover_fields",
        ):
            assert key in keys, f"{key} is gone from the rail"

    def test_rail_rows_render_their_titles_as_label_columns(self):
        at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
        at.session_state["data_source_choice"] = "Synthetic test trial"
        at.run()
        labels = " ".join(_label_markup(at))
        assert labels, "no UX-51 row labels rendered anywhere in the rail"
        for title in ("Color fixations by", "Drift correction", "Marker shape"):
            assert f">{title}</span>" in labels, f"{title} lost its label column"
        # …carrying the control's help as the title's own tooltip.
        assert 'title="Drift correction — Snap fixations' in labels
