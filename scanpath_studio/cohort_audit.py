"""Local evidence behind a cohort profile and comparisons of two revisions."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from .aggregation import MEASURES
from .analysis_recipe import jsonable

_KIND = "scanpath-studio/cohort-snapshot"
_KEYS = ("participant_id", "trial_id", "screen_id", "word_id")


def _cell(value):
    if pd.isna(value):
        return None
    if isinstance(value, (float, np.floating)) and not np.isfinite(value):
        return str(value)
    return jsonable(value)


def _records(table):
    return [
        {column: _cell(value) for column, value in zip(table.columns, row)}
        for row in table.itertuples(index=False, name=None)
    ]


def profile_snapshot(
    rows: pd.DataFrame, table: pd.DataFrame, csv: bytes, choices: dict
) -> dict:
    """A data-bearing snapshot, written separately from the portable analysis recipe."""
    return {
        "kind": _KIND,
        "version": 1,
        "choices": jsonable(choices),
        "observations": _records(rows),
        "profile": _records(table),
        "csv_sha256": hashlib.sha256(csv).hexdigest(),
    }


def compare_profiles(before: dict, after: dict) -> tuple[pd.DataFrame, str]:
    """Compare observations at their recorded grain, ignoring source row order."""

    def group(snapshot):
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("kind") != _KIND
            or snapshot.get("version") != 1
        ):
            raise ValueError("Choose a version 1 Scanpath Studio cohort snapshot.")
        rows = snapshot.get("observations")
        if not isinstance(rows, list) or not isinstance(snapshot.get("profile"), list):
            raise ValueError(
                "The snapshot is missing its observation or profile table."
            )
        values = {}
        for row in rows:
            if (
                not isinstance(row, dict)
                or not {"participant_id", "word_id", "value"} <= row.keys()
            ):
                raise ValueError(
                    "A snapshot observation is missing its reader, word or value."
                )
            key = tuple(row.get(k) for k in _KEYS)
            if any(type(part) not in (str, int, float, type(None)) for part in key):
                raise ValueError("A snapshot reading or word has an invalid ID.")
            values.setdefault(key, []).append(
                {k: v for k, v in row.items() if k not in _KEYS}
            )
        for observations in values.values():
            observations.sort(key=lambda row: json.dumps(row, sort_keys=True))
        return values

    old, new = group(before), group(after)
    changes = []
    for key in sorted(old.keys() | new.keys(), key=str):
        left, right = old.get(key), new.get(key)
        if left != right:
            change = (
                "added" if left is None else "removed" if right is None else "changed"
            )
            changes.append(
                {
                    **dict(zip(_KEYS, key)),
                    "change": change,
                    "before": left,
                    "after": right,
                }
            )
    notes = []
    if before.get("choices") != after.get("choices"):
        notes.append("The analysis choices differ.")
    if before["profile"] != after["profile"]:
        notes.append("The published profile rows differ.")
    elif before.get("csv_sha256") != after.get("csv_sha256"):
        notes.append("The CSV bytes changed while the profile values stayed the same.")
    else:
        notes.append("The published CSV is identical.")
    return pd.DataFrame(changes), " ".join(notes)


def profile_methods(recipe: dict) -> str:
    """Editable methods for a cohort profile, with the corresponding recipe fields."""
    a = recipe["analysis"]
    m = MEASURES[a["measure"]["key"]]
    text = a["text"]["id"]
    screen = f", screen {a['screen']}" if a.get("screen") is not None else ""
    agg = a["aggregation"]
    unit = m.unit or ("proportion" if m.is_rate else "count")
    conditions = []
    for rule in recipe.get("trial_filters", []):
        values = rule.get("values", rule.get("range", []))
        chosen = ", ".join(map(str, values))
        condition = f"{rule['field']} ({chosen})"
        if rule.get("unknown"):
            condition += f", unknown values {rule['unknown']}"
        conditions.append(condition)
    filters = " and ".join(conditions) if conditions else "the full trial pool"
    return (
        "\n".join(
            [
                f"The profile for text {text}{screen} was produced with Scanpath Studio {recipe['app']['version']}. [analysis.text, analysis.screen, app.version]",
                f"The measure was {m.label} ({unit}). Normalization was {a['normalization']}. [analysis.measure, analysis.normalization]",
                f"For each word we used the {agg} across a participant's finite observations and then the {agg} across those participants. [analysis.aggregation]",
                f"Words required at least {a['min_readers']} contributing participants. The spread shown was {a['spread']}. [analysis.min_readers, analysis.spread]",
                f"The analysis used {filters}. [trial_filters]",
                "Add the sampling procedure, study design and rationale for exclusions before submission.",
            ]
        )
        + "\n"
    )
