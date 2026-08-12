"""Small dependency-boundary tests for the core data pipeline."""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"


def _relative_imports(module: str) -> set[str]:
    tree = ast.parse((PACKAGE / f"{module}.py").read_text())
    return {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level
    }


def test_core_data_dependencies_are_one_way():
    """Keep the two cycles removed by ENG-28 from growing back."""
    assert "datasets" not in _relative_imports("data")
    assert "preprocessing" not in _relative_imports("measures")
