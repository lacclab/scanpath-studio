"""In-app debug log + state inspector.

Streamlit reruns the script top-to-bottom on every interaction, and plain
``logging`` / ``print`` output only reaches the *server* terminal — never the
browser. This module bridges that gap: a :class:`logging.Handler` captures log
records into a capped buffer in ``st.session_state`` so they can be rendered
inside the app, behind a debug toggle.

Activation is a single toggle (**UX-37**): "🐛 Debug mode" under ❓ Help puts the
🐛 Debug popover on the menu bar, and that popover holds a level filter, an
app/session-state snapshot, and a JSON export. It used to be two-stage and the
first stage was a URL param — ``?debug=1`` revealed the toggle — which meant the
whole feature was reachable only by someone who already knew it existed. The
param is still honoured as a *seed* so old links keep working, but it is no
longer the way in.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from contextlib import contextmanager
from datetime import datetime
from time import perf_counter
from typing import Any

import streamlit as st

# Keep the buffer small: it lives in session_state and is re-rendered every run.
_MAX_RECORDS = 500
_BUFFER_KEY = "_debug_log_records"

#: Session key of the "🐛 Debug mode" toggle under ❓ Help. This *is* the gate —
#: :func:`debug_enabled` reads nothing else.
DEBUG_STATE_KEY = "_debug_mode_on"

#: The legacy URL param. Kept as a one-shot seed for links already in the world;
#: see :func:`seed_debug_mode`.
DEBUG_URL_PARAM = "debug"

#: The package's own logger. Everything the app logs is a child of this, which is
#: what :class:`_AppRecordsOnly` keys on.
_APP_LOGGER = "scanpath_studio"

_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LEVEL_COLOR = {
    "DEBUG": "#888",
    "INFO": "#3b82f6",
    "WARNING": "#d97706",
    "ERROR": "#dc2626",
    "CRITICAL": "#dc2626",
}


@contextmanager
def timed(what: str, level: int = logging.INFO, **fields: Any):
    """Log ``what`` with how long it took, and with any facts worth having.

    The debug panel's whole value is answering "what did that click actually
    do?", and a log line per *computation* is what makes it answerable — the
    stages are otherwise invisible: Streamlit reruns the script top to bottom and
    a cache hit looks exactly like a cache miss.

    Cheap enough to leave on: one ``perf_counter`` pair and one formatted string
    per stage, at stage granularity, not per row. An exception still logs (at
    WARNING, marked ``failed``) and then propagates — a stage that blew up is
    exactly the line you want in the report.

        with timed("normalize", rows=len(df)):
            ...
    """
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    start = perf_counter()
    try:
        yield
    except Exception as exc:  # re-raised below
        logging.getLogger("scanpath_studio").warning(
            "%s failed after %.0f ms%s: %s",
            what,
            (perf_counter() - start) * 1000,
            f" · {extra}" if extra else "",
            exc,
        )
        raise
    logging.getLogger("scanpath_studio").log(
        level,
        "%s · %.0f ms%s",
        what,
        (perf_counter() - start) * 1000,
        f" · {extra}" if extra else "",
    )


def log_event(what: str, **fields: Any) -> None:
    """Log a user-driven state change (a pick, a toggle, a step).

    Interactions are logged when they *change something* — the data source, the
    trial, the view — not on every widget touch: Streamlit reruns the script for
    each one, so a line per widget would be a line per rerun per widget and the
    computation lines would drown in it.
    """
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    logging.getLogger("scanpath_studio").info(
        "%s%s", what, f" · {extra}" if extra else ""
    )


def log_state_change(state_key: str, value: Any, what: str, **fields: Any) -> None:
    """:func:`log_event`, but only when ``value`` differs from the last run's.

    A rerun re-executes everything, so logging a selection unconditionally would
    print the same line on every interaction anywhere in the app. This keeps one
    line per actual change, which is what makes the log readable.
    """
    marker = f"_logged_{state_key}"
    if st.session_state.get(marker) == value:
        return
    st.session_state[marker] = value
    log_event(what, **fields)


def _buffer() -> deque[dict[str, Any]]:
    """The session-scoped ring buffer of captured log records."""
    buf = st.session_state.get(_BUFFER_KEY)
    if buf is None:
        buf = deque(maxlen=_MAX_RECORDS)
        st.session_state[_BUFFER_KEY] = buf
    return buf


class _AppRecordsOnly(logging.Filter):
    """Keep the app's own records, plus anything that went wrong anywhere.

    The handler sits on the *root* logger, so without a filter the panel fills
    with third-party chatter — tornado logs a line per websocket frame, watchdog
    per filesystem event, urllib3 per connection. That is what made the panel
    unreadable (UX-37 follow-up: "each log entry shows up identical like a
    hundred times"), and none of it answers "what did the app just do?".

    ``WARNING`` and above is kept whatever its source: a library that failed is
    exactly what a bug report needs, and those arrive one at a time.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        return (
            record.name == _APP_LOGGER
            or record.name.startswith(f"{_APP_LOGGER}.")
            or record.levelno >= logging.WARNING
        )


class _SessionStateHandler(logging.Handler):
    """Append each emitted record to the session-state ring buffer.

    Identical lines are **collapsed** rather than repeated: a match anywhere in
    the buffer bumps that entry's ``count``, refreshes its timestamp and moves it
    to the newest position. Streamlit reruns the whole script per interaction, so
    anything logged outside a cache or a change-guard recurs verbatim — and 100
    copies of one line push the other 99 events out of a 500-entry buffer. The
    count keeps the "this happened a lot" signal without the noise.

    The handler is attached to the root logger, so it can capture every module's
    ``logging`` output; :class:`_AppRecordsOnly` narrows that to the app's own
    records plus WARNING-and-above from anywhere. It never raises into the
    logging machinery: a failure to record a log line must not break the thing
    being logged.

    One instance serves the whole process (see ``install_log_capture``): the
    buffer it appends to is resolved through ``st.session_state`` at emit time,
    which Streamlit binds to the *calling* thread's script-run context, so a
    record logged during a session's run lands in that session's buffer and
    nowhere else. A record emitted from a thread with no context raises inside
    ``_buffer`` and is swallowed here rather than being misfiled.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            buf = _buffer()
            stamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
            seen = (record.levelname, record.name, record.getMessage())
            for index, entry in enumerate(buf):
                if (entry["level"], entry["logger"], entry["message"]) == seen:
                    entry["count"] += 1
                    entry["time"] = stamp
                    # Move to the newest position. Safe mid-iteration only
                    # because this returns immediately.
                    del buf[index]
                    buf.append(entry)
                    return
            buf.append(
                {
                    "time": stamp,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "count": 1,
                }
            )
        except Exception:  # pragma: no cover - logging must never crash callers
            pass


def install_log_capture(level: int = logging.INFO) -> None:
    """Attach the session-state handler to the root logger (once per *process*).

    Idempotent, and idempotent at the right scope: the guard reads the root
    logger's own handler list, not ``st.session_state``. The root logger is
    process-wide while session state is not, so a session-scoped flag let every
    new session add another handler — N sessions meant N handlers, each record
    appended N times to whichever session's buffer was live, and handlers piling
    up for the process's lifetime (S10). One handler is enough: it resolves the
    buffer per script-run context, so each session still sees only its own
    records. Call this early in ``main()``.

    The level is raised on the **app's** logger, not the root one. Raising root
    to INFO switches on every library that hasn't set its own level — tornado,
    watchdog, urllib3, PIL, streamlit's internals — and they, not the app, were
    what flooded the panel. A record's level is tested where it is logged, and
    propagation to an ancestor's *handlers* ignores the ancestor's level, so
    scoping it here still delivers every ``scanpath_studio`` INFO line to both
    this handler and the terminal.
    """
    app_logger = logging.getLogger(_APP_LOGGER)
    if app_logger.level == logging.NOTSET or app_logger.level > level:
        app_logger.setLevel(level)
    root = logging.getLogger()
    if any(isinstance(h, _SessionStateHandler) for h in root.handlers):
        return
    handler = _SessionStateHandler()
    handler.setLevel(logging.DEBUG)
    handler.addFilter(_AppRecordsOnly())
    root.addHandler(handler)


def seed_debug_mode() -> None:
    """Honour a legacy ``?debug=1`` link by pre-arming the toggle, once.

    ``setdefault`` rather than a write: the toggle is the gate now, so a user who
    turns debug mode *off* on a ``?debug=1`` URL must stay off for the rest of
    the session instead of having the param switch it back on every rerun. Call
    from ``main`` before :func:`debug_enabled` is read.
    """
    if (st.query_params.get(DEBUG_URL_PARAM) or "").lower() in {"1", "true", "yes"}:
        st.session_state.setdefault(DEBUG_STATE_KEY, True)


def debug_enabled() -> bool:
    """True when the ❓ Help → "🐛 Debug mode" toggle is on."""
    return bool(st.session_state.get(DEBUG_STATE_KEY))


def render_debug_toggle(host=None) -> None:
    """Render the "🐛 Debug mode" toggle into the ❓ Help popover.

    The single gate (**UX-37**). Flipping it on puts the 🐛 Debug popover on the
    menu bar *next* run — ``menu.render_top_menu`` runs at the top of ``main``
    and this renders at the bottom — which is the ordinary Streamlit widget
    round-trip, not a delay worth engineering around.
    """
    (host if host is not None else st).toggle(
        "🐛 Debug mode",
        key=DEBUG_STATE_KEY,
        help="Add a 🐛 Debug panel to the menu bar: the captured log, a snapshot "
        "of what's loaded, and a JSON download to attach to a bug report.",
    )


def _state_snapshot() -> list[dict[str, str]]:
    """A few high-signal facts about what's currently loaded, best-effort.

    Reads optional session-state keys defensively — missing keys are simply
    omitted so this never crashes regardless of app state.
    """
    ss = st.session_state
    rows: list[dict[str, str]] = []

    def add(label: str, value: Any) -> None:
        if value is not None:
            rows.append({"key": label, "value": str(value)})

    add("Active view", ss.get("active_view"))
    add("Dataset / source", ss.get("data_source") or ss.get("_active_source_name"))
    add("Participant", ss.get("_deeplink_participant"))

    # Frame shapes for any cached DataFrame-like objects in session_state.
    for key, val in list(ss.items()):
        shape = getattr(val, "shape", None)
        if shape is not None and isinstance(shape, tuple) and len(shape) == 2:
            add(f"{key} (rows×cols)", f"{shape[0]} × {shape[1]}")

    rows.append({"key": "session_state keys", "value": str(len(ss))})
    return rows


def render_debug_panel(host=None) -> None:
    """Render the debug panel into the 🐛 Debug menu popover.

    No-op unless the ❓ Help toggle is on — which is also what puts the popover
    on the menu bar (``menu.render_top_menu(show_debug=…)``), so ``host`` is None
    in exactly the sessions this returns early for. The panel is the captured-log
    view, a state snapshot and a JSON download, rendered bare: a popover nests no
    expander.
    """
    if not debug_enabled():
        return

    panel = host if host is not None else st.container()
    records = list(_buffer())

    with panel:
        cols = st.columns([3, 1])
        with cols[0]:
            min_level = st.selectbox(
                "Min level", _LEVELS, index=_LEVELS.index("INFO"), key="_debug_level"
            )
        with cols[1]:
            st.write("")
            if st.button("Clear", key="_debug_clear", width="stretch"):
                _buffer().clear()
                st.rerun()

        threshold = _LEVELS.index(min_level)
        shown = [
            r
            for r in records
            if r["level"] in _LEVELS and _LEVELS.index(r["level"]) >= threshold
        ]

        # "lines", not "records": identical ones are collapsed, so the two
        # numbers differ and saying which is which is the whole point.
        events = sum(int(r.get("count", 1)) for r in records)
        st.caption(
            f"{len(shown)} / {len(records)} lines"
            + (
                f" · {events} events, identical lines collapsed"
                if events > len(records)
                else ""
            )
        )

        if shown:
            lines = []
            for r in reversed(shown):  # newest first
                color = _LEVEL_COLOR.get(r["level"], "#888")
                # Collapsed repeats carry their tally; a one-off shows nothing,
                # so the common case reads exactly as it did before.
                repeats = int(r.get("count", 1))
                tally = (
                    f' <span style="color:#888">× {repeats}</span>'
                    if repeats > 1
                    else ""
                )
                lines.append(
                    f'<div style="font-family:monospace;font-size:11px;'
                    f'line-height:1.5;white-space:pre-wrap;word-break:break-word">'
                    f'<span style="color:#888">{r["time"]}</span> '
                    f'<span style="color:{color};font-weight:600">'
                    f"{r['level']:<7}</span> "
                    f'<span style="color:#888">{r["logger"]}</span> '
                    f"{_escape(r['message'])}{tally}</div>"
                )
            st.markdown(
                f'<div style="max-height:300px;overflow-y:auto">{"".join(lines)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No log records at this level yet.")

        st.divider()
        st.caption(
            "App / session state",
            help="A snapshot of what this browser session currently holds: the "
            "active view, the dataset it was loaded from, the size of every "
            "table in memory (rows × columns), and how many session-state keys "
            "exist. It is a read-out, not a control — nothing here changes the "
            "app. Send it with a bug report: it says which data and which view "
            "produced the log above.",
        )
        snapshot = _state_snapshot()
        st.dataframe(snapshot, hide_index=True, width="stretch")

        export = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "records": records,
            "state": snapshot,
        }
        st.download_button(
            "⬇️ Download logs (JSON)",
            data=json.dumps(export, indent=2, default=str),
            file_name="scanpath_studio_debug.json",
            mime="application/json",
            width="stretch",
            key="_debug_download",
        )


def _escape(text: str) -> str:
    """Minimal HTML escaping for log messages rendered via st.markdown."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
