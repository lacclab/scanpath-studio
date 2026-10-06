"""UX-190 / UX-195: the chips above the plot, drawn as a table.

UX-190 replaced Compare mode's two chip strips: two strips of ``Field = Value``
chips put A's value and B's in different rows at different horizontal offsets,
so comparing them meant searching. The table gives each field one column — A's
value directly above B's — and writes a value the two readings share in both
rows, muted (it was once one cell spanning both rows, which read as B's cell
left blank). UX-195 drew the single trial's chips the same way, as a
one-row table.
"""

from __future__ import annotations

import re

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.tabs import ChipEntry, _chip_table_html

BLUE, RED = "#1f77b4", "#d62728"
# The drawn element — the stylesheet names the class too.
TABLE = '<table class="sps-chip-table"'


def _entry(col, value, *, label=None, trial_level=True, color=tabs._CHIP_NEUTRAL_BG):
    return ChipEntry(
        col=col,
        label=label or col.title(),
        value=value,
        trial_level=trial_level,
        color=color,
    )


def _table(a, b, order):
    return _chip_table_html(("A", BLUE, a), ("B", RED, b), order=order)


def _header(html):
    return re.findall(r"<th[^>]*scope=\"col\"[^>]*>(.*?)</th>", html)


def _rows(html):
    return re.findall(r"<tr>(.*?)</tr>", html.split("<tbody>", 1)[1])


class TestTheTable:
    def test_a_shared_value_is_written_muted_in_both_rows(self):
        html = _table(
            [_entry("text", "2_2_2_Adv")], [_entry("text", "2_2_2_Adv")], ["text"]
        )

        assert "rowspan" not in html
        a_row, b_row = _rows(html)
        for row in (a_row, b_row):
            assert "2_2_2_Adv" in row
            assert "sps-ct-same" in row

    def test_differing_values_get_a_cell_each(self):
        html = _table(
            [_entry("participant", "l37")],
            [_entry("participant", "l7")],
            ["participant"],
        )

        a_row, b_row = _rows(html)
        assert "l37" in a_row and "l7" not in a_row
        assert "l7" in b_row
        assert "rowspan" not in html

    def test_a_value_missing_on_one_side_reads_as_a_dash(self):
        html = _table([_entry("samples", "2,233")], [], ["samples"])

        _, b_row = _rows(html)
        assert "–" in b_row
        assert "sps-ct-missing" in b_row

    def test_a_field_missing_on_both_sides_has_no_column(self):
        html = _table([_entry("text", "t")], [_entry("text", "t")], ["text", "samples"])

        assert _header(html) == ["Text"]

    def test_columns_follow_the_order_given_not_which_values_differ(self):
        """Stepping trials must not reshuffle the columns under the user."""
        a = [_entry("text", "t"), _entry("time", "70.7")]
        b = [_entry("text", "t"), _entry("time", "22.8")]

        html = _table(a, b, ["text", "time"])

        assert _header(html) == ["Text", "Time"]

    def test_each_row_is_named_in_its_scanpaths_colour(self):
        html = _table([_entry("text", "t")], [_entry("text", "t")], ["text"])

        a_row, b_row = _rows(html)
        assert BLUE in a_row and ">A<" in a_row
        assert RED in b_row and ">B<" in b_row

    def test_a_chip_colour_tints_its_value_and_neutral_does_not(self):
        green = "#d4edda"
        html = _table(
            [_entry("correct", "True", color=green), _entry("text", "t")],
            [_entry("correct", "True", color=green), _entry("text", "t")],
            ["correct", "text"],
        )

        assert f"background:{green}" in html
        assert tabs._CHIP_NEUTRAL_BG not in html

    def test_each_side_keeps_its_own_tint_when_the_values_differ(self):
        green, red = "#d4edda", "#f8d7da"
        html = _table(
            [_entry("correct", "True", color=green)],
            [_entry("correct", "False", color=red)],
            ["correct"],
        )

        a_row, b_row = _rows(html)
        assert green in a_row and red in b_row

    def test_a_numeric_column_is_right_aligned(self):
        html = _table(
            [_entry("time", "70.7"), _entry("text", "t")],
            [_entry("time", "22.8"), _entry("text", "u")],
            ["time", "text"],
        )

        cells = re.findall(r"<t[hd][^>]*>", html)
        numeric = [c for c in cells if "sps-ct-num" in c]
        assert len(numeric) == 3  # the header and both values
        assert html.index("sps-ct-num") < html.index(">Text<")

    def test_a_thousands_separator_still_counts_as_a_number(self):
        html = _table([_entry("samples", "2,233")], [], ["samples"])

        assert "sps-ct-num" in html

    def test_a_value_that_varies_within_its_trial_keeps_the_warning(self):
        html = _table(
            [_entry("speed", "fast", trial_level=False)],
            [_entry("speed", "fast")],
            ["speed"],
        )

        assert "warning" in html

    def test_labels_and_values_are_escaped(self):
        html = _table(
            [_entry("x", "<b>bold</b>", label="A & B")],
            [_entry("x", "plain")],
            ["x"],
        )

        assert "<b>bold</b>" not in html
        assert "&lt;b&gt;bold&lt;/b&gt;" in html
        assert "A &amp; B" in html

    def test_it_is_one_line_so_markdown_cannot_read_it_as_code(self):
        html = _table([_entry("text", "t")], [_entry("text", "u")], ["text"])

        assert "\n" not in html


class TestTheEntries:
    """The chip strip and the table read their values through one function."""

    def test_entries_carry_what_the_strip_would_draw(self, monkeypatch):
        monkeypatch.setattr(
            tabs,
            "_summary_rows",
            lambda w, f, g=None, **_kw: [
                {"Field": "Number of fixations", "Value": "154"}
            ],
        )
        words = pd.DataFrame({"trial_id": ["t1"], "difficulty_level": ["Adv"]})

        entries = tabs._trial_chip_entries(
            words, pd.DataFrame(), "p1", ["@fixation_count", "difficulty_level"]
        )

        assert [(e.col, e.value) for e in entries] == [
            ("@fixation_count", "154"),
            ("difficulty_level", "Adv"),
        ]
        assert entries[1].color != tabs._CHIP_NEUTRAL_BG  # the Adv/Ele colour

    def test_a_sample_count_stands_in_for_the_samples(self):
        """Compare's B hands over a cached count, not its samples."""
        entries = tabs._trial_chip_entries(
            pd.DataFrame(),
            pd.DataFrame(),
            "p1",
            ["@gaze_sample_count"],
            gaze_samples=2233,
        )

        assert [e.value for e in entries] == ["2,233"]

    def test_an_empty_value_is_no_entry(self):
        words = pd.DataFrame({"trial_id": ["t1"], "gender": ["nan"]})

        assert tabs._trial_chip_entries(words, pd.DataFrame(), "p1", ["gender"]) == []


class TestOneReading:
    """UX-195: the single trial's chips are the same table with one row."""

    @staticmethod
    def _one(entries, order):
        return _chip_table_html((None, None, entries), order=order)

    def test_one_row_with_no_label_column(self):
        html = self._one(
            [_entry("text", "t"), _entry("time", "70.7")], ["text", "time"]
        )

        assert _header(html) == ["Text", "Time"]
        (row,) = _rows(html)
        assert "<th" not in row  # no A/B label to tell one row apart
        assert "sps-ct-corner" not in html

    def test_a_lone_value_is_not_muted_as_shared(self):
        html = self._one([_entry("text", "t")], ["text"])

        assert "sps-ct-same" not in html
        assert "rowspan" not in html

    def test_tints_numbers_and_the_warning_mark_carry_over(self):
        green = "#d4edda"
        html = self._one(
            [
                _entry("correct", "True", color=green),
                _entry("time", "70.7"),
                _entry("speed", "fast", trial_level=False),
            ],
            ["correct", "time", "speed"],
        )

        assert f"background:{green}" in html
        assert "sps-ct-num" in html
        assert "warning" in html


class TestBsSampleCount:
    @staticmethod
    def _count(frame, screen=None):
        from scanpath_studio.data import frame_fingerprint

        return tabs._c_gaze_sample_count(
            frame, frame_fingerprint(frame), "p2", "t2", screen
        )

    def test_counts_bs_own_samples(self):
        samples = pd.DataFrame(
            {"participant_id": ["p1", "p2", "p2"], "trial_id": ["t1", "t2", "t2"]}
        )

        assert self._count(samples) == 2

    def test_no_samples_for_b_is_no_count(self):
        samples = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})

        assert self._count(samples) is None

    def test_a_screen_needs_samples_that_name_their_screen(self):
        """As for A: samples with no screen id are hidden on a multipart trial,
        not counted across every screen."""
        samples = pd.DataFrame({"participant_id": ["p2"], "trial_id": ["t2"]})

        assert self._count(samples, screen="page_1") is None


@pytest.mark.timeout(180)
class TestTheAppDrawsTheTable:
    def test_compare_mode_shows_one_ab_table(self):
        from tests.conftest import APP_SCRIPT

        streamlit_testing = pytest.importorskip("streamlit.testing.v1")
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.session_state["single_compare_toggle"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception

        bodies = [m.value for m in at.markdown]
        tables = [b for b in bodies if TABLE in b]
        assert len(tables) == 1
        assert "Trial ID" in tables[0]
        assert ">A</th>" in tables[0] and ">B</th>" in tables[0]

    def test_a_single_trial_shows_a_one_row_table(self):
        from tests.conftest import APP_SCRIPT

        streamlit_testing = pytest.importorskip("streamlit.testing.v1")
        at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception

        tables = [m.value for m in at.markdown if TABLE in m.value]
        assert len(tables) == 1
        assert len(_rows(tables[0])) == 1
        assert "sps-ct-side" not in tables[0]
        assert 'class="sps-chip"' not in " ".join(m.value for m in at.markdown)
