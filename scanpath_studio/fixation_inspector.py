"""The local fixation inspector and the click event from the live figure."""

from __future__ import annotations

import base64
from functools import lru_cache

import numpy as np
import pandas as pd
import streamlit as st

from .column_names import active
from .fixation_source import explain

# Only a displayed fixation's trial order crosses the frame boundary.
PLOT_CLICK = """document.getElementById('{plot_id}').on('plotly_click', event => {
    const point = event.points.find(p => p.data.name === 'Fixations' && p.data.ids);
    if (point) window.parent.postMessage({spsFixationOrder: point.data.ids[point.pointNumber]}, window.parent.location.origin);
});"""


@lru_cache(maxsize=1)
def _bridge():
    return st.components.v2.component(
        "scanpath_fixation_click",
        js=r"""
    export default ({parentElement, setTriggerValue}) => {
        const win = parentElement.ownerDocument.defaultView;
        const listen = e => {
            if (!e.data || typeof e.data.spsFixationOrder !== 'string') return;
            const order = e.data.spsFixationOrder;
            if (!/^\d+$/.test(order)) return;
            const frames = win.document.querySelectorAll('iframe');
            const source = [...frames].find(f => f.contentWindow === e.source);
            try {
                if (source?.contentDocument?.getElementById('truescale-single'))
                    setTriggerValue('order', order);
            } catch { /* An unrelated frame can have a different origin. */ }
        };
        win.addEventListener('message', listen);
        return () => win.removeEventListener('message', listen);
    }""",
    )


def plot_numbers(values) -> np.ndarray:
    if isinstance(values, dict) and "bdata" in values:
        return np.frombuffer(base64.b64decode(values["bdata"]), dtype=values["dtype"])
    return pd.to_numeric(np.asarray(values), errors="coerce")


def render(figure, words, fixations):
    """Look up selected points by their published trial order, never a source row number."""
    trace = next(
        (t for t in figure.data if t.name == "Fixations" and t.ids is not None), None
    )
    if trace is None:
        return
    xs, ys = plot_numbers(trace.x), plot_numbers(trace.y)
    points = {
        str(i): (x, y)
        for i, x, y in zip(trace.ids, xs, ys)
        if np.isfinite(x) and np.isfinite(y)
    }
    if not points:
        return
    event = _bridge()(
        key="single_fixation_click", on_order_change=lambda: None, height=0
    )
    chosen = getattr(event, "order", None)
    key = "single_inspected_fixation"
    if chosen in points:
        st.session_state[key] = chosen
    elif st.session_state.get(key) not in points:
        st.session_state.pop(key, None)
    with st.expander("Inspect a fixation", expanded=chosen in points):
        order = st.selectbox(
            "Plotted fixation",
            list(points),
            key=key,
            index=None,
            placeholder="Click a fixation on the plot or choose one here",
            format_func=lambda i: (
                f"Fixation {i} · ({points[i][0]:g}, {points[i][1]:g})"
            ),
            persist_state="session",
        )
        if order is None:
            return
        match = fixations[fixations["order_in_trial"].astype(str).eq(order)]
        if len(match) != 1:
            st.caption(
                "The selected point has no unique input fixation in this reading."
            )
            return
        report = explain(match.iloc[0], words, active(st.session_state, "fixations"))
        where = report["location"]
        if where["File"] is not None:
            st.text(f"{where['File']} · data row {where['Row']} (header excluded)")
        elif where["Row"] is not None:
            st.text(f"Input table row {where['Row']} · file name unavailable")
        else:
            st.caption("The input location was not recorded for this reading.")
        st.text(f"Fixation {order} · {report['assignment']} · word {report['word']}")
        st.dataframe(pd.DataFrame(report["fields"]), hide_index=True)
        if report["contributors"]:
            st.caption(
                "These input rows contributed to this fixation's merged duration."
            )
            st.dataframe(pd.DataFrame(report["contributors"]), hide_index=True)
