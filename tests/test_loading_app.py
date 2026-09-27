"""UX-166 … UX-169 in the running app, via AppTest.

A run freezes with ``st.stop()`` inside the step under test, so the tree keeps
the card that step is showing — with ``loading._KEEP_ON_STOP`` set, since a
stopped run otherwise clears its cards. ``loading.DELAY_S = 0`` reveals cards
on the script thread, so what AppTest sees does not depend on timing.
"""

from __future__ import annotations

import pytest

from scanpath_studio import app, loading
from scanpath_studio.constants import _VIEW_CORPUS
from tests.conftest import APP_SCRIPT, pin_view

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
SYNTHETIC = "Synthetic test trial"


def _stop(*_args, **_kwargs):
    import streamlit as st

    st.stop()


def _markdown(at) -> str:
    """Every markdown element's source except the app's stylesheets.

    The injected ``<style>`` sheet names every loading class (``.sps-card-head``,
    ``.sps-page-skeleton``, ``.sps-step-done`` …), so leaving it in would make
    each "is it on the page?" check true on every run, and each "is it gone?"
    check false.
    """
    return "\n".join(
        m.value for m in at.markdown if not m.value.lstrip().startswith("<style")
    )


@pytest.fixture
def at():
    test = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    test.session_state["data_source_choice"] = SYNTHETIC
    return test


def test_a_finished_load_leaves_no_card_and_no_skeleton(at):
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text
    assert at.session_state[app.LAST_LOADED_SOURCE_KEY] == SYNTHETIC


def test_a_slow_load_shows_the_skeleton_and_its_step_list(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _stop)
    at.session_state["_pending_source_choice"] = "Bundled Demo"
    at.run()
    text = _markdown(at)
    assert "sps-sk-scanpath" in text and "sps-reveal-page" in text
    assert "sps-step-done" in text  # Reading files ✓
    assert "Normalizing" in text  # the current step, with the row counts


def test_switching_view_shows_the_target_skeleton_at_once(at, monkeypatch):
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "render_corpus_analysis_tab", _stop)
    pin_view(at, _VIEW_CORPUS)
    at.run()
    text = _markdown(at)
    assert "Opening Corpus Analysis" in text
    assert "sps-sk-corpus" in text


def _unmappable(raw_words, raw_fixations, **_kwargs):
    return raw_words, raw_fixations, ["A required column isn't mapped yet."]


def test_an_early_return_takes_the_card_and_the_skeleton_down(at, monkeypatch):
    """BUG-81, for the card that replaced the loading banners: a run that returns
    early (here, a mapping that can't be satisfied) takes a *showing* card and
    its skeleton down itself — `_KEEP_ON_STOP` switches off the run's own
    safety net, so only the early return can have cleared them."""
    at.run()
    monkeypatch.setattr(loading, "DELAY_S", 0)
    monkeypatch.setattr(loading, "_KEEP_ON_STOP", True)
    monkeypatch.setattr(app, "prepare_data", _unmappable)
    at.run()
    assert not at.exception, at.exception
    text = _markdown(at)
    assert "sps-card-head" not in text and "sps-page-skeleton" not in text
    assert app.DATASET_TASK_KEY not in at.session_state


def test_the_missing_corpus_notice_stays_above_the_view(at, monkeypatch):
    """UX-7(b)'s panel is drawn on the way to the view. With the view inside the
    reserved area it has to go in there too, or it lands below the whole page."""

    def _notice():
        import streamlit as st

        st.markdown("missing-corpus-notice")

    def _view(*_args, **_kwargs):
        import streamlit as st

        st.markdown("scanpath-view-body")

    monkeypatch.setattr(app, "_render_dataset_unavailable", _notice)
    monkeypatch.setattr(app, "render_single_trial_tab", _view)
    at.run()
    assert not at.exception, at.exception
    order = [m.value for m in at.markdown]
    assert order.index("missing-corpus-notice") < order.index("scanpath-view-body")
