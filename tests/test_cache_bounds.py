"""Per-trial caches are bounded (PERF-6).

``st.cache_data`` keeps every distinct call it has ever seen. That is right for
the handful of whole-corpus results the app re-reads on each rerun, and wrong
for anything keyed per *trial*: a bulk export over OneStop's 20,000 trials
computes each one once, never asks again, and would leave 20,000 frames in the
cache behind it.

So the per-trial caches declare a ceiling. The number is not the point — that it
is finite is.
"""

from __future__ import annotations

import pytest

from scanpath_studio import data as data_module

#: Cached functions whose key includes a single trial's frames.
PER_TRIAL_CACHES = [
    "_compute_word_metrics_cached",
    "_preprocess_fixation_stage_cached",
]


@pytest.mark.parametrize("name", PER_TRIAL_CACHES)
def test_the_cache_is_bounded(name):
    cached = getattr(data_module, name)
    assert cached._info.max_entries is not None, (
        f"{name} is keyed per trial, so an unbounded cache grows with the "
        "export instead of with the app"
    )


@pytest.mark.parametrize("name", PER_TRIAL_CACHES)
def test_the_bound_still_covers_ordinary_browsing(name):
    """Small enough to bound an export, big enough that stepping back and forth
    through a few dozen trials still hits."""
    assert 32 <= getattr(data_module, name)._info.max_entries <= 512
