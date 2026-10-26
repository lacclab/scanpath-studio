"""Pytest configuration and fixtures for scanpath visualization tests."""

from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import tabs
from scanpath_studio.constants import _VIEW_DATA
from tests.synthetic_data import make_synthetic_fixations, make_synthetic_words

#: Absolute path to the app entry point driven by ``AppTest.from_file``.
#: ``from_file`` resolves a *relative* script path against the file that calls
#: it, not the process CWD, so ``"streamlit_app.py"`` would look for
#: ``tests/streamlit_app.py``. Always pass this constant.
APP_SCRIPT = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture(autouse=True, scope="session")
def _experimental_features_on():
    """Run the suite with the experimental features **exposed**.

    The features behind ``SCANPATH_EXPERIMENTAL`` (vertical drift correction,
    NLD similarity scoring, the app's computed measures and others) are hidden
    by default, but they still work and are still covered —
    hiding them must not quietly delete their test coverage. So the whole suite
    runs with ``SCANPATH_EXPERIMENTAL=1``, and the tests that assert the *hidden*
    build (``tests/test_experimental_gate.py``) unset it themselves. Every gate
    reads the env var at call time, which is what makes that work.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SCANPATH_EXPERIMENTAL", "1")
        yield


@pytest.fixture(autouse=True, scope="session")
def _local_filesystem_on():
    """Run the suite as a local install sees it: the path box, picker and ⬇ on.

    Unset, the gate follows the server's bind address, and an AppTest's
    ``server.address`` is unset — every interface, which reads as a shared
    deployment — so without this every Data-page test would see the hosted
    build. The gate's own tests (``tests/test_deployment_gate.py``) unset it.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SCANPATH_LOCAL_FS", "1")
        yield


@pytest.fixture(autouse=True)
def _advanced_ui_mode(monkeypatch):
    """Boot every ``AppTest`` in Full mode, the full interface.

    Most tests drive controls that Essentials mode hides, so each app starts with
    ``?ui=full``. A test that sets ``at.query_params["ui"]`` itself after
    ``from_file`` overrides it.
    """
    from_file = AppTest.from_file.__func__

    def pinned(cls, *args, **kwargs):
        at = from_file(cls, *args, **kwargs)
        at.query_params["ui"] = "full"
        return at

    monkeypatch.setattr(AppTest, "from_file", classmethod(pinned))


@pytest.fixture
def experimental_off(monkeypatch):
    """Force the experimental features **hidden**, as a default build sees them."""
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)


@pytest.fixture(autouse=True, scope="session")
def _plain_text_cli_output():
    """Pin CLI/argparse output to uncoloured text for the whole run.

    Python 3.14's argparse colourises ``--help``, and `_colorize.can_colorize`
    honours ``FORCE_COLOR`` / ``PYTHON_COLORS`` *before* it looks at whether the
    stream is a terminal. Agent harnesses, CI wrappers and some shells export
    those, so a developer with one set would see the help-text assertions in
    ``tests/test_cli_drift.py`` fail on ANSI escapes that CI never emits — a
    failure about the environment, not the code. ``NO_COLOR`` wins over both,
    and also covers a ``pytest -s`` run where stdout really is a tty.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("FORCE_COLOR", raising=False)
        mp.delenv("PYTHON_COLORS", raising=False)
        mp.setenv("NO_COLOR", "1")
        yield


@pytest.fixture
def synthetic_words_df():
    """Normalized words for the fully-specified synthetic trial.

    See ``tests/synthetic_data.py`` for the layout and the hand-traced
    ``EXPECTED`` measure values.
    """
    return make_synthetic_words()


@pytest.fixture
def synthetic_fixations_df():
    """Normalized fixations for the synthetic trial (word_id left NaN)."""
    return make_synthetic_fixations()


@pytest.fixture
def sample_words_df():
    """Create a sample Words table dataframe for testing."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t1", "t1"],
            "word_id": [1, 2, 3, 1, 2],
            "IA_LEFT": [100, 200, 300, 100, 200],
            "IA_RIGHT": [150, 250, 350, 150, 250],
            "IA_TOP": [50, 50, 50, 50, 50],
            "IA_BOTTOM": [100, 100, 100, 100, 100],
            "IA_LABEL": ["word1", "word2", "word3", "word1", "word2"],
            "paragraph_id": ["para1", "para1", "para1", "para1", "para1"],
        }
    )


@pytest.fixture
def sample_raw_gaze_df():
    """Create a sample raw gaze dataframe for testing."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p1", "p1"],
            "trial_id": ["t1", "t1", "t1", "t1", "t1"],
            "x": [120, 125, 130, 220, 225],
            "y": [70, 75, 80, 70, 75],
            "timestamp": [0, 1, 2, 3, 4],
        }
    )


@pytest.fixture
def normalized_words_df():
    """Create a normalized words dataframe for testing."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1"],
            "trial_id": ["t1", "t1", "t1"],
            "word_id": [1, 2, 3],
            "x": [100, 200, 300],
            "y": [50, 50, 50],
            "width": [50, 50, 50],
            "height": [50, 50, 50],
            "text": ["word1", "word2", "word3"],
            "text_id": ["para1", "para1", "para1"],
            "line_idx": [1, 1, 1],
        }
    )


@pytest.fixture
def normalized_fixations_df():
    """Create a normalized fixations dataframe for testing."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1"],
            "trial_id": ["t1", "t1", "t1"],
            "x": [125, 225, 325],
            "y": [75, 75, 75],
            "duration_ms": [200, 250, 180],
            "timestamp_ms": [0, 200, 450],
            "word_id": [1, 2, 3],
            "order_in_trial": [1, 2, 3],
            "pass_index": [1, 1, 1],
            "saccade_type": ["RIGHT", "RIGHT", "LEFT"],
            "eye": ["Both", "Both", "Both"],
            "noise_flag": [False, False, False],
        }
    )


#: Labels of the Scanpath view's per-trial subtabs, and the session key that
#: selects one. The expensive panels render only when their tab is open
#: (`st.tabs(key=…)` + `tab.open`), so a test that wants Export must open it
#: first, exactly as a user does.
#: Re-exported from ``tabs`` rather than repeated, since the set is conditional
#: (📐 Line assignment is offered only while drift correction is).
SUBTAB_KEY = "single_subtab"
SUBTAB_ANNOTATIONS = tabs.SUBTAB_ANNOTATIONS
SUBTAB_COMPARISONS = tabs.SUBTAB_COMPARISONS
SUBTAB_LINE_ASSIGNMENT = tabs.SUBTAB_LINE_ASSIGNMENT
SUBTAB_EXPORT = tabs.SUBTAB_EXPORT
SUBTAB_SHARE = tabs.SUBTAB_SHARE

#: 🔎 Data Inspection is not a subtab of the Scanpath view — its content is
#: part of the 🗂️ **Data** page, a top-level view. Reaching it is a nav switch,
#: not a tab click.
NAV_KEY = "main_nav"
NAV_MIRROR_KEY = "_nav_mirrored"
VIEW_DATA = _VIEW_DATA


def pin_view(at, view: str) -> None:
    """Ask for ``view`` on the *next* run, without running.

    Clearing ``menu._MIRROR_KEY`` alongside the request is what makes this work
    twice. ``render_nav`` honours a ``main_nav`` request only when it differs
    from what it last mirrored — the check that stops a nav *click* reading as
    "go back" — so without the clear, a second ``main_nav = Data`` on an app
    already showing Data is ignored and the assertions land on another page.

    ``AppTest`` remembers the page a run finished on, the way a browser's URL
    does, and a ``st.switch_page`` inside a run does not move it. So the remembered page is dropped too, and the run starts on
    the default page, from which ``render_nav`` switches to the request.
    """
    at.session_state[NAV_KEY] = view
    at.session_state[NAV_MIRROR_KEY] = None
    # A first run pinned to a view is about that view, but the first-visit
    # welcome tour takes a first run to Scanpath, where its steps point. Count
    # the tour as seen unless the test has already decided.
    if "tour_seen" not in at.session_state:
        at.session_state["tour_seen"] = True
    if hasattr(at, "_finished_page_script_hash"):
        at._finished_page_script_hash = ""
        at._page_hash = ""


def pin_data_view(at) -> None:
    """:func:`pin_view` for the 🗂️ Data page — the common case."""
    pin_view(at, VIEW_DATA)


def picked_trial_id(value) -> str | None:
    """The trial id in the trial picker's value (``single_trial_id``), which
    names a reading — participant and trial."""
    from scanpath_studio.utils import split_reading_key

    return split_reading_key(value)[1]


def picker_trial_id(option: str) -> str:
    """The trial id behind a trial-picker option, as ``AppTest`` shows it.

    The picker displays an id part by part, and ``AppTest`` exposes only the
    displayed text — so rejoin the parts with ``_``. An id that did not split
    is shown as it is. The demo's ids carry no reading part, so nothing the
    display leaves out needs putting back.
    """
    # The annotation badges (★) follow the trial id; strip them first.
    shown = str(option).removesuffix(" ★").strip()
    return "_".join(shown.split(" · "))


def arm_debug_dialog(at) -> None:
    """Ask for the ❓ Help → About → Debug modal on the *next* run.

    Call it before **every** ``at.run()`` in a flow that drives the dialog, not
    just the first. In a browser an interaction inside a dialog reruns only the
    dialog — a fragment — so the modal stays open on its own; ``AppTest`` has no
    fragment reruns and replays the whole script, which pops the request flag.
    Re-arming is how a test says "the user has not dismissed it yet".
    """
    from scanpath_studio import debug_log

    at.session_state[debug_log._DEBUG_DIALOG_KEY] = True


def open_data_view(at, timeout: int = 60):
    """Switch to the 🗂️ Data page and rerun, so its body renders."""
    pin_data_view(at)
    return at.run(timeout=timeout)


def open_dataset_editor(at, timeout: int = 60):
    """Open ✏️ Edit dataset on the open dataset's row, as a user does.

    A built-in source's column-mapping panels are drawn only while it is
    open; on every other run their picks are read from session state."""
    from scanpath_studio.app import _dataset_row_slug

    open_data_view(at, timeout=timeout)
    token = str(at.session_state["data_source_choice"])
    at.button(key=f"dataset_row_edit_{_dataset_row_slug(token)}").click()
    pin_data_view(at)
    return at.run(timeout=timeout)


def edit_builtin_mapping(at, picks: dict, timeout: int = 60):
    """Change a built-in source's column mapping the way a user does.

    Opens ✏️ Edit dataset, sets each ``{widget key: value}`` in its panels and
    presses ✅ Save changes — until then the panels are a draft and the
    dataset keeps its mapping."""
    open_dataset_editor(at, timeout=timeout)
    for key, value in picks.items():
        widget = next(
            (
                w
                for group in (at.selectbox, at.multiselect, at.radio)
                for w in group
                if w.key == key
            ),
            None,
        )
        assert widget is not None, f"no mapping widget {key!r} in the editor"
        widget.set_value(value)
    pin_data_view(at)
    at.run(timeout=timeout)
    at.button(key="builtin_mapping_save").click()
    pin_data_view(at)
    return at.run(timeout=timeout)


def answer_setup_step(at, *, screen=None, geometry=None, text=None):
    """Answer the add-dataset wizard's Recording-setup step.

    ``Add dataset`` is gated on all three groups being answered — deliberately,
    so an uploaded dataset can never inherit a silent 2560x1440 / 597 mm / 16 px
    guess. Every AppTest that finalizes an upload therefore has to say how it
    knows its setup, exactly as a user does. The defaults here take the named
    defaults (provenance ``assumed``), which is the cheapest honest answer.

    Does **not** rerun — set the keys, then run, so a caller can batch this with
    its own session-state writes on the same pass.
    """
    from scanpath_studio.wizard import (
        _GEOM_DEFAULT,
        _SCREEN_DEFAULT,
        _SETUP_MODE_KEYS,
        _TEXT_DEFAULT,
    )

    at.session_state[_SETUP_MODE_KEYS["screen"]] = screen or _SCREEN_DEFAULT
    at.session_state[_SETUP_MODE_KEYS["geometry"]] = geometry or _GEOM_DEFAULT
    at.session_state[_SETUP_MODE_KEYS["text"]] = text or _TEXT_DEFAULT
    return at
