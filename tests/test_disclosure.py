"""UX-20: the AI-assistance disclosure, and the facts behind it.

The note is deliberately three lines — built with AI assistance, cross-check
before publishing, here is where to report it. It used to also spell out two
things a reader could verify (the ground-truth trial, EyeLink precedence); that
prose was cut as clutter, but the *guarantees* it described are what let the note
stay this short, so they keep their tests here. A disclosure resting on claims
nobody checks is worse than no disclosure.

The route to the ground-truth trial is UX-37 behaviour now, not a documented
claim, and is covered in ``tests/test_debug_log.py``.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (REPO / path).read_text(encoding="utf-8")


class TestTheNoteIsOnEverySurface:
    """The citation lives in three places; so does this."""

    @pytest.mark.parametrize(
        "path", ["README.md", "docs/index.md", "scanpath_studio/app.py"]
    )
    def test_the_surface_carries_the_disclosure(self, path):
        body = _text(path)
        assert "AI assistance" in body, path
        # The actionable half — without it the note is unfalsifiable.
        assert "cross-check" in body.lower(), path
        # It must never send a reader off to hand-edit a URL: someone who has to
        # do that verifies nothing. Scoped to the note itself, since app.py also
        # *explains* the old param in a code comment.
        note = body[body.lower().find("ai assistance") :][:2000]
        assert "?source=synthetic" not in note, path

    @pytest.mark.parametrize("path", ["README.md", "docs/index.md"])
    def test_it_points_somewhere_a_report_can_land(self, path):
        assert "scanpath-studio/issues" in _text(path), path

    @pytest.mark.parametrize(
        "path", ["README.md", "docs/index.md", "scanpath_studio/app.py"]
    )
    def test_the_note_explicitly_welcomes_feature_requests(self, path):
        body = _text(path).lower()
        note = body[body.find("ai assistance") :][:2000]
        assert "feature request" in note, path

    def test_the_in_app_note_links_issues_via_the_citation_metadata(self):
        """Not a hard-coded URL — the repo link already lives in CITATION."""
        body = _text("scanpath_studio/app.py")
        assert 'CITATION["url"]}/issues' in body

    def test_no_liability_disclaimer_language(self):
        """Deliberately not a warranty notice — MIT already carries that, and
        legal boilerplate is what makes people stop reading these."""
        for path in ("README.md", "docs/index.md", "scanpath_studio/app.py"):
            body = _text(path).lower()
            section = body[body.find("ai assistance") :][:2000]
            for phrase in ("no warranty", "as is", "not liable", "disclaim"):
                assert phrase not in section, f"{path}: {phrase!r}"


@pytest.mark.timeout(90)
class TestTheGroundTruthFixtureIsReal:
    """The reading measures are pinned to a hand-traced trial. Nothing in the UI
    says so anymore, but it is the reason the note needs no hedging beyond
    "cross-check"."""

    def test_the_expectations_cover_every_canonical_measure(self):
        """Expected values have to exist for *every* measure, or the fixture
        only proves the easy ones. (The exhaustive value-by-value assertions
        live in `tests/test_synthetic.py`; this pins the coverage.)"""
        from tests.synthetic_data import EXPECTED

        assert {
            "first_fixation_ms",
            "first_pass_gaze_duration_ms",
            "regression_path_duration_ms",
            "total_fixation_duration_ms",
            "n_fixations",
            "skip_flag",
            "regression_in_flag",
            "regression_out_flag",
        } <= set(EXPECTED)
        assert (REPO / "tests" / "test_synthetic.py").is_file()

    def test_a_hand_traced_value_still_matches_what_the_code_computes(self):
        """One live spot-check, so the claim isn't purely bibliographic. Word 1
        is the interesting one: it's re-fixated after a regression, so its TFD
        (230 ms) exceeds its first-pass gaze duration (150 ms)."""
        from scanpath_studio.measures import compute_per_word_measures
        from tests.synthetic_data import (
            EXPECTED,
            make_synthetic_fixations,
            make_synthetic_words,
        )

        measured = compute_per_word_measures(
            make_synthetic_fixations(), make_synthetic_words()
        ).set_index("word_id")
        for column in ("total_fixation_duration_ms", "first_pass_gaze_duration_ms"):
            for word_id, want in EXPECTED[column].items():
                got = measured.loc[word_id, column]
                assert got == pytest.approx(want), (column, word_id, got, want)
        assert EXPECTED["total_fixation_duration_ms"][1] == 230
        assert EXPECTED["first_pass_gaze_duration_ms"][1] == 150


class TestEyeLinkMeasuresWin:
    """On a normal EyeLink export the numbers are the vendor's, not ours — the
    architectural rule from AGENTS.md ("pre-computed IA values take precedence
    over computed ones"), which is only true if the `IA_*` columns actually
    survive both normalization and the end of the pipeline."""

    def test_a_precomputed_column_survives_normalization_unchanged(self):
        from scanpath_studio.data import infer_word_schema, normalize_words

        raw = pd.DataFrame(
            {
                "RECORDING_SESSION_LABEL": ["p1", "p1"],
                "unique_paragraph_id": ["1_1_Ele", "1_1_Ele"],
                "IA_ID": [0, 1],
                "IA_LABEL": ["The", "cat"],
                "IA_LEFT": [100.0, 160.0],
                "IA_RIGHT": [155.0, 210.0],
                "IA_TOP": [50.0, 50.0],
                "IA_BOTTOM": [80.0, 80.0],
                # A value no fixation-derived computation could produce.
                "IA_DWELL_TIME": [4242.0, 7.0],
            }
        )
        out = normalize_words(raw, infer_word_schema(raw))
        assert list(out["total_fixation_duration_ms"]) == [4242.0, 7.0]

    def test_compute_word_metrics_keeps_the_precomputed_values(self):
        """The end of the pipeline, not just normalization: a trial whose
        fixations would imply different numbers must still report the export's."""
        from scanpath_studio.data import compute_word_metrics

        words = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "word_id": [0, 1],
                "text": ["The", "cat"],
                "x": [100.0, 160.0],
                "y": [50.0, 50.0],
                "width": [55.0, 50.0],
                "height": [30.0, 30.0],
                "total_fixation_duration_ms": [4242.0, 7.0],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "x": [110.0, 170.0],
                "y": [65.0, 65.0],
                "duration_ms": [180.0, 220.0],
                "timestamp_ms": [0.0, 200.0],
                "order_in_trial": [1, 2],
            }
        )
        out = compute_word_metrics(words, fixations)
        assert list(out["total_fixation_duration_ms"]) == [4242.0, 7.0]
