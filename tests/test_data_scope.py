"""Data Management distinguishes filtered recordings from whole-dataset checks."""

from __future__ import annotations

import pytest

from scanpath_studio.constants import md_literal
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

    assert not _captions(at, "whole dataset")
    assert not _captions(at, "before the trial filters")

    # Set on the Scanpath view, where the filter panel publishes the result
    # `app.main` filters with on the following run.
    pin_view(at, "Scanpath")
    at.run(timeout=90)
    at.session_state["filter_participants"] = ["l7_183"]
    at.run(timeout=90)
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception

    scope = "Scanpath filters include 12 of 24 trials."
    assert _captions(at, scope)
    assert "12 of 12" in at.button(key="data_inspect_fixations").label
    at.button(key="data_inspect_fixations").click()
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    captions = _captions(at, scope)
    assert len(captions) == 1 and md_literal("Participant: l7_183") in captions[0]
    assert {
        "Fixations",
        "Words",
        "Raw gaze samples",
        "Participants",
        "Trials",
        "Texts",
    } <= {h.value for h in at.subheader}

    pin_data_view(at, section="Dataset library")
    at.run(timeout=90)
    assert _captions(at, "Whole datasets, before the trial filters")


@pytest.mark.timeout(180)
def test_empty_trial_filters_leave_the_dataset_open_for_inspection():
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    at.session_state["filter_favorites"] = True
    at.run(timeout=90)
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert _captions(at, "0 of 24 trials")
    assert {m.label: m.value for m in at.metric}["Trials"] == "0"
    at.segmented_control(key="data_inspection_panel").set_value("Data checks")
    pin_data_view(at)
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert any("Compare with planned trials" in e.label for e in at.expander)
    assert not at.button(key="data_edit_current").disabled


class TestDatasetTableScopeNote:
    def test_nothing_to_say_when_the_row_and_stats_agree(self):
        from scanpath_studio.app import dataset_table_scope_note

        assert dataset_table_scope_note(filtered=False, stand_in_for=None) is None

    def test_a_filter_alone(self):
        from scanpath_studio.app import dataset_table_scope_note

        note = dataset_table_scope_note(filtered=True, stand_in_for=None)
        assert note.startswith("Whole datasets, before the trial filters")

    def test_the_stand_in_is_named_with_or_without_a_filter(self):
        from scanpath_studio.app import dataset_table_scope_note

        bare = dataset_table_scope_note(filtered=False, stand_in_for="PoTeC")
        assert bare == (
            "Rows count whole datasets. PoTeC isn't loaded, so Overview "
            "counts the bundled demo shown in its place."
        )
        both = dataset_table_scope_note(filtered=True, stand_in_for="PoTeC")
        assert both.endswith("in its place, narrowed by the trial filters.")


@pytest.mark.timeout(180)
def test_the_table_says_when_stats_counts_the_demo_standing_in(monkeypatch):
    """A corpus that isn't on disk: its row keeps its published counts while
    Stats counts the bundled demo shown in its place — the note says so even
    with no filter on."""
    from scanpath_studio import datasets

    monkeypatch.setattr(datasets, "potec_present", lambda root: False)
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "PoTeC — Potsdam Textbook Corpus"
    pin_data_view(at, section="Dataset library")
    at.run(timeout=90)
    assert not at.exception, at.exception
    notes = _captions(at, "counts the bundled demo shown in its place.")
    assert len(notes) == 1, notes
    assert "isn't loaded" in notes[0]
