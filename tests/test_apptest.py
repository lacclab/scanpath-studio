"""Streamlit AppTest integration: spin up the app and assert key surfaces render."""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _make_apptest() -> "AppTest":
    return AppTest.from_file("streamlit_app.py")


@pytest.mark.timeout(60)
class TestAppLaunches:
    def test_app_launches_with_bundled_demo(self):
        at = _make_apptest()
        at.run(timeout=30)
        # The four-tab UI should render without exceptions
        assert not at.exception, f"Streamlit exceptions: {at.exception}"

    def test_title_present(self):
        at = _make_apptest()
        at.run(timeout=30)
        titles = [t.value for t in at.title]
        assert any("Scanpath Visualization" in v for v in titles)

    def test_no_streamlit_errors(self):
        at = _make_apptest()
        at.run(timeout=30)
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
