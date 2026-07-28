"""UX-20: the AI-assistance disclosure, and the claims it makes.

The note claims only what a reader can check for themselves, so both claims are
pinned here: that the ground-truth trial really is reachable the way the note
says, and that pre-computed EyeLink measures really do take precedence over
derived ones. A disclosure whose "you can verify this yourself" turns out to be
wrong is worse than no disclosure.
"""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

REPO = pathlib.Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (REPO / path).read_text()


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
        assert "?source=synthetic" in body, path

    @pytest.mark.parametrize("path", ["README.md", "docs/index.md"])
    def test_it_points_somewhere_a_report_can_land(self, path):
        assert "scanpath-studio/issues" in _text(path), path

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
class TestTheClaimsHold:
    def test_the_ground_truth_trial_is_reachable_the_way_the_note_says(self):
        """The note tells the reader to add `?source=synthetic`. The synthetic
        source is deliberately NOT offered in the data-source picker, so this
        deep link is the only route — if it breaks, the note is a dead end."""
        at = AppTest.from_file("streamlit_app.py")
        at.query_params["source"] = "synthetic"
        at.run(timeout=60)
        assert not at.exception, f"Streamlit exceptions: {at.exception}"
        assert at.error == [], f"st.error calls: {[e.value for e in at.error]}"
        assert at.session_state["data_source_choice"] == "Synthetic test trial"
        picker = next(s for s in at.selectbox if s.label.startswith("Trial ID"))
        assert list(picker.options) == ["synthetic_2line_demo"]

    def test_the_expectations_cover_every_canonical_measure(self):
        """ "Expected values per measure" has to be true of *every* measure, or
        the note oversells what was checked. (The exhaustive value-by-value
        assertions live in `tests/test_synthetic.py`; this pins the coverage
        claim itself.)"""
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
    """The strongest sentence in the note: on a normal EyeLink export the
    numbers are the vendor's, not ours. That is only true if the pre-computed
    `IA_*` columns actually take precedence over the derived ones."""

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
