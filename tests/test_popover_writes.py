"""A server-side write to a popover widget's key goes through `write_through`.

A widget inside an ``st.popover`` is mounted in the browser only while its
popover is open. Once it has been open, the browser sends back the value it
last showed on every rerun, so a one-off write made while the popover is closed
holds for one run and then snaps back (`controls.write_through`). A plain
write is safe only when the script repeats it on every run before the widget
draws, or when the widget is mounted as the write lands — and, for a widget
with an ``on_change``, only when that callback cannot act on the echo: the
browser's old value differs from the one the server wrote, so Streamlit runs
the callback before the script re-derives anything.

Which keys live in a popover is read from the running app, in every view,
subtab and mode that draws a popover. Every plain assignment to session state
whose key the source names — a literal, a module constant, or an f-string
pattern — is checked against them. A write through a helper's argument
(`url_state._RestoreContext.put`), a loop over keys, or a key computed at run
time names none here, and stays a reviewer's check (REVIEW.md).
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
import re
from functools import cache
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import scanpath_studio
from scanpath_studio.constants import (
    _VIEW_CORPUS,
    _VIEW_DATA,
    _VIEW_SCANPATH,
    DATA_INSPECTION_KEY,
)
from scanpath_studio.session_keys import CORPUS_SUBTAB
from tests.conftest import APP_SCRIPT, pin_view

_ANIMATE = {"single_animate": True}
_COMPARE = {"single_compare_toggle": True}


def _states() -> list[tuple[str, dict, str]]:
    """``(view, state, ui)`` for every view, subtab and mode that draws a
    popover: the plot alone, replayed and compared, in both modes; each
    Scanpath subtab; each Corpus Analysis subtab; each Data page panel."""
    from scanpath_studio.tabs import subtab_labels_for

    states = [
        (_VIEW_SCANPATH, state, ui)
        for ui in ("full", "essentials")
        for state in ({}, _ANIMATE, _COMPARE)
    ]
    states += [
        (_VIEW_SCANPATH, _COMPARE | _ANIMATE, "full"),
        (_VIEW_SCANPATH, _COMPARE | {"global_show_raw_gaze": True}, "full"),
    ]
    states += [
        (_VIEW_SCANPATH, {"single_subtab": label}, "full")
        for label in subtab_labels_for(False, line_assignment=True)
    ]
    states += [
        (_VIEW_CORPUS, {CORPUS_SUBTAB: name}, "full")
        for name in (
            "Overview",
            "Per text",
            "Per participant",
            "Groups",
            "Per sentence",
        )
    ]
    states += [
        (_VIEW_DATA, {DATA_INSPECTION_KEY: name}, "full")
        for name in ("Overview", "Tables", "Data checks", "Annotations")
    ]
    return states


#: Plain writes to a popover key: ``module.function`` → the keys it writes,
#: and why the browser's echo cannot undo them.
ALLOWED = {
    "app.seed_canvas_state": (
        {"global_base_font_size"},
        "the px font size is derived from the pt size on every run while pt is "
        "in use, and the px box is not drawn then",
    ),
    "app._rail_text_rows": (
        {"global_base_font_size"},
        "the same derivation, as the rail draws the pt box; the px box is not "
        "drawn in that branch",
    ),
    "controls._apply_view_preset_state": (
        {"cmp0_marker_size_range", "cmp1_marker_size_range"},
        "its only caller, `_apply_view_preset`, holds every value it changed "
        "through `_hold_view_writes`, which calls `write_through`",
    ),
    "controls.render_trial_filters": (
        {"filter_favorites", "cmpfilter_favorites"},
        "seeds the favorites switch only while its key is absent, so the "
        "browser has no value of its own to send back",
    ),
    "controls.render_plot_controls": (
        {"global_saccade_style"},
        "heals an invalid saccade style on every run before its control draws; "
        "an echo can only send a valid one, and the control has no callback",
    ),
    "plot_navigation._open_setting": (
        {"plot_filter_readings"},
        "the setting finder's callback opens the menu and section holding the "
        "widget in the same write, so the widget mounts with the written value",
    ),
    "tabs._render_compare_selector": (
        {"single_compare_order"},
        "heals a sort order the options no longer offer, on every run before "
        "the sort popover draws; the sort control has no callback",
    ),
    "tabs._apply_anim_quality": (
        {"plot_detail_frame_timing"},
        "opens the frame-timing section beside the quality control; whether the "
        "user or an echo fires the callback, an open section is harmless",
    ),
    "tabs._clear_pool_filters": (
        {"corpus_pool_popover"},
        "the popover's own open state, closed by the Clear button inside it, "
        "which is open as the click lands",
    ),
}

#: Plain writes the echo can undo, or whose widget's ``on_change`` can act on
#: the echo before the write: known bugs, each with how it shows. A hazard
#: found in review is listed here until it is fixed, so this check still stops
#: new ones; fixing one leaves its entry stale, which fails below until the
#: entry is dropped.
ECHO_HAZARDS: dict[str, tuple[set[str], str]] = {}


def _listed(where: str) -> set[str]:
    return ALLOWED.get(where, (set(), ""))[0] | ECHO_HAZARDS.get(where, (set(), ""))[0]


def _keys_in(node) -> set[str]:
    found = set()
    key = getattr(node, "key", None)
    if isinstance(key, str):
        found.add(key)
    children = getattr(node, "children", None)
    if isinstance(children, dict):
        for child in children.values():
            found |= _keys_in(child)
    return found


@cache
def _popover_keys() -> frozenset[str]:
    keys: set[str] = set()
    for view, state, ui in _states():
        at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        at.query_params["ui"] = ui
        for key, value in state.items():
            at.session_state[key] = value
        pin_view(at, view)
        at.run()
        at.run()
        assert not at.exception, at.exception
        for popover in at.get("popover"):
            keys |= _keys_in(popover)
    return frozenset(keys)


def _session_names(function: ast.AST) -> set[str]:
    """Names that hold session state in ``function``: ``ss`` by convention, and
    any name it binds to ``st.session_state``."""
    names = {"ss"}
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and (
            ast.unparse(node.value) == "st.session_state"
        ):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _keys_named(key: ast.AST, module_name: str, popover: frozenset[str]) -> set:
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return {key.value} & popover
    if isinstance(key, ast.JoinedStr):
        # Each `{…}` as one underscore-free word, as `{prefix}` or `{idx}` is.
        pattern = "".join(
            re.escape(part.value) if isinstance(part, ast.Constant) else "[A-Za-z0-9]*"
            for part in key.values
        )
        return {k for k in popover if re.fullmatch(pattern, k)}
    if isinstance(key, (ast.Name, ast.Attribute)):
        value = importlib.import_module(f"scanpath_studio.{module_name}")
        for part in ast.unparse(key).split("."):
            value = getattr(value, part, None)
        return {value} & popover if isinstance(value, str) else set()
    return set()


def _direct_writes(popover: frozenset[str]) -> dict[str, set[str]]:
    """``module.function`` → the popover keys it writes to session state with
    a plain assignment."""
    package = Path(scanpath_studio.__file__).parent
    writes: dict[str, set[str]] = {}
    for info in pkgutil.iter_modules([str(package)]):
        tree = ast.parse((package / f"{info.name}.py").read_text(encoding="utf-8"))
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for function in functions:
            session = _session_names(function)
            # Only the function's own statements: a nested function is its own.
            nested = {
                id(inner)
                for child in function.body
                for inner in ast.walk(child)
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef))
                for inner in ast.walk(inner)
            }
            for node in ast.walk(function):
                if id(node) in nested:
                    continue
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                    if isinstance(node, ast.AugAssign)
                    else []
                )
                for target in targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    holder = ast.unparse(target.value)
                    if holder != "st.session_state" and holder not in session:
                        continue
                    keys = _keys_named(target.slice, info.name, popover)
                    if keys:
                        where = f"{info.name}.{function.name}"
                        writes.setdefault(where, set()).update(keys)
    return writes


@pytest.mark.timeout(600)
def test_a_write_to_a_popover_widget_holds_against_its_echo():
    """Every plain write to a popover widget's key is listed: with why the
    browser's echo cannot undo it, or as a known hazard. Any other goes
    through `write_through`."""
    popover = _popover_keys()
    # A broken walk would find no keys and pass everything below.
    assert "global_saccade_style" in popover
    assert any(key.startswith("cmp0_") for key in popover)
    assert any(key.startswith("_anim_quality__w") for key in popover)

    writes = _direct_writes(popover)
    unlisted = {
        where: sorted(keys - _listed(where))
        for where, keys in writes.items()
        if keys - _listed(where)
    }
    assert not unlisted, (
        "these write a popover widget's key directly. Once its popover has "
        "been open, the browser sends the old value back on the next rerun, so "
        "the write snaps back: use `controls.write_through`, or list the key in "
        f"ALLOWED with why it holds: {unlisted}"
    )
    stale = sorted(
        f"{where} {sorted(keys - writes.get(where, set()))}"
        for listing in (ALLOWED, ECHO_HAZARDS)
        for where, (keys, _why) in listing.items()
        if keys - writes.get(where, set())
    )
    assert not stale, f"no longer written directly; drop the entry: {stale}"
