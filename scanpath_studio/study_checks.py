"""Compare a lab's planned readings and file mappings with the recordings."""

from __future__ import annotations

import pandas as pd

from .data import time_unit_ms, trial_keys

_READING = ["participant_id", "trial_id"]


def inclusion_report(
    words, fixations, kept, steps
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Count the actual pool once, and evaluate each individual rule on the full study."""
    all_keys = trial_keys(words) | trial_keys(fixations)
    excluded = all_keys - kept
    reasons = {key: [] for key in excluded}
    for label, decide, _ in steps:
        w, f = decide(words, fixations)
        for key in excluded - trial_keys(w) - trial_keys(f):
            reasons[key].append(label)
    report = pd.DataFrame(
        [
            [
                p,
                t,
                (p, t) in kept,
                " · ".join(reasons.get((p, t), []))
                or ("Other active selection" if (p, t) in excluded else ""),
            ]
            for p, t in sorted(all_keys)
        ],
        columns=[*_READING, "included", "exclusion_reasons"],
    )
    participants = {p for p, _ in all_keys}
    included = {p for p, _ in kept}
    summary = pd.DataFrame(
        [
            ["Total", len(participants), len(all_keys)],
            ["Included", len(included), len(kept)],
            ["Excluded entirely", len(participants - included), len(excluded)],
        ],
        columns=["population", "participants", "readings"],
    )
    return summary, report


def reconcile_run_sheet(
    expected: pd.DataFrame, tables: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Expected and extra reading keys, with the layers actually received."""
    if not set(_READING) <= set(expected):
        raise ValueError("The run sheet needs participant_id and trial_id columns.")
    expected = expected.copy()
    for name in [*_READING, "screen_id", "planned_omission"]:
        expected[name] = (
            expected[name].fillna("").astype(str) if name in expected else ""
        )
    if expected[_READING].eq("").any(axis=None):
        raise ValueError(
            "Each planned reading needs both a participant ID and a trial ID."
        )
    keys = [*_READING, "screen_id"]
    if (expected.groupby(keys, dropna=False)["planned_omission"].nunique() > 1).any():
        raise ValueError(
            "Two rows for the same reading disagree about its planned omission."
        )
    planned = dict(
        zip(
            expected[keys].itertuples(index=False, name=None),
            expected["planned_omission"],
        )
    )
    received = {}
    for name, frame in tables.items():
        if frame is None or frame.empty or not set(_READING) <= set(frame):
            continue
        id_cols = [c for c in keys if c in frame]
        ids = (
            frame[id_cols]
            .drop_duplicates()
            .dropna(subset=_READING)
            .fillna("")
            .astype(str)
        )
        if "screen_id" not in ids:
            ids["screen_id"] = ""
        for key in ids[keys].itertuples(index=False, name=None):
            received.setdefault(key, set()).add(name)
    parents = {}
    for (p, t, _), layers in received.items():
        parents.setdefault((p, t), set()).update(layers)
    planned_parents = {k[:2] for k in planned}
    rows = []
    for key in sorted(planned.keys() | received.keys()):
        p, t, screen = key
        if screen and key not in planned and (p, t, "") in planned:
            continue
        layers = received.get(key, set()) if screen else parents.get((p, t), set())
        omission = planned.get(key, "")
        if not screen and key not in planned and (p, t) in planned_parents:
            status = "Screen unspecified"
            layers = received[key]
        elif key not in planned:
            status = "Unscheduled"
        elif omission and layers:
            status = "Received despite planned omission"
        elif omission:
            status = "Planned omission"
        elif not layers:
            status = "Missing"
        elif layers == {"raw_gaze"}:
            status = "Raw gaze only"
        else:
            status = "Received"
        rows.append([*key, status, ", ".join(sorted(layers)), omission])
    return pd.DataFrame(rows, columns=[*keys, "status", "tables", "planned_omission"])


def compare_file_mapping(filename, header, mapping: dict) -> list[dict]:
    """Report mapped input names missing from this file, including time-unit changes."""
    import re

    def base(name):
        return re.sub(r"\s*[\[(][^\[\]()]*[\])]\s*$", "", name).strip().casefold()

    rows = []
    for field, mapped in mapping.items():
        names = mapped if isinstance(mapped, list) else [mapped]
        for name in names:
            if not isinstance(name, str) or name in header:
                continue
            candidates = [
                c for c in header if isinstance(c, str) and base(c) == base(name)
            ]
            other = candidates[0] if len(candidates) == 1 else ""
            detail = "Mapped header missing"
            if (
                other
                and field in ("duration", "timestamp")
                and time_unit_ms(other) != time_unit_ms(name)
            ):
                detail = f"Changed time unit. Import {other} separately to convert by ×{time_unit_ms(other):g} to milliseconds."
            rows.append(
                dict(
                    file=filename,
                    field=field,
                    mapped_header=name,
                    possible_header=other,
                    finding=detail,
                )
            )
    return rows
