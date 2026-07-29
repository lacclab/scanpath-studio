"""BUG-8: detect a 1-based fixation ``word_id`` against 0-based word boxes.

The bundled OneStop demo's fixation report numbers its word column ``1..N``
while ``ia.csv``'s ``IA_ID`` runs ``0..N-1``, so every fixation's pre-assigned
``word_id`` pointed at the *next* word. ``data.detect_word_id_offset`` has to
catch that without ever firing on a correctly-numbered dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scanpath_studio.data import (
    correct_word_id_offset,
    detect_word_id_offset,
    harmonize_frames,
)


def _words(n_words: int = 5, start: int = 0, trials=("t1",)) -> pd.DataFrame:
    rows = []
    for trial in trials:
        for i in range(n_words):
            rows.append(
                {
                    "participant_id": "p1",
                    "trial_id": trial,
                    "word_id": float(start + i),
                    "text": f"w{i}",
                    "x": 100.0 + 50 * i,
                    "y": 100.0,
                    "width": 50.0,
                    "height": 20.0,
                }
            )
    return pd.DataFrame(rows)


def _fixations(word_ids, trials=("t1",)) -> pd.DataFrame:
    rows = []
    for trial in trials:
        for order, wid in enumerate(word_ids, start=1):
            rows.append(
                {
                    "participant_id": "p1",
                    "trial_id": trial,
                    "word_id": float(wid),
                    "x": 110.0,
                    "y": 105.0,
                    "duration_ms": 200.0,
                    "order_in_trial": order,
                }
            )
    return pd.DataFrame(rows)


class TestDetection:
    def test_one_based_frame_is_detected(self):
        # words 0..4, fixations 1..5 — the demo's exact shape.
        assert detect_word_id_offset(_words(5), _fixations([1, 2, 3, 4, 5])) == 1

    def test_zero_based_frame_is_left_alone(self):
        assert detect_word_id_offset(_words(5), _fixations([0, 1, 2, 3, 4])) == 0

    def test_consistent_frame_with_a_gap_is_left_alone(self):
        # The reader never fixated word 0 and never went past the last word:
        # ids 1..4 against words 0..4 is a plain skip, not a shift.
        assert detect_word_id_offset(_words(5), _fixations([1, 2, 4])) == 0

    def test_runaway_fixation_id_is_not_treated_as_a_shift(self):
        # More than one past the last word means something else is wrong.
        assert detect_word_id_offset(_words(5), _fixations([1, 2, 6])) == 0

    def test_one_trial_shifted_and_one_not_is_left_alone(self):
        words = _words(5, trials=("t1", "t2"))
        fix = pd.concat(
            [_fixations([1, 2, 5], trials=("t1",)), _fixations([0, 1], trials=("t2",))],
            ignore_index=True,
        )
        assert detect_word_id_offset(words, fix) == 0

    def test_words_not_starting_at_zero_is_left_alone(self):
        # A 1-based words table with 1-based fixations is already consistent.
        assert detect_word_id_offset(_words(5, start=1), _fixations([1, 2, 3])) == 0

    def test_fractional_ids_are_left_alone(self):
        words = _words(5)
        fix = _fixations([1, 2, 5])
        fix.loc[0, "word_id"] = 1.5
        assert detect_word_id_offset(words, fix) == 0

    def test_all_nan_fixation_ids_are_left_alone(self):
        words = _words(5)
        fix = _fixations([1, 2, 5])
        fix["word_id"] = np.nan
        assert detect_word_id_offset(words, fix) == 0

    def test_empty_frames_are_left_alone(self):
        assert detect_word_id_offset(pd.DataFrame(), pd.DataFrame()) == 0
        assert detect_word_id_offset(_words(5), pd.DataFrame()) == 0

    def test_missing_word_id_column_is_left_alone(self):
        fix = _fixations([1, 2, 5]).drop(columns=["word_id"])
        assert detect_word_id_offset(_words(5), fix) == 0


class TestCorrection:
    def test_shift_is_applied_once(self):
        words, fix = _words(5), _fixations([1, 2, 3, 4, 5])
        corrected = correct_word_id_offset(words, fix)
        assert corrected["word_id"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]
        # Idempotent: the corrected frame no longer looks 1-based.
        assert detect_word_id_offset(words, corrected) == 0
        assert correct_word_id_offset(words, corrected)["word_id"].tolist() == [
            0.0,
            1.0,
            2.0,
            3.0,
            4.0,
        ]

    def test_correct_frame_is_returned_untouched(self):
        words, fix = _words(5), _fixations([0, 1, 2, 3, 4])
        corrected = correct_word_id_offset(words, fix)
        assert corrected["word_id"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]

    def test_harmonize_frames_applies_the_shift(self):
        words, fix = _words(5), _fixations([1, 2, 3, 4, 5])
        _, harmonized = harmonize_frames(words, fix)
        assert harmonized["word_id"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]


class TestBundledSample:
    def test_demo_fixations_line_up_with_the_word_boxes(self):
        from scanpath_studio import api

        words, fixations = api.load_sample_data()
        trial = "l37_1129_2_2_1_Adv_r0"
        tw = words[words["trial_id"] == trial]
        tf = fixations[fixations["trial_id"] == trial].sort_values("order_in_trial")
        # Both tables now run over the same id range.
        assert float(tw["word_id"].min()) == 0.0
        assert float(tf["word_id"].min()) == 0.0
        assert float(tf["word_id"].max()) <= float(tw["word_id"].max())
        # The first fixation sits inside the first word's box and now says so.
        first = tf.iloc[0]
        box = tw[tw["word_id"] == 0].iloc[0]
        assert box["x"] <= first["x"] <= box["x"] + box["width"]
        assert box["y"] <= first["y"] <= box["y"] + box["height"]
        assert float(first["word_id"]) == 0.0
