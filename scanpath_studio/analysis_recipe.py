"""The analysis recipe — how one Corpus Analysis table was made.

A small JSON file downloaded beside each Corpus Analysis table. It records what
the table cannot say about itself: the app version, the dataset it was read
from, the trial filters that shaped the pool, the analysis choices (text,
screen, measure, aggregation, normalization, spread, minimum readers, group
definitions) and the counts behind the result.

It **references** the dataset by name and never embeds it: no table rows, and
no annotation notes (a *Favorites only* or tag filter is recorded as the filter
it is, not as the annotations behind it). Filters and figure settings are kept
apart on purpose — this file holds the filters and no styling; the figure
settings file (🔗 Share → Settings file) holds styling and no filters — so the recipe
says so in ``excludes`` rather than leaving a reader to guess.

Overview tables and word profiles can be rerun with the original data and filter inputs.

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

OVERVIEW_VIEW = "Mean and range"
REPLAYABLE_VIEWS = (
    ("Overview", OVERVIEW_VIEW),
    ("Per text", "Cohort profile"),
    ("Groups", "Difference word profile"),
)

#: What the recipe deliberately leaves out, written into every one.
EXCLUDES = {
    "figure_settings": (
        "Palette, canvas and fonts are in the settings file (Scanpath → "
        "Share → Settings file). That file has no trial filters."
    ),
    "data": (
        "The recipe has no table rows or annotation notes. It names the "
        "dataset, which must be loaded to repeat the analysis."
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
    group_by: str | None = None,
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
    if group_by:
        out["group_by"] = group_by
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
            "z-score per participant" if normalize and not rate else "none"
        )
    if spread:
        from .aggregation import effective_spread

        out["spread"] = effective_spread(spread, aggregation)
        if out["spread"] != spread:
            out["requested_spread"] = spread
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
    selection: Mapping | None = None,
    inputs: Mapping | None = None,
) -> dict:
    """The recipe for one Corpus Analysis table.

    ``trial_filters`` is ``controls.active_filter_items`` — one
    ``{"field", "values" | "range"}`` entry per filter narrowing the pool (a
    range also carries ``"unknown": "kept" | "excluded"`` — what it does with
    the records that have no value); an
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
                if k in ("field", "values", "range", "unknown")
            }
            for item in trial_filters
        ],
        "pool": jsonable(dict(pool)),
        "analysis": jsonable(dict(analysis)),
        "result": {"file": table_file, **jsonable(dict(counts))},
        "excludes": dict(EXCLUDES),
    }
    if inputs is not None:
        recipe["inputs"] = jsonable(inputs)
    if selection is not None:
        recipe["selection"] = jsonable(selection)
    if exported_at is None:
        del recipe["exported_at"]
    return recipe


def recipe_file_name(table_file: str) -> str:
    """``cohort_profile_tfd_3.csv`` → ``cohort_profile_tfd_3.recipe.json``."""
    stem = table_file[:-4] if table_file.lower().endswith(".csv") else table_file
    return f"{stem}.recipe.json"


def _object(value, what: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ValueError(f"The recipe needs a JSON object for {what}.")
    return value


def _list(value, what: str, *, strings: bool = True) -> list:
    if not isinstance(value, list) or any(
        not isinstance(item, str if strings else (str, int, float, bool))
        for item in value
    ):
        raise ValueError(f"The recipe needs a list of values for {what}.")
    return value


def _predicates(spec: Mapping, field: str) -> tuple[dict, dict]:
    values = {}
    for name, allowed in _object(spec.get(field, {}), field).items():
        values[name] = _list(allowed, name, strings=False)
        if not values[name]:
            raise ValueError(f"The {name!r} filter has no selected values.")
    ranges = {}
    for name, bounds in _object(spec.get("ranges", {}), "ranges").items():
        if not (
            isinstance(bounds, list)
            and len(bounds) == 2
            and all(type(x) in (int, float) and np.isfinite(x) for x in bounds)
            and bounds[0] <= bounds[1]
        ):
            raise ValueError(f"Invalid numeric range for {name!r}.")
        ranges[name] = bounds
    return values, ranges


def _legacy_selection(filters: list) -> dict:
    """Only filter roles with an unambiguous interpretation in older recipes."""
    selection = {}
    annotation = {}
    for rule in filters:
        rule = _object(rule, "trial filter")
        field = rule.get("field")
        if field == "Participant" and set(rule) == {"field", "values"}:
            selection["participants"] = rule["values"]
        elif field == "Favorites only" and set(rule) == {"field"}:
            annotation["favorites_only"] = True
        elif field in ("With any of these tags", "Excluding tags") and set(rule) == {
            "field",
            "values",
        }:
            key = (
                "required_tags"
                if field == "With any of these tags"
                else "excluded_tags"
            )
            annotation[key] = rule["values"]
        else:
            raise ValueError(
                f"This older recipe lists {field!r} without its source field. Download the cohort profile recipe again from Corpus Analysis."
            )
    selection["annotations"] = annotation
    return selection


def _metadata_join_columns(grain, mapping, header):
    canonical = f"{grain}_id"
    if isinstance(mapping, list):
        columns = _list(mapping, f"{grain} metadata ID columns")
        if (
            not columns
            or not all(columns)
            or (grain == "participant" and len(columns) != 1)
        ):
            raise ValueError(f"Invalid ID columns for {grain} metadata.")
    elif isinstance(mapping, str) and mapping:
        columns = [mapping]
        if grain != "participant" and " + " in mapping:
            # Older attachments saved only a display label. A header can itself
            # contain the separator, so splitting it can select a different key.
            parts = mapping.split(" + ")
            composite = all(c in header for c in parts)
            wrapped = f" + {mapping} + "
            nested = any(
                isinstance(c, str)
                and " + " in c
                and c != mapping
                and f" + {c} + " in wrapped
                for c in header
            )
            if sum((mapping in header, composite, canonical in header)) > 1 or nested:
                raise ValueError(
                    f"The older {grain} metadata ID mapping {mapping!r} is ambiguous. "
                    "Reattach the metadata with the original ID columns and download a fresh recipe."
                )
            if composite:
                columns = parts
    else:
        raise ValueError(
            f"The recipe is missing the ID column of its {grain} metadata."
        )
    if all(c in header for c in columns):
        return columns
    if canonical in header:
        return [canonical]
    raise ValueError(f"The {grain} metadata needs its ID columns {columns!r}.")


def _metadata_matches(grain, spec, supplied, words, fixations, raw_gaze):
    from . import api, data
    from . import metadata as md

    if supplied is None:
        raise ValueError(
            f"The recipe requires the {grain} metadata table. Supply --{grain}-metadata."
        )
    mapping = spec.get("id_column")
    reader = spec.get("participant_column")
    if reader is not None and not isinstance(reader, str):
        raise ValueError("Invalid trial metadata participant ID column.")

    def plan(header):
        columns = _metadata_join_columns(grain, mapping, header)
        return data.ReadPlan(
            identity=tuple(
                c for c in header if c in (*columns, "participant_id", reader)
            )
        )

    frame = api._as_dataframe(
        supplied,
        f"{grain} metadata",
        plan_for=plan,
    )
    columns = _metadata_join_columns(grain, mapping, frame.columns)
    values, ranges = _predicates(spec, "values")
    unknown = _object(spec.get("keep_unknown", {}), "keep_unknown")
    if any(type(v) is not bool or k not in ranges for k, v in unknown.items()):
        raise ValueError("Invalid Keep unknown values setting in the recipe.")
    if not (values or ranges):
        raise ValueError(f"The recipe has no predicate for {grain} metadata.")
    kwargs = dict(selections=values, ranges=ranges, keep_unknown=unknown)
    if grain == "participant":
        table = md.build_participant_metadata(
            frame, columns[0], participants=md.participant_ids(words, fixations)
        )
        matches = md.participants_matching(table, **kwargs)
    elif grain == "text":
        col = spec.get("column")
        if col not in ("text_id", "unique_text_id") or col not in {*words, *fixations}:
            raise ValueError("The recipe's text filter needs its text ID column.")
        if spec.get("requires_raw_gaze") and (raw_gaze is None or raw_gaze.empty):
            raise ValueError(
                "This recipe uses text IDs from the Raw gaze table. Supply --raw-gaze."
            )
        readings = md.recording_keys(fixations, words, raw_gaze)
        table = md.build_text_metadata(frame, columns, keys=md.text_keys(readings))
        texts = md.texts_matching(table, **kwargs)
        matches = None if texts is None else md.readings_for_texts(readings, texts)
    else:
        keys = data.trial_keys(words) | data.trial_keys(fixations)
        if reader and reader not in frame:
            if "participant_id" not in frame:
                raise ValueError(
                    f"The trial metadata needs its participant column {reader!r}."
                )
            reader = "participant_id"
        table = md.build_trial_metadata(frame, columns, reader, keys=keys)
        matches = md.trials_matching(table, keys=keys, **kwargs)
    missing = (set(values) | set(ranges)) - set(table.names)
    if missing or matches is None:
        raise ValueError(
            f"The {grain} metadata lacks usable entries for {', '.join(sorted(missing or set(values) | set(ranges)))}."
        )
    return matches


def _select_words(
    words, fixations, selection: Mapping, metadata: Mapping, annotations, raw_gaze=None
):
    from pathlib import Path

    from . import data
    from .annotations import deserialize, select_keys

    known = {
        "participants",
        "conditions",
        "ranges",
        "drop_unknown",
        "metadata",
        "annotations",
        "fixation_fields",
        "word_fields",
    }
    if unknown := set(selection) - known:
        raise ValueError(f"Unsupported recipe filter: {', '.join(sorted(unknown))}.")
    participants = selection.get("participants")
    if participants is not None:
        participants = set(_list(participants, "participants"))
    conditions, ranges = _predicates(selection, "conditions")
    drop_unknown = _list(selection.get("drop_unknown", []), "drop_unknown")
    if set(drop_unknown) - set(ranges):
        raise ValueError("The recipe excludes unknown values for a missing range.")
    for frame, key, flag in (
        (fixations, "fixation_fields", "--fixations"),
        (words, "word_fields", "--words"),
    ):
        required = set(_list(selection.get(key, []), key))
        if missing := required - set(frame if not frame.empty else ()):
            raise ValueError(
                f"Supply {flag} with the filter field(s) {', '.join(sorted(missing))}."
            )
    trial_keys = None
    for grain, spec in _object(selection.get("metadata", {}), "metadata").items():
        if grain not in metadata:
            raise ValueError(f"Unsupported metadata grain {grain!r}.")
        spec = _object(spec, grain)
        matches = _metadata_matches(
            grain, spec, metadata[grain], words, fixations, raw_gaze
        )
        if grain == "participant":
            participants = matches if participants is None else participants & matches
        else:
            trial_keys = matches if trial_keys is None else trial_keys & matches
    if missing := (set(conditions) | set(ranges)) - {*words, *fixations}:
        raise ValueError(
            f"Missing trial filter field(s): {', '.join(sorted(missing))}."
        )
    words, _ = data.filter_trials(
        words, fixations, participants, conditions, ranges, drop_unknown
    )
    if trial_keys is not None:
        words = data.filter_frame_to_keys(words, trial_keys)
    annotation = _object(selection.get("annotations", {}), "annotations")
    if annotation:
        if annotations is None:
            raise ValueError(
                "The recipe requires the dataset's annotations JSON. Supply --annotations."
            )
        if (
            set(annotation) - {"favorites_only", "required_tags", "excluded_tags"}
            or type(annotation.get("favorites_only", False)) is not bool
        ):
            raise ValueError("Invalid annotation filter in the recipe.")
        for key in ("required_tags", "excluded_tags"):
            _list(annotation.get(key, []), key)
        store = deserialize(Path(annotations).read_bytes())
        keys = select_keys(store, list(data.trial_keys(words)), **annotation)
        words = data.filter_frame_to_keys(words, set(keys))
    return words


def _recipe_group(group, words, fixations):
    from .aggregation import resolve_group_spec

    group = _object(group, "group")
    constraints = group.get("constraints")
    if not isinstance(constraints, list):
        raise ValueError("Each group needs a list of constraints.")
    spec = {}
    for constraint in constraints:
        constraint = _object(constraint, "group constraint")
        field = constraint.get("field")
        values = constraint.get("values")
        if isinstance(field, list):
            field = tuple(_list(field, "group ID columns"))
            if (
                not field
                or not isinstance(values, list)
                or any(
                    not isinstance(row, list) or len(row) != len(field)
                    for row in values
                )
            ):
                raise ValueError("Each composite group ID needs one value per column.")
            values = [tuple(_list(row, "group ID", strings=False)) for row in values]
        elif isinstance(field, str) and field:
            values = _list(values, "group values", strings=False)
        else:
            raise ValueError("A group constraint needs a field name.")
        if field in spec:
            raise ValueError(f"Repeated group constraint for {field!r}.")
        spec[field] = values
    result = resolve_group_spec(spec, words, fixations)
    if result.missing:
        raise ValueError(
            f"The group needs fields missing from the source tables: {result.missing}."
        )
    return result.spec


def analysis_recipe_table(
    recipe, words, fixations, *, metadata, annotations, raw_gaze=None
) -> pd.DataFrame:
    """Apply the saved selection and reproduce one published analysis table."""
    from .aggregation import MEASURES, corpus_overview

    recipe = _object(recipe, "recipe")
    if (
        recipe.get("kind") != RECIPE_KIND
        or type(recipe.get("version")) is not int
        or recipe["version"] != RECIPE_VERSION
    ):
        raise ValueError("Unsupported analysis recipe kind or version.")
    a = _object(recipe.get("analysis"), "analysis")
    view = (a.get("section"), a.get("view"))
    if view not in REPLAYABLE_VIEWS:
        raise ValueError(
            "The recipe runner supports Overview, Per text → Cohort profile and Groups → Difference word profile."
        )
    key = _object(a.get("measure"), "measure").get("key")
    measure = MEASURES.get(key) if isinstance(key, str) else None
    if not measure or not measure.per_word or measure.column not in words:
        raise ValueError(
            f"The Words table needs the recipe's mapped reading measure {key!r}."
        )
    filters = recipe.get("trial_filters")
    if not isinstance(filters, list):
        raise ValueError("The recipe needs a trial_filters list.")
    selection = (
        _object(recipe["selection"], "selection")
        if "selection" in recipe
        else _legacy_selection(filters)
    )
    words = _select_words(words, fixations, selection, metadata, annotations, raw_gaze)
    if view == ("Overview", OVERVIEW_VIEW):
        if a.get("aggregation") != "mean" or set(a) - {
            "section",
            "view",
            "aggregation",
            "group_by",
            "measure",
        }:
            raise ValueError(
                "The overview recipe supports the mean of a recorded word measure, grouped by text or participant."
            )
        table = corpus_overview(words, measure, a.get("group_by"))
    else:
        table = _profile_table(a, words, fixations, measure)
    expected = _object(recipe.get("result"), "result").get("rows")
    if type(expected) is not int or expected != len(table):
        raise ValueError(
            f"The analysis produced {len(table)} rows; the recipe records {expected}. Check the input data, mappings and filters."
        )
    return table


# Direct callers of the word-profile runner use this name.
cohort_recipe_table = analysis_recipe_table


def _profile_table(a, words, fixations, measure):
    from .aggregation import (
        cohort_word_profile,
        group_word_difference,
        text_screen_options,
    )

    difference = a["view"] == "Difference word profile"
    text = _object(a.get("text"), "text")
    field, text_id = text.get("field"), text.get("id")
    if (
        not isinstance(field, str)
        or field not in words
        or not isinstance(text_id, (str, int, float))
    ):
        raise ValueError(
            "The recipe needs a text ID and its matching column in the Words table."
        )
    agg, spread, norm, minimum = (
        a.get(k) for k in ("aggregation", "spread", "normalization", "min_readers")
    )
    if difference:
        if norm not in (None, "none") or spread is not None:
            raise ValueError(
                "Difference word profiles use unnormalized group values and have no spread band."
            )
        norm = "none"
    if agg not in ("mean", "median", "sum") or (
        not difference
        and spread
        not in (
            "SD",
            "SEM",
            "IQR",
            "Bootstrap CI",
        )
    ):
        raise ValueError(
            "Unsupported aggregation or spread in the cohort profile recipe."
        )
    if norm not in ("none", "z-score per participant") or (
        measure.is_rate and norm != "none"
    ):
        raise ValueError("Unsupported normalization in the cohort profile recipe.")
    if type(minimum) is not int or minimum < 1:
        raise ValueError("Min participants per word must be a positive integer.")
    screen = a.get("screen")
    if screen is not None and str(screen) not in text_screen_options(
        words, field, text_id
    ):
        raise ValueError(
            f"Screen {screen!r} of text {text_id!r} is missing after filtering."
        )
    if difference:
        groups = a.get("groups")
        if not isinstance(groups, list) or len(groups) != 2:
            raise ValueError(
                "A difference word profile needs exactly two group definitions."
            )
        spec_a, spec_b = (_recipe_group(group, words, fixations) for group in groups)
        table = group_word_difference(
            words,
            field,
            text_id,
            measure,
            spec_a,
            spec_b,
            agg=agg,
            min_readers=minimum,
            screen_id=screen,
        )
    else:
        table = cohort_word_profile(
            words,
            field,
            text_id,
            measure,
            agg=agg,
            spread=spread,
            normalize=norm != "none",
            min_readers=minimum,
            screen_id=screen,
        )
    if minimum > 1 or not difference:
        table = table.loc[table["enough"].eq(True)]
    return table


def load_recipe_sources(
    recipe,
    words,
    fixations,
    raw_gaze=None,
    *,
    word_schema=None,
    fix_schema=None,
    keep_columns=None,
    trial_parts_manifest=None,
):
    """Apply the recipe's upload mapping and wizard steps to the supplied source files."""
    from . import api, data

    inputs = _object(_object(recipe, "recipe").get("inputs", {}), "inputs")
    schemas = _object(inputs.get("schemas", {}), "schemas")
    word_schema = word_schema if word_schema is not None else schemas.get("words")
    fix_schema = fix_schema if fix_schema is not None else schemas.get("fixations")
    gaze_schema = schemas.get("raw_gaze")
    for schema in (word_schema, fix_schema, gaze_schema):
        if schema is not None:
            _object(schema, "column mapping")
            if any(
                v is not None
                and not isinstance(v, str)
                and not (isinstance(v, list) and all(isinstance(c, str) for c in v))
                for v in schema.values()
            ):
                raise ValueError("A column mapping must name source columns.")
    steps = _list(inputs.get("steps", []), "steps")
    if any(s != "aggregate_char_boxes" for s in steps):
        raise ValueError("Unsupported Words table preparation step in the recipe.")
    derive = inputs.get("derive") or []
    derive = [derive] if isinstance(derive, Mapping) else derive
    if not isinstance(derive, list):
        raise ValueError("Invalid column derivations in the recipe.")
    if derive or steps:
        frames = {}
        if fixations is not None:
            frames["Fixations"] = api._as_dataframe(
                fixations,
                "fixations",
                kind="fixations",
                plan_for=lambda header: data.identity_text_plan(header, fix_schema),
            )
        frames["Words table"] = api._as_dataframe(
            words,
            "words",
            kind="words",
            plan_for=lambda header: data.verbatim_text_plan(header, word_schema),
        )
        if raw_gaze is not None:
            frames["Raw gaze"] = api._as_dataframe(
                raw_gaze,
                "raw gaze",
                plan_for=lambda header: data.identity_text_plan(
                    header, gaze_schema, kind="raw_gaze"
                ),
            )
        for rule in derive:
            rule = _object(rule, "column derivation")
            column = rule.get("column", data.SOURCE_FILE_COLUMN)
            if not isinstance(column, str):
                raise ValueError("Invalid source column in the recipe's derivation.")
            target = rule.get("table")
            if target == "Raw gaze" and raw_gaze is None:
                continue
            if target is None:
                target = next((t for t, f in frames.items() if column in f), None)
            if not isinstance(target, str) or target not in frames:
                raise ValueError(
                    f"The column derivation needs its {target or 'original'} table."
                )
            frame = frames[target]
            if column not in frame:
                raise ValueError(f"Column derivation needs {column!r} in {target}.")
            if rule.get("mode") == "Split on a delimiter" and isinstance(
                rule.get("delimiter"), str
            ):
                frames[target], _ = data.split_named_columns(
                    frame, column, rule["delimiter"], set(frame.columns)
                )
            elif rule.get("mode") == "Extract with a regex" and isinstance(
                rule.get("pattern"), str
            ):
                frames[target] = data.extract_columns_from_source_file(
                    frame,
                    rule["pattern"],
                    column=column,
                    lowercase=bool(rule.get("lower")),
                )
            else:
                raise ValueError("Unsupported column derivation in the recipe.")
        words, fixations = frames["Words table"], frames.get("Fixations")
        raw_gaze = frames.get("Raw gaze")
        if "aggregate_char_boxes" in steps:
            words = data.aggregate_char_boxes(
                words, word_schema or data.propose_word_schema(words)
            )
    selection = _object(recipe.get("selection", {}), "selection")
    kept = set(_list(inputs.get("keep_columns", []), "keep_columns"))
    for key in ("word_fields", "fixation_fields"):
        kept.update(_list(selection.get(key, []), key))
    tables = api.load_scanpath_data(
        words,
        fixations,
        word_schema=word_schema,
        fix_schema=fix_schema,
        keep_columns=sorted(kept | set(keep_columns or ())),
        trial_parts_manifest=trial_parts_manifest,
    )
    samples = (
        api.load_raw_gaze(raw_gaze, raw_gaze_schema=gaze_schema)
        if raw_gaze is not None
        else None
    )
    return tables, samples
