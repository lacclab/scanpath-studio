"""Coordinates shared by fixation charts and their raw-gaze layer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .constants import DRAWABLE_PX_LIMIT, SAMPLE_INDEX
from .data import assign_derived, synthesized_onset_mask

# This axis is computed on a complete reading, before selecting a screen or window.
ELAPSED = "@elapsed_seconds"
ELAPSED_LABEL = "Seconds since first fixation onset"
GAZE_OVER_TIME = (ELAPSED, "x")
POSITION_FIELDS = ("x", "y")
CLOCK_FIELDS = ("timestamp_ms", ELAPSED)
SAMPLE_FIELDS = (
    *POSITION_FIELDS,
    "timestamp_ms",
    SAMPLE_INDEX,
    "pupil_area",
    "pupil_diameter",
)


_ORIGIN = "_sps_first_recorded_onset_ms"


def recorded_onsets(fixations: pd.DataFrame) -> pd.Series:
    """Read only finite, measured onsets, preserving row alignment."""
    onset = pd.to_numeric(fixations["timestamp_ms"], errors="coerce")
    return onset.mask(synthesized_onset_mask(fixations))


def has_clock(fixations: pd.DataFrame) -> bool:
    return "timestamp_ms" in fixations and bool(
        recorded_onsets(fixations).notna().any()
    )


def origin_ms(fixations: pd.DataFrame) -> float:
    if _ORIGIN in fixations.attrs:
        return fixations.attrs[_ORIGIN]
    return recorded_onsets(fixations).min() if "timestamp_ms" in fixations else np.nan


def with_origin(fixations: pd.DataFrame) -> pd.DataFrame:
    """Keep the complete reading's time origin through screen and window selection."""
    view = fixations.copy(deep=False)
    view.attrs[_ORIGIN] = origin_ms(fixations)
    assign_derived(view, "reading_time_origin", fixations)
    return view


def position_chart(fields: tuple[str, str], along: str) -> bool:
    return along in fields and any(field in POSITION_FIELDS for field in fields)


def raw_axes_available(fields: tuple[str, str], raw: pd.DataFrame | None) -> bool:
    if raw is None or raw.empty:
        return False
    allowed = {*SAMPLE_FIELDS, ELAPSED}
    return all(
        field in allowed and ("timestamp_ms" if field == ELAPSED else field) in raw
        for field in fields
    )


def drawable_raw_samples(
    fields: tuple[str, str],
    raw: pd.DataFrame | None,
    fixations: pd.DataFrame | None = None,
) -> bool:
    """Whether the figure can place at least one sample on these axes."""
    if not raw_axes_available(fields, raw):
        return False
    if ELAPSED in fields and (
        fixations is None or not np.isfinite(origin_ms(fixations))
    ):
        return False
    x, y = ("timestamp_ms" if field == ELAPSED else field for field in fields)
    x_limit, y_limit = (
        DRAWABLE_PX_LIMIT if field in POSITION_FIELDS else np.inf for field in fields
    )
    # Normalized recordings usually answer from their first sample.
    first = pd.to_numeric([raw[x].iat[0], raw[y].iat[0]], errors="coerce")
    if np.isfinite(first).all() and (np.abs(first) <= (x_limit, y_limit)).all():
        return True
    xs, ys = (pd.to_numeric(raw[c], errors="coerce") for c in (x, y))
    return bool(
        (
            np.isfinite(xs)
            & np.isfinite(ys)
            & xs.abs().le(x_limit)
            & ys.abs().le(y_limit)
        ).any()
    )
