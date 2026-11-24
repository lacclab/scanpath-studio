"""A server-side write to a popover widget's key goes through `write_through`.

A widget inside an ``st.popover`` is mounted in the browser only while its
popover is open. Once it has been open, the browser sends back the value it
last showed on every rerun, so a one-off write made while the popover is closed
holds for one run and then snaps back (`controls.write_through`). A plain
write is safe only when the script repeats it on every run before the widget
draws, or when the widget is mounted as the write lands.

Which keys live in a popover is read from the running app, in the states that
draw the rail's popovers. Every write to session state whose key the source
names — a literal, a module constant, or an f-string pattern — is checked
against them. A write with a key computed at run time names none, and stays a
reviewer's check (REVIEW.md).
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
from scanpath_studio.constants import _VIEW_SCANPATH
from tests.conftest import APP_SCRIPT, pin_view

#: The app states whose popovers are read: the static plot in both modes, the
#: replay, and Compare, which adds each reading's own controls.
_STATES = {
    "static": ({}, "full"),
    "essentials": ({}, "essentials"),
    "replay": ({"single_animate": True}, "full"),
    "compare": ({"single_compare_toggle": True}, "full"),
}

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
        {
            "global_saccade_style",
            "global_highlight_span_on",
            "global_highlight_span_mode",
        },
        "heals an invalid saccade style, and derives the span switch and mode "
        "from the canonical span style, on every run before those widgets draw",
    ),
    "plot_navigation._open_setting": (
        {"plot_filter_readings"},
        "the setting finder's callback opens the menu and section holding the "
        "widget in the same write, so the widget mounts with the written value",
    ),
    "tabs._render_compare_selector": (
        {"single_compare_order"},
        "heals a sort order the options no longer offer, on every run before "
        "the sort popover draws",
    ),
    "tabs.render_single_trial_tab": (
        {"global_anim_quality"},
        "re-infers the replay quality from the frame grid on every run before "
        "its control draws",
    ),
    "tabs._apply_anim_quality": (
        {"plot_detail_frame_timing"},
        "the quality control's own callback opens the frame-timing section in "
        "the popover the user is using, which is open",
    ),
}


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
    for state, ui in _STATES.values():
        at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
        at.query_params["ui"] = ui
        for key, value in state.items():
            at.session_state[key] = value
        pin_view(at, _VIEW_SCANPATH)
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


@pytest.mark.timeout(300)
def test_a_write_to_a_popover_widget_holds_against_its_echo():
    """Every plain write to a popover widget's key is listed with why the
    browser's echo cannot undo it; any other goes through `write_through`."""
    unlisted = {
        where: sorted(keys - ALLOWED.get(where, (set(), ""))[0])
        for where, keys in _direct_writes(_popover_keys()).items()
        if keys - ALLOWED.get(where, (set(), ""))[0]
    }
    assert not unlisted, (
        "these write a popover widget's key directly. Once its popover has "
        "been open, the browser sends the old value back on the next rerun, so "
        "the write snaps back: use `controls.write_through`, or list the key in "
        f"ALLOWED with why it holds: {unlisted}"
    )


@pytest.mark.timeout(300)
def test_every_listed_write_still_happens():
    writes = _direct_writes(_popover_keys())
    stale = sorted(
        f"{where} {sorted(keys - writes.get(where, set()))}"
        for where, (keys, _why) in ALLOWED.items()
        if keys - writes.get(where, set())
    )
    assert not stale, f"no longer written directly; drop from ALLOWED: {stale}"


@pytest.mark.timeout(300)
def test_the_rail_popovers_are_read():
    """A broken walk would find no keys and pass everything above."""
    keys = _popover_keys()
    assert {"global_saccade_style", "global_anim_quality"} <= keys
    assert any(key.startswith("cmp0_") for key in keys)
