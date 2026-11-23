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


# Recognized fields whose units are specified by the normalized schema.
COMPARISON_FIELDS = frozenset(
    (
        *POSITION_FIELDS,
        *CLOCK_FIELDS,
        "order_in_trial",
        "order_in_screen",
        "duration_ms",
        "fixation_id",
        SAMPLE_INDEX,
    )
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


#: What numbers a sample: its reading, screen and eye, where the table has them.
_SAMPLE_GROUPS = ("participant_id", "trial_id", "screen_id", "eye")


def with_sample_index(samples: pd.DataFrame | None) -> pd.DataFrame | None:
    """``samples`` with each one's ``sample_index`` for a chart axis.

    Samples imported without a clock already carry it. Otherwise each sample
    is numbered 1, 2, … within its reading, screen and eye, in the order it
    was recorded: by its timestamp, a tie or a missing one keeping table order.
    Every sample is counted, including those without a gaze position."""
    if samples is None or samples.empty or SAMPLE_INDEX in samples:
        return samples
    if "timestamp_ms" in samples:
        clock = pd.to_numeric(samples["timestamp_ms"], errors="coerce").to_numpy(
            dtype=float
        )
        order = np.argsort(clock, kind="stable")  # missing times sort last
    else:
        order = np.arange(len(samples))
    recorded = samples.iloc[order]
    keys = [key for key in _SAMPLE_GROUPS if key in recorded]
    counts = (
        recorded.groupby(keys, sort=False, dropna=False).cumcount().to_numpy() + 1
        if keys
        else np.arange(1, len(recorded) + 1)
    )
    number = np.empty(len(samples), dtype=np.int64)
    number[order] = counts
    return samples.assign(**{SAMPLE_INDEX: number})


def comparison_coordinates(
    fixations: pd.DataFrame, samples: pd.DataFrame | None, fields: tuple[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Materialize a reading's recorded clock before combining its rows with another."""
    if SAMPLE_INDEX in fields:
        samples = with_sample_index(samples)
    if not any(field in CLOCK_FIELDS for field in fields):
        return fixations, samples
    if ELAPSED in fields and ELAPSED in fixations:
        # Already projected before concatenation, when the parent origin was available.
        return fixations, samples
    origin = origin_ms(fixations)
    if "timestamp_ms" in fixations:
        onsets = recorded_onsets(fixations)
        fixations = fixations.assign(timestamp_ms=onsets)
        if ELAPSED in fields:
            fixations[ELAPSED] = (onsets - origin) / 1000
    if ELAPSED in fields and samples is not None and "timestamp_ms" in samples:
        samples = samples.assign(**{ELAPSED: (samples["timestamp_ms"] - origin) / 1000})
    return fixations, samples


def has_word_boxes(words: pd.DataFrame | None) -> bool:
    """Whether any word has a drawable rectangle in recorded screen coordinates."""
    fields = ("x", "y", "width", "height")
    if words is None or words.empty or not all(f in words for f in fields):
        return False

    def valid(values):
        return (np.abs(values) <= DRAWABLE_PX_LIMIT).all(axis=-1) & (
            values[..., 2:] > 0
        ).all(axis=-1)

    boxes = words.loc[:, list(fields)]
    if valid(pd.to_numeric(boxes.iloc[0], errors="coerce").to_numpy(dtype=float)):
        return True
    return bool(
        valid(boxes.apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)).any()
    )


def drawable_fixations(fields: tuple[str, str], fixations: pd.DataFrame | None) -> bool:
    """Can this reading place a fixation on both selected axes?"""
    if fixations is None or fixations.empty:
        return False
    axes = []
    for field in fields:
        if field in CLOCK_FIELDS and ELAPSED not in fixations:
            if "timestamp_ms" not in fixations:
                return False
            values = recorded_onsets(fixations)
        elif field in fixations:
            values = pd.to_numeric(fixations[field], errors="coerce")
        else:
            return False
        valid = np.isfinite(values)
        if field in POSITION_FIELDS:
            valid &= values.abs() <= DRAWABLE_PX_LIMIT
        axes.append(valid)
    return bool((axes[0] & axes[1]).any())


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
