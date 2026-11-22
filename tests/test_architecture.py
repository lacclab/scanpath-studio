"""Small dependency-boundary tests for the core data pipeline."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"


def _package_imports(source: str) -> set[str]:
    """Direct imports of this package's modules, including function-local imports."""
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level == 1:
                base = f"scanpath_studio.{base}".rstrip(".")
            names = [f"{base}.{alias.name}" for alias in node.names]
        else:
            continue
        for name in names:
            if name.startswith("scanpath_studio."):
                modules.add(name.split(".")[1])
    return modules


@pytest.mark.parametrize(
    "source",
    [
        "from .datasets import load_potec",
        "from . import datasets as ds",
        "from scanpath_studio import datasets",
        "import scanpath_studio.datasets as ds",
        "from scanpath_studio.datasets import load_potec",
    ],
)
def test_package_import_spellings(source):
    assert _package_imports(source) == {"datasets"}


@pytest.mark.parametrize(
    ("module", "forbidden"),
    [
        ("data", {"datasets"}),
        ("measures", {"preprocessing"}),
        ("metadata_editor", {"app", "tabs", "wizard"}),
        ("wizard", {"tabs"}),
    ],
)
def test_module_dependencies_are_one_way(module, forbidden):
    imports = _package_imports((PACKAGE / f"{module}.py").read_text(encoding="utf-8"))
    assert imports.isdisjoint(forbidden), f"{module} imports {imports & forbidden}"


def test_offscreen_page_twins_are_actually_hidden():
    """Every off-screen page copy carries its own `display: none` rule.

    The 🗂️ Data page renders on *every* run and is hidden by key when it is not
    the active view — the widgets inside are gates whose keys Streamlit drops if
    they do not render. That makes the hiding load-bearing and its failure
    silent: a stylesheet does not raise, so a selector that stops matching —
    say, one left dangling on a comma and folded into the next rule's selector
    list — just puts a whole page on top of every screen.

    Data is the only such page: ❓ Help's entries open dialogs, and a popover
    needs no twin because a popover body executes every run by itself.
    """
    import re

    from scanpath_studio.constants import DATA_PAGE_OFFSCREEN_KEY

    css = (PACKAGE / "styles.py").read_text(encoding="utf-8")
    for key in (DATA_PAGE_OFFSCREEN_KEY,):
        pattern = rf"\.st-key-{re.escape(key)}\s*\{{[^}}]*display:\s*none"
        assert re.search(pattern, css), (
            f"`.st-key-{key}` has no `display: none` rule of its own — the "
            "hidden page copy will render on every view."
        )
