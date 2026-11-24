"""Shared by `tests/test_wire_golden.py` and `scripts/capture_golden.py`.

The golden fixtures pin what users already hold. Share links, settings files
and the recovery cache written by a released version must keep restoring to
the same state. These helpers build the inputs (from the app's own tables, so
they are valid by construction) and turn a session into comparable JSON.
"""

from __future__ import annotations

import contextlib
import json
import math
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

GOLDEN = Path(__file__).resolve().parent / "fixtures" / "golden"
#: A reading of the bundled demo, and a second one for comparisons.
TRIAL = ("l37_273", "l37_273_2_2_2_Adv")
OTHER = ("l7_183", "l7_183_2_2_2_Adv")
#: What opening a link selects, besides the settings `read_link` covers.
SELECTION_KEYS = ("data_source_choice", "single_participant", "single_trial_id")


class FakeSt:
    """The slice of `streamlit` the link helpers use, without a script run."""

    def __init__(self) -> None:
        self.session_state: dict[str, Any] = {}
        self.query_params: dict[str, str] = {}
        self.notes: list[str] = []

    def _note(self, *args, **kwargs) -> None:
        self.notes.append(" ".join(str(arg) for arg in args))

    warning = info = toast = error = _note


@contextlib.contextmanager
def fake_streamlit() -> Iterator[FakeSt]:
    """Point every module the link helpers touch at one `FakeSt`."""
    from scanpath_studio import app, controls, url_state

    fake = FakeSt()
    modules = (app, controls, url_state)
    saved = [module.st for module in modules]
    for module in modules:
        module.st = fake
    try:
        yield fake
    finally:
        for module, original in zip(modules, saved, strict=True):
            module.st = original


def jsonable(value: Any) -> Any:
    """`value` as plain JSON, or `_SKIP` for what a snapshot leaves out."""
    if isinstance(value, (pd.DataFrame, pd.Series)) or callable(value):
        return _SKIP
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        out = {str(k): jsonable(v) for k, v in value.items()}
        return {k: v for k, v in out.items() if v is not _SKIP}
    if isinstance(value, (set, frozenset)):
        return sorted((jsonable(v) for v in value), key=repr)
    if isinstance(value, (list, tuple, np.ndarray)):
        return [jsonable(v) for v in value]
    return _SKIP


_SKIP = object()


def snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    """The JSON-comparable part of a session, keyed and sorted."""
    out = {}
    for key in sorted(state, key=str):
        value = jsonable(state[key])
        if value is not _SKIP:
            out[str(key)] = value
    return json.loads(json.dumps(out, sort_keys=True))


def differences(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> list[str]:
    """Each captured key whose restored value differs, or that is now missing.

    Keys the session has and the capture lacks are ignored, so adding a
    setting never fails here; renaming or re-reading one does. A captured key
    renamed on purpose is looked up under its new name once its old one is
    registered in `session_keys.LEGACY_SESSION_KEYS`."""
    from scanpath_studio.session_keys import rename_legacy_keys

    problems = []
    for key, value in rename_legacy_keys(expected).items():
        if key not in actual:
            problems.append(f"{key}: missing (was {value!r})")
        elif actual[key] != value:
            problems.append(f"{key}: {actual[key]!r} (was {value!r})")
    return problems


def _off_default(default: Any, bounds: tuple) -> Any:
    lo, hi = bounds
    if isinstance(lo, int) and isinstance(hi, int) and not isinstance(default, float):
        value = lo + (hi - lo) * 3 // 7
        return value if value != default else min(lo + 1, hi)
    value = round(lo + (hi - lo) * 0.37, 2)
    return value if value != default else round((lo + hi) / 2, 3)


def maximal_link_state() -> dict[str, Any]:
    """The defaults, with every linkable switch flipped and every bounded
    number moved off its default (inside its bounds)."""
    from scanpath_studio import controls, url_state

    state = dict(controls._VIZ_WIDGET_DEFAULTS)
    for key in url_state._SHARE_TOGGLE_PARAMS.values():
        state[key] = not bool(state.get(key, False))
    for key, bounds in url_state._URL_BOUNDED.items():
        if key in state and isinstance(state[key], (int, float)) and len(bounds) == 2:
            state[key] = _off_default(state[key], bounds)
    for key in (
        *url_state._SHARE_INT_RANGE_PARAMS.values(),
        *url_state._SHARE_FLOAT_RANGE_PARAMS.values(),
    ):
        current = state.get(key)
        if isinstance(current, (list, tuple)) and len(current) == 2:
            lo, hi = current
            if (
                isinstance(lo, (int, float))
                and isinstance(hi, (int, float))
                and hi > lo
            ):
                step = (hi - lo) / 5
                kind = int if all(isinstance(v, int) for v in current) else float
                state[key] = (kind(lo + step), kind(hi - step))
    return state


def palette_link_states() -> dict[str, dict[str, Any]]:
    """One state per named palette, Compare styles included."""
    from scanpath_studio import controls
    from scanpath_studio.constants import PALETTES

    return {
        name: {
            **controls._VIZ_WIDGET_DEFAULTS,
            **controls.palette_state(name, include_compare=True),
            "global_palette": name,
        }
        for name in PALETTES
    }


def write_link(state: Mapping[str, Any], data_choice: str | None = None) -> str:
    """The query string 🔗 Share → Link writes for `state`."""
    from scanpath_studio import url_state
    from scanpath_studio.constants import DEMO_CHOICE

    with fake_streamlit() as fake:
        fake.session_state.update(state)
        fake.session_state["_share_selection"] = {
            "participant_id": TRIAL[0],
            "trial_id": TRIAL[1],
        }
        query, _ = url_state._build_share_query(data_choice or DEMO_CHOICE)
    return query


def open_link_in_app(query: str) -> dict[str, Any]:
    """The dataset, reading and settings the app shows after opening `query`."""
    at = _app(query)
    at.run()  # the rerun the next click would cause
    assert not at.exception, at.exception
    keys = (*SELECTION_KEYS, *settings_keys())
    return snapshot(
        {key: at.session_state[key] for key in keys if key in at.session_state}
    )


def read_link(query: str) -> dict[str, Any]:
    """The settings a fresh session takes from opening `query`."""
    from urllib.parse import parse_qs

    from scanpath_studio import url_state

    with fake_streamlit() as fake:
        fake.query_params = {
            k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()
        }
        url_state._apply_url_preset()
        return snapshot(fake.session_state)


# ---------------------------------------------------------------------------
# Settings files: the real writer (Share → File) and reader (an upload)
# ---------------------------------------------------------------------------
class _Upload:
    """What `st.file_uploader` holds."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self.name = "scanpath_studio_settings.json"
        self.size = len(data)
        self.file_id = "golden-settings"

    def getvalue(self) -> bytes:
        return self._data


def settings_keys() -> frozenset[str]:
    from scanpath_studio.session_keys import (
        PLOT_CONFIG_OTHER_STATE_KEYS,
        PLOT_CONFIG_STATE_KEYS,
    )

    return frozenset(PLOT_CONFIG_STATE_KEYS) | frozenset(PLOT_CONFIG_OTHER_STATE_KEYS)


def _app(query: str | None = None):
    from urllib.parse import parse_qs

    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    at.query_params["ui"] = "full"
    for key, values in parse_qs(query or "", keep_blank_values=True).items():
        at.query_params[key] = values[0]
    at.run()
    assert not at.exception, at.exception
    return at


def write_settings_file(query: str) -> dict:
    """The file 🔗 Share → File writes after opening `query`."""
    from scanpath_studio import tabs
    from scanpath_studio.url_state import SHARE_SECTION_KEY
    from tests.conftest import SUBTAB_KEY, SUBTAB_SHARE

    written: list[dict] = []
    real = tabs._build_studio_config

    def recording(**kwargs):
        config = real(**kwargs)
        written.append(config)
        return config

    tabs._build_studio_config = recording
    try:
        at = _app(query)
        at.session_state[SUBTAB_KEY] = SUBTAB_SHARE
        at.session_state[SHARE_SECTION_KEY] = "Settings file"
        at.run()
        assert not at.exception, at.exception
    finally:
        tabs._build_studio_config = real
    assert written, "Share → File built no settings file"
    return json.loads(json.dumps(written[-1]))


def read_settings_file(config: dict) -> dict[str, Any]:
    """The settings a fresh session takes from uploading `config`."""
    at = _app()
    at.session_state["plot_config_upload"] = _Upload(json.dumps(config).encode())
    at.run()
    assert not at.exception, at.exception
    at.run()  # the rerun the next click would cause
    assert not at.exception, at.exception
    return snapshot(
        {
            key: at.session_state[key]
            for key in settings_keys()
            if key in at.session_state
        }
    )


# ---------------------------------------------------------------------------
# The recovery cache
# ---------------------------------------------------------------------------
def cache_session() -> dict[str, Any]:
    """An uploaded dataset with annotations and a description, plus the
    maximal settings: what a working session leaves for the cache."""
    words = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "word_id": [1, 2, 3],
            "text": ["The", "quick", "fox"],
            "x": [10.0, 60.0, 130.0],
            "y": [20.0, 20.0, 20.0],
            "width": [45.0, 65.0, 40.0],
            "height": [30.0, 30.0, 30.0],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"] * 4,
            "trial_id": ["t1"] * 4,
            "x": [25.0, 80.0, 30.0, 140.0],
            "y": [32.0, 33.0, 35.0, 31.0],
            "duration_ms": [210, 180, 240, 200],
        }
    )
    raw_gaze = pd.DataFrame(
        {
            "participant_id": ["p1"] * 3,
            "trial_id": ["t1"] * 3,
            "timestamp_ms": [0, 2, 4],
            "x": [24.0, 25.0, None],
            "y": [31.0, 32.0, None],
        }
    )
    import scanpath_studio.annotations as annotations_mod
    from scanpath_studio.column_names import for_tables
    from scanpath_studio.constants import DATASET_ALIASES_KEY
    from scanpath_studio.dataset_identity import DATASET_IDS_KEY
    from scanpath_studio.experimental_setup import Provenance, SetupSnapshot

    # The names the user's own files gave the columns, as the wizard records
    # them beside the canonical frames.
    schemas = {
        "words": {"participant": "Reader", "trial": "Paragraph", "text": "Word"},
        "fixations": {"participant": "Reader", "trial": "Paragraph", "duration": "Dur"},
        "raw_gaze": None,
    }
    raw = {
        "words": pd.DataFrame(columns=["Reader", "Paragraph", "Word", "Left", "Top"]),
        "fixations": pd.DataFrame(columns=["Reader", "Paragraph", "Dur", "X", "Y"]),
    }
    setup = SetupSnapshot(
        canvas_width=1280,
        canvas_height=720,
        monitor_width_mm=531.0,
        viewing_distance_mm=650.0,
        base_font_size=22,
        screen_provenance=Provenance.MEASURED,
        geometry_provenance=Provenance.MEASURED,
    )
    session = {
        **maximal_link_state(),
        "_datasets": {
            CACHE_DATASET: {
                "words": words,
                "fixations": fixations,
                "raw_gaze": raw_gaze,
                "filter_fields": ["condition"],
                "composite_trial_columns": [],
                "schemas": schemas,
                "column_names": for_tables(schemas, raw),
                "dropped_columns": {
                    "words": ["Notes"],
                    "fixations": [],
                    "raw_gaze": [],
                },
                "setup": setup.to_dict(),
            }
        },
        "data_source_choice": CACHE_DATASET,
        "_dataset_descriptions": {CACHE_DATASET: "A three-word pilot."},
        # A private dataset's share links find it by this id, and show its alias.
        DATASET_IDS_KEY: {CACHE_DATASET: "0d6c1e7a-5b8f-4c3e-9a21-7f04b1c2d3e4"},
        DATASET_ALIASES_KEY: {CACHE_DATASET: "Pilot (three words)"},
    }
    # As every app run does: the annotations belong to the open dataset.
    annotations_mod.activate_dataset(session, CACHE_DATASET)
    session["trial_annotations"] = {
        ("p1", "t1"): {"star": True, "tags": ["Review"], "note": "regression?"}
    }
    return session


CACHE_DATASET = "Golden corpus"


def read_cache(root: Path) -> dict[str, Any]:
    """What a fresh session restores from the cache at `root`: the keys the
    cache saves for the user, each dataset's own fields (its column names,
    recording setup, filter fields), its annotations, and its frames."""
    import scanpath_studio.annotations as annotations_mod
    from scanpath_studio.persistence import _SESSION_KEYS, restore_state

    restored: dict[str, Any] = {}
    assert restore_state(restored, root), f"nothing restored from {root}"
    datasets = restored.get("_datasets", {})
    frames = {
        f"{name}/{table}": jsonable(
            frame.astype(object).where(frame.notna(), None).to_dict("list")
        )
        for name, entry in datasets.items()
        for table, frame in entry.items()
        if isinstance(frame, pd.DataFrame) and not frame.empty
    }
    fields = {
        f"{name}/{field}": value
        for name, entry in datasets.items()
        for field, value in snapshot(
            {k: v for k, v in entry.items() if not isinstance(v, pd.DataFrame)}
        ).items()
    }
    annotations_mod.activate_dataset(restored, CACHE_DATASET)
    notes = sorted(
        (
            {"participant_id": key[0], "trial_id": key[1], **jsonable(value)}
            for key, value in (restored.get("trial_annotations") or {}).items()
        ),
        key=lambda row: (row["participant_id"], row["trial_id"]),
    )
    state = snapshot({k: v for k, v in restored.items() if k in _SESSION_KEYS})
    return {
        "state": state,
        "datasets": fields,
        "annotations": notes,
        "frames": frames,
    }


# ---------------------------------------------------------------------------
# Figures: the API's output, normalized so only our own drawing counts
# ---------------------------------------------------------------------------
def _typed_array(value: Mapping) -> np.ndarray | None:
    """Plotly's `{"dtype", "bdata"[, "shape"]}` encoding of an array, decoded."""
    import base64

    if set(value) - {"dtype", "bdata", "shape"} or not {"dtype", "bdata"} <= set(value):
        return None
    array = np.frombuffer(
        base64.b64decode(value["bdata"]), dtype=np.dtype(value["dtype"])
    )
    shape = value.get("shape")
    if shape:
        dims = (
            [int(d) for d in str(shape).split(",")] if isinstance(shape, str) else shape
        )
        array = array.reshape(dims)
    return array


def _normal(value: Any) -> Any:
    if isinstance(value, Mapping) and (array := _typed_array(value)) is not None:
        value = array
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6) if math.isfinite(value) else repr(value)
    if isinstance(value, Mapping):
        return {str(k): _normal(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normal(v) for v in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return str(value)
    return value


def figure_digest(fig) -> str:
    """A hash of the figure as our code built it. Plotly's template is left
    out, and every array (Plotly's typed-array encoding included) is decoded to
    a list of floats rounded to six places, so neither a Plotly upgrade nor a
    last-bit difference in the arithmetic changes it."""
    import hashlib

    data = fig.to_dict()
    data.get("layout", {}).pop("template", None)
    text = json.dumps(_normal(data), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


#: The pinned figures: which builder, and the options it is given. The options
#: are stored beside the digest, so adding a figure option changes neither.
#: "Maximal" turns every spatial layer on and moves colour, size and opacity
#: off their defaults.
FIGURE_CASES: dict[str, tuple[str, dict[str, Any]]] = {
    "static-default": ("static", {}),
    "static-maximal": (
        "static",
        {
            "show_words": True,
            "show_word_labels": True,
            "show_fixations": True,
            "show_order": True,
            "show_saccades": True,
            "show_saccade_arrows": True,
            "show_heatmap": True,
            "show_raw_gaze": True,
            "heatmap_style": "Smoothed",
            "heatmap_colorscale": "Greens",
            "heatmap_opacity": 0.8,
            "color_by": "duration_ms",
            "fixation_colorscale": "Viridis",
            "fixation_opacity": 0.5,
            "marker_size_range": [5, 20],
            "marker_size_scale": "log",
            "saccade_color": "#123456",
            "saccade_opacity": 0.5,
            "fixation_outline_color": "#336699",
        },
    ),
    "animation-default": ("animation", {}),
    "comparison-default": ("comparison", {}),
}


def build_figure(kind: str, options: Mapping[str, Any]):
    """One pinned figure, through the public API on the bundled demo."""
    from scanpath_studio import api

    words, fixations = api.load_sample_data()
    if kind == "static":
        raw_gaze = api.load_sample_raw_gaze()
        return api.plot_scanpath(words, fixations, *TRIAL, raw_gaze=raw_gaze, **options)
    if kind == "animation":
        return api.animate_scanpath(words, fixations, *TRIAL, **options)
    return api.compare_scanpaths(words, fixations, TRIAL, OTHER, **options)
