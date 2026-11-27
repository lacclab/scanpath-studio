"""Types and units of the CSV columns actually written to an export bundle."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .aggregation import MEASURES

# These are keys whose spelling identifies a reading. Numeric word and fixation
# positions remain numbers so readers can use them as indices.
_TEXT_IDS = {
    "participant_id",
    "trial_id",
    "text_id",
    "screen_id",
    "word_key",
    "unique_participant_id",
    "unique_trial_id",
    "unique_text_id",
}
_UNITS = {
    **{measure.column: measure.unit for measure in MEASURES.values() if measure.unit},
    **dict.fromkeys(
        (
            "x",
            "y",
            "width",
            "height",
            "canvas_width",
            "canvas_height",
            "saccade_amplitude",
        ),
        "px",
    ),
    **dict.fromkeys(("duration_ms", "timestamp_ms", "screen_timestamp_ms"), "ms"),
    **dict.fromkeys(
        ("next_saccade_amplitude_deg", "prev_saccade_amplitude_deg"), "degrees"
    ),
}


class CsvDictionary:
    """One schema per distinct set of written headers and dtypes, shared across files."""

    def __init__(self, folder: str = ""):
        self._prefix = folder + "/" if folder else ""
        self.files: dict[str, str] = {}
        self.schemas: dict[str, list[dict]] = {}
        self._ids: dict[tuple, str] = {}

    def record(self, path: str, canonical: Iterable, written: pd.DataFrame) -> None:
        signature = tuple(zip(canonical, written.columns, written.dtypes, strict=True))
        schema = self._ids.get(signature)
        if schema is None:
            schema = str(len(self.schemas) + 1)
            self._ids[signature] = schema
            columns = []
            for name, header, dtype in signature:
                if name in _TEXT_IDS:
                    value_type = "character"
                elif pd.api.types.is_bool_dtype(dtype):
                    value_type = "logical"
                elif pd.api.types.is_numeric_dtype(dtype):
                    value_type = "numeric"
                else:
                    value_type = "character"
                columns.append(
                    {
                        "column": str(header),
                        "canonical": str(name),
                        "r_type": value_type,
                        "identifier": name in _TEXT_IDS,
                        "unit": _UNITS.get(name),
                    }
                )
            self.schemas[schema] = columns
        self.files[path.removeprefix(self._prefix)] = schema

    def manifest(self) -> dict:
        if not self.files:
            return {}
        return {
            "csv_files": self.files,
            "csv_schemas": self.schemas,
            "csv_missing_values": {
                "empty_field": "missing",
                "zero": "observed zero",
                "text": "An empty string and a missing string share the same CSV representation.",
            },
        }


R_IMPORT = """# Run from the extracted bundle folder. Requires the R package jsonlite.
dictionary <- jsonlite::fromJSON("columns.json", simplifyVector = FALSE)
read_scanpath_csv <- function(path) {
  if (!isTRUE(path %in% names(dictionary$csv_files))) {
    stop("Choose a CSV listed in dictionary$csv_files")
  }
  schema <- dictionary$csv_schemas[[dictionary$csv_files[[path]]]]
  types <- vapply(schema, function(column) column$r_type, character(1))
  read.csv(path, colClasses = unname(types), check.names = FALSE,
           na.strings = "", fileEncoding = "UTF-8", stringsAsFactors = FALSE)
}

# Edit this path to read a different exported table.
example <- read_scanpath_csv(names(dictionary$csv_files)[1])
"""
