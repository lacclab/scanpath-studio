"""Pytest configuration and fixtures for scanpath visualization tests."""

from pathlib import Path

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.constants import _VIEW_DATA
from tests.synthetic_data import make_synthetic_fixations, make_synthetic_words

#: Absolute path to the app entry point driven by ``AppTest.from_file``.
#: Streamlit 1.61 resolves a *relative* script path against the file that calls
#: ``from_file`` (previously the process CWD), so ``"streamlit_app.py"`` would
#: look for ``tests/streamlit_app.py``. Always pass this constant.
APP_SCRIPT = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


@pytest.fixture(autouse=True, scope="session")
def _experimental_features_on():
    """Run the suite with PRE-21's gated features **exposed**.

    Vertical drift correction and the NLD similarity scoring are hidden by
    default ahead of publication, but they still work and are still covered —
    hiding them must not quietly delete their test coverage. So the whole suite
    runs with ``SCANPATH_EXPERIMENTAL=1``, and the tests that assert the *hidden*
    build (``tests/test_experimental_gate.py``) unset it themselves. Every gate
    reads the env var at call time, which is what makes that work.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SCANPATH_EXPERIMENTAL", "1")
        yield


@pytest.fixture
def experimental_off(monkeypatch):
    """Force PRE-21's gated features **hidden**, as a default build sees them."""
    monkeypatch.delenv("SCANPATH_EXPERIMENTAL", raising=False)


@pytest.fixture(autouse=True, scope="session")
def _no_developer_local_benchmark_bundle(tmp_path_factory):
    """Point benchmark discovery at an empty directory for the whole suite (M16).

    DATA-27 made the public-dataset registry a *function* that enumerates every
    prepared corpus found under `EYEGENBENCH_DEFAULT_DIR` — which is
    ``data/EyeGenBench`` inside the repo. A developer who has built a bundle
    there (or, worse, is building one *while* the suite runs) therefore gets a
    different registry from CI's, and any test that reasons about the whole
    registry — how many corpora, which short names, whether an option list
    contains one — silently changes meaning with the contents of an untracked
    directory. Pinning it here means a benchmark corpus exists in a test only
    when that test writes one and points the constant at it, which every
    DATA-27 test already does (a `monkeypatch.setattr` inside a test wins over
    this).

    **Every module that binds the name is patched**, not just `app`: each does
    its own ``from .constants import EYEGENBENCH_DEFAULT_DIR``, so each holds a
    separate binding and patching `constants` alone reaches none of them. In
    particular `compare_source` resolves the bundle location independently when
    it enumerates comparison sources, so an `app`-only patch would leave the
    compare surface reading the developer's real ``data/EyeGenBench``.
    """
    from scanpath_studio import app, compare_source, constants

    empty = tmp_path_factory.mktemp("no-benchmark-bundle")
    with pytest.MonkeyPatch.context() as mp:
        for module in (constants, app, compare_source):
            mp.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(empty))
        yield


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
#: Re-exported from ``tabs`` rather than repeated, since PRE-21 made the set
#: conditional (📐 Line assignment is offered only while drift correction is).
SUBTAB_KEY = "single_subtab"
SUBTAB_ANNOTATIONS = tabs.SUBTAB_ANNOTATIONS
SUBTAB_COMPARISONS = tabs.SUBTAB_COMPARISONS
SUBTAB_LINE_ASSIGNMENT = tabs.SUBTAB_LINE_ASSIGNMENT
SUBTAB_EXPORT = tabs.SUBTAB_EXPORT

#: DATA-26: 🔎 Data Inspection is no longer a subtab of the Scanpath view — its
#: content is the lower half of the 🗂️ **Data** page, a third top-level view.
#: Reaching it is a nav switch, not a tab click.
NAV_KEY = "main_nav"
NAV_MIRROR_KEY = "_nav_mirrored"
VIEW_DATA = _VIEW_DATA


def open_subtab(at, label: str):
    """Select a per-trial subtab and rerun, so its body renders (PERF-3)."""
    at.session_state[SUBTAB_KEY] = label
    return at.run()


def pin_view(at, view: str) -> None:
    """Ask for ``view`` on the *next* run, without running (DATA-26).

    Clearing ``menu._MIRROR_KEY`` alongside the request is what makes this work
    twice. ``render_nav`` honours a ``main_nav`` request only when it differs
    from what it last mirrored — the check that stops a nav *click* reading as
    "go back" — and it relies on the router remembering the selected page across
    reruns, which a browser does through the URL and ``AppTest`` does not. So a
    second ``main_nav = Data`` on an app already showing Data is ignored, the
    router falls back to its default page, and the assertions land on Scanpath.
    """
    at.session_state[NAV_KEY] = view
    at.session_state[NAV_MIRROR_KEY] = None


def pin_data_view(at) -> None:
    """:func:`pin_view` for the 🗂️ Data page — the common case."""
    pin_view(at, VIEW_DATA)


def arm_session_dialog(at) -> None:
    """Ask for the 💾 Session modal on the *next* run (UX-100).

    Call it before **every** ``at.run()`` in a flow that drives the panel, not
    just the first. In a browser an interaction inside a dialog reruns only the
    dialog — a fragment — so the modal stays open on its own; ``AppTest`` has no
    fragment reruns and replays the whole script, which pops the request flag.
    Re-arming is how a test says "the user has not dismissed it yet".
    """
    from scanpath_studio import app

    at.session_state[app._SESSION_DIALOG_KEY] = True


def open_data_view(at, timeout: int = 60):
    """Switch to the 🗂️ Data page and rerun, so its body renders (DATA-26)."""
    pin_data_view(at)
    return at.run(timeout=timeout)


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


def _write_benchmark_corpus(
    root, name: str, *, readers=("r1",), paragraphs=("p1",), fix_leftovers=None
) -> None:
    """Write one prepared benchmark corpus (DATA-27) under ``root/<name>/``.

    The frames match `eyegenbench.EYEGENBENCH_WORD_SCHEMA` / `_FIX_SCHEMA` —
    trivial single-column frames fail schema mapping, and `main()` returns early
    on an unmapped source (`_render_unmapped_view`) without reaching most of what
    these tests assert on.

    ``fix_leftovers`` is a ``{column: value}`` mapping stamped onto every
    fixation row, and it exists because the idealized default hid two real bugs
    for a whole branch. A real prepared corpus carries the **publisher's** ~190
    columns through beside the harmonised ones, and the app's auto-detection
    seizes on them: EMTeC ships a `TRIAL_ID` that outranks `unique_paragraph_id`
    (so the words broadcast to zero rows, silently), and Provo/SBSAT ship a
    `page` that reads as a multipart screen on the fixations only (so the pair
    is rejected outright). Pass the leftovers when a test needs the shape the
    bundle actually has rather than the shape the schema describes.
    """
    import pandas as pd

    directory = root / name
    directory.mkdir(parents=True)
    n = len(paragraphs)
    pd.DataFrame(
        {
            "unique_paragraph_id": [p for p in paragraphs for _ in (0, 1)],
            "ia_index": [0, 1] * n,
            "ia_label": ["ab", "cd"] * n,
            "line": [0, 0] * n,
            "start_x": [10.0, 70.0] * n,
            "end_x": [60.0, 120.0] * n,
            "start_y": [20.0, 20.0] * n,
            "end_y": [40.0, 40.0] * n,
        }
    ).to_parquet(directory / "words.parquet")
    rows = [
        (reader, paragraph, fix_index)
        for reader in readers
        for paragraph in paragraphs
        for fix_index in (0, 1)
    ]
    fixations = pd.DataFrame(
        {
            "eyegenbench_trial_id": [f"t_{p}" for _, p, _ in rows],
            "unique_participant_id": [r for r, _, _ in rows],
            "unique_paragraph_id": [p for _, p, _ in rows],
            "fix_index": [i for _, _, i in rows],
            "ia_index": [i for _, _, i in rows],
            "fix_duration": [200 if i == 0 else 180 for _, _, i in rows],
            "x": [35.0 if i == 0 else 95.0 for _, _, i in rows],
            "y": [30.0 for _ in rows],
        }
    )
    for column, value in (fix_leftovers or {}).items():
        fixations[column] = value
    fixations.to_parquet(directory / "fixations.parquet")
    pd.DataFrame(
        {
            "unique_participant_id": list(readers),
            "participant_language": ["xx"] * len(readers),
        }
    ).to_parquet(directory / "participants.parquet")


def _write_benchmark_manifest(root, entries) -> None:
    """Write the bundle manifest. ``entries`` are real manifest rows — in
    particular ``language`` is an **ISO code** ('de'), never a name."""
    import json

    (root / "manifest.json").write_text(json.dumps({"datasets": list(entries)}))
