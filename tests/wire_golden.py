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
DEMO_SELECTION = {"participant_id": "l42_458", "trial_id": "1_Adv_1"}


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
    setting never fails here; renaming or re-reading one does."""
    problems = []
    for key, value in expected.items():
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
        fake.session_state["_share_selection"] = dict(DEMO_SELECTION)
        query, _ = url_state._build_share_query(data_choice or DEMO_CHOICE)
    return query


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
    return {
        **maximal_link_state(),
        "_datasets": {
            "Golden corpus": {
                "words": words,
                "fixations": fixations,
                "raw_gaze": raw_gaze,
                "filter_fields": [],
                "composite_trial_columns": [],
                "schemas": {"words": {"trial": "trial_id"}},
            }
        },
        "data_source_choice": "Golden corpus",
        "trial_annotations": {
            ("p1", "t1"): {"star": True, "tags": ["Review"], "note": "regression?"}
        },
        "_dataset_descriptions": {"Golden corpus": "A three-word pilot."},
    }


def read_cache(root: Path) -> dict[str, Any]:
    """What a fresh session restores from the cache at `root`, frames as records."""
    from scanpath_studio.persistence import restore_state

    restored: dict[str, Any] = {}
    assert restore_state(restored, root), f"nothing restored from {root}"
    frames = {
        f"{name}/{table}": jsonable(
            frame.astype(object).where(frame.notna(), None).to_dict("list")
        )
        for name, entry in restored.get("_datasets", {}).items()
        for table, frame in entry.items()
        if isinstance(frame, pd.DataFrame) and not frame.empty
    }
    return {"state": snapshot(restored), "frames": frames}


# ---------------------------------------------------------------------------
# Figures: the API's output, normalized so only our own drawing counts
# ---------------------------------------------------------------------------
def _normal(value: Any) -> Any:
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
    """A hash of the figure as our code built it — Plotly's template left out,
    arrays as lists, floats rounded — so a Plotly upgrade alone changes nothing."""
    import hashlib

    data = fig.to_dict()
    data.get("layout", {}).pop("template", None)
    text = json.dumps(_normal(data), sort_keys=True, default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def golden_figures() -> dict[str, Any]:
    """The figures the golden digests pin, built through the public API."""
    from scanpath_studio import api
    from tests.test_render_every_option import OTHER, TRIAL, _maximal_state

    words, fixations = api.load_sample_data()
    static = _maximal_state("static").settings
    return {
        "static-default": lambda: api.plot_scanpath(words, fixations, *TRIAL),
        "static-maximal": lambda: api.plot_scanpath(words, fixations, *TRIAL, **static),
        "animation-default": lambda: api.animate_scanpath(words, fixations, *TRIAL),
        "comparison-default": lambda: api.compare_scanpaths(
            words, fixations, TRIAL, OTHER
        ),
    }
