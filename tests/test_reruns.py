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
    """`st.rerun` and `st.switch_page` themselves only inside `reruns`."""
    package = Path(scanpath_studio.__file__).parent
    direct = []
    for path in sorted(package.glob("*.py")):
        if path.name == "reruns.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("rerun", "switch_page")
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "st"
            ):
                direct.append(f"{path.name}:{node.lineno}")
    assert not direct, (
        "start a rerun with `reruns.rerun` / `reruns.switch_page`, which keep "
        f"the held widget writes through it: {direct}"
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


def test_a_click_that_reaches_the_rerun_still_meets_the_hold(state):
    """The run the script asked for can arrive with the browser's values (a
    click sent while it was pending): the closed menu's old value is still
    put back, not let through for a run."""
    state[STYLE] = "Solid"
    controls.reassert_pending_writes()
    controls.keep_holds_through_rerun()
    state[STYLE] = "Solid"  # the browser's echo arrives with that run
    controls.reassert_pending_writes()
    assert state[STYLE] == "Dashed"


def test_the_hold_ends_once_the_browser_shows_it_after_a_rerun(state):
    """Kept through the script's own rerun, the hold still ends when the
    browser shows the value, so a later pick of the old value stands."""
    controls.keep_holds_through_rerun()
    controls.reassert_pending_writes()  # the script's rerun
    controls.reassert_pending_writes()  # the browser shows Dashed
    state[STYLE] = "Solid"  # the user picks Solid
    controls.reassert_pending_writes()
    assert state[STYLE] == "Solid"
    assert STYLE not in (state.get(controls._PENDING_WRITES_KEY) or {})


@pytest.mark.parametrize("scope", ["app", "fragment"])
def test_rerun_keeps_the_holds_only_for_a_rerun_of_the_app(scope, state, monkeypatch):
    """A fragment's rerun runs no `reassert_pending_writes`, so it keeps none."""
    started = []
    monkeypatch.setattr(reruns.st, "rerun", lambda **kw: started.append(kw))
    reruns.rerun(scope=scope)
    assert started == [{"scope": scope}]
    write = state[controls._PENDING_WRITES_KEY][STYLE]
    assert write.through_rerun is (scope == "app")


def test_switch_page_keeps_the_holds_and_passes_the_page_on(state, monkeypatch):
    """❓ Help's entries bounce back to the view through `switch_page`, whose
    run brings no browser values either."""
    started = []
    monkeypatch.setattr(
        reruns.st, "switch_page", lambda page, **kw: started.append((page, kw))
    )
    reruns.switch_page("view.py", query_params={})
    assert started == [("view.py", {"query_params": {}})]
    assert state[controls._PENDING_WRITES_KEY][STYLE].through_rerun is True


def test_a_fragments_run_is_not_marked(state, monkeypatch):
    """A dialog or fragment run holds the browser's own values (no hold was
    re-applied in it), so the next run reads them as always: a value the
    browser already shows ends the hold."""
    from types import SimpleNamespace

    monkeypatch.setattr(
        controls,
        "get_script_run_ctx",
        lambda: SimpleNamespace(fragment_ids_this_run=["dialog"]),
    )
    controls.keep_holds_through_rerun()
    assert state[controls._PENDING_WRITES_KEY][STYLE].through_rerun is False


def test_a_callback_that_reasserts_keeps_the_holds_it_does_not_write(state):
    """Undo and a view tile put the held values back in their callback before
    writing their own; the run's own reassert, with nothing newer from the
    browser, must not take the others as answered."""
    state[STYLE] = "Solid"  # the click that runs the callback echoes it
    controls._reassert_in_callback()
    controls.reassert_pending_writes()  # the run the callback belongs to
    state[STYLE] = "Solid"  # the browser's next run echoes again
    controls.reassert_pending_writes()
    assert state[STYLE] == "Dashed"
