"""BUG-15: a viz widget that first renders on a later run must show its value.

Streamlit only sends a session-state value down to the browser on the run where
that key was written *programmatically* (``set_value`` on the widget's proto).
``controls._seed_viz_state`` used to write the defaults with ``setdefault``, so
the push happened once — on the first run. A widget whose popover only renders
later (its layer toggle was off at load, from a deep link or a restored config)
then mounted with **no** value: the two ``st.segmented_control`` pickers showed
nothing pressed at all (their proto default is empty) and a colour picker showed
black while the figure drew the linked colour.

The fix is ``controls._pin``: re-assert the stored value every run. These tests
pin the mechanism — the flag Streamlit itself reads to decide whether to push a
value — plus the invariant that makes it safe (no viz widget passes a default),
because both are invisible from the rendered output.
"""

from __future__ import annotations

import pytest

from scanpath_studio import controls

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


_FIX = {
    "participant_id": ["p1", "p1"],
    "trial_id": ["t1", "t1"],
    "x": [1.0, 2.0],
    "y": [3.0, 4.0],
    "duration_ms": [100, 200],
    "order_in_trial": [1, 2],
}

# The keys behind the two controls the bug was reported on, plus one of each
# other affected kind (a colour picker and a range).
_WATCHED = (
    "global_saccade_style",
    "global_saccade_render_mode",
    "global_saccade_color",
    "global_marker_size_range",
    "cmp0_saccade_style",
)


def _seed_twice_app():
    """Seed the viz state on two consecutive runs; record the sync flag."""
    import pandas as pd
    import streamlit as st
    from streamlit.runtime.state.session_state_proxy import get_session_state

    from scanpath_studio.controls import _seed_viz_state

    # A stored non-default value, as a deep link or restored config would leave.
    st.session_state.setdefault("global_saccade_style", "Dotted")
    _seed_viz_state(pd.DataFrame(st.session_state["_fix"]), 14, None, rewrite=True)

    state = get_session_state()
    st.session_state["_run"] = st.session_state.get("_run", 0) + 1
    st.session_state["_pushes"] = {
        key: state.is_new_state_value(key) for key in st.session_state["_watched"]
    }
    st.session_state["_style"] = st.session_state["global_saccade_style"]


def test_stored_values_are_re_pushed_on_every_run():
    """Every run marks the keys "newly set", so a late-mounting widget syncs.

    ``is_new_state_value`` is exactly what ``register_widget`` reads to set
    ``set_value`` on the proto — if it goes False on the second run, a widget
    that first renders then shows its proto default instead of this value.
    """
    at = AppTest.from_function(_seed_twice_app)
    at.session_state["_fix"] = _FIX
    at.session_state["_watched"] = list(_WATCHED)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert all(at.session_state["_pushes"].values()), at.session_state["_pushes"]

    at.run(timeout=30)  # second run: nothing was written programmatically
    assert not at.exception, at.exception
    assert at.session_state["_run"] == 2
    missing = [k for k, pushed in at.session_state["_pushes"].items() if not pushed]
    assert not missing, (
        "these keys are no longer re-asserted, so a widget that first renders on "
        f"a later run will show its default instead of the stored value: {missing}"
    )
    # Re-asserting must not overwrite what was already there.
    assert at.session_state["_style"] == "Dotted"


def _pin_app():
    """``_pin`` keeps an existing value and fills in a missing one."""
    import streamlit as st

    from scanpath_studio.controls import _pin

    st.session_state["k"] = "kept"
    _pin("k", "fallback", rewrite=True)
    _pin("fresh", "fallback", rewrite=True)


def test_pin_keeps_an_existing_value():
    """``_pin`` is a defaulting write, not a reset."""
    at = AppTest.from_function(_pin_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["k"] == "kept"
    assert at.session_state["fresh"] == "fallback"


def test_no_pinned_widget_passes_a_default():
    """The invariant ``_pin`` relies on: widgets take their value from state only.

    A ``value=``/``index=``/``default=`` beside a pinned ``key=`` would fight the
    stored value *and* make Streamlit log its "default value but also had its
    value set via Session State API" warning. (The colour pickers that do pass
    ``value=`` — the compare styles and the VIZ-8 class colours — are the older,
    per-widget workaround for this same desync; they are keyless or unpinned, so
    they don't collide.)
    """
    import ast
    import inspect

    pinned = set(controls._VIZ_WIDGET_DEFAULTS) | {"global_marker_size_range"}
    tree = ast.parse(inspect.getsource(controls))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kwargs = {kw.arg: kw for kw in node.keywords if kw.arg}
        key = kwargs.get("key")
        if key is None or not isinstance(key.value, ast.Constant):
            continue
        if key.value.value not in pinned:
            continue
        clashes = sorted({"value", "index", "default"} & set(kwargs))
        if clashes:
            offenders.append(f"{key.value.value}: {clashes} (line {node.lineno})")
    assert not offenders, (
        "a pinned viz widget now passes an explicit default — see "
        f"controls._pin: {offenders}"
    )
