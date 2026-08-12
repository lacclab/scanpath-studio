"""The in-app debug log: capture, filter, escape, and the ``?debug=1`` gate.

``logging`` and ``print`` only reach the *server* terminal, so this panel is how
a log line gets in front of a user who is running the hosted demo or the desktop
bundle. ENG-37 found it was the thinnest-covered module in the package — the only
part under test was the S10 install-once guard (``tests/test_security_fixes.py``),
which meant nothing checked that a captured record actually renders, or that a
log message containing HTML can't inject into the panel (it is written with
``unsafe_allow_html=True``).
"""

from __future__ import annotations

import logging

import pytest

from scanpath_studio import debug_log
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_escaping_neutralizes_markup_in_a_log_message():
    """The panel renders messages with ``unsafe_allow_html=True``.

    A logger is fed by anything the app touches, including file names and column
    names that came out of a user's corpus.
    """
    escaped = debug_log._escape("<img src=x onerror=alert(1)> a & b")
    assert escaped == "&lt;img src=x onerror=alert(1)&gt; a &amp; b"
    assert "<" not in escaped and ">" not in escaped


def _capture_app():
    """Install the handler, log one record of each level, report the buffer."""
    import logging as _logging

    import streamlit as st

    from scanpath_studio.debug_log import _buffer, install_log_capture

    install_log_capture()
    logger = _logging.getLogger("scanpath_studio.test")
    logger.info("an info line")
    logger.warning("a warning line")
    logger.debug("a debug line")
    st.session_state["_seen"] = [
        (r["level"], r["logger"], r["message"]) for r in _buffer()
    ]


def test_records_land_in_the_session_buffer():
    at = AppTest.from_function(_capture_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    seen = at.session_state["_seen"]
    levels = {level for level, _, _ in seen}
    assert ("INFO", "scanpath_studio.test", "an info line") in seen
    assert ("WARNING", "scanpath_studio.test", "a warning line") in seen
    # install_log_capture raises the root level to INFO, so DEBUG is filtered out
    # before it reaches any handler.
    assert "DEBUG" not in levels


def test_the_buffer_is_capped_so_a_chatty_run_cannot_grow_session_state():
    def _flood():
        import logging as _logging

        import streamlit as st

        from scanpath_studio.debug_log import _MAX_RECORDS, _buffer, install_log_capture

        install_log_capture()
        logger = _logging.getLogger("scanpath_studio.flood")
        for index in range(_MAX_RECORDS + 50):
            logger.info("line %d", index)
        buf = _buffer()
        st.session_state["_len"] = len(buf)
        st.session_state["_first"] = buf[0]["message"]

    at = AppTest.from_function(_flood)
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert at.session_state["_len"] == debug_log._MAX_RECORDS
    # Oldest records are dropped, not newest — the tail is what you want to read.
    assert at.session_state["_first"] == "line 50"


def test_the_handler_swallows_a_record_it_cannot_file():
    """A log record from a thread with no script-run context must not raise.

    Logging is called from everywhere, including background work; a handler that
    raises would surface as a failure in whatever was being logged about.
    """
    handler = debug_log._SessionStateHandler()
    record = logging.LogRecord(
        "x", logging.INFO, __file__, 1, "boom %s", ("arg",), None
    )
    handler.emit(record)  # no session-state context here — must not raise


def test_the_toggle_is_offered_without_any_url_param():
    """UX-37: the toggle *is* the way in, so a plain visit has to show it."""
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    assert not at.exception, at.exception
    toggles = [t for t in at.toggle if t.key == debug_log.DEBUG_STATE_KEY]
    assert toggles, "the 🐛 Debug mode toggle is not on the ❓ Help menu"
    assert toggles[0].value is False, "debug mode must default off"
    # …and with it off, the panel draws nothing.
    assert not [s for s in at.selectbox if s.key == "_debug_level"]


def test_the_toggle_reveals_the_panel():
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    toggles = [t for t in at.toggle if t.key == debug_log.DEBUG_STATE_KEY]

    # Turning it on renders the panel: a level filter, a Clear button, a state
    # snapshot and the JSON download.
    at = toggles[0].set_value(True).run(timeout=90)
    assert not at.exception, at.exception
    assert [s for s in at.selectbox if s.key == "_debug_level"]
    assert [b for b in at.button if b.key == "_debug_clear"]
    assert any(d.key == "_debug_download" for d in at.get("download_button"))
    # …and the 🐛 Debug popover joins the menu bar to host it.
    labels = {p.proto.popover.label for p in at.get("popover")}
    assert "🐛 Debug" in labels


def test_a_legacy_debug_url_param_still_arms_it():
    """`?debug=1` links are already in the world; they keep working as a seed."""
    at = AppTest.from_file(APP_SCRIPT)
    at.query_params["debug"] = "1"
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[debug_log.DEBUG_STATE_KEY] is True
    assert [s for s in at.selectbox if s.key == "_debug_level"]


def test_the_url_param_does_not_override_turning_it_off():
    """A seed, not a lock: on a ?debug=1 URL the toggle still wins, or it would
    switch itself back on every rerun."""
    at = AppTest.from_file(APP_SCRIPT)
    at.query_params["debug"] = "1"
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    toggle = next(t for t in at.toggle if t.key == debug_log.DEBUG_STATE_KEY)
    at = toggle.set_value(False).run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[debug_log.DEBUG_STATE_KEY] is False
    assert not [s for s in at.selectbox if s.key == "_debug_level"]
