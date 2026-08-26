"""Planning an uploaded table's read (PERF-6, decision 2a).

The wizard is the one path where the columns a plan would drop are still
*offerable*: each table's own "Extra fields to keep" picker (UX-114) lists
exactly the columns nothing claims, and its mapping dropdowns list every
column in the file. So the plan has to fold in what the user has already
named, and the picker has to keep reading the file's header rather than the
narrowed frame.
"""

from __future__ import annotations

import pandas as pd

from scanpath_studio import app
from scanpath_studio.app import _columns_chosen_in_state, upload_read_plan

HEADER = [
    "RECORDING_SESSION_LABEL",
    "paragraph_id",
    "IA_ID",
    "IA_LABEL",
    "IA_LEFT",
    "IA_RIGHT",
    "IA_TOP",
    "IA_BOTTOM",
    "IA_DWELL_TIME",
    "IA_AREA",
    "NEXT_SAC_ANGLE",
]


class TestColumnsChosenInState:
    """What the user has already named, gathered from the wizard's own keys."""

    def test_finds_a_mapping_override(self):
        state = {"col_map_words_trial": "IA_AREA"}
        assert _columns_chosen_in_state(state, HEADER) == {"IA_AREA"}

    def test_finds_a_composite_mapping(self):
        state = {"col_map_words_trial": ["IA_AREA", "NEXT_SAC_ANGLE"]}
        assert _columns_chosen_in_state(state, HEADER) == {"IA_AREA", "NEXT_SAC_ANGLE"}

    def test_finds_extra_fields_to_keep(self):
        state = {"wizard_keep_extra": ["NEXT_SAC_ANGLE"]}
        assert _columns_chosen_in_state(state, HEADER) == {"NEXT_SAC_ANGLE"}

    def test_finds_the_per_table_keep_picker(self):
        """UX-114: one picker per table (`wizard_keep_<prefix>`) replaced the
        old single cross-table `wizard_keep_extra` — the sweep matches the
        prefix, not the exact old name, so either shape is found."""
        state = {"wizard_keep_col_map_words": ["NEXT_SAC_ANGLE"]}
        assert _columns_chosen_in_state(state, HEADER) == {"NEXT_SAC_ANGLE"}

    def test_ignores_names_that_are_not_columns_of_this_table(self):
        """The two upload boxes share one state; a fixation column is not a word
        column, and a stale pick from a previous dataset is not one either."""
        state = {
            "col_map_fix_x": "CURRENT_FIX_X",
            "wizard_keep_extra": ["gone_in_this_file"],
        }
        assert _columns_chosen_in_state(state, HEADER) == set()

    def test_ignores_unrelated_state(self):
        state = {"global_show_words": True, "wizard_dataset_name": "IA_AREA"}
        assert _columns_chosen_in_state(state, HEADER) == set()


class TestUploadReadPlan:
    """The plan itself: mapped + registry, plus whatever the user named."""

    def test_narrows_to_the_columns_normalization_keeps(self):
        plan = upload_read_plan(HEADER, "words")
        assert "IA_LABEL" in plan.columns  # mapped
        assert "IA_DWELL_TIME" in plan.columns  # registry
        assert "IA_AREA" not in plan.columns  # nothing claims it

    def test_keeps_a_column_the_user_chose_to_keep(self):
        plan = upload_read_plan(HEADER, "words", chosen={"IA_AREA"})
        assert "IA_AREA" in plan.columns

    def test_preserves_the_files_column_order(self):
        plan = upload_read_plan(HEADER, "words", chosen={"IA_AREA"})
        assert list(plan.columns) == [c for c in HEADER if c in set(plan.columns)]


class TestUploadedTableRead:
    """The seam the wizard reads through, end to end.

    The wizard's own flow tests monkeypatch ``app._read_uploaded_frame``, so
    they run *past* the planning that happens inside it — these exercise it.
    """

    def _upload(self, tmp_path, name="ia.tsv"):
        """A file-like object shaped like Streamlit's ``UploadedFile``."""
        import io

        frame = pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["l1_001", "l1_001"],
                "paragraph_id": ["p1", "p1"],
                "IA_ID": [1, 2],
                "IA_LABEL": ["Hello", "world"],
                "IA_LEFT": [10, 60],
                "IA_RIGHT": [50, 110],
                "IA_TOP": [100, 100],
                "IA_BOTTOM": [130, 130],
                "IA_DWELL_TIME": [220, 180],
                "IA_AREA": [1200, 1500],
            }
        )
        buf = io.BytesIO(frame.to_csv(sep="\t", index=False).encode())
        buf.name = name
        return buf

    def test_parses_only_the_planned_columns(self, tmp_path):
        frame = app._read_uploaded_table_cached(
            self._upload(tmp_path), ("id1", "ia.tsv", 1), kind="words"
        )
        assert "IA_DWELL_TIME" in frame.columns
        assert "IA_AREA" not in frame.columns

    def test_a_column_the_user_keeps_comes_back_on_the_next_read(self, tmp_path):
        """Ticking a column in 'Additional fields to keep' has to actually widen
        the frame — `chosen` is in the cache key, so the file is read again."""
        frame = app._read_uploaded_table_cached(
            self._upload(tmp_path),
            ("id1", "ia.tsv", 1),
            kind="words",
            chosen=("IA_AREA",),
        )
        assert "IA_AREA" in frame.columns

    def test_without_a_kind_it_reads_the_whole_table(self, tmp_path):
        frame = app._read_uploaded_table_cached(
            self._upload(tmp_path), ("id2", "ia.tsv", 1)
        )
        assert "IA_AREA" in frame.columns

    def test_a_column_only_a_later_file_has_is_still_kept(self, tmp_path):
        """One file per participant is the common upload shape, and an export
        can gain a column between them — resolving the user's picks against
        only the first file's header would silently drop it from all of them."""
        import io

        first = self._upload(tmp_path, "a.tsv")
        later = pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["l1_002"],
                "paragraph_id": ["p1"],
                "IA_ID": [1],
                "IA_LABEL": ["Later"],
                "IA_LEFT": [10],
                "IA_RIGHT": [50],
                "IA_TOP": [100],
                "IA_BOTTOM": [130],
                "ADDED_LATER": ["kept"],
            }
        )
        buf = io.BytesIO(later.to_csv(sep="\t", index=False).encode())
        buf.name = "b.tsv"
        header = app._upload_header([first, buf], multi=True)
        assert "ADDED_LATER" in header

    def test_a_multi_file_upload_plans_each_file(self, tmp_path):
        uploads = [self._upload(tmp_path, "a.tsv"), self._upload(tmp_path, "b.tsv")]
        frame = app._read_uploaded_tables_cached(
            uploads, (("a", "a.tsv", 1), ("b", "b.tsv", 1)), kind="words"
        )
        assert len(frame) == 4
        assert "IA_AREA" not in frame.columns
