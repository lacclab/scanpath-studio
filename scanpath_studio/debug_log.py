"""In-app debug log + state inspector.

Streamlit reruns the script top-to-bottom on every interaction, and plain
``logging`` / ``print`` output only reaches the *server* terminal — never the
browser. This module bridges that gap: a :class:`logging.Handler` captures log
records into a capped buffer in ``st.session_state`` so they can be rendered
inside the app, behind a debug toggle.

Activation is two-stage: the ``?debug=1`` URL param reveals a "🐛 Debug mode"
toggle in the sidebar, and the toggle controls whether the panel is shown. The
panel offers a level filter, an app/session-state snapshot, and a JSON export.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List

import streamlit as st

# Keep the buffer small: it lives in session_state and is re-rendered every run.
_MAX_RECORDS = 500
_BUFFER_KEY = "_debug_log_records"
_HANDLER_FLAG = "_debug_log_handler_installed"

_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LEVEL_COLOR = {
    "DEBUG": "#888",
    "INFO": "#3b82f6",
    "WARNING": "#d97706",
    "ERROR": "#dc2626",
    "CRITICAL": "#dc2626",
}


def _buffer() -> Deque[Dict[str, Any]]:
    """The session-scoped ring buffer of captured log records."""
    buf = st.session_state.get(_BUFFER_KEY)
    if buf is None:
        buf = deque(maxlen=_MAX_RECORDS)
        st.session_state[_BUFFER_KEY] = buf
    return buf


class _SessionStateHandler(logging.Handler):
    """Append each emitted record to the session-state ring buffer.

    The handler is attached to the root logger, so it captures every module's
    ``logging`` output. It never raises into the logging machinery: a failure to
    record a log line must not break the thing being logged.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            buf = _buffer()
            buf.append(
                {
                    "time": datetime.fromtimestamp(record.created).strftime(
                        "%H:%M:%S.%f"
                    )[:-3],
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                }
            )
        except Exception:  # pragma: no cover - logging must never crash callers
            pass


def install_log_capture(level: int = logging.INFO) -> None:
    """Attach the session-state handler to the root logger (once per session).

    Idempotent: guarded by a session_state flag so repeated Streamlit reruns
    don't stack duplicate handlers. Call this early in ``main()``.
    """
    if st.session_state.get(_HANDLER_FLAG):
        return
    handler = _SessionStateHandler()
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    # Make sure records at INFO actually propagate to handlers.
    if root.level > level:
        root.setLevel(level)
    root.addHandler(handler)
    st.session_state[_HANDLER_FLAG] = True


def debug_enabled() -> bool:
    """True when the ``?debug=1`` URL param is present (reveals the toggle)."""
    return (st.query_params.get("debug") or "").lower() in {"1", "true", "yes"}


def _state_snapshot() -> List[Dict[str, str]]:
    """A few high-signal facts about what's currently loaded, best-effort.

    Reads optional session-state keys defensively — missing keys are simply
    omitted so this never crashes regardless of app state.
    """
    ss = st.session_state
    rows: List[Dict[str, str]] = []

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


def render_debug_panel() -> None:
    """Render the sidebar debug toggle + panel.

    No-op unless ``?debug=1`` is set. The toggle then controls the expander
    holding the captured-log view, a state snapshot, and a JSON download.
    """
    if not debug_enabled():
        return

    if not st.sidebar.toggle("🐛 Debug mode", key="_debug_mode_on"):
        return

    records = list(_buffer())

    with st.sidebar.expander("🐛 Debug log", expanded=True):
        cols = st.columns([3, 1])
        with cols[0]:
            min_level = st.selectbox(
                "Min level", _LEVELS, index=_LEVELS.index("INFO"), key="_debug_level"
            )
        with cols[1]:
            st.write("")
            if st.button("Clear", key="_debug_clear", use_container_width=True):
                _buffer().clear()
                st.rerun()

        threshold = _LEVELS.index(min_level)
        shown = [
            r
            for r in records
            if r["level"] in _LEVELS and _LEVELS.index(r["level"]) >= threshold
        ]

        st.caption(f"{len(shown)} / {len(records)} records")

        if shown:
            lines = []
            for r in reversed(shown):  # newest first
                color = _LEVEL_COLOR.get(r["level"], "#888")
                lines.append(
                    f'<div style="font-family:monospace;font-size:11px;'
                    f'line-height:1.5;white-space:pre-wrap;word-break:break-word">'
                    f'<span style="color:#888">{r["time"]}</span> '
                    f'<span style="color:{color};font-weight:600">'
                    f"{r['level']:<7}</span> "
                    f'<span style="color:#888">{r["logger"]}</span> '
                    f"{_escape(r['message'])}</div>"
                )
            st.markdown(
                f'<div style="max-height:300px;overflow-y:auto">{"".join(lines)}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No log records at this level yet.")

        st.divider()
        st.caption("App / session state")
        snapshot = _state_snapshot()
        st.dataframe(snapshot, hide_index=True, use_container_width=True)

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
            use_container_width=True,
            key="_debug_download",
        )


def _escape(text: str) -> str:
    """Minimal HTML escaping for log messages rendered via st.markdown."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
