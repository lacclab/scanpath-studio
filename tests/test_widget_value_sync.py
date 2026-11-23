"""A viz widget that first renders on a later run must show its value.

Two things go wrong when a control renders only sometimes — its layer toggle was
off at load, or its whole panel lives on a view the user isn't on:

1. Streamlit drops a widget's key from session state at the end of any run in
   which the widget did not render, so the stored value is simply gone.
2. Even when the value is still there, Streamlit only pushes it to the browser
   on the run it was written *programmatically*, so a late-mounting widget
   arrives at its **proto** default — nothing pressed at all on a
   ``st.segmented_control``, black on a colour picker — while the figure keeps
   drawing the value the state actually holds.

Streamlit handles both itself: ``persist_state="session"`` preserves the value
while the widget is unmounted *and* marks it changed on remount so the frontend
adopts it. ``controls._pin`` is a plain default-if-absent; nothing re-asserts
every stored value on every run.

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

    That gap is the whole hazard: run 2 is a rerun where the widget's popover is
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
    """The outcome that matters, whatever mechanism delivers it.

    Without it the key is pruned on run 2 and ``_seed_viz_state`` writes the
    factory default over the user's setting on run 3 — permanently, since it
    then looks like their choice.
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


#: The widgets that hold a value. Buttons, uploaders and the like keep none.
_STATEFUL_WIDGETS = frozenset(
    {
        "checkbox",
        "color_picker",
        "date_input",
        "multiselect",
        "number_input",
        "pills",
        "radio",
        "segmented_control",
        "select_slider",
        "selectbox",
        "slider",
        "text_area",
        "text_input",
        "time_input",
        "toggle",
    }
)


def _saved_keys() -> frozenset[str]:
    """Every key a user gets back: a share link, a settings file, the recovery
    cache, a link's seeded selection, or a pinned viz default."""
    from scanpath_studio import persistence, session_keys

    return (
        session_keys.LINK_STATE_KEYS
        | session_keys.SETTINGS_FILE_STATE_KEYS
        | persistence._SESSION_KEYS
        | session_keys.URL_SEEDED_STATE_KEYS
        | set(controls._VIZ_WIDGET_DEFAULTS)
        | {"global_marker_size_range"}
    ) - _NO_PERSIST_STATE


def _saved_widgets():
    """``(where, keys, kwargs)`` for each widget, in every module, whose ``key=``
    can name a saved key.

    A literal or a module constant (``key=SINGLE_SHOW_CHIPS``, ``key=sk.X``)
    names one key; an f-string names every saved key its pattern matches. A key
    computed at run time names none it can be checked against."""
    import ast
    import importlib
    import pkgutil
    import re
    from pathlib import Path

    import scanpath_studio

    saved = _saved_keys()
    package = Path(scanpath_studio.__file__).parent
    for info in pkgutil.iter_modules([str(package)]):
        tree = ast.parse((package / f"{info.name}.py").read_text(encoding="utf-8"))
        module = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else None
            kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
            key = kwargs.get("key")
            if name not in _STATEFUL_WIDGETS or key is None:
                continue
            if isinstance(key, ast.Constant):
                keys = {key.value} & saved
            elif isinstance(key, ast.JoinedStr):
                pattern = "".join(
                    re.escape(part.value) if isinstance(part, ast.Constant) else ".+"
                    for part in key.values
                )
                keys = {k for k in saved if re.fullmatch(pattern, k)}
            elif isinstance(key, (ast.Name, ast.Attribute)):
                # Imported only when needed: a module constant names the key.
                module = module or importlib.import_module(
                    f"scanpath_studio.{info.name}"
                )
                value = module
                for part in ast.unparse(key).split("."):
                    value = getattr(value, part, None)
                keys = {value} & saved if isinstance(value, str) else set()
            else:
                keys = set()
            if keys:
                yield f"{info.name}:{node.lineno}", keys, kwargs


def test_every_saved_widget_declares_persist_state():
    """The contract that keeps a conditionally rendered widget's value.

    A widget on a key a link, a settings file or the cache restores can render
    conditionally, and one without ``persist_state="session"`` silently loses
    the user's value the first time its panel doesn't render. That is
    invisible until someone reports a setting resetting itself, so it is
    pinned here, for every module and however the key is written."""
    offenders = sorted(
        f"{where} {sorted(keys)}"
        for where, keys, kwargs in _saved_widgets()
        if getattr(kwargs.get("persist_state"), "value", None) != "session"
    )
    assert not offenders, (
        "these widgets sit on a saved key but do not declare "
        'persist_state="session", so their value is lost the first time their '
        f"panel does not render: {offenders}"
    )


def test_no_saved_widget_passes_a_default():
    """A saved key is written into session state *before* its widget exists
    (by a link, a settings file or the cache), so the widget must take its
    value from state alone and seed a missing default with ``setdefault``
    (``controls._pin``). A ``value=`` / ``index=`` / ``default=`` beside it
    fights the restored value and makes Streamlit log "default value but also
    had its value set via the Session State API" on every run. A literal
    ``None`` is not a default: it lets the widget be empty, and Streamlit does
    not warn about it."""
    import ast

    def defaults(kwargs) -> list[str]:
        return sorted(
            name
            for name in ("value", "index", "default")
            if name in kwargs
            and not (
                isinstance(kwargs[name], ast.Constant) and kwargs[name].value is None
            )
        )

    offenders = sorted(
        f"{where} {sorted(keys)}: {defaults(kwargs)}"
        for where, keys, kwargs in _saved_widgets()
        if defaults(kwargs)
    )
    assert not offenders, (
        "a widget on a saved key passes an explicit default; seed it with "
        f"st.session_state.setdefault instead so a restored value wins: {offenders}"
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


def test_canvas_settings_survive_a_corpus_analysis_round_trip():
    """The canvas panel renders only in the Scanpath rail — it must not lose
    its settings on a view that doesn't render it.

    Streamlit drops a widget's key from session state at the end of any run in
    which the widget did not render. A single trip through **Corpus Analysis**
    would prune all fourteen of the monitor / typography / background panel's
    keys — and since `app.seed_canvas_state` seeds them with ``setdefault``, the
    *next* Corpus run would write the factory default over the user's settings
    and keep it (canvas 1234 → 700, font 33 → 16, text colour → #343a40),
    including six keys that are share-link / saved-config wire format. Each of
    those widgets takes ``persist_state="session"``, which is what keeps the
    keys alive across a view that never renders them.

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
        "Analysis — their widgets must take persist_state='session', because "
        f"only the Scanpath rail renders them: {survived}"
    )


def test_the_selected_trial_survives_a_trip_to_another_view():
    """The trial picker renders only on the Scanpath view, and Streamlit drops
    an unrendered widget's key at the end of the run — so a trip to Corpus
    Analysis or the 🗂️ Data page must not come back on trial 1 (in Compare,
    with A and B left on different texts)."""
    from tests.conftest import pin_view

    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    picker = next(s for s in at.selectbox if s.key == "single_trial_id")
    # The options are the ids as shown.
    from tests.conftest import picked_trial_id, picker_trial_id

    chosen = picker_trial_id(picker.options[3])
    picker.select_index(3)
    at.run()
    assert picked_trial_id(at.session_state["single_trial_id"]) == chosen

    for view in ("Corpus Analysis", "Data", "Scanpath"):
        pin_view(at, view)
        at.run()
        assert not at.exception, at.exception
    assert picked_trial_id(at.session_state["single_trial_id"]) == chosen


def test_a_rerun_with_animate_on_does_not_rebuild_the_replay(monkeypatch):
    """A click while 🎬 Animate is on must not rebuild every frame of the replay
    (~3 s on the demo, 22 s at the finest smoothness) — nor may moving the
    playback speed or flipping Autoplay, which only re-time the frames."""
    from scanpath_studio import tabs

    calls = []
    real = tabs.build_scanpath_replay
    monkeypatch.setattr(
        tabs,
        "build_scanpath_replay",
        lambda *a, **k: calls.append(1) or real(*a, **k),
    )
    # Start cold, so the one expected build is this test's own.
    tabs._cached_scanpath_animation.clear()
    tabs._cached_replay_view.clear()
    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["single_animate"] = True
    at.run()
    at.run()
    at.session_state["single_playback_speed"] = 2.0
    at.run()
    at.session_state["global_anim_autoplay"] = False
    at.run()
    assert not at.exception, at.exception
    assert len(calls) == 1, f"the replay was built {len(calls)} times"


def test_seeded_highlight_column_follows_the_dataset(monkeypatch):
    """A highlight column the app seeded is re-derived for each dataset.

    Only the bundled demo is seeded (its answer span). Another dataset
    opens with nothing highlighted — not its first yes/no column (``IA_SKIP``),
    and not ``is_in_aspan`` either when it happens to have one. A column the
    user picked stays put."""
    import pandas as pd
    import streamlit

    from scanpath_studio import controls
    from scanpath_studio.constants import DEMO_CHOICE

    fixations = pd.DataFrame({"x": [1.0], "y": [2.0], "duration_ms": [200.0]})
    demo = pd.DataFrame(
        {"is_in_aspan": [True], "IA_SKIP": [False], "IA_REGRESSION_IN": [True]}
    )
    onestop = demo.drop(columns="is_in_aspan")

    monkeypatch.setattr(streamlit, "session_state", {})
    ss = streamlit.session_state
    ss["data_source_choice"] = DEMO_CHOICE
    controls._seed_viz_state(fixations, 16, demo)
    assert ss["global_highlight_column"] == "is_in_aspan"
    ss["data_source_choice"] = "Dataset 1"
    controls._seed_viz_state(fixations, 16, onestop)
    assert ss.get("global_highlight_column") is None
    controls._seed_viz_state(fixations, 16, demo)  # its own is_in_aspan
    assert ss.get("global_highlight_column") is None
    ss["data_source_choice"] = DEMO_CHOICE
    controls._seed_viz_state(fixations, 16, demo)
    assert ss["global_highlight_column"] == "is_in_aspan"

    ss["global_highlight_column"] = "IA_REGRESSION_IN"
    ss["data_source_choice"] = "Dataset 1"
    controls._seed_viz_state(fixations, 16, onestop)
    ss["data_source_choice"] = DEMO_CHOICE
    controls._seed_viz_state(fixations, 16, demo)
    assert ss["global_highlight_column"] == "IA_REGRESSION_IN"


def test_a_highlight_draws_a_key_naming_it():
    """Whenever words are highlighted, the figure says by what."""
    import scanpath_studio as sps

    words, fixations = sps.load_sample_data(names="canonical")
    trial = (fixations["participant_id"].iloc[0], fixations["trial_id"].iloc[0])
    marked = sps.plot_scanpath(words, fixations, *trial, highlight_column="is_in_aspan")
    keys = [a.text for a in marked.layout.annotations if a.name == "highlight_key"]
    assert len(keys) == 1 and "Highlighted: is_in_aspan (answer span)" in keys[0]
    plain = sps.plot_scanpath(words, fixations, *trial)
    assert not [a for a in plain.layout.annotations if a.name == "highlight_key"]
