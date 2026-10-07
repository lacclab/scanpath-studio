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
        # Only what the files hold: the map's fixation_id is not in this table.
        assert "fixation_id" not in rows
        # The alias left out of the file is left out of the manifest too.
        assert "unique_trial_id" not in rows
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


# --- The parity review's cases ---------------------------------------------


def test_columns_json_matches_the_files_on_a_demo_shaped_map(frames):
    """The demo's file calls its trial id `unique_trial_id`: the alias is left
    out and `trial_id` is written under that name — and the manifest says so."""
    names = ColumnNames(
        {
            "trial_id": SourceName(("unique_trial_id",)),
            "unique_trial_id": SourceName(("unique_trial_id",)),
            "duration_ms": SourceName(("CURRENT_FIX_DURATION",)),
        }
    )
    with _export(frames, column_names={"fixations": names}) as zf:
        fix = pd.read_csv(zf.open("per_trial/p1__t1/fixations.csv"))
        manifest = json.loads(zf.read("columns.json"))
    rows = {row["canonical"]: row["column"] for row in manifest["tables"]["fixations"]}
    assert rows == {
        "trial_id": "unique_trial_id",
        "duration_ms": "CURRENT_FIX_DURATION",
    }
    assert set(rows.values()) <= set(fix.columns)
    assert list(fix.columns).count("unique_trial_id") == 1


def test_a_derived_table_names_only_its_ids():
    """A summary's `n_fixations` is its own count, not the file's column of the
    same canonical name."""
    names = ColumnNames(
        {
            "participant_id": SourceName(("RECORDING_SESSION_LABEL",)),
            "n_fixations": SourceName(("IA_FIXATION_COUNT",)),
            "x": SourceName(("CURRENT_FIX_X",)),
        }
    )
    summary = pd.DataFrame({"participant_id": ["p1"], "n_fixations": [12], "x": [3]})
    out = cn.as_written(summary, names.identity())
    assert list(out.columns) == ["RECORDING_SESSION_LABEL", "n_fixations", "x"]


def test_a_dataset_with_no_map_exports_as_before(frames):
    """An app dataset with no names (synthetic, authored) passes empty maps."""
    with _export(frames, column_names={"fixations": cn.EMPTY, "words": cn.EMPTY}) as zf:
        assert "columns.json" not in zf.namelist()
        readme = zf.read("README.md").decode("utf-8")
    assert "Column names (Scanpath Studio's standard names)" in readme


def test_an_alias_whose_values_differ_is_kept():
    """A `unique_text_id` that parted from its `text_id` is data, not a copy."""
    names = ColumnNames(
        {
            "text_id": SourceName(("PARAGRAPH",)),
            "unique_text_id": SourceName(("PARAGRAPH",)),
        }
    )
    frame = pd.DataFrame({"text_id": ["P1"], "unique_text_id": ["U-A"]})
    assert names.redundant_aliases(frame) == set()
    assert "unique_text_id" in cn.as_written(frame, names)


def test_a_kept_unique_text_id_is_the_users_own_column():
    raw = pd.DataFrame(columns=["T", "PARAGRAPH", "unique_text_id", "D", "X", "Y"])
    schema = {"trial": "T", "text_id": "PARAGRAPH", "duration": "D", "x": "X", "y": "Y"}
    names = cn.from_schema("fixations", schema, raw.columns)
    assert names.source("unique_text_id") is None
    assert names.source("text_id") == SourceName(("PARAGRAPH",))


def test_a_pattern_alias_never_names_the_apps_own_count(frames):
    _, words, fixations = frames
    names = ColumnNames({"n_fixations": SourceName(("IA_FIXATION_COUNT",))})
    fields = pattern_fields("p1", "t1", words, fixations, {}, column_names=names)
    assert "IA_FIXATION_COUNT" not in fields


class TestRewrites:
    """A header the file used never sits over values the load changed."""

    def test_a_rewritten_column_is_marked_converted(self):
        names = ColumnNames({"word_id": SourceName(("IA_ID",))})
        rewritten = names.with_rewrites("fixations", [("fixations", "word_id", " − 1")])
        assert rewritten.kind_of("word_id") == cn.CONVERTED
        assert rewritten.label("word_id") == "IA_ID − 1"
        # …so it is exported under its internal name.
        assert rewritten.export_headers(["word_id"]) == {}
        # Another table's rewrite leaves this one alone.
        assert names.with_rewrites("words", [("fixations", "word_id", " − 1")]) == names

    def test_harmonizing_reports_a_shifted_word_id(self):
        from scanpath_studio import data

        words = pd.DataFrame(
            {
                "participant_id": ["p"] * 3,
                "trial_id": ["t"] * 3,
                "text_id": ["t"] * 3,
                "word_id": [0, 1, 2],
                "text": ["a", "b", "c"],
                "x": [0.0, 10.0, 20.0],
                "y": [0.0, 0.0, 0.0],
                "width": [10.0] * 3,
                "height": [10.0] * 3,
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p"] * 3,
                "trial_id": ["t"] * 3,
                "text_id": ["t"] * 3,
                "word_id": [1, 2, 3],
                "x": [5.0, None, 25.0],
                "y": [5.0, None, 5.0],
                "duration_ms": [100] * 3,
            }
        )
        *_frames, rewrites = data.harmonize_frames_reporting(words, fixations)
        assert ("fixations", "word_id", " − 1") in rewrites
        assert {("fixations", axis) for axis in ("x", "y")} <= {
            (table, column) for table, column, _how in rewrites
        }

    def test_the_demo_names_its_shifted_word_id_honestly(self):
        """BUG-8 shifts the demo's fixation word ids on every load."""
        from scanpath_studio.compare_source import _builtin_column_names
        from scanpath_studio.constants import DEMO_CHOICE

        payload = _builtin_column_names(DEMO_CHOICE)["fixations"]
        names = ColumnNames.from_payload(payload)
        assert names.kind_of("word_id") == cn.CONVERTED
        assert names.label("word_id").endswith(" − 1")
