"""The frames handed out by the load cache are never mutated in place.

``st.cache_data`` hands every caller a private *copy* of its result, which at
corpus scale costs ~1.15 s and ~1.2 GB of churn on every rerun — paid on each
widget touch, for data the app already has. Handing out the shared object
instead is only safe while nothing downstream writes into it, and the failure
mode if that stops being true is silent: a later rerun quietly reads an altered
frame.

So the invariant gets a test rather than a comment. This captures the words and
fixations frames at the moment the loader yields them, runs a full app render on
top, and asserts they come back byte-identical — same values, index, columns and
dtypes. A change that starts mutating them in place fails here.
"""

from __future__ import annotations

from unittest import mock

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import data
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


@pytest.fixture
def captured_demo_gaze():
    """Spy on the demo's samples as the app receives them, with their hashes."""
    from scanpath_studio import app as app_module

    captured: list = []
    real = app_module.normalized_sample_raw_gaze

    def spy():
        result = real()
        captured.append((result[0], _content_hash(result[0])))
        return result

    with mock.patch.object(app_module, "normalized_sample_raw_gaze", side_effect=spy):
        yield captured


def _shares_buffers(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    numeric = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
    return bool(numeric) and all(
        np.shares_memory(a[c].to_numpy(), b[c].to_numpy()) for c in numeric
    )


def test_every_session_shares_the_demo_gaze_buffers(captured_demo_gaze):
    """The demo's samples are read once per process, not copied per visitor:
    each session holds its own frame over the same buffers."""
    first = AppTest.from_file(APP_SCRIPT, default_timeout=120).run()
    first.run()
    second = AppTest.from_file(APP_SCRIPT, default_timeout=120).run()
    assert not first.exception and not second.exception
    frames = [frame for frame, _ in captured_demo_gaze]
    assert len(frames) == 3, "the demo samples were not loaded on every run"
    mine, again, theirs = frames
    assert again is mine, "a session's frame changed between reruns"
    assert theirs is not mine
    assert len(mine) > 100_000
    assert _shares_buffers(mine, theirs)
    # Named when it was loaded, so no session hashes it to key a cache.
    assert data.frame_fingerprint(mine)[0] == "assigned"
    assert data.frame_fingerprint(theirs) == data.frame_fingerprint(mine)


def test_a_write_to_the_demo_gaze_stays_in_one_sessions_copy():
    data.forget_frame_cache("demo_raw_gaze")
    frame, _, _ = data.normalized_sample_raw_gaze()
    content, fingerprint = _content_hash(frame), data.frame_fingerprint(frame)
    frame["extra"] = 1
    frame.loc[frame.index[0], "x"] = -1.0
    frame.attrs["edited"] = True
    data.forget_frame_cache("demo_raw_gaze")  # what another session starts from
    fresh, _, _ = data.normalized_sample_raw_gaze()
    assert fresh is not frame
    assert _content_hash(fresh) == content
    assert "edited" not in fresh.attrs
    assert data.frame_fingerprint(fresh) == fingerprint


def test_drawing_the_demo_gaze_leaves_the_shared_frame_untouched(captured_demo_gaze):
    """A session's copy keeps one fingerprint for its life, so an in-place
    edit would leave caches keyed on content it no longer has."""
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.query_params["show_raw_gaze"] = "1"
    at.run()
    assert at.session_state["global_show_raw_gaze"] is True
    at.button(key="viz_view_gaze_over_time").click().run()
    at.run()
    assert not at.exception
    assert captured_demo_gaze, "the spy is not wired to the app"
    for frame, content in captured_demo_gaze:
        assert _content_hash(frame) == content, "demo gaze frame mutated in place"
