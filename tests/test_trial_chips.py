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
    # VIZ-45: the gaze-sample count is a default too — drawn only for a trial
    # that has samples, so a fixation trial without them still shows two.
    assert "@gaze_sample_count" in shown
    assert set(_CHIP_DEFAULT_SUMMARY) == {
        "@reading_time_s",
        "@trial_duration_s",
        "@fixation_count",
        "@gaze_sample_count",
    }


def test_trial_duration_is_onset_to_offset_and_named_apart_from_fixation_time():
    """#374 F8: two different numbers never share the name "reading time"."""
    import pandas as pd

    from scanpath_studio import tabs
    from scanpath_studio.controls import SUMMARY_CHIP_FIELDS

    fixations = pd.DataFrame(
        {"timestamp_ms": [1000.0, 1300.0, 2000.0], "duration_ms": [200.0, 250.0, 300.0]}
    )
    rows = {
        r["Field"]: r["Value"] for r in tabs._summary_rows(pd.DataFrame(), fixations)
    }
    assert rows[SUMMARY_CHIP_FIELDS["@reading_time_s"]] == "0.8"  # 750 ms summed
    assert rows[SUMMARY_CHIP_FIELDS["@trial_duration_s"]] == "1.3"  # 1000 → 2300
    assert SUMMARY_CHIP_FIELDS["@reading_time_s"] == "Total fixation time (s)"
    assert not any("reading time" in v.lower() for v in SUMMARY_CHIP_FIELDS.values())
    # No timestamps, no duration chip.
    no_clock = tabs._summary_rows(pd.DataFrame(), fixations[["duration_ms"]])
    assert "Trial duration (s)" not in {r["Field"] for r in no_clock}


def test_every_summary_field_is_still_pickable():
    """Dropping two from the default must not drop them from the picker."""
    import pandas as pd

    from scanpath_studio.controls import SUMMARY_CHIP_FIELDS, _chip_field_options

    options = _chip_field_options(pd.DataFrame(), pd.DataFrame(), set())
    for key in SUMMARY_CHIP_FIELDS:
        assert key in options, key


def test_a_summary_field_renders_as_a_column_not_a_popover(monkeypatch):
    """The chip table gives a computed field a column exactly as it does a data
    column, and returns nothing for a popover to show."""
    import pandas as pd

    from scanpath_studio import tabs

    written: list[str] = []
    monkeypatch.setattr(
        tabs.st, "markdown", lambda body, **kw: written.append(str(body))
    )
    monkeypatch.setattr(
        tabs,
        "_summary_rows",
        lambda w, f, g=None, **_kw: [
            {"Field": "Total fixation time (s)", "Value": "12.3"},
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
    table = " ".join(written)
    assert ">Total fixation time (s)</th>" in table and ">12.3</td>" in table
    assert ">Number of fixations</th>" in table and ">154</td>" in table


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


def test_a_full_screen_figure_says_how_to_zoom_to_the_text():
    """#374 F39: the empty band under the text is the screen, and says so."""
    from scanpath_studio import tabs

    note = tabs._full_screen_note({"fit_to_monitor": True}, 2560, 1440)
    assert note.startswith("Full 2560×1440 screen") and "Crop to data" in note
    assert tabs._full_screen_note({"fit_to_monitor": False}, 2560, 1440) == ""
    assert tabs._full_screen_note({}, None, None) == ""


def test_the_chip_editor_offers_each_role_once():
    """#374 F5: no second "Trial (unique_trial_id)" beside "Trial"."""
    import pandas as pd

    from scanpath_studio import controls

    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "unique_trial_id": ["t1"],
            "text_id": ["a"],
            "unique_text_id": ["a"],
            "cond": ["x"],
        }
    )
    level = set(fixations.columns)
    options = controls._chip_field_options(fixations, fixations, level)
    assert options.count("trial_id") + options.count("unique_trial_id") == 1
    assert options.count("text_id") + options.count("unique_text_id") == 1
    assert "cond" in options


def test_hiding_the_chips_keeps_their_fields():
    """#373: the ✏️ menu's switch hides the chip table and keeps the field
    selection, so showing it again brings back the same row."""
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "streamlit_app.py"
    at = AppTest.from_file(str(app), default_timeout=60)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run()
    assert not at.exception, at.exception

    def table_drawn() -> bool:
        return any('class="sps-chip-table-wrap"' in m.value for m in at.markdown)

    assert table_drawn()
    fields = list(at.session_state["trial_chip_fields"])
    at.toggle(key="single_show_chips").set_value(False).run()
    assert not table_drawn()
    assert list(at.session_state["trial_chip_fields"]) == fields
    at.toggle(key="single_show_chips").set_value(True).run()
    assert table_drawn()
