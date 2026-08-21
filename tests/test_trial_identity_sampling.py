"""VAL-7's identity check on a sample of trials (PERF-6).

The check runs on the *unfiltered* corpus every time a dataset loads — 4.1 s at
OneStop scale (24,046 trials) to produce one warning line. It is a screen, not a
census: a mapping that under-specifies does so systematically, so it shows up in
any fair sample. The full scan stays available on demand.
"""

from __future__ import annotations

import pandas as pd

from scanpath_studio.data import diagnose_trial_identity, trial_identity_warning

TRIALS = 60


def _corpus(broken: set[int] = frozenset()):
    """``TRIALS`` two-word trials; a broken one repeats its words (two readings
    concatenated under one id)."""
    words, fixations = [], []
    for t in range(TRIALS):
        readings = 2 if t in broken else 1
        for r in range(readings):
            for wid in (0, 1):
                words.append(
                    {
                        "participant_id": f"p{t % 5}",
                        "trial_id": f"t{t}",
                        "word_id": wid,
                        "text": "w",
                        "x": wid * 50,
                        "y": 100,
                        "width": 40,
                        "height": 20,
                    }
                )
                fixations.append(
                    {
                        "participant_id": f"p{t % 5}",
                        "trial_id": f"t{t}",
                        "fixation_id": wid,
                        "timestamp_ms": r * 1000 + wid * 100,
                        "duration_ms": 200,
                        "x": wid * 50 + 20,
                        "y": 110,
                    }
                )
    return pd.DataFrame(words), pd.DataFrame(fixations)


class TestSampling:
    def test_examines_at_most_the_sample_size(self):
        words, fixations = _corpus()
        report = diagnose_trial_identity(words, fixations, sample_trials=10)
        assert report["trials"] <= 10

    def test_records_what_it_sampled_from(self):
        words, fixations = _corpus()
        report = diagnose_trial_identity(words, fixations, sample_trials=10)
        assert report["sampled_from"] == TRIALS

    def test_is_deterministic(self):
        """A screen whose answer flickers between reruns is worse than none."""
        words, fixations = _corpus({3, 17, 40})
        first = diagnose_trial_identity(words, fixations, sample_trials=20)
        second = diagnose_trial_identity(words, fixations, sample_trials=20)
        assert first == second

    def test_a_small_corpus_is_not_sampled_at_all(self):
        words, fixations = _corpus({1})
        full = diagnose_trial_identity(words, fixations)
        sampled = diagnose_trial_identity(words, fixations, sample_trials=TRIALS * 10)
        assert sampled["sampled_from"] is None
        assert sampled == full

    def test_no_sample_size_means_the_whole_corpus(self):
        words, fixations = _corpus({1})
        assert diagnose_trial_identity(words, fixations)["sampled_from"] is None

    def test_still_finds_a_problem_that_is_everywhere(self):
        """The failure this screens for is systematic — every trial broken the
        same way — so any fair sample must catch it."""
        words, fixations = _corpus(set(range(TRIALS)))
        report = diagnose_trial_identity(words, fixations, sample_trials=10)
        assert report["affected_trials"] > 0

    def test_a_clean_corpus_stays_clean(self):
        words, fixations = _corpus()
        assert (
            diagnose_trial_identity(words, fixations, sample_trials=10)[
                "affected_trials"
            ]
            == 0
        )


class TestWarningWording:
    def test_says_when_the_figure_came_from_a_sample(self):
        words, fixations = _corpus(set(range(TRIALS)))
        warning = trial_identity_warning(
            diagnose_trial_identity(words, fixations, sample_trials=10)
        )
        assert "sample" in warning.lower()

    def test_says_nothing_about_sampling_on_a_full_scan(self):
        words, fixations = _corpus(set(range(TRIALS)))
        warning = trial_identity_warning(diagnose_trial_identity(words, fixations))
        assert "sample" not in warning.lower()
