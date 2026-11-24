"""A rerun the app starts keeps the writes held against a closed menu's echo.

`controls.write_through` holds a write until the browser shows it. A rerun the
script starts brings no browser values, so without `reruns.rerun` the held key
would read as taken and the hold would end before the echo arrives.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import scanpath_studio
from scanpath_studio import controls, reruns

STYLE = "global_saccade_style"


def test_the_package_starts_every_rerun_through_the_helper():
    """`st.rerun` itself only inside `reruns.rerun`."""
    package = Path(scanpath_studio.__file__).parent
    direct = []
    for path in sorted(package.glob("*.py")):
        if path.name == "reruns.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "rerun"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"
            ):
                direct.append(f"{path.name}:{node.lineno}")
    assert not direct, (
        "start a rerun with `reruns.rerun`, which keeps the held widget "
        f"writes through it: {direct}"
    )


@pytest.fixture
def state(monkeypatch) -> dict:
    session: dict = {STYLE: "Solid"}
    monkeypatch.setattr(controls.st, "session_state", session)
    # A view tile's callback holds Dashed against the menu's Solid.
    controls.write_through(STYLE, "Dashed")
    controls.reassert_pending_writes()  # the run the write was made for
    return session


def test_a_script_rerun_keeps_a_hold_its_run_put_back(state):
    state[STYLE] = "Solid"  # the next run: the closed menu echoes
    controls.reassert_pending_writes()  # ... and the hold puts Dashed back
    controls.keep_holds_through_rerun()  # the script reruns itself
    controls.reassert_pending_writes()  # that rerun: no browser values
    state[STYLE] = "Solid"  # the browser's next run echoes again
    controls.reassert_pending_writes()
    assert state[STYLE] == "Dashed"


def test_a_dialog_rerun_leaves_an_echoed_hold_for_the_next_run(state):
    """A dialog's run gets the browser's echo but re-applies no hold; the
    rerun of the whole app it starts must still put the write back."""
    state[STYLE] = "Solid"
    controls.keep_holds_through_rerun()
    controls.reassert_pending_writes()  # the app's rerun
    assert state[STYLE] == "Dashed"


@pytest.mark.parametrize("scope", ["app", "fragment"])
def test_rerun_keeps_the_holds_only_for_a_rerun_of_the_app(scope, state, monkeypatch):
    """A fragment's rerun runs no `reassert_pending_writes`, so it keeps none."""
    started = []
    monkeypatch.setattr(reruns.st, "rerun", lambda **kw: started.append(kw))
    reruns.rerun(scope=scope)
    assert started == [{"scope": scope}]
    write = state[controls._PENDING_WRITES_KEY][STYLE]
    assert write.fresh is (scope == "app")
