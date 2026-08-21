"""The frames handed out by the load cache are never mutated in place (PERF-6).

``st.cache_data`` hands every caller a private *copy* of its result, which at
corpus scale costs ~1.15 s and ~1.2 GB of churn on every rerun — paid on each
widget touch, for data the app already had. Handing out the shared object
instead is only safe while nothing downstream writes into it, and the failure
mode if that stops being true is silent: a later rerun quietly reads an altered
frame.

So the invariant gets a test rather than a comment. This captures the words and
fixations frames at the moment the loader yields them, runs a full app render on
top, and asserts they come back byte-identical — same values, index, columns and
dtypes. A change that starts mutating them in place fails here.

The static half of the audit is an AST sweep for writes into an un-rebound
frame parameter; it is clean, and this is the half that stays clean.
"""

from __future__ import annotations

from unittest import mock

import pandas as pd
import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _content_hash(frame: pd.DataFrame):
    """Everything a silent in-place edit could change."""
    return (
        tuple(frame.columns),
        tuple(str(d) for d in frame.dtypes),
        frame.shape,
        int(pd.util.hash_pandas_object(frame, index=True).sum()),
    )


@pytest.fixture
def captured_frames():
    """Spy on the loader, keeping the frames it hands the app *and* their hashes."""
    from scanpath_studio import app as app_module

    captured: list = []
    real = app_module._normalize_pair

    def spy(*args, **kwargs):
        words, fixations = real(*args, **kwargs)
        captured.append(
            (words, _content_hash(words), fixations, _content_hash(fixations))
        )
        return words, fixations

    with mock.patch.object(app_module, "_normalize_pair", side_effect=spy):
        yield captured


def test_a_full_render_leaves_the_loaded_frames_untouched(captured_frames):
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    assert not at.exception
    assert captured_frames, "the loader never ran — the spy is not wired to the app"
    for words, words_hash, fixations, fix_hash in captured_frames:
        assert _content_hash(words) == words_hash, "words frame mutated in place"
        assert _content_hash(fixations) == fix_hash, "fixations frame mutated in place"


def test_a_second_rerun_leaves_them_untouched(captured_frames):
    """The rerun is the case that matters: it is where a shared frame would be
    read back after whatever the previous run did to it."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.run()
    at.run()
    assert not at.exception
    for words, words_hash, fixations, fix_hash in captured_frames:
        assert _content_hash(words) == words_hash
        assert _content_hash(fixations) == fix_hash
