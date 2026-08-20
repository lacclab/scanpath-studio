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
from tests.conftest import APP_SCRIPT, arm_session_dialog

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
    # install_log_capture puts the app logger at INFO, so DEBUG is filtered out
    # at the logger before it reaches any handler.
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


class TestOnlyTheAppsOwnRecordsAreKept:
    """UX-37 follow-up ("much too much logs"). The handler sits on the *root*
    logger, so without a filter the panel fills with third-party chatter."""

    def test_a_third_party_info_line_is_dropped(self):
        handler = debug_log._SessionStateHandler()
        handler.addFilter(debug_log._AppRecordsOnly())
        noisy = logging.LogRecord(
            "tornado.access", logging.INFO, __file__, 1, "200 GET /", (), None
        )
        assert bool(handler.filter(noisy)) is False

    def test_a_third_party_warning_is_kept(self):
        """A library that failed is exactly what a bug report needs."""
        handler = debug_log._SessionStateHandler()
        handler.addFilter(debug_log._AppRecordsOnly())
        broke = logging.LogRecord(
            "urllib3.connectionpool", logging.WARNING, __file__, 1, "retrying", (), None
        )
        assert bool(handler.filter(broke)) is True

    @pytest.mark.parametrize("name", ["scanpath_studio", "scanpath_studio.data"])
    def test_the_apps_own_info_lines_are_kept(self, name):
        handler = debug_log._SessionStateHandler()
        handler.addFilter(debug_log._AppRecordsOnly())
        mine = logging.LogRecord(
            name, logging.INFO, __file__, 1, "did a thing", (), None
        )
        assert bool(handler.filter(mine)) is True

    def test_a_lookalike_logger_name_is_not_treated_as_ours(self):
        """`scanpath_studio_extras` is somebody else's package, not a child."""
        handler = debug_log._SessionStateHandler()
        handler.addFilter(debug_log._AppRecordsOnly())
        theirs = logging.LogRecord(
            "scanpath_studio_extras", logging.INFO, __file__, 1, "hi", (), None
        )
        assert bool(handler.filter(theirs)) is False

    def test_install_does_not_raise_the_root_level(self):
        """Raising root to INFO is what switched on every library in the process.

        The app's own logger carries the level instead; propagation to an
        ancestor's handlers ignores the ancestor's level, so our INFO lines still
        arrive.
        """
        root = logging.getLogger()
        before = root.level
        try:
            root.setLevel(logging.WARNING)
            debug_log.install_log_capture()
            assert root.level == logging.WARNING
            assert logging.getLogger("scanpath_studio").isEnabledFor(logging.INFO)
        finally:
            root.setLevel(before)


class TestIdenticalLinesCollapse:
    """A rerun re-executes the script, so anything logged outside a cache or a
    change-guard recurs verbatim — and 100 copies of one line push the other 99
    events out of a 500-entry buffer."""

    def _handler_and_buffer(self, monkeypatch):
        from collections import deque

        buf = deque(maxlen=debug_log._MAX_RECORDS)
        monkeypatch.setattr(debug_log, "_buffer", lambda: buf)
        return debug_log._SessionStateHandler(), buf

    def _record(self, message: str, name: str = "scanpath_studio"):
        return logging.LogRecord(name, logging.INFO, __file__, 1, message, (), None)

    def test_a_repeat_bumps_the_count_instead_of_appending(self, monkeypatch):
        handler, buf = self._handler_and_buffer(monkeypatch)
        for _ in range(100):
            handler.emit(self._record("Filters applied · trials=24"))
        assert len(buf) == 1
        assert buf[0]["count"] == 100

    def test_a_repeat_moves_back_to_the_newest_position(self, monkeypatch):
        """Interleaved is the shape a rerun actually produces (A, B, A, B …), so
        collapsing only *consecutive* duplicates would not have helped."""
        handler, buf = self._handler_and_buffer(monkeypatch)
        for _ in range(50):
            handler.emit(self._record("A"))
            handler.emit(self._record("B"))
        assert [(e["message"], e["count"]) for e in buf] == [("A", 50), ("B", 50)]

    def test_distinct_lines_are_all_kept(self, monkeypatch):
        handler, buf = self._handler_and_buffer(monkeypatch)
        for index in range(10):
            handler.emit(self._record(f"line {index}"))
        assert len(buf) == 10
        assert all(entry["count"] == 1 for entry in buf)

    def test_same_text_at_a_different_level_is_a_different_line(self, monkeypatch):
        handler, buf = self._handler_and_buffer(monkeypatch)
        handler.emit(self._record("careful"))
        handler.emit(
            logging.LogRecord(
                "scanpath_studio", logging.WARNING, __file__, 1, "careful", (), None
            )
        )
        assert len(buf) == 2


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


def _app_records(caplog):
    """Only the app's own records.

    ``caplog`` collects from the root logger, so anything else running in the
    same worker lands in ``caplog.records`` too — Streamlit's bare-mode
    *"missing ScriptRunContext!"* warning above all (#BUG-39). Asserting on the
    whole list makes a test hostage to every library that logs.
    """
    return [r for r in caplog.records if r.name.split(".")[0] == "scanpath_studio"]


class TestTheComputationLog:
    """UX-37 follow-up: the panel is only worth opening if it says what the app
    actually did. Stages log with their duration; interactions log on change."""

    def test_timed_logs_the_duration_and_the_fields(self, caplog):
        with caplog.at_level(logging.INFO, logger="scanpath_studio"):
            with debug_log.timed("normalize", rows=42):
                pass
        (record,) = _app_records(caplog)
        assert record.getMessage().startswith("normalize · ")
        assert "ms" in record.getMessage()
        assert "rows=42" in record.getMessage()

    def test_a_failing_stage_still_logs_and_still_raises(self, caplog):
        with caplog.at_level(logging.WARNING, logger="scanpath_studio"):
            with pytest.raises(ValueError):
                with debug_log.timed("normalize"):
                    raise ValueError("boom")
        (record,) = _app_records(caplog)
        assert "normalize failed after" in record.getMessage()
        assert "boom" in record.getMessage()

    def test_a_state_change_logs_once_per_change(self, caplog):
        import streamlit as st

        st.session_state.clear()
        with caplog.at_level(logging.INFO, logger="scanpath_studio"):
            debug_log.log_state_change("view", "Scanpath", "View", view="Scanpath")
            debug_log.log_state_change("view", "Scanpath", "View", view="Scanpath")
            debug_log.log_state_change("view", "Corpus", "View", view="Corpus")
        # Two lines, not three: a rerun re-executes everything, so an
        # unconditional log would print on every widget touch anywhere.
        assert [r.getMessage() for r in _app_records(caplog)] == [
            "View · view=Scanpath",
            "View · view=Corpus",
        ]
        st.session_state.clear()


def test_the_run_logs_its_computations_and_selections():
    """End to end: the lines reach the in-app buffer the panel renders.

    The computation lines are logged *inside* the cached functions — on a miss
    only, which is the case worth reading — so the caches have to be cold or
    this asserts on lines an earlier test already warmed away. In-process
    ``@st.cache_data`` is shared across the whole session.
    """
    import streamlit as st

    st.cache_data.clear()
    at = AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    assert not at.exception, at.exception
    messages = [r["message"] for r in at.session_state["_debug_log_records"]]
    assert any("normalize + harmonize" in m for m in messages), messages
    assert any("build scanpath figure" in m for m in messages), messages
    assert any(m.startswith("Dataset ready ·") for m in messages), messages
    assert any(m.startswith("View ·") for m in messages), messages
    assert any(m.startswith("Filters applied ·") for m in messages), messages


def _boot_with_session_open(**session) -> AppTest:
    """Boot with the 💾 Session modal open — where the 🐛 Debug tools live.

    UX-100 made the group a dialog, so its widgets render only while it is open,
    and `arm_session_dialog` has to be repeated before every run (AppTest
    replays the whole script rather than rerunning the dialog fragment).
    """
    at = AppTest.from_file(APP_SCRIPT)
    for key, value in session.items():
        at.session_state[key] = value
    arm_session_dialog(at)
    at.run(timeout=90)
    return at


def test_the_toggle_is_offered_without_any_url_param():
    """UX-37: the Session toggle is the way in, even on a plain visit."""
    at = _boot_with_session_open(data_source_choice="Synthetic test trial")
    assert not at.exception, at.exception
    toggles = [t for t in at.toggle if t.key == debug_log._DEBUG_TOGGLE_KEY]
    assert toggles, "the 🐛 Debug mode toggle is not in the Session dialog"
    assert toggles[0].value is False, "debug mode must default off"
    # …and with it off, the panel draws nothing.
    assert not [s for s in at.selectbox if s.key == "_debug_level"]


def test_the_toggle_reveals_the_panel():
    at = _boot_with_session_open(data_source_choice="Synthetic test trial")
    toggles = [t for t in at.toggle if t.key == debug_log._DEBUG_TOGGLE_KEY]

    # Turning it on renders the panel: a level filter, a Clear button, a state
    # snapshot and the JSON download.
    arm_session_dialog(at)
    at = toggles[0].set_value(True).run(timeout=90)
    assert not at.exception, at.exception
    assert [s for s in at.selectbox if s.key == "_debug_level"]
    assert [b for b in at.button if b.key == "_debug_clear"]
    assert any(d.key == "_debug_download" for d in at.get("download_button"))
    # …and it remains under the Session dialog's Debug tools block rather than
    # recreating the old menu-bar popover.
    headings = " ".join(str(markdown.value) for markdown in at.markdown)
    assert "🐛 Debug tools" in headings
    labels = {popover.proto.popover.label for popover in at.get("popover")}
    assert "🐛 Debug" not in labels


def test_a_legacy_debug_url_param_still_arms_it():
    """`?debug=1` links are already in the world; they keep working as a seed."""
    at = AppTest.from_file(APP_SCRIPT)
    at.query_params["debug"] = "1"
    at.session_state["data_source_choice"] = "Synthetic test trial"
    arm_session_dialog(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[debug_log.DEBUG_STATE_KEY] is True
    assert [s for s in at.selectbox if s.key == "_debug_level"]


@pytest.mark.timeout(90)
class TestTheGroundTruthTrialIsDebugOnly:
    """UX-37: the six-word verification fixture is a developer affordance, not a
    corpus, so it sits behind the same toggle as the log panel rather than in
    every user's data-source list. (It used to be advertised in the AI-assistance
    note; that prose was cut, but the route it described still has to work.)"""

    def test_it_is_absent_until_debug_mode_is_on(self):
        at = AppTest.from_file(APP_SCRIPT)
        arm_session_dialog(at)
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert "Synthetic test trial" not in at.session_state["_data_source_entries"]

        arm_session_dialog(at)
        at.toggle(key=debug_log._DEBUG_TOGGLE_KEY).set_value(True).run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        entries = at.session_state["_data_source_entries"]
        assert "Synthetic test trial" in entries, entries

    def test_selecting_it_loads_the_ground_truth_trial(self):
        """The old `?source=synthetic` link still resolves — the token stays in
        the share-link wire format — so this drives it the same way. What
        changed is that it is no longer the only route."""
        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "synthetic"
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert at.session_state["data_source_choice"] == "Synthetic test trial"
        picker = next(s for s in at.selectbox if s.label.startswith("**Select Trial**"))
        assert list(picker.options) == ["synthetic_2line_demo"]


def test_the_url_param_does_not_override_turning_it_off():
    """A seed, not a lock: on a ?debug=1 URL the toggle still wins, or it would
    switch itself back on every rerun."""
    at = AppTest.from_file(APP_SCRIPT)
    at.query_params["debug"] = "1"
    at.session_state["data_source_choice"] = "Synthetic test trial"
    arm_session_dialog(at)
    at.run(timeout=90)
    toggle = next(t for t in at.toggle if t.key == debug_log._DEBUG_TOGGLE_KEY)
    assert toggle.value is True, "the ?debug=1 seed should show the toggle on"
    arm_session_dialog(at)
    at = toggle.set_value(False).run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[debug_log.DEBUG_STATE_KEY] is False
    assert not [s for s in at.selectbox if s.key == "_debug_level"]
