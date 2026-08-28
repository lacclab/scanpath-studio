"""ENG-37: `multipart.py`'s rejection rules.

`tests/test_multipart.py` covers the happy paths and the app-level navigators.
What was untested is the half of the module that exists to say **no** — the
identity, conflict and manifest checks. Each of those is a rule whose failure
mode is silence rather than an error: a screen quietly dropped, a canvas quietly
taken from the first row, a manifest quietly leaving rows behind. A rule that
regresses into acceptance breaks nothing loudly, which is exactly why it needs a
test that pins the rejection itself.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.multipart import (
    apply_trial_parts_manifest,
    extract_part,
    normalize_screen_identity,
    part_catalog,
    screen_canvas_size,
    validate_matching_parts,
)


def _frame(**overrides):
    base = {
        "participant_id": ["p1", "p1", "p1", "p1"],
        "trial_id": ["t1", "t1", "t1", "t1"],
        "screen_id": ["a", "a", "b", "b"],
    }
    base.update(overrides)
    return pd.DataFrame(base)


class TestScreenIdentity:
    def test_a_frame_with_neither_column_is_left_alone(self):
        """Legacy single-screen data must pass through untouched."""
        frame = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
        assert normalize_screen_identity(frame) is frame

    def test_missing_parent_columns_are_named(self):
        frame = pd.DataFrame({"screen_id": ["a"]})
        with pytest.raises(ValueError, match="canonical parent columns"):
            normalize_screen_identity(frame)

    def test_index_alone_becomes_the_id(self):
        out = normalize_screen_identity(
            pd.DataFrame(
                {
                    "participant_id": ["p1", "p1"],
                    "trial_id": ["t1", "t1"],
                    "screen_index": [1, 2],
                }
            )
        )
        assert list(out["screen_id"]) == ["1", "2"]

    def test_a_non_numeric_index_alone_is_refused(self):
        with pytest.raises(ValueError, match="non-numeric"):
            normalize_screen_identity(
                pd.DataFrame(
                    {
                        "participant_id": ["p1"],
                        "trial_id": ["t1"],
                        "screen_index": ["intro"],
                    }
                )
            )

    def test_order_is_derived_from_first_appearance(self):
        out = normalize_screen_identity(_frame())
        assert list(out["screen_index"]) == [1, 1, 2, 2]

    @pytest.mark.parametrize(
        "index, message",
        [
            ([1, 1, 0, 0], "positive integers"),
            ([1, 1, 1.5, 1.5], "whole numbers"),
        ],
    )
    def test_a_bad_explicit_index_is_refused(self, index, message):
        with pytest.raises(ValueError, match=message):
            normalize_screen_identity(_frame(screen_index=index))

    def test_one_id_may_not_carry_two_indexes(self):
        with pytest.raises(ValueError, match="more than one screen_index"):
            normalize_screen_identity(_frame(screen_index=[1, 2, 3, 3]))

    def test_one_index_may_not_carry_two_ids(self):
        with pytest.raises(ValueError, match="more than one screen_id"):
            normalize_screen_identity(
                _frame(screen_id=["a", "a", "b", "b"], screen_index=[1, 1, 1, 1])
            )

    def test_a_non_positive_canvas_is_refused(self):
        with pytest.raises(ValueError, match="must be positive"):
            normalize_screen_identity(_frame(canvas_width=[0, 0, 100, 100]))

    def test_a_canvas_that_changes_inside_one_screen_is_refused(self):
        """Never resolved by taking the first row — a screen has one canvas."""
        with pytest.raises(ValueError, match="conflicts within one screen"):
            normalize_screen_identity(_frame(canvas_height=[10, 20, 30, 30]))


class TestTheCatalogue:
    def test_legacy_data_yields_an_empty_catalogue(self):
        assert part_catalog(pd.DataFrame(), None).empty

    def test_metadata_disagreeing_across_tables_is_refused(self):
        """Words and fixations describing the same screen differently is a
        mapping error, not something to resolve with a silent `first()`."""
        words = _frame(canvas_width=[100, 100, 100, 100])
        fixations = _frame(canvas_width=[999, 999, 100, 100])
        with pytest.raises(ValueError, match="conflicts across tables"):
            part_catalog(words, fixations)

    def test_screens_come_back_in_recorded_order(self):
        catalog = part_catalog(_frame(screen_id=["b", "b", "a", "a"]))
        assert list(catalog["screen_id"]) == ["b", "a"]


class TestMatchingParts:
    def test_identity_in_only_one_report_is_refused(self):
        with pytest.raises(ValueError, match="only one report"):
            validate_matching_parts(
                _frame(),
                pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]}),
            )

    def test_an_orphan_screen_is_named(self):
        words = normalize_screen_identity(_frame())
        fixations = normalize_screen_identity(_frame(screen_id=["a", "a", "c", "c"]))
        with pytest.raises(ValueError, match="orphan screens"):
            validate_matching_parts(words, fixations)

    def test_matching_reports_pass(self):
        frame = normalize_screen_identity(_frame())
        validate_matching_parts(frame, frame)

    def test_an_empty_report_is_not_an_orphan(self):
        validate_matching_parts(pd.DataFrame(), _frame())


class TestExtractPart:
    def test_a_screen_on_a_single_screen_dataset_is_refused(self):
        flat = pd.DataFrame({"participant_id": ["p1"], "trial_id": ["t1"]})
        with pytest.raises(ValueError, match="single-screen dataset"):
            extract_part(flat, "p1", "t1", "a")

    def test_an_empty_frame_passes_through(self):
        empty = pd.DataFrame()
        assert extract_part(empty, "p1", "t1") is empty


class TestTheNestedManifest:
    @staticmethod
    def _source():
        return pd.DataFrame(
            {
                "participant_id": ["p1"] * 4,
                "trial_id": ["t1"] * 4,
                "page": ["intro", "intro", "body", "body"],
            }
        )

    @staticmethod
    def _manifest(**part_overrides):
        part = {"screen_id": "intro", "words": {"page": "intro"}}
        part.update(part_overrides)
        return {
            "trials": [
                {
                    "participant_id": "p1",
                    "trial_id": "t1",
                    "parts": [part, {"screen_id": "body", "words": {"page": "body"}}],
                }
            ]
        }

    def test_an_empty_report_passes_through(self):
        empty = pd.DataFrame()
        assert (
            apply_trial_parts_manifest(
                empty, self._source(), self._manifest(), kind="words"
            )
            is empty
        )

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(ValueError, match="kind must be"):
            apply_trial_parts_manifest(
                self._source(), self._source(), self._manifest(), kind="raw_gaze"
            )

    def test_a_manifest_without_a_trials_list_is_refused(self):
        with pytest.raises(ValueError, match="'trials' list"):
            apply_trial_parts_manifest(
                self._source(), self._source(), {"trials": "nope"}, kind="words"
            )

    def test_a_parent_matching_no_rows_is_refused(self):
        manifest = self._manifest()
        manifest["trials"][0]["participant_id"] = "ghost"
        with pytest.raises(ValueError, match="matches no rows"):
            apply_trial_parts_manifest(
                self._source(), self._source(), manifest, kind="words"
            )

    def test_a_part_without_a_screen_id_is_refused(self):
        with pytest.raises(ValueError, match="non-empty screen_id"):
            apply_trial_parts_manifest(
                self._source(),
                self._source(),
                self._manifest(screen_id=""),
                kind="words",
            )

    def test_a_part_without_a_selector_is_refused(self):
        manifest = self._manifest()
        del manifest["trials"][0]["parts"][0]["words"]
        with pytest.raises(ValueError, match="needs a words selector"):
            apply_trial_parts_manifest(
                self._source(), self._source(), manifest, kind="words"
            )

    def test_a_selector_naming_an_unknown_column_is_refused(self):
        with pytest.raises(ValueError, match="unknown column"):
            apply_trial_parts_manifest(
                self._source(),
                self._source(),
                self._manifest(words={"nope": 1}),
                kind="words",
            )

    def test_a_selector_matching_nothing_is_refused(self):
        with pytest.raises(ValueError, match="matches no rows"):
            apply_trial_parts_manifest(
                self._source(),
                self._source(),
                self._manifest(words={"page": "missing"}),
                kind="words",
            )

    def test_overlapping_parts_are_refused(self):
        """Two screens claiming one row is ambiguous; the module never picks."""
        manifest = self._manifest()
        manifest["trials"][0]["parts"][1]["words"] = {"page": "intro"}
        with pytest.raises(ValueError, match="overlaps another part"):
            apply_trial_parts_manifest(
                self._source(), self._source(), manifest, kind="words"
            )

    def test_a_declared_parent_with_rows_left_over_is_refused(self):
        """Silently dropping the rows no part claimed is the failure this
        prevents — they would vanish from the trial without a word."""
        manifest = self._manifest()
        del manifest["trials"][0]["parts"][1]
        with pytest.raises(ValueError, match="declared-parent row"):
            apply_trial_parts_manifest(
                self._source(), self._source(), manifest, kind="words"
            )

    def test_a_clean_manifest_assigns_both_screens_in_order(self):
        out = apply_trial_parts_manifest(
            self._source(), self._source(), self._manifest(), kind="words"
        )
        assert list(out["screen_id"]) == ["intro", "intro", "body", "body"]
        assert list(out["screen_index"]) == [1, 1, 2, 2]


class TestScreenCanvasSize:
    def test_both_dimensions_present_and_constant(self):
        frame = _frame(canvas_width=[100] * 4, canvas_height=[50] * 4)
        assert screen_canvas_size(frame) == (100, 50)

    @pytest.mark.parametrize(
        "frame",
        [
            pd.DataFrame(),
            _frame(canvas_width=[100] * 4),  # height missing
            _frame(canvas_width=[100, 200, 100, 100], canvas_height=[50] * 4),
            _frame(canvas_width=[0] * 4, canvas_height=[50] * 4),
        ],
        ids=["empty", "one-dimension", "not-constant", "non-positive"],
    )
    def test_anything_less_reports_nothing(self, frame):
        assert screen_canvas_size(frame) is None
