"""An uncaught error asks the user to report it, instead of a bare traceback."""

from __future__ import annotations

import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scanpath_studio import cli, crash_report
from scanpath_studio.constants import CITATION

ROOT = Path(__file__).resolve().parents[1]


def _crashing_script() -> None:
    from scanpath_studio.crash_report import guarded

    with guarded():
        raise TypeError("dialog_decorator() got an unexpected keyword argument")


def _stopping_script() -> None:
    import streamlit as st

    from scanpath_studio.crash_report import guarded

    with guarded():
        st.write("before")
        st.stop()


def _guarded_fragment_script() -> None:
    import streamlit as st

    from scanpath_studio.crash_report import guarded

    @st.fragment
    @guarded()
    def panel() -> None:
        raise ValueError("inside a fragment")

    with guarded():
        panel()


def _unguarded_fragment_script() -> None:
    import streamlit as st

    from scanpath_studio.crash_report import guarded

    @st.fragment
    def panel() -> None:
        raise ValueError("inside a fragment")

    with guarded():
        panel()


def test_a_crash_shows_the_report_note_and_the_traceback():
    at = AppTest.from_function(_crashing_script).run()
    assert len(at.error) == 1
    note = at.error[0].value
    assert "unexpected error" in note
    assert "Report this bug" in note
    assert CITATION["bug_report_url"] in note
    assert CITATION["questions_url"] in note
    # The traceback stays, for the report — exactly once, not also Streamlit's own.
    assert len(at.exception) == 1
    assert "dialog_decorator()" in at.exception[0].message


def test_streamlit_control_flow_passes_through():
    at = AppTest.from_function(_stopping_script).run()
    assert not at.error
    assert not at.exception


def test_a_guarded_fragment_shows_the_note_once():
    at = AppTest.from_function(_guarded_fragment_script).run()
    assert len(at.error) == 1
    assert len(at.exception) == 1


def test_an_error_streamlit_already_drew_is_not_drawn_again():
    """A fragment's own handler draws the traceback, then raises
    FragmentHandledException — which the outer guard must let through."""
    at = AppTest.from_function(_unguarded_fragment_script).run()
    assert not at.error
    assert len(at.exception) == 1


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    return ast.unparse(target)


def test_every_dialog_and_fragment_is_guarded():
    """Streamlit calls a fragment or dialog directly when it reruns on its own,
    outside the script run run_app guards."""
    unguarded = []
    for path in sorted((ROOT / "scanpath_studio").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            names = [_decorator_name(d) for d in node.decorator_list]
            if any(n in ("st.dialog", "st.fragment") for n in names) and (
                "guarded" not in names
            ):
                unguarded.append(f"{path.name}:{node.lineno} {node.name}")
    assert not unguarded, unguarded


def test_the_report_link_carries_only_the_error_type():
    """The message can hold paths or values from the user's data."""
    url = crash_report.report_url(ValueError("/Users/someone/secret.csv"))
    assert url.startswith(CITATION["bug_report_url"] + "&title=")
    assert "ValueError" in url
    assert "secret" not in url


def test_every_entry_script_runs_the_app_through_the_guard():
    for script in (
        ROOT / "streamlit_app.py",
        ROOT / "scanpath_studio" / "streamlit_entry.py",
    ):
        assert "run_app()" in script.read_text(encoding="utf-8"), script


def test_the_cli_launches_the_guarded_entry(monkeypatch):
    from streamlit.web import cli as st_cli

    seen: dict = {}
    monkeypatch.setattr(
        st_cli, "main", lambda: seen.setdefault("argv", list(cli.sys.argv))
    )
    monkeypatch.setattr(cli.sys, "exit", lambda *a, **k: None)
    monkeypatch.setattr(cli.sys, "argv", list(cli.sys.argv))
    cli.launch_app([])
    assert Path(seen["argv"][2]).name == "streamlit_entry.py"
