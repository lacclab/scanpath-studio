"""AN-34: the analysis recipe — how one Corpus Analysis table was made.

A small JSON file downloaded beside each Corpus Analysis table. It records what
the table cannot say about itself: the app version, the dataset it was read
from, the trial filters that shaped the pool, the analysis choices (text,
screen, measure, aggregation, normalization, spread, minimum readers, group
definitions) and the counts behind the result.

It **references** the dataset by name and never embeds it: no table rows, and
no annotation notes (a *Favorites only* or tag filter is recorded as the filter
it is, not as the annotations behind it). Filters and figure settings are kept
apart on purpose — this file holds the filters and no styling; the figure
settings file (🔗 Share → File) holds styling and no filters — so the recipe
says so in ``excludes`` rather than leaving a reader to guess.

It describes the current analysis only. There is no runner and no workspace
format: nothing reads a recipe back.

Pure — no Streamlit; ``tabs._download_tidy`` assembles the inputs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

#: What a recipe is, so a script can tell it from the figure settings file.
RECIPE_KIND = "scanpath-studio/analysis-recipe"
#: Bumped when a field changes meaning; adding a field does not bump it.
RECIPE_VERSION = 1

#: What the recipe deliberately leaves out, written into every one.
EXCLUDES = {
    "figure_settings": (
        "Palette, canvas and fonts are not recorded here. Save them with "
        "Share → File, which holds no trial filters."
    ),
    "data": (
        "No table rows and no annotation notes. The dataset is referenced by "
        "name and must be loaded to repeat the analysis."
    ),
}


def jsonable(value: Any) -> Any:
    """``value`` with sets, tuples and numpy scalars made JSON-native.

    Sets are sorted (by their text) so the same analysis writes the same file.
    """
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return [jsonable(v) for v in sorted(value, key=str)]
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.ndarray, pd.Index, pd.Series)):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def group_definition(label: str, spec: Mapping | None) -> dict:
    """One cohort as ``{"label", "constraints"}`` — the spec the views used.

    ``spec`` is ``aggregation.group_mask``'s ``{column: allowed values}``; a
    composite key (a trial-metadata cohort's ``(participant_id, trial_id)``)
    keeps its columns as a list. An empty spec is the whole pool.
    """
    constraints = [
        {
            "field": list(col) if isinstance(col, tuple) else str(col),
            "values": jsonable(values),
        }
        for col, values in (spec or {}).items()
        if values is not None
    ]
    return {"label": str(label), "constraints": constraints}


def analysis_choices(
    *,
    section: str | None = None,
    view: str | None = None,
    text: tuple[str, Any] | None = None,
    screen: Any = None,
    reader: Any = None,
    measure: Any = None,
    measures: Sequence[Any] | None = None,
    aggregation: str | None = None,
    normalize: bool | None = None,
    spread: str | None = None,
    min_readers: int | None = None,
    feature: str | None = None,
    x_axis: str | None = None,
    groups: Sequence[dict] | None = None,
) -> dict:
    """The choices that made one table, with what does not apply left out.

    ``measure`` is an ``aggregation.Measure`` (anything with ``key`` / ``label``
    / ``is_rate``). ``normalize`` is recorded as it was *applied*: the
    aggregation helpers never z-score a 0–1 rate, so a rate reads ``none``
    whatever the toggle says.
    """
    out: dict = {}
    if section:
        out["section"] = section
    if view:
        out["view"] = view
    if text is not None:
        out["text"] = {"field": str(text[0]), "id": jsonable(text[1])}
    if screen is not None:
        out["screen"] = jsonable(screen)
    if reader is not None:
        out["reader"] = jsonable(reader)
    if measure is not None:
        out["measure"] = {"key": measure.key, "label": measure.label}
    if measures:
        out["measures"] = [{"key": m.key, "label": m.label} for m in measures]
    if aggregation:
        out["aggregation"] = aggregation
    if normalize is not None:
        rate = bool(getattr(measure, "is_rate", False))
        out["normalization"] = (
            "z-score within reader" if normalize and not rate else "none"
        )
    if spread:
        out["spread"] = spread
    if min_readers is not None:
        out["min_readers"] = int(min_readers)
    if feature:
        out["feature"] = feature
    if x_axis:
        out["x_axis"] = x_axis
    if groups:
        out["groups"] = list(groups)
    return out


def result_counts(table: pd.DataFrame | None, extra: Mapping | None = None) -> dict:
    """What the table itself says about its size: rows, and readers when it
    names them. ``extra`` adds counts the view already computed (a cohort's
    readers and fixations), never recomputed here."""
    out: dict = {"rows": 0 if table is None else len(table)}
    if table is not None and "participant_id" in table.columns:
        out["readers"] = int(table["participant_id"].astype(str).nunique())
    if extra:
        out.update(jsonable(dict(extra)))
    return out


def build_analysis_recipe(
    *,
    app_version: str,
    dataset: Mapping,
    trial_filters: Sequence[Mapping],
    pool: Mapping,
    analysis: Mapping,
    table_file: str,
    counts: Mapping,
    exported_at: str | None = None,
) -> dict:
    """The recipe for one Corpus Analysis table.

    ``trial_filters`` is ``controls.active_filter_items`` — one
    ``{"field", "values" | "range"}`` entry per filter narrowing the pool; an
    empty list is an unfiltered pool. ``pool`` holds its trial and reader
    counts against the dataset's.
    """
    recipe = {
        "kind": RECIPE_KIND,
        "version": RECIPE_VERSION,
        "app": {"name": "Scanpath Studio", "version": str(app_version)},
        "exported_at": exported_at,
        "dataset": jsonable(dict(dataset)),
        "trial_filters": [
            {
                k: jsonable(v)
                for k, v in item.items()
                if k in ("field", "values", "range")
            }
            for item in trial_filters
        ],
        "pool": jsonable(dict(pool)),
        "analysis": jsonable(dict(analysis)),
        "result": {"file": table_file, **jsonable(dict(counts))},
        "excludes": dict(EXCLUDES),
    }
    if exported_at is None:
        del recipe["exported_at"]
    return recipe


def recipe_file_name(table_file: str) -> str:
    """``cohort_profile_tfd_3.csv`` → ``cohort_profile_tfd_3.recipe.json``."""
    stem = table_file[:-4] if table_file.lower().endswith(".csv") else table_file
    return f"{stem}.recipe.json"
