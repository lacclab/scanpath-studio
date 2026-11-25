"""Links in the Scanpath view that open a panel of the Data Management page."""

from __future__ import annotations

import pytest

from scanpath_studio.constants import (
    _VIEW_DATA,
    DATA_INSPECTION_KEY,
    SUBTAB_ANNOTATIONS,
)
from tests.conftest import APP_SCRIPT, pin_view

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _scanpath_app():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    pin_view(at, "Scanpath")
    return at


def _assert_on_data_panel(at, panel: str) -> None:
    assert not at.exception, at.exception
    assert at.session_state["main_nav"] == _VIEW_DATA
    assert at.session_state[DATA_INSPECTION_KEY] == panel
    assert at.segmented_control(key=DATA_INSPECTION_KEY).value == panel


@pytest.mark.timeout(240)
def test_tables_button_beside_the_dataset_picker_opens_the_tables():
    at = _scanpath_app()
    at.run(timeout=90)
    assert not at.exception, at.exception
    at.button(key="open_data_tables_btn").click().run(timeout=90)
    _assert_on_data_panel(at, "Tables")
    assert "Fixations" in [h.value for h in at.subheader]


@pytest.mark.timeout(240)
def test_annotations_subtab_pointer_opens_the_annotations_panel():
    at = _scanpath_app()
    at.session_state["single_subtab"] = SUBTAB_ANNOTATIONS
    at.run(timeout=90)
    assert not at.exception, at.exception
    at.button(key="annotation_open_data_annotations").click().run(timeout=90)
    _assert_on_data_panel(at, "Annotations")
