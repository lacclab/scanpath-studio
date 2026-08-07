"""BUG-15: a viz widget that first renders on a later run must show its value.

Two things go wrong when a control renders only sometimes — its layer toggle was
off at load, or its whole panel lives on a view the user isn't on:

1. Streamlit drops a widget's key from session state at the end of any run in
   which the widget did not render, so the stored value is simply gone.
2. Even when the value is still there, Streamlit only pushes it to the browser
   on the run it was written *programmatically*, so a late-mounting widget
   arrives at its **proto** default — nothing pressed at all on a
   ``st.segmented_control``, black on a colour picker — while the figure keeps
   drawing the value the state actually holds.

Both used to be worked around from Python, by re-asserting every stored value on
every run (``controls._pin(rewrite=True)``). Streamlit 1.61 handles both itself:
``persist_state="session"`` preserves the value while the widget is unmounted
*and* marks it changed on remount so the frontend adopts it (ENG-36). ``_pin`` is
back to a plain default-if-absent.

So these tests pin the outcome (a value survives a run without its widget) and
the contract that produces it (every wire-format widget declares
``persist_state``), plus the invariant that keeps it safe (no such widget passes
its own default) — none of which is visible in the rendered output.
"""

from __future__ import annotations

import pytest

from scanpath_studio import controls
from tests.conftest import APP_SCRIPT

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

#: Persisted keys whose widget genuinely cannot take ``persist_state``.
_NO_PERSIST_STATE = {
    # st.file_uploader takes no persist_state; the decoded image is stashed
    # separately by controls._uploaded_image_data_uri anyway.
    "global_stimulus_image_upload",
}


def _late_mount_app():
    """Render the saccade-style picker on every run *except* the second.

    That gap is the whole bug: run 2 is a rerun where the widget's popover is
    closed (its layer toggle is off), which is when Streamlit prunes the key.
    """
    import pandas as pd
    import streamlit as st

    from scanpath_studio.controls import _seed_viz_state

    run = st.session_state.get("_run", 0) + 1
    st.session_state["_run"] = run
    if run == 1:
        # A stored non-default value, as a deep link or restored config leaves it.
        st.session_state.setdefault("global_saccade_style", "Dotted")

    _seed_viz_state(pd.DataFrame(st.session_state["_fix"]), 14, None)

    if run != 2:
        st.segmented_control(
            "Line style",
            options=["Solid", "Dashed", "Dotted"],
            key="global_saccade_style",
            persist_state="session",
        )
    st.session_state["_style"] = st.session_state.get("global_saccade_style", "<GONE>")


def test_a_value_survives_a_run_whose_widget_did_not_render():
    """The outcome BUG-15 is about, whatever mechanism delivers it.

    Without it the key is pruned on run 2 and ``_seed_viz_state`` writes the
    factory default over the user's setting on run 3 — permanently, since it now
    looks like their choice.
    """
    at = AppTest.from_function(_late_mount_app)
    at.session_state["_fix"] = _FIX
    for expected_run in (1, 2, 3):
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_run"] == expected_run
        assert at.session_state["_style"] == "Dotted", (
            f"run {expected_run}: the stored value did not survive a run without "
            "its widget — check persist_state='session' on the widget"
        )


def test_every_wire_format_widget_declares_persist_state():
    """The contract that replaced the re-assert-every-run workaround (ENG-36).

    A widget on a share-link / saved-config key can render conditionally, and one
    without ``persist_state="session"`` silently loses the user's value the first
    time its panel doesn't render. That is invisible until someone reports a
    setting resetting itself, so it is pinned here instead.
    """
    import ast
    import inspect

    from scanpath_studio import app, session_keys, tabs

    keys = (
        set(controls._VIZ_WIDGET_DEFAULTS)
        | {"global_marker_size_range"}
        | set(session_keys.PLOT_CONFIG_STATE_KEYS)
        | set(session_keys.URL_SEEDED_STATE_KEYS)
    ) - _NO_PERSIST_STATE
    offenders = []
    for module in (app, controls, tabs):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {kw.arg: kw for kw in node.keywords if kw.arg}
            key = kwargs.get("key")
            if key is None or not isinstance(key.value, ast.Constant):
                continue
            if key.value.value not in keys:
                continue
            persist = kwargs.get("persist_state")
            if persist is None or getattr(persist.value, "value", None) != "session":
                offenders.append(f"{module.__name__}:{node.lineno} {key.value.value}")
    assert not offenders, (
        "these widgets sit on a persisted key but do not declare "
        f'persist_state="session", so their value is lost the first time their '
        f"panel does not render: {offenders}"
    )


def _pin_app():
    """``_pin`` keeps an existing value and fills in a missing one."""
    import streamlit as st

    from scanpath_studio.controls import _pin

    st.session_state["k"] = "kept"
    _pin("k", "fallback")
    _pin("fresh", "fallback")


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


def test_no_wire_format_widget_passes_a_default():
    """The same invariant, for every module — not just ``controls.py``.

    ``test_no_pinned_widget_passes_a_default`` only scans ``controls.py`` for
    keys in ``_VIZ_WIDGET_DEFAULTS``, so the identical bug went unnoticed in
    ``app.py``: the PRE-1 ``global_preproc_*`` widgets each passed ``value=``
    beside a key that ``url_state`` writes pre-widget, and Streamlit logged
    "was created with a default value but also had its value set via the Session
    State API" on every run of a restored session.

    Any key in the wire format (``session_keys``) is written into session state
    *before* its widget exists, so the widget must take its value from state
    alone and seed a missing default with ``setdefault``.
    """
    import ast
    import inspect

    from scanpath_studio import app, session_keys, tabs

    wire = set(session_keys.PLOT_CONFIG_STATE_KEYS) | set(
        session_keys.URL_SEEDED_STATE_KEYS
    )
    offenders = []
    for module in (app, controls, tabs):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            kwargs = {kw.arg: kw for kw in node.keywords if kw.arg}
            key = kwargs.get("key")
            if key is None or not isinstance(key.value, ast.Constant):
                continue
            if key.value.value not in wire:
                continue
            clashes = sorted({"value", "index", "default"} & set(kwargs))
            if clashes:
                offenders.append(
                    f"{module.__name__}:{node.lineno} {key.value.value}: {clashes}"
                )
    assert not offenders, (
        "a widget whose key is part of the share-link / saved-config wire format "
        "now passes an explicit default; seed it with st.session_state.setdefault "
        f"instead so a restored value wins: {offenders}"
    )


def test_canvas_settings_survive_a_corpus_analysis_round_trip():
    """VIZ-31: the canvas panel renders only in the Scanpath rail — it must not
    lose its settings on a view that doesn't render it.

    Streamlit drops a widget's key from session state at the end of any run in
    which the widget did not render. Once VIZ-31 moved the monitor / typography /
    background panel out of the always-present sidebar and into the Scanpath
    rail, a single trip through **Corpus Analysis** pruned all fourteen of its
    keys — and because `app.seed_canvas_state` seeded them with ``setdefault``,
    the *next* Corpus run wrote the factory default over the user's settings and
    kept it (canvas 1234 → 700, font 33 → 16, text colour → #343a40), including
    six keys that are share-link / saved-config wire format. The seeder now uses
    ``persist_state="session"`` on each of those widgets, which is what keeps the
    keys alive across a view that never renders them (ENG-36; before 1.61 this
    was a hand-rolled re-assert-every-run in ``controls._pin``).

    Two Corpus runs matter: the first is the one that prunes, the second is the
    one that would re-seed a default over the gap.
    """
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run()

    edits = {
        "global_canvas_width": 1234,
        "global_canvas_height": 999,
        "global_base_font_size": 33,
        "global_line_spacing": 2.5,
        "global_text_color": "#ff0000",
        "global_font_family": "Courier New",
        "global_monitor_width_mm": 500.0,
        "global_viewing_distance_mm": 650.0,
    }
    for key, value in edits.items():
        at.session_state[key] = value
    at.run()
    assert not at.exception

    at.session_state["main_nav"] = "Corpus Analysis"
    at.run()
    at.run()
    at.session_state["main_nav"] = "Scanpath"
    at.run()
    assert not at.exception

    survived = {key: at.session_state[key] for key in edits}
    assert survived == edits, (
        "a canvas / typography setting was reset by a trip through Corpus "
        "Analysis — app.seed_canvas_state must _pin(rewrite=True) these keys, "
        "not setdefault them, because only the Scanpath rail renders their "
        f"widgets: {survived}"
    )
