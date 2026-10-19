"""The recovery cache restores the last view only on a bare visit: a page the
URL names, or a link, opens where it says."""

from __future__ import annotations

import pytest
from streamlit.navigation.page import calc_hash
from streamlit.testing.v1 import AppTest

from scanpath_studio import persistence
from scanpath_studio.menu import _VIEW_CORPUS, _VIEW_DATA, _VIEW_SCANPATH
from scanpath_studio.persistence import restore_local_state, save_state
from tests.conftest import APP_SCRIPT, NAV_KEY

URL = "http://localhost:8501"


def _first_run(page_url_path: str, restored_view: str) -> AppTest:
    """A session's first run on ``page_url_path`` with ``restored_view`` in
    ``main_nav``, the way the recovery cache leaves it before the nav draws."""
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state[NAV_KEY] = restored_view
    at._page_hash = calc_hash(page_url_path) if page_url_path else ""
    at.run(timeout=90)
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize(
    ("url_path", "restored", "expected"),
    [
        ("data", _VIEW_CORPUS, _VIEW_DATA),
        ("corpus-analysis", _VIEW_DATA, _VIEW_CORPUS),
        ("scanpath", _VIEW_DATA, _VIEW_DATA),  # the default page: resumes
    ],
)
def test_a_page_named_in_the_url_wins_over_the_restored_view(
    url_path, restored, expected
):
    at = _first_run(url_path, restored)
    assert at.session_state[NAV_KEY] == expected


def test_a_bare_visit_resumes_the_restored_view():
    at = _first_run("", _VIEW_DATA)
    assert at.session_state[NAV_KEY] == _VIEW_DATA


def test_later_requests_still_switch_the_view():
    """Only the first run defers to the URL: the app's own requests (the Data
    page's Open in Scanpath, the tour, Add dataset) keep working after it."""
    at = _first_run("data", _VIEW_CORPUS)
    at.session_state[NAV_KEY] = _VIEW_SCANPATH
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[NAV_KEY] == _VIEW_SCANPATH


class TestALinkKeepsTheStoredViewOut:
    @pytest.fixture
    def cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
        monkeypatch.setattr(persistence, "state_directory", lambda *a, **k: tmp_path)
        assert save_state({NAV_KEY: _VIEW_DATA, "global_show_heatmap": True}, tmp_path)
        return tmp_path

    def test_a_bare_visit_restores_it(self, cache):
        session = {}
        restore_local_state(session, URL)
        assert session[NAV_KEY] == _VIEW_DATA

    def test_a_link_leaves_it_out_and_keeps_the_rest(self, cache):
        session = {}
        restore_local_state(session, URL, protect_view=True)
        assert NAV_KEY not in session
        assert session["global_show_heatmap"] is True
