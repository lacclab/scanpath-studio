"""The chips popover's field colours: ✕ puts a chip back to the default gray,
and a picker the browser has not shown yet never mounts black.

The color picker gives no way to land on that exact gray.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _picker(at, field: str):
    """The field's colour picker, whatever generation its key is at."""
    return next(
        p for p in at.color_picker if str(p.key).startswith(f"trial_chip_color_{field}")
    )


def _app(colors: dict[str, str]):
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT, default_timeout=300)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["trial_chip_fields"] = ["participant_id", "text_id"]
    at.session_state["trial_chip_colors"] = colors
    return at


def test_clear_button_resets_the_color_to_gray() -> None:
    at = _app({"participant_id": "#FF0000"})
    at.run()
    key = "trial_chip_color_clear_participant_id"
    clear = next(b for b in at.button if b.key == key)
    assert not clear.disabled

    clear.click().run()

    assert _picker(at, "participant_id").value.upper() == "#EEF2F7"
    # …which the picker logic reads as no highlight.
    assert at.session_state["trial_chip_colors"] == {}
    assert next(b for b in at.button if b.key == key).disabled
    # A later run keeps it there.
    at.run()
    assert at.session_state["trial_chip_colors"] == {}
    assert not at.exception


def test_a_picker_is_sent_its_color_as_default_on_every_run() -> None:
    """The browser mounts a popover's picker only when the popover opens, at
    the default the last run sent. That default is the stored colour or the
    neutral gray on every run, never Streamlit's black: a black default
    turned every summary chip black after the menu was first opened."""
    at = _app({"participant_id": "#FF0000"})
    at.run()
    at.run()  # the picker keys now exist: the run that used to drop `value=`
    assert _picker(at, "participant_id").proto.default.upper() == "#FF0000"
    assert _picker(at, "text_id").proto.default.upper() == "#EEF2F7"
    assert at.session_state["trial_chip_colors"] == {"participant_id": "#FF0000"}
    assert not at.exception
