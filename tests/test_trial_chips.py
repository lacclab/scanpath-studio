"""The trial-condition chip strip above the scanpath.

UX-11 split the strip by *kind*: conditions inline as chips, the computed stats
(reading time, the counts) behind a **Summary stats** popover beside it. This
round folded the stats back in as ordinary chips — the two numbers most often
wanted cost a click, and the control was empty as often as not — so the popover
is gone and the picker offers all four alongside every other field.
"""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def test_two_summary_fields_are_chips_by_default():
    from scanpath_studio.controls import (
        _CHIP_DEFAULT_SUMMARY,
        SUMMARY_CHIP_FIELDS,
        _default_chip_fields,
    )

    available = list(SUMMARY_CHIP_FIELDS) + ["participant_id"]
    shown = _default_chip_fields(available)

    assert "@reading_time_s" in shown
    assert "@fixation_count" in shown
    # The other two are offered like any other field, not shown by default —
    # four computed chips crowd out the conditions beside them.
    assert "@word_count" not in shown
    assert "@in_text_fixations" not in shown
    assert set(_CHIP_DEFAULT_SUMMARY) == {"@reading_time_s", "@fixation_count"}


def test_every_summary_field_is_still_pickable():
    """Dropping two from the default must not drop them from the picker."""
    import pandas as pd

    from scanpath_studio.controls import SUMMARY_CHIP_FIELDS, _chip_field_options

    options = _chip_field_options(pd.DataFrame(), pd.DataFrame(), set())
    for key in SUMMARY_CHIP_FIELDS:
        assert key in options, key


def test_a_summary_field_renders_as_a_chip_not_a_popover(monkeypatch):
    """The strip writes `Label = Value` for a computed field exactly as it does
    for a data column, and returns nothing for a popover to show."""
    import pandas as pd

    from scanpath_studio import tabs

    written: list[str] = []
    monkeypatch.setattr(
        tabs.st, "markdown", lambda body, **kw: written.append(str(body))
    )
    monkeypatch.setattr(
        tabs,
        "_summary_rows",
        lambda w, f: [
            {"Field": "Total reading time (s)", "Value": "12.3"},
            {"Field": "Number of fixations", "Value": "154"},
        ],
    )

    result = tabs._render_trial_condition_chips(
        pd.DataFrame(),
        pd.DataFrame(),
        "p1",
        ["@reading_time_s", "@fixation_count"],
    )

    assert result is None
    strip = " ".join(written)
    assert "Total reading time (s) = 12.3" in strip
    assert "Number of fixations = 154" in strip


def test_the_summary_stats_popover_is_gone():
    from scanpath_studio import tabs

    assert not hasattr(tabs, "_render_trial_details_popover")


def test_the_picker_says_where_the_colours_are():
    """The per-chip colour pickers sit *below* the two drag buckets, off-screen
    until you scroll — so the caption over the buckets points at them."""
    import inspect

    from scanpath_studio.controls import render_trial_chip_picker

    # Source-level: the caption is drawn into a `host` the picker is handed, and
    # the buckets themselves are a `sort_items` component AppTest cannot read.
    source = " ".join(inspect.getsource(render_trial_chip_picker).split())
    assert 'set below the list."' in source
