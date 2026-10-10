"""#422 — the rail's *Available fields* are the ones the figure renders with.

The list, the pattern's validation and its preview were computed for a
stand-in trial ("p01" · "t01") with no `combos` row, so the preview showed
made-up ids and a field the figure itself accepts could be refused as unknown.
They now come from `tabs._title_caption_fields` for the selected trial.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.export import pattern_fields
from scanpath_studio.synthetic import PARTICIPANT, TRIAL
from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

pytestmark = pytest.mark.timeout(180)


def _app(pattern: str) -> AppTest:
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["global_show_title"] = True
    at.session_state["global_title_pattern"] = pattern
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _previews(at: AppTest) -> list[str]:
    return [c.value for c in at.caption if "Title preview" in str(c.value)]


def test_the_preview_is_the_selected_trial():
    at = _app("{participant_id} · {trial_id}")
    assert _previews(at) == [f"Title preview — **{PARTICIPANT} · {TRIAL}**"]


def test_the_preview_counts_the_fixations_in_the_window():
    """The figure draws only the fixation window, and its `{n_fixations}`
    counts those; the preview must say the same."""
    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["global_show_title"] = True
    at.session_state["global_title_pattern"] = "{n_fixations}"
    at.session_state["single_fix_range"] = (1, 3)
    at.run(timeout=60)
    assert not at.exception, at.exception
    assert _previews(at) == ["Title preview — **3**"]


def test_the_rail_asks_the_figures_fields_with_live_settings(monkeypatch):
    """The figure renders with the trial's `combos` row; so does the rail."""
    from scanpath_studio import tabs

    seen = []
    original = tabs._title_caption_fields

    def spy(*args, **kwargs):
        fields = original(*args, **kwargs)
        seen.append(fields)
        return fields

    monkeypatch.setattr(tabs, "_title_caption_fields", spy)
    at = _app("{settings}")
    assert seen, "the rail did not ask the figure's fields"
    preview = _previews(at)[0]
    # The live settings, not an empty stand-in ("layers: none").
    assert "layers: none" not in preview
    assert not [e.value for e in at.error]


def test_the_trials_row_is_fields_but_its_bookkeeping_is_not():
    fields = pattern_fields(
        "p",
        "t",
        pd.DataFrame(),
        pd.DataFrame(),
        {},
        combo_row={"participant_id": "p", "TRIAL_INDEX": 3, "_data_order": 7},
    )
    assert fields["TRIAL_INDEX"] == 3
    assert "_data_order" not in fields
