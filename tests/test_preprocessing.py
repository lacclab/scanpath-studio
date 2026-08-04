import numpy as np
import pandas as pd

from scanpath_studio import alignment
from scanpath_studio.measures import compute_per_word_measures, enrich_fixations
from scanpath_studio.preprocessing import (
    add_text_direction,
    character_grid,
    duration_mass_table,
    materialize_runs,
    measure_sensitivity,
    preprocess_fixations,
    saccade_table,
    sentence_measures,
)


def test_disabled_preprocessing_is_identity(
    normalized_words_df, normalized_fixations_df
):
    result, report = preprocess_fixations(
        normalized_fixations_df, normalized_words_df, settings={"enabled": False}
    )
    assert result is normalized_fixations_df
    assert report.empty


def test_merge_short_fixation_preserves_duration_and_provenance(normalized_words_df):
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "timestamp_ms": [0, 40],
            "duration_ms": [40, 200],
            "x": [110, 115],
            "y": [60, 60],
            "word_id": [1, 1],
        }
    )
    processed, report = preprocess_fixations(
        fixations,
        normalized_words_df,
        settings={"enabled": True, "short_policy": "Merge"},
    )
    assert processed.loc[~processed["excluded"], "duration_ms"].sum() == 240
    assert processed["excluded_reason"].eq("merged_short").sum() == 1
    assert report.iloc[0]["n_merged"] == 1


def test_blink_adjacent_rows_are_soft_excluded(normalized_words_df):
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "timestamp_ms": [0, 100, 200],
            "duration_ms": [100, 100, 100],
            "x": [100, 110, 120],
            "y": [60, 60, 60],
            "word_id": [1, 1, 1],
            "is_blink": [False, True, False],
        }
    )
    processed, _ = preprocess_fixations(
        fixations,
        normalized_words_df,
        settings={"enabled": True, "discard_blink_adjacent": True},
    )
    assert processed["excluded"].all()
    assert set(processed["excluded_reason"]) == {"blink_adjacent"}


def test_run_structure_marks_word_revisits(normalized_fixations_df):
    fixations = normalized_fixations_df.copy()
    fixations["word_id"] = [1, 2, 1]
    runs = materialize_runs(fixations)
    assert list(runs["word_run"].astype(int)) == [1, 1, 2]
    assert list(runs["reread"]) == [False, False, True]


def test_excluded_rows_do_not_create_runs_saccades_or_summary_counts(
    normalized_words_df,
):
    from scanpath_studio.aggregation import trial_summary_table

    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "timestamp_ms": [0.0, 40.0, 280.0],
            "duration_ms": [40.0, 240.0, 100.0],
            "x": [100.0, 110.0, 300.0],
            "y": [60.0, 60.0, 60.0],
            "word_id": [1.0, 1.0, 2.0],
            "excluded": [True, False, False],
        }
    )
    runs = materialize_runs(fixations)
    assert pd.isna(runs.loc[0, "word_run"])
    assert runs.loc[1:, "word_run"].notna().all()
    saccades = saccade_table(runs, words=normalized_words_df)
    assert len(saccades) == 1
    summary = trial_summary_table(normalized_words_df, runs).iloc[0]
    assert summary["n_fixations"] == 2
    assert summary["total_fixation_ms"] == 340


def test_new_word_measures_include_landing_second_pass_and_regression_count(
    normalized_words_df, normalized_fixations_df
):
    revisit = normalized_fixations_df.iloc[[0]].copy()
    revisit["timestamp_ms"] = 700
    revisit["duration_ms"] = 150
    fixations = pd.concat([normalized_fixations_df, revisit], ignore_index=True)
    measured = compute_per_word_measures(fixations, normalized_words_df)
    first = measured.set_index("word_id").loc[1]
    assert first["number_of_regressions_in"] == 1
    assert first["second_pass_duration_ms"] == 150
    assert np.isfinite(first["initial_landing_position"])


def test_rtl_detection_character_grid_and_landing_direction():
    words = pd.DataFrame(
        {
            "participant_id": ["p"],
            "trial_id": ["t"],
            "text_id": ["x"],
            "word_id": [1],
            "text": ["שלום"],
            "line_idx": [0],
            "x": [100.0],
            "y": [50.0],
            "width": [80.0],
            "height": [30.0],
        }
    )
    directed = add_text_direction(words)
    assert bool(directed.iloc[0]["right_to_left"])
    chars = character_grid(directed)
    assert list(chars["letternum"]) == [4, 3, 2, 1]
    assert list(chars["letword"]) == [4, 3, 2, 1]
    assert "letline" in chars
    # Physical left-to-right boxes contain the logical word in reverse order.
    assert "".join(chars.sort_values("x")["character"]) == "םולש"


def test_duration_mass_uses_character_support_and_preserves_total_duration():
    words = pd.DataFrame(
        {
            "participant_id": ["p"],
            "trial_id": ["t"],
            "word_id": [1],
            "text": ["abc"],
            "line_idx": [0],
            "x": [0.0],
            "y": [0.0],
            "width": [30.0],
            "height": [20.0],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"],
            "trial_id": ["t"],
            "x": [15.0],
            "y": [10.0],
            "duration_ms": [300.0],
        }
    )
    mass = duration_mass_table(words, fixations, sigma_chars=0.75)
    assert np.isclose(mass["duration_mass_ms"].sum(), 300.0)
    assert (
        mass.loc[mass["character"] == "b", "duration_mass_ms"].iloc[0]
        > mass.loc[mass["character"] == "a", "duration_mass_ms"].iloc[0]
    )
    assert mass["center_x"].tolist() == [5.0, 15.0, 25.0]


def test_sentence_and_saccade_tables(normalized_words_df, normalized_fixations_df):
    words = normalized_words_df.copy()
    words["text"] = ["One", "sentence.", "Next!"]
    fixations = enrich_fixations(normalized_fixations_df, words)
    sentences = sentence_measures(words, fixations)
    assert set(sentences["sentence_id"]) == {1, 2}
    saccades = saccade_table(fixations, pixels_per_degree=50, words=words)
    assert len(saccades) == len(fixations) - 1
    assert saccades["amplitude_deg"].notna().all()
    assert {"angle", "launch_letter", "landing_letter"} <= set(saccades)


def test_saccade_duration_is_gap_after_fixation_and_uses_canonical_line_idx():
    fixations = pd.DataFrame(
        {
            "participant_id": ["p", "p"],
            "trial_id": ["t", "t"],
            "timestamp_ms": [100.0, 380.0],
            "duration_ms": [250.0, 200.0],
            "x": [10.0, 30.0],
            "y": [10.0, 20.0],
            "line_idx": [2, 3],
        }
    )
    row = saccade_table(fixations).iloc[0]
    assert row["duration_ms"] == 30.0
    assert row["launch_line"] == 2
    assert row["landing_line"] == 3


def test_cleaning_report_has_after_counts_reason_percentages_and_terminal_merge_drop(
    normalized_words_df,
):
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "timestamp_ms": [0, 200],
            "duration_ms": [200, 40],
            "x": [1000, 10],
            "y": [60, 60],
            "word_id": [1, 2],
        }
    )
    processed, report = preprocess_fixations(
        fixations,
        normalized_words_df,
        settings={"enabled": True, "short_policy": "Merge"},
    )
    assert processed.iloc[-1]["excluded_reason"] == "short_unmerged"
    row = report.iloc[0]
    assert row["n_fixations_after"] == 1
    assert row["short_discarded_pct"] == 0.5
    assert {"blink_adjacent_pct", "merged_pct"} <= set(report)


def test_sentence_lookback_and_lookfrom_are_distinct_paths():
    words = pd.DataFrame(
        {
            "participant_id": ["p"] * 3,
            "trial_id": ["t"] * 3,
            "text_id": ["text"] * 3,
            "word_id": [1, 2, 3],
            "sentence_id": [1, 2, 3],
            "text": ["One.", "Two.", "Three."],
            "line_idx": [0, 0, 0],
            "x": [0.0, 100.0, 200.0],
            "y": [0.0, 0.0, 0.0],
            "width": [80.0] * 3,
            "height": [20.0] * 3,
        }
    )
    sequence = [1, 2, 1, 2, 3, 2]
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"] * len(sequence),
            "trial_id": ["t"] * len(sequence),
            "word_id": sequence,
            "timestamp_ms": np.arange(len(sequence)) * 100.0,
            "duration_ms": [80.0] * len(sequence),
            "x": [words.set_index("word_id").loc[w, "x"] + 10 for w in sequence],
            "y": [10.0] * len(sequence),
        }
    )
    sentence_two = sentence_measures(words, fixations).set_index("sentence_id").loc[2]
    assert sentence_two["lookback_n_fixations"] == 1
    assert sentence_two["lookfrom_n_fixations"] == 1
    assert sentence_two["firstpass_reread_n_fixations"] == 1


def test_sensitivity_is_trial_scoped():
    words = pd.DataFrame(
        {
            "participant_id": ["p"] * 4,
            "trial_id": ["a", "a", "b", "b"],
            "word_id": [1, 2, 1, 2],
            "text": ["a", "b", "a", "b"],
            "line_idx": [0, 1, 0, 1],
            "x": [0.0, 0.0, 0.0, 0.0],
            "y": [0.0, 100.0, 1000.0, 1100.0],
            "width": [20.0] * 4,
            "height": [20.0] * 4,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"] * 4,
            "trial_id": ["a", "a", "b", "b"],
            "timestamp_ms": [0.0, 100.0, 0.0, 100.0],
            "duration_ms": [80.0] * 4,
            "x": [10.0] * 4,
            "y": [10.0, 110.0, 1010.0, 1110.0],
            "word_id": [1, 2, 1, 2],
        }
    )
    _, report = measure_sensitivity(words, fixations, methods=("attach", "slice"))
    assert len(report) == 4
    assert set(report["trial_id"]) == {"a", "b"}


def test_slice_consensus_and_sensitivity_are_available(
    normalized_words_df, normalized_fixations_df
):
    words = pd.concat(
        [
            normalized_words_df.assign(y=40, line_idx=0),
            normalized_words_df.assign(word_id=[4, 5, 6], y=140, line_idx=1),
        ],
        ignore_index=True,
    )
    for method in ("slice", "consensus"):
        corrected, assigned = alignment.correct(
            normalized_fixations_df, words, method=method
        )
        assert assigned.notna().all()
        assert "y_correction" in corrected
    combined, report = alignment.correction_sensitivity(normalized_fixations_df, words)
    assert "assignment_disagreement" in combined
    assert set(report["algorithm"]) == {"attach", "slice", "consensus"}
