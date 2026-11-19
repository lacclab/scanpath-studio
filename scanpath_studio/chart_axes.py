"""Coordinates shared by fixation charts and their raw-gaze layer."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data import TIMESTAMP_SYNTHESIZED, assign_derived

# This axis is computed on a complete reading, before selecting a screen or window.
ELAPSED = "@elapsed_seconds"
ELAPSED_LABEL = "Seconds since first fixation onset"
POSITION_FIELDS = ("x", "y")
CLOCK_FIELDS = ("timestamp_ms", ELAPSED)


_ORIGIN = "_sps_first_recorded_onset_ms"


def recorded_onsets(fixations: pd.DataFrame) -> pd.Series:
    """Read only finite, measured onsets, preserving row alignment."""
    onset = pd.to_numeric(fixations["timestamp_ms"], errors="coerce")
    missing = ~np.isfinite(onset)
    if TIMESTAMP_SYNTHESIZED in fixations:
        missing |= fixations[TIMESTAMP_SYNTHESIZED].fillna(False)
    return onset.mask(missing)


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
    allowed = {*POSITION_FIELDS, *CLOCK_FIELDS}
    return all(
        field in allowed and ("timestamp_ms" if field == ELAPSED else field) in raw
        for field in fields
    )
