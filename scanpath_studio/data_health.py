"""Values that parsed as numbers but cannot be what they claim to be.

The load already reports cells that are not numbers at all
(`data.numeric_parse_issues`) and trial ids that merge several readings
(`data.diagnose_trial_identity`). A value can pass both and still be unusable:
a fixation lasting −40 ms, a gaze position at infinity, a word box with no
width. Nothing here changes or drops a row — each check counts the rows, names
the columns they came from, shows a few, and says what the app does with them,
so the researcher can decide.

Pure (no Streamlit): the 🗂️ Data page draws :func:`check_data_health` through a
cached wrapper, and `api.check_data_health` returns the same findings as a table.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .multipart import SCREEN_ID

#: How many offending rows a finding quotes.
EXAMPLE_ROWS = 3

#: The identity a quoted example row is shown with, when the table has it.
_EXAMPLE_KEYS = ("participant_id", "trial_id", SCREEN_ID)


@dataclass(frozen=True)
class HealthFinding:
    """One check that found rows: how many, where, and what happens to them."""

    check: str
    table: str
    title: str
    columns: tuple[str, ...]
    rows: int
    total_rows: int
    trials: int
    breakdown: dict[str, int] = field(default_factory=dict)
    examples: tuple[dict, ...] = ()
    consequence: str = ""
    #: ``"warning"``, or ``"note"`` for what is ordinary in such data (raw-gaze
    #: samples whose only gap is a missing position: blinks, track loss).
    severity: str = "warning"

    def to_record(self) -> dict:
        """A flat row for a table (`api.check_data_health`)."""
        return {
            "table": self.table,
            "check": self.check,
            "problem": self.title,
            "columns": ", ".join(self.columns),
            "rows": self.rows,
            "of_rows": self.total_rows,
            "trials": self.trials,
            "severity": self.severity,
            "breakdown": ", ".join(f"{n:,} {k}" for k, n in self.breakdown.items()),
            "what_happens": self.consequence,
            "examples": list(self.examples),
        }


@dataclass(frozen=True)
class _Check:
    key: str
    table: str
    title: str
    columns: tuple[str, ...]
    #: ``frame → {label: mask}``; the finding's rows are their union.
    masks: Callable[[pd.DataFrame], dict[str, pd.Series]]
    consequence: str


def _number(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").astype(float)


def _duration_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    duration = _number(frame, "duration_ms")
    return {"negative": duration < 0, "zero": duration == 0}


def _timing_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    duration, onset = _number(frame, "duration_ms"), _number(frame, "timestamp_ms")
    return {"infinite duration": np.isinf(duration), "infinite onset": np.isinf(onset)}


def _canvas_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    width, height = _number(frame, "canvas_width"), _number(frame, "canvas_height")
    infinite = np.isinf(width) | np.isinf(height)
    return {
        "infinite": infinite,
        "0 or less": ((width <= 0) | (height <= 0)) & ~infinite,
    }


def _position_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    xs, ys = _number(frame, "x"), _number(frame, "y")
    infinite = np.isinf(xs) | np.isinf(ys)
    return {"infinite": infinite, "missing": (xs.isna() | ys.isna()) & ~infinite}


def _box_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    width, height = _number(frame, "width"), _number(frame, "height")
    xs, ys = _number(frame, "x"), _number(frame, "y")
    return {
        "width ≤ 0": width <= 0,
        "height ≤ 0": height <= 0,
        "infinite size": np.isinf(width) | np.isinf(height),
        "infinite position": np.isinf(xs) | np.isinf(ys),
    }


#: What a per-screen screen size the figure cannot use does, on either table.
_CANVAS_CONSEQUENCE = (
    "They stay in every table and export. The figure ignores a screen size that "
    "is not one finite, positive number per screen, and draws that screen at the "
    "size it uses when there is none: the Recording setup in the app, the size "
    "given or one fitted to the data in the API and on the command line."
)


#: The checks, in the order they are reported. Each consequence is what the
#: app does with those rows today: none of them is removed from a table.
CHECKS: tuple[_Check, ...] = (
    _Check(
        "fixation_duration",
        "fixations",
        "Fixations lasting 0 ms or less",
        ("duration_ms",),
        _duration_masks,
        "They stay in every table and export, and are counted at their value "
        "wherever durations are summed (reading time, dwell). The plot draws them "
        "at the smallest marker size. A blank or unreadable duration cell also "
        "loads as 0 ms.",
    ),
    _Check(
        "fixation_timing",
        "fixations",
        "Fixations with an infinite duration or onset",
        ("duration_ms", "timestamp_ms"),
        _timing_masks,
        "They stay in every table and export, and an infinite duration makes "
        "every sum it enters infinite (reading time, dwell). The figure draws it "
        "at the smallest marker size and the replay counts it as 0 ms; a trial "
        "with an infinite onset draws that fixation last, and its replay is "
        "timed by the fixation durations instead of the onsets.",
    ),
    _Check(
        "fixation_position",
        "fixations",
        "Fixations with no finite position",
        ("x", "y"),
        _position_masks,
        "They stay in every table and export, but the plot cannot place them: "
        "their marker, and the saccades to and from them, are left out of the "
        "figure. A missing position is one neither the data nor the fixated "
        "word's box could supply.",
    ),
    _Check(
        "raw_gaze_position",
        "raw_gaze",
        "Raw-gaze samples with no finite position",
        ("x", "y"),
        _position_masks,
        "They stay in the table and its export; the raw-gaze layer leaves them "
        "out. Missing positions are usual in sample data (blinks, track loss).",
    ),
    _Check(
        "word_box_size",
        "words",
        "Word boxes with no area or no finite position",
        ("x", "y", "width", "height"),
        _box_masks,
        "They stay in every table and export. A box with no area holds no "
        "fixation, so fixations reach such a word only through the data's own "
        "word ids, and the box draws as a line or not at all; a box with an "
        "infinite size or position is left out of the figure.",
    ),
    _Check(
        "word_canvas",
        "words",
        "Word rows with an unusable screen size",
        ("canvas_width", "canvas_height"),
        _canvas_masks,
        _CANVAS_CONSEQUENCE,
    ),
    _Check(
        "fixation_canvas",
        "fixations",
        "Fixations with an unusable screen size",
        ("canvas_width", "canvas_height"),
        _canvas_masks,
        _CANVAS_CONSEQUENCE,
    ),
)


def _examples(frame: pd.DataFrame, mask: pd.Series, columns, n: int) -> tuple:
    keys = [c for c in _EXAMPLE_KEYS if c in frame.columns]
    shown = frame.loc[mask, [*keys, *columns]].head(n)
    return tuple(shown.to_dict("records"))


def check_data_health(
    words: pd.DataFrame | None,
    fixations: pd.DataFrame | None,
    raw_gaze: pd.DataFrame | None = None,
    *,
    examples: int = EXAMPLE_ROWS,
) -> list[HealthFinding]:
    """Run every check on the normalized tables; return the ones that found rows.

    Reads the canonical columns (``duration_ms``, ``x``/``y``, ``width``/
    ``height``) and changes nothing. A table without a check's columns is not
    checked. Each finding names its rows, the trials they fall in (by
    participant and trial), a breakdown by kind, ``examples`` rows with their
    identity, and what the app does with them.
    """
    frames = {"words": words, "fixations": fixations, "raw_gaze": raw_gaze}
    findings: list[HealthFinding] = []
    for check in CHECKS:
        frame = frames[check.table]
        if frame is None or frame.empty:
            continue
        if any(c not in frame.columns for c in check.columns):
            continue
        masks = {k: m.fillna(False) for k, m in check.masks(frame).items()}
        union = pd.Series(False, index=frame.index)
        for mask in masks.values():
            union |= mask
        rows = int(union.sum())
        if not rows:
            continue
        trial_keys = [c for c in ("participant_id", "trial_id") if c in frame.columns]
        trials = (
            len(frame.loc[union, trial_keys].drop_duplicates()) if trial_keys else 0
        )
        breakdown = {k: int(m.sum()) for k, m in masks.items() if m.any()}
        ordinary = check.table == "raw_gaze" and set(breakdown) == {"missing"}
        findings.append(
            HealthFinding(
                check=check.key,
                table=check.table,
                title=check.title,
                columns=check.columns,
                rows=rows,
                total_rows=len(frame),
                trials=trials,
                breakdown=breakdown,
                examples=_examples(frame, union, check.columns, examples),
                consequence=check.consequence,
                severity="note" if ordinary else "warning",
            )
        )
    return findings


def findings_frame(findings: list[HealthFinding]) -> pd.DataFrame:
    """The findings as one row each (empty, with the columns, when none)."""
    columns = list(HealthFinding("", "", "", (), 0, 0, 0).to_record())
    return pd.DataFrame([f.to_record() for f in findings], columns=columns)
