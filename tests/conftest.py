"""Pytest configuration and fixtures for scanpath visualization tests."""

from pathlib import Path

import pandas as pd
import pytest

from tests.synthetic_data import make_synthetic_fixations, make_synthetic_words

#: Absolute path to the app entry point driven by ``AppTest.from_file``.
#: Streamlit 1.61 resolves a *relative* script path against the file that calls
#: ``from_file`` (previously the process CWD), so ``"streamlit_app.py"`` would
#: look for ``tests/streamlit_app.py``. Always pass this constant.
APP_SCRIPT = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


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
    """Create a sample words/IA dataframe for testing."""
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
def sample_fixations_df():
    """Create a sample fixations dataframe for testing."""
    return pd.DataFrame(
        {
            "participant_id": ["p1", "p1", "p1", "p2", "p2"],
            "trial_id": ["t1", "t1", "t1", "t1", "t1"],
            "CURRENT_FIX_X": [125, 225, 325, 125, 225],
            "CURRENT_FIX_Y": [75, 75, 75, 75, 75],
            "CURRENT_FIX_DURATION": [200, 250, 180, 220, 190],
            "CURRENT_FIX_START": [0, 200, 450, 0, 220],
            "CURRENT_FIX_INTEREST_AREA_ID": [1, 2, 3, 1, 2],
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
#: selects one. PERF-3 made the four expensive panels render only when their tab
#: is open (`st.tabs(key=…)` + `tab.open`), so a test that wants Export or Data
#: Inspection must open it first, exactly as a user does.
SUBTAB_KEY = "single_subtab"
SUBTAB_ANNOTATIONS = "📝 Annotations"
SUBTAB_COMPARISONS = "🔬 Comparisons"
SUBTAB_LINE_ASSIGNMENT = "📐 Line assignment"
SUBTAB_EXPORT = "Export"
SUBTAB_DATA_INSPECTION = "🔎 Data Inspection"


def open_subtab(at, label: str):
    """Select a per-trial subtab and rerun, so its body renders (PERF-3)."""
    at.session_state[SUBTAB_KEY] = label
    return at.run()


def answer_setup_step(at, *, screen=None, geometry=None, text=None):
    """Answer the wizard's Recording-setup step (DATA-22 step 4).

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
