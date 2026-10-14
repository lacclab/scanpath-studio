"""The chips popover's ✕ removes a chip's highlight.

Picking the default gray back was the only way before, and the color picker
gives no way to land on that exact gray.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def test_clear_button_removes_the_highlight() -> None:
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=300)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["trial_chip_fields"] = ["participant_id"]
    at.session_state["trial_chip_colors"] = {"participant_id": "#FF0000"}
    at.run()
    key = "trial_chip_color_clear_participant_id"
    clear = next(b for b in at.button if b.key == key)
    assert not clear.disabled

    clear.click().run()

    assert at.session_state["trial_chip_colors"] == {}
    assert next(b for b in at.button if b.key == key).disabled
    assert not at.exception
