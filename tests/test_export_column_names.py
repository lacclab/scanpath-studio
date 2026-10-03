"""DATA-66 phase 3: exported tables name their columns as the dataset does."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from scanpath_studio import column_names as cn
from scanpath_studio.column_names import ColumnNames, SourceName
from scanpath_studio.export import (
    ComparisonSide,
    ExportOptions,
    bulk_export,
    pair_export,
    pattern_fields,
    render_pattern,
)

FIXATION_NAMES = ColumnNames(
    {
        "participant_id": SourceName(("RECORDING_SESSION_LABEL",)),
        "trial_id": SourceName(("TRIAL",)),
        "unique_trial_id": SourceName(("TRIAL",)),
        "x": SourceName(("CURRENT_FIX_X",)),
        "y": SourceName(("CURRENT_FIX_Y",)),
        "duration_ms": SourceName(("CURRENT_FIX_DURATION",)),
        "fixation_id": SourceName((), cn.GENERATED, "1, 2, … per trial"),
    }
)
WORD_NAMES = ColumnNames(
    {
        "participant_id": SourceName(("RECORDING_SESSION_LABEL",)),
        "trial_id": SourceName(("TRIAL",)),
        "x": SourceName(("IA_LEFT",)),
        "width": SourceName(
            ("IA_RIGHT", "IA_LEFT"), cn.CONVERTED, "IA_RIGHT − IA_LEFT"
        ),
        "total_fixation_duration_ms": SourceName(("IA_DWELL_TIME",)),
    }
)
MAPS = {"fixations": FIXATION_NAMES, "words": WORD_NAMES}


@pytest.fixture
def frames():
    combos = pd.DataFrame(
        {"participant_id": ["p1"], "trial_id": ["t1"], "text_id": ["a"]}
    )
    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "text_id": ["a", "a"],
            "word_id": [1, 2],
            "text": ["the", "cat"],
            "line_idx": [1, 1],
            "x": [100, 200],
            "y": [50, 50],
            "width": [80, 80],
            "height": [40, 40],
            "total_fixation_duration_ms": [200, 250],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "unique_trial_id": ["t1", "t1"],
            "text_id": ["a", "a"],
            "x": [140, 240],
            "y": [70, 70],
            "duration_ms": [200, 250],
            "timestamp_ms": [0, 200],
            "order_in_trial": [1, 2],
        }
    )
    return combos, words, fixations


def _export(frames, **kwargs):
    combos, words, fixations = frames
    zip_bytes, _ = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=800,
        canvas_height=400,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        settings={},
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_fixations=True,
            include_measures=True,
            table_format="csv",
        ),
        **kwargs,
    )
    return zipfile.ZipFile(io.BytesIO(zip_bytes))


class TestAsWritten:
    def test_a_mapped_column_takes_its_files_name(self, frames):
        _, _, fixations = frames
        out = cn.as_written(fixations, FIXATION_NAMES)
        assert {"RECORDING_SESSION_LABEL", "TRIAL", "CURRENT_FIX_X"} <= set(out)
        assert "participant_id" not in out
        # The app's own column keeps its name.
        assert "order_in_trial" in out

    def test_an_alias_of_the_same_column_is_written_once(self, frames):
        _, _, fixations = frames
        out = cn.as_written(fixations, FIXATION_NAMES)
        assert list(out.columns).count("TRIAL") == 1
        assert "unique_trial_id" not in out

    def test_a_converted_column_keeps_its_internal_name(self, frames):
        _, words, _ = frames
        out = cn.as_written(words, WORD_NAMES)
        assert "width" in out and "IA_LEFT" in out
        assert "IA_DWELL_TIME" in out

    def test_a_header_that_would_repeat_a_column_is_not_used(self):
        frame = pd.DataFrame({"x": [1], "CURRENT_FIX_X": [2]})
        assert list(cn.as_written(frame, FIXATION_NAMES).columns) == [
            "x",
            "CURRENT_FIX_X",
        ]

    def test_without_names_the_frame_is_unchanged(self, frames):
        _, _, fixations = frames
        assert cn.as_written(fixations, cn.EMPTY) is fixations


class TestBulkExport:
    def test_the_tables_are_written_under_the_datasets_names(self, frames):
        with _export(frames, column_names=MAPS) as zf:
            fix = pd.read_csv(zf.open("per_trial/p1__t1/fixations.csv"))
            words = pd.read_csv(zf.open("per_trial/p1__t1/measures.csv"))
        assert "CURRENT_FIX_DURATION" in fix and "duration_ms" not in fix
        # Each table by its own file's names: a word box's x is IA_LEFT.
        assert "IA_LEFT" in words and "CURRENT_FIX_X" not in words
        assert "IA_DWELL_TIME" in words

    def test_columns_json_maps_every_column_back(self, frames):
        with _export(frames, column_names=MAPS) as zf:
            manifest = json.loads(zf.read("columns.json"))
        assert manifest["schema"] == cn.COLUMNS_FILE_SCHEMA
        rows = {row["canonical"]: row for row in manifest["tables"]["fixations"]}
        assert rows["duration_ms"]["column"] == "CURRENT_FIX_DURATION"
        assert rows["fixation_id"]["kind"] == cn.GENERATED
        words = {row["canonical"]: row for row in manifest["tables"]["words"]}
        assert words["width"]["column"] == "width"
        assert words["width"]["sources"] == ["IA_RIGHT", "IA_LEFT"]

    def test_the_readme_dictionary_says_where_each_column_came_from(self, frames):
        with _export(frames, column_names=MAPS) as zf:
            readme = zf.read("README.md").decode("utf-8")
        assert "`CURRENT_FIX_DURATION` (internally `duration_ms`)" in readme
        assert "converted from your `IA_RIGHT`, `IA_LEFT`" in readme
        assert "- IA_DWELL_TIME" in readme

    def test_without_names_the_bundle_keeps_the_internal_names(self, frames):
        with _export(frames) as zf:
            fix = pd.read_csv(zf.open("per_trial/p1__t1/fixations.csv"))
            assert "columns.json" not in zf.namelist()
        assert "duration_ms" in fix


class TestPatterns:
    def test_a_pattern_can_use_the_datasets_name(self, frames):
        _, words, fixations = frames
        fields = pattern_fields(
            "p1",
            "t1",
            words,
            fixations,
            {},
            column_names=cn.across_tables(MAPS),
        )
        assert render_pattern("{RECORDING_SESSION_LABEL}-{TRIAL}", fields) == "p1-t1"
        assert render_pattern("{participant_id}", fields) == "p1"


class TestPairExport:
    def _pair(self, frames, dataset_b):
        _, words, fixations = frames
        side_a = ComparisonSide("p1", "t1", words, fixations)
        side_b = ComparisonSide("p1", "t1", words, fixations, dataset=dataset_b)
        data = pair_export(
            None,
            side_a,
            side_b,
            canvas_width=800,
            canvas_height=400,
            x_field="x",
            y_field="y",
            settings={},
            options=ExportOptions(
                include_png=False,
                include_svg=False,
                include_fixations=True,
                table_format="csv",
            ),
            column_names=MAPS,
        )
        zf = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in zf.namelist() if n.endswith("fixations.csv"))
        return zf, pd.read_csv(zf.open(name))

    def test_a_same_dataset_pair_uses_the_datasets_names(self, frames):
        _, fix = self._pair(frames, None)
        assert "CURRENT_FIX_DURATION" in fix

    def test_a_pair_across_datasets_keeps_the_shared_internal_names(self, frames):
        zf, fix = self._pair(frames, "Other corpus")
        assert "duration_ms" in fix
        assert not any(n.endswith("columns.json") for n in zf.namelist())
