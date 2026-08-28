"""PERF-8: one filesystem probe per placeholder tuple, not per row.

`data.resolve_stimulus_image_paths` is VIZ-14's headless surface — the app's
local stimulus-folder controls, `render --stimulus-image-root` and
`api.load_scanpath_data` all go through it. It resolved and stat'd a path for
*every row*: two syscalls each, on every rerun that had a folder attached, over
the unfiltered frames. A pattern only reads a couple of columns, so on OneStop
that was millions of syscalls for a few hundred distinct answers.

The per-row form also had a bug that only showed on some tables.
`DataFrame.apply(axis=1)` hands the callback each row as a Series of ONE dtype,
so an integer `trial_id` stringified as ``"7.0"`` whenever any *other* column in
the frame happened to be a float — and as ``"7"`` otherwise. A normalized
fixations frame always carries float `x`/`y`, so ``{trial_id}.png`` matched the
words table and missed the fixations table, from the same folder, in the same
call. Reading each column at its own dtype is both the fast way and the correct
one; :class:`TestOneColumnAtATime` is what pins it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.data import _pattern_placeholders, resolve_stimulus_image_paths


@pytest.fixture
def images(tmp_path: Path) -> Path:
    """A folder of stimulus images: a.png, b.png, sub/a_1.png, 7.png, 7.0.png."""
    for name in ("a.png", "b.png", "7.png", "7.0.png", "nan.png"):
        (tmp_path / name).write_bytes(b"\x89PNG")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a_1.png").write_bytes(b"\x89PNG")
    return tmp_path


class TestProbesAreDeduped:
    """The whole point: distinct placeholder tuples, not rows."""

    def test_a_thousand_rows_of_three_texts_stat_three_paths(self, images, monkeypatch):
        probes: list[str] = []
        real = Path.is_file
        monkeypatch.setattr(
            Path, "is_file", lambda self: (probes.append(str(self)), real(self))[1]
        )
        frame = pd.DataFrame({"text_id": ["a", "b", "c"] * 400})

        resolved = resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert len(probes) == 3, "one probe per distinct text_id, not per row"
        assert len(resolved) == 1200
        assert resolved["image_path"].notna().sum() == 800  # a and b exist, c doesn't

    def test_two_placeholders_dedupe_on_the_pair(self, images, monkeypatch):
        probes: list[str] = []
        real = Path.is_file
        monkeypatch.setattr(
            Path, "is_file", lambda self: (probes.append(str(self)), real(self))[1]
        )
        frame = pd.DataFrame(
            {"text_id": ["a", "a", "b", "b"] * 50, "trial_id": [1, 2, 1, 2] * 50}
        )

        resolve_stimulus_image_paths(frame, images, "sub/{text_id}_{trial_id}.png")

        assert len(probes) == 4

    def test_a_pattern_with_no_placeholders_probes_once(self, images, monkeypatch):
        probes: list[str] = []
        real = Path.is_file
        monkeypatch.setattr(
            Path, "is_file", lambda self: (probes.append(str(self)), real(self))[1]
        )
        frame = pd.DataFrame({"text_id": list("abcdefghij")})

        resolved = resolve_stimulus_image_paths(frame, images, "a.png")

        assert len(probes) == 1
        assert resolved["image_path"].nunique() == 1


class TestOneColumnAtATime:
    """Each column keeps its own dtype — the `apply(axis=1)` row-upcast bug."""

    def test_an_int_id_is_not_stringified_through_float(self, images):
        # `x` is a float, as it is on every normalized fixations frame. The row
        # Series `apply(axis=1)` built was therefore float64 throughout, and
        # `{trial_id}` came out "7.0".
        frame = pd.DataFrame({"trial_id": [7], "x": [1.5]})

        resolved = resolve_stimulus_image_paths(frame, images, "{trial_id}.png")

        assert resolved["image_path"].iloc[0] == str(images / "7.png")

    def test_the_same_ids_resolve_the_same_whatever_else_the_table_holds(self, images):
        words = pd.DataFrame({"trial_id": [7], "width": [10]})
        fixations = pd.DataFrame({"trial_id": [7], "x": [1.5], "y": [2.5]})

        a = resolve_stimulus_image_paths(words, images, "{trial_id}.png")
        b = resolve_stimulus_image_paths(fixations, images, "{trial_id}.png")

        assert a["image_path"].iloc[0] == b["image_path"].iloc[0]

    def test_a_genuinely_float_id_still_formats_as_a_float(self, images):
        frame = pd.DataFrame({"trial_id": [7.0]})

        resolved = resolve_stimulus_image_paths(frame, images, "{trial_id}.png")

        assert resolved["image_path"].iloc[0] == str(images / "7.0.png")


class TestTheFallbackIsPerRow:
    """A miss keeps that row's OWN prior `image_path`, never a shared one."""

    def test_each_missed_row_keeps_its_own_previous_value(self, images):
        frame = pd.DataFrame(
            {
                "text_id": ["a", "nope", "also-nope"],
                "image_path": ["/old/0.png", "/old/1.png", None],
            }
        )

        resolved = resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert resolved["image_path"].tolist() == [
            str(images / "a.png"),
            "/old/1.png",
            None,
        ]

    def test_a_frame_with_no_image_path_column_gets_one(self, images):
        frame = pd.DataFrame({"text_id": ["a", "nope"]})

        resolved = resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert resolved["image_path"].tolist() == [str(images / "a.png"), None]

    def test_the_input_frame_is_not_mutated(self, images):
        frame = pd.DataFrame({"text_id": ["a"]})

        resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert "image_path" not in frame.columns


class TestMissingPlaceholders:
    """NaN must stay *absent* from the mapping, not become the string "nan"."""

    def test_a_nan_id_does_not_resolve_nan_png(self, images):
        # nan.png exists in the fixture precisely so this can fail loudly.
        frame = pd.DataFrame({"text_id": ["a", np.nan]})

        resolved = resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert resolved["image_path"].tolist() == [str(images / "a.png"), None]

    def test_nan_in_any_referenced_column_is_enough(self, images):
        frame = pd.DataFrame({"text_id": ["a", "a"], "trial_id": ["1", np.nan]})

        resolved = resolve_stimulus_image_paths(
            frame, images, "sub/{text_id}_{trial_id}.png"
        )

        assert resolved["image_path"].tolist() == [
            str(images / "sub" / "a_1.png"),
            None,
        ]

    def test_a_nullable_id_column_is_a_float_column_and_formats_like_one(self, images):
        # Not a quirk of the dedup — it is what the column *is*. pandas has no
        # integer dtype carrying a NaN, so `1` beside a missing value really is
        # `1.0`, and the pattern writes `a_1.0.png`. The per-row form agreed
        # (its row Series was float64 too). Pinned so nobody "fixes" it into a
        # guess about which floats were meant to be ints.
        frame = pd.DataFrame({"text_id": ["a", "a"], "trial_id": [1, np.nan]})

        resolved = resolve_stimulus_image_paths(
            frame, images, "sub/{text_id}_{trial_id}.png", require_exists=False
        )

        assert resolved["image_path"].iloc[0] == str(images / "sub" / "a_1.0.png")

    def test_a_nan_in_an_unreferenced_column_is_irrelevant(self, images):
        frame = pd.DataFrame({"text_id": ["a"], "unused": [np.nan]})

        resolved = resolve_stimulus_image_paths(frame, images, "{text_id}.png")

        assert resolved["image_path"].iloc[0] == str(images / "a.png")

    def test_a_pattern_naming_a_column_the_table_lacks_resolves_nothing(self, images):
        frame = pd.DataFrame({"text_id": ["a"], "image_path": ["/old/0.png"]})

        resolved = resolve_stimulus_image_paths(frame, images, "{no_such_column}.png")

        assert resolved["image_path"].tolist() == ["/old/0.png"]


class TestTheFolderIsAFence:
    """`root` bounds the resolution — the security half of the contract."""

    def test_a_traversing_id_raises_rather_than_reading_outside(self, images):
        frame = pd.DataFrame({"text_id": ["../outside"]})

        with pytest.raises(ValueError, match="outside the selected folder"):
            resolve_stimulus_image_paths(frame, images, "{text_id}.png")

    def test_an_absolute_pattern_is_refused_up_front(self, images):
        frame = pd.DataFrame({"text_id": ["a"]})

        with pytest.raises(ValueError, match="non-empty relative path"):
            resolve_stimulus_image_paths(frame, images, "/etc/{text_id}")

    def test_an_empty_pattern_is_refused_up_front(self, images):
        frame = pd.DataFrame({"text_id": ["a"]})

        with pytest.raises(ValueError, match="non-empty relative path"):
            resolve_stimulus_image_paths(frame, images, "")


class TestRequireExists:
    """`require_exists=False` is the headless "trust me, build the path" mode."""

    def test_a_missing_file_still_yields_a_path(self, images):
        frame = pd.DataFrame({"text_id": ["nope"]})

        resolved = resolve_stimulus_image_paths(
            frame, images, "{text_id}.png", require_exists=False
        )

        assert resolved["image_path"].iloc[0] == str(images / "nope.png")

    def test_the_fence_still_holds_without_the_existence_check(self, images):
        frame = pd.DataFrame({"text_id": ["../outside"]})

        with pytest.raises(ValueError, match="outside the selected folder"):
            resolve_stimulus_image_paths(
                frame, images, "{text_id}.png", require_exists=False
            )


class TestEmptyInput:
    def test_an_empty_frame_comes_back_empty(self, images):
        resolved = resolve_stimulus_image_paths(pd.DataFrame(), images)

        assert resolved.empty

    def test_none_comes_back_as_an_empty_frame(self, images):
        assert resolve_stimulus_image_paths(None, images).empty


class TestPatternPlaceholders:
    """The parse that decides which columns form the dedup key."""

    @pytest.mark.parametrize(
        ("pattern", "expected"),
        [
            ("{text_id}.png", ["text_id"]),
            ("{text_id}/{trial_id}.png", ["text_id", "trial_id"]),
            ("{text_id}_{text_id}.png", ["text_id"]),  # deduped, order kept
            ("{trial_id:0>3}.png", ["trial_id"]),  # format spec trimmed
            ("{text_id!r}.png", ["text_id"]),  # conversion trimmed
            ("{a.b}.png", ["a"]),  # attribute access keys on `a`
            ("{a[0]}.png", ["a"]),  # index access keys on `a`
            ("stim.png", []),
            ("{}.png", []),  # auto-numbered: names no row field
        ],
    )
    def test_fields_are_read_off_the_pattern(self, pattern, expected):
        assert _pattern_placeholders(pattern) == expected
