"""Small dependency-boundary tests for the core data pipeline."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"


def _relative_imports(module: str) -> set[str]:
    tree = ast.parse((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))
    return {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level
    }


def test_core_data_dependencies_are_one_way():
    """Keep the two cycles removed by ENG-28 from growing back."""
    assert "datasets" not in _relative_imports("data")
    assert "preprocessing" not in _relative_imports("measures")


def test_offscreen_page_twins_are_actually_hidden():
    """BUG-34: every off-screen page copy carries its own `display: none` rule.

    The Session and 🗂️ Data pages render on *every* run and are hidden by key
    when they are not the active view — the widgets inside are gates whose keys
    Streamlit drops if they do not render. That makes the hiding load-bearing
    and its failure silent: a stylesheet does not raise, so a selector that
    stops matching just puts a whole page on top of every screen. It happened
    once already, when #UX-65 retired the Help twin and left the Session
    selector dangling on a comma, folded into the next rule's selector list.
    """
    import re

    from scanpath_studio.constants import (
        DATA_PAGE_OFFSCREEN_KEY,
        SESSION_PAGE_OFFSCREEN_KEY,
    )

    css = (PACKAGE / "styles.py").read_text(encoding="utf-8")
    for key in (SESSION_PAGE_OFFSCREEN_KEY, DATA_PAGE_OFFSCREEN_KEY):
        pattern = rf"\.st-key-{re.escape(key)}\s*\{{[^}}]*display:\s*none"
        assert re.search(pattern, css), (
            f"`.st-key-{key}` has no `display: none` rule of its own — the "
            "hidden page copy will render on every view."
        )
