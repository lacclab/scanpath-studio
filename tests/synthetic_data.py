"""Re-export the synthetic ground-truth trial from the package.

The dataset lives in ``scanpath_studio.synthetic``, a single source of truth
shared by the test suite and the in-app "Synthetic test trial" data source.
This module lets tests import it as ``tests.synthetic_data``.
"""

from __future__ import annotations

from scanpath_studio.synthetic import (
    EXPECTED,
    PARAGRAPH,
    PARTICIPANT,
    TRIAL,
    make_synthetic_fixations,
    make_synthetic_words,
)

__all__ = [
    "EXPECTED",
    "PARAGRAPH",
    "PARTICIPANT",
    "TRIAL",
    "make_synthetic_fixations",
    "make_synthetic_words",
]
