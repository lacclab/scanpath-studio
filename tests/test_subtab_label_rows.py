"""UX-59: the Scanpath subtabs read `label | field`, not label-above.

The sibling [`test_rail_label_rows.py`](test_rail_label_rows.py) pins the row
itself (key + label + collapsed visibility + the folded-in tooltip). What is new
here is *reach*: the row moved down into :mod:`scanpath_studio.fields` so the
three modules that render these subtabs — `annotations`, `export`, `url_state` —
can use it, and `controls` (which imports two of them, and so cannot be imported
back) now delegates to the same code.

So these cover the two things that pass could break and a rendered page would
not show: that the delegation kept `controls`' own row intact, and that each
converted subtab field still carries its real label and key while hiding them.
"""

from __future__ import annotations

import pytest
from streamlit.proto.LabelVisibility_pb2 import LabelVisibility

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

COLLAPSED = LabelVisibility.LabelVisibilityOptions.COLLAPSED


def _labels(at) -> list[str]:
    """Every row label rendered this run, as raw markdown."""
    return [m.value for m in at.markdown if "sps-flabel" in (m.value or "")]


class TestSharedPrimitive:
    """`controls` and the subtabs must be the same row, not two copies of one."""

    def test_controls_delegates_to_fields(self):
        from scanpath_studio import controls, fields

        assert controls._row_label is fields.row_label
        assert controls._plain is fields.plain
        assert controls._LABEL_W == fields.NARROW_LABEL_W

    def test_a_panel_row_is_wider_than_a_rail_row(self):
        """The two widths are the point of having two entry points.

        The rail lives in a ~28rem popover and the subtabs are 4/5 of the page,
        so one shared share would either crush the rail's fields or spend a
        quarter of a full-width panel on its titles.
        """
        from scanpath_studio import fields

        assert fields.PANEL_LABEL_W < fields.NARROW_LABEL_W

    def test_panel_field_can_be_pushed_back_to_the_narrow_width(self):
        """`panel_field` sets a default, not a policy — a side column overrides."""

        def app():
            import streamlit as st

            from scanpath_studio.fields import NARROW_LABEL_W, panel_field

            panel_field(
                st,
                "selectbox",
                "Comparison column",
                options=["a"],
                key="k",
                label_width=NARROW_LABEL_W,
            )

        at = AppTest.from_function(app).run(timeout=30)
        assert not at.exception, at.exception
        assert ">Comparison column</span>" in _labels(at)[0]


class TestConvertedFields:
    """One representative field per module that renders a subtab."""

    def test_the_annotations_editor_keeps_its_keys_and_labels(self):
        """The keys are the annotation store's own; the labels are AppTest's."""

        def app():
            from scanpath_studio.annotations import render_trial_annotations

            render_trial_annotations("p1", "t1", bare=True)

        at = AppTest.from_function(app).run(timeout=30)
        assert not at.exception, at.exception

        tags = at.multiselect(key="annotrial_tags_p1__t1__parent")
        assert tags.label == "Tags"
        assert tags.proto.label_visibility.value == COLLAPSED

        note = at.text_area(key="annotrial_note_p1__t1__parent")
        assert note.label == "Notes"
        assert note.proto.label_visibility.value == COLLAPSED

        rendered = _labels(at)
        assert any(">Tags</span>" in label for label in rendered)
        assert any(">Notes</span>" in label for label in rendered)

    def test_a_shortened_title_keeps_the_full_label_and_says_so_on_hover(self):
        """`display` shortens what is *drawn*, never the accessible name.

        The favorite checkbox's label is a sentence, and the title column is one
        ellipsized line — so the column carries "⭐ Favorite" and the widget
        keeps "⭐ Favorite (star this trial)" for the store, for AppTest and for
        a screen reader.
        """

        def app():
            from scanpath_studio.annotations import render_trial_annotations

            render_trial_annotations("p1", "t1", bare=True)

        at = AppTest.from_function(app).run(timeout=30)
        star = at.checkbox(key="annotrial_star_p1__t1__parent")
        assert star.label == "⭐ Favorite (star this trial)"
        assert star.proto.label_visibility.value == COLLAPSED

        (drawn,) = [label for label in _labels(at) if "Favorite" in label]
        assert ">⭐ Favorite</span>" in drawn
        assert "data-tip" in drawn, "the shortened title must carry its help"

    def test_the_export_options_render_as_rows(self):
        """`render_export_options` is handed `st`; the rows go through it."""

        def app():
            import pandas as pd

            from scanpath_studio.export import render_export_options

            combos = pd.DataFrame(
                {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["x1"]}
            )
            render_export_options(__import__("streamlit"), combos, key_prefix="bulk")

        at = AppTest.from_function(app).run(timeout=30)
        assert not at.exception, at.exception

        scope = at.radio(key="bulk_scope")
        assert scope.label == "Trials to include"
        assert scope.proto.label_visibility.value == COLLAPSED

        rendered = _labels(at)
        for title in ("Trials to include", "Formats", "Separable layers"):
            assert any(f">{title}</span>" in label for label in rendered), title

    def test_every_converted_widget_hides_its_own_label(self):
        """A row that forgot `label_visibility` prints its title twice."""

        def app():
            import pandas as pd

            from scanpath_studio.export import render_export_options

            combos = pd.DataFrame(
                {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["x1"]}
            )
            render_export_options(__import__("streamlit"), combos, key_prefix="bulk")

        at = AppTest.from_function(app).run(timeout=30)
        widgets = [
            *at.radio,
            *at.selectbox,
            *at.multiselect,
            *at.text_input,
            *at.number_input,
        ]
        assert widgets, "the panel rendered no widgets to check"
        for widget in widgets:
            assert widget.proto.label_visibility.value == COLLAPSED, widget.label
