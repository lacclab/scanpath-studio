"""UX-174: what a row of 📂 Available datasets says, and how the list orders.

The row model (`scanpath_studio.dataset_table`) is pure, so every rule the
issue set — grouped numbers, a reason in place of every missing count, zero only
when it was measured, numeric sorting with the gaps last, a list that does not
move when the open dataset changes — is checked here without booting the app.
The AppTest side (clicks landing on the right row) is in `test_apptest.py`.
"""

from __future__ import annotations

import pytest

from scanpath_studio import dataset_table as dt
from scanpath_studio.dataset_table import DatasetRow


def _row(name: str, order: int, **kwargs) -> DatasetRow:
    return DatasetRow(token=name, name=name, order=order, **kwargs)


class TestCells:
    def test_counts_are_grouped(self):
        row = _row("OneStop", 0, source="published", counts={"Fixations": 2400788})
        assert row.cell("Fixations") == "2,400,788"

    def test_a_measured_zero_is_shown_as_zero(self):
        row = _row("Empty", 0, source="loaded", counts={"Participants": 0})
        assert row.value("Participants") == 0
        assert row.cell("Participants") == "0"
        assert row.gap("Participants") == ""

    def test_never_opened_and_publishing_nothing_is_not_loaded(self):
        row = _row("MultiplEYE", 0)
        assert {row.cell(f) for f in dt.DATASET_COUNT_FIELDS} == {dt.NOT_LOADED}

    def test_a_figure_the_corpus_does_not_publish_is_not_reported(self):
        row = _row("PoTeC", 0, source="published", counts={"Participants": 75})
        assert row.cell("Participants") == "75"
        assert row.cell("Screens") == dt.NOT_REPORTED

    def test_an_absent_table_is_not_applicable_once_loaded(self):
        row = _row("Demo", 0, source="loaded", counts={"Participants": 3})
        for field in ("Screens", "Words", "Fixations", "Gaze points"):
            assert row.cell(field) == dt.NOT_APPLICABLE
        # The explanation names the reason for *that* field.
        assert "raw-gaze" in row.gap_explanation("Gaze points")
        assert "single screen" in row.gap_explanation("Screens")

    def test_a_count_the_load_could_not_determine_is_unknown(self):
        row = _row("Odd", 0, source="loaded", counts={"Trials": 5})
        assert row.cell("Participants") == dt.UNKNOWN

    def test_counted_but_empty_is_unknown_not_not_loaded(self):
        row = _row("Odd", 0, measured=True)
        assert row.cell("Texts") == dt.UNKNOWN

    @pytest.mark.parametrize("field", dt.DATASET_COUNT_FIELDS)
    def test_no_cell_is_ever_python_none_or_nan(self, field):
        for row in (
            _row("a", 0),
            _row("b", 0, source="loaded", counts=dict.fromkeys([field])),
            _row("c", 0, source="published", counts={}),
        ):
            assert row.cell(field) not in {"", "None", "nan", "NaN", "0"}

    def test_every_gap_label_is_explained(self):
        for label in (dt.NOT_LOADED, dt.NOT_REPORTED, dt.NOT_APPLICABLE, dt.UNKNOWN):
            assert dt.GAP_EXPLANATIONS[label]


class TestStatus:
    """BUG-113: Status says whether a dataset can be opened, never where its
    numbers came from."""

    @pytest.mark.parametrize("source", ["loaded", "published", ""])
    def test_a_row_with_nothing_missing_is_available_whatever_its_counts(self, source):
        assert _row("x", 0, source=source).status_label == dt.AVAILABLE

    def test_a_row_this_session_read_is_loaded(self):
        assert _row("x", 0, loaded=True).status_label == dt.LOADED

    def test_missing_files_win_over_loaded(self):
        row = _row("x", 0, loaded=True, status=dt.NEEDS_SETUP)
        assert row.status_label == dt.NEEDS_SETUP

    def test_a_missing_state_takes_its_place(self):
        row = _row("PoTeC", 0, source="loaded", status=dt.NEEDS_DOWNLOAD)
        assert row.status_label == dt.NEEDS_DOWNLOAD

    def test_opening_a_row_does_not_change_what_it_says(self):
        from dataclasses import replace

        row = _row("OneStop", 0, source="loaded", status=dt.NEEDS_DOWNLOAD)
        assert replace(row, active=True).status_label == row.status_label

    def test_every_status_is_explained(self):
        for label in (dt.LOADED, dt.AVAILABLE, dt.NEEDS_DOWNLOAD, dt.NEEDS_SETUP):
            assert dt.STATUS_EXPLANATIONS[label]
        assert dt.COUNTS_EXPLANATION


class TestSorting:
    @pytest.fixture
    def rows(self):
        return [
            _row("Demo", 0, kind="Demo", source="loaded", counts={"Trials": 36}),
            _row("Sample", 1, kind="Manual"),
            _row("PoTeC", 2, kind="Public", source="published", counts={"Trials": 900}),
            _row(
                "OneStop",
                3,
                kind="Public",
                source="published",
                counts={"Trials": 24046},
            ),
            _row("mine", 4, kind="Private", source="loaded", counts={"Trials": 9}),
        ]

    def test_unsorted_is_the_offered_order(self, rows):
        assert [r.name for r in dt.sort_rows(reversed(rows), None)] == [
            "Demo",
            "Sample",
            "PoTeC",
            "OneStop",
            "mine",
        ]

    def test_counts_sort_numerically_not_lexically(self, rows):
        # Lexically "9" > "900" > "36" > "24046"; numerically it is the reverse.
        ordered = dt.sort_rows(rows, "Trials", descending=True)
        assert [r.name for r in ordered] == [
            "OneStop",
            "PoTeC",
            "Demo",
            "mine",
            "Sample",
        ]

    def test_missing_values_sort_last_in_both_directions(self, rows):
        assert dt.sort_rows(rows, "Trials")[-1].name == "Sample"
        assert dt.sort_rows(rows, "Trials", descending=True)[-1].name == "Sample"

    def test_names_sort_case_insensitively(self, rows):
        assert [r.name for r in dt.sort_rows(rows, "Dataset")] == [
            "Demo",
            "mine",
            "OneStop",
            "PoTeC",
            "Sample",
        ]

    def test_kind_sorts_by_what_a_row_is(self, rows):
        kinds = [r.kind for r in dt.sort_rows(rows, "Kind")]
        assert kinds == ["Demo", "Manual", "Private", "Public", "Public"]

    def test_the_open_dataset_does_not_move_the_list(self, rows):
        from dataclasses import replace

        before = [r.name for r in dt.sort_rows(rows, None)]
        opened = [replace(r, active=r.name == "OneStop") for r in rows]
        assert [r.name for r in dt.sort_rows(opened, None)] == before

    def test_status_sorts_as_text(self, rows):
        ordered = [r.status_label for r in dt.sort_rows(rows, "Status")]
        assert ordered == sorted(ordered, key=str.casefold)

    def test_a_header_click_cycles_through_both_directions_then_off(self):
        state = dt.next_sort(None, "Trials")
        assert state == ("Trials", True)  # a count starts largest first
        state = dt.next_sort(state, "Trials")
        assert state == ("Trials", False)
        assert dt.next_sort(state, "Trials") is None
        # A text column starts A → Z, and another column starts over.
        assert dt.next_sort(("Trials", True), "Dataset") == ("Dataset", False)


class TestFiltering:
    @pytest.fixture
    def rows(self):
        return [
            _row("PoTeC", 0, kind="Public", language="German"),
            _row("OneStop", 1, kind="Public", language="English (L1)"),
            _row("My study", 2, kind="Private", language=""),
        ]

    def test_nothing_picked_keeps_everything(self, rows):
        assert dt.filter_rows(rows) == rows

    def test_search_is_a_case_insensitive_substring(self, rows):
        assert [r.name for r in dt.filter_rows(rows, query="stud")] == ["My study"]

    def test_kind_and_language_narrow_together(self, rows):
        picked = dt.filter_rows(rows, kinds=["Public"], languages=["German"])
        assert [r.name for r in picked] == ["PoTeC"]


def test_the_record_keeps_values_and_cells_apart():
    record = dt.row_record(
        _row("PoTeC", 0, source="published", counts={"Participants": 75})
    )
    assert record["Participants"] == 75
    assert record["Screens"] is None
    assert record["_cells"]["Participants"] == "75"
    assert record["_cells"]["Screens"] == dt.NOT_REPORTED
    assert record["Counts"] == "Published"
    assert record["Status"] == dt.AVAILABLE
