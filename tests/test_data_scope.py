"""UX-203 — the Data Management page says which counts follow the trial filters.

📊 Stats and the raw tables count the filtered pool while 📂 Available datasets
and *Available with this dataset* count the whole dataset. Before this nothing
on the page said which was which. One ``AppTest`` flow on the bundled demo
(2 readers × 12 trials) pins both states.
"""

from __future__ import annotations

import pytest

from tests.conftest import APP_SCRIPT, pin_data_view, pin_view

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


def _captions(at, needle: str) -> list[str]:
    return [c.value for c in at.caption if needle in c.value]


@pytest.mark.timeout(240)
def test_the_data_page_names_the_scope_of_its_counts():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception

    # Unfiltered: Stats and the three trial tables say "whole dataset", and
    # nothing else on the page needs to.
    whole = _captions(at, "24 trials · 2 readers · whole dataset")
    assert len(whole) == 4, whole  # Stats + Fixations + Words + Raw gaze
    assert not _captions(at, "before the trial filters")

    # Set on the Scanpath view, where the filter panel publishes the result
    # `app.main` filters with on the following run (as in UX-198's test).
    pin_view(at, "Scanpath")
    at.run(timeout=90)
    at.session_state["filter_participants"] = ["l7_1090"]
    at.run(timeout=90)
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception

    scoped = _captions(at, "12 of 24 trials · 1 of 2 readers · filtered")
    assert len(scoped) == 4, scoped
    assert all("Participant: l7\\_1090" in c for c in scoped)
    # The table and the capabilities block say they did not follow.
    assert _captions(at, "Whole datasets, before the trial filters")
    assert _captions(at, "Available with this dataset** · whole dataset")
