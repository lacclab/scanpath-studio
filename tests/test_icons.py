"""UX-138: the app's icon vocabulary lives in one registry, `constants.ICONS`.

Two guards. Every entry must name a real Material Symbols icon — Streamlit ships
the list it validates against, so a typo fails here rather than as a blank box
in the browser. And no ``icon=`` argument may take a raw emoji again: that slot
is chrome by definition, which is exactly what the registry is for, and literals
there are how the app ended up speaking two icon languages at once.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from streamlit.material_icon_names import ALL_MATERIAL_ICONS

from scanpath_studio import constants
from scanpath_studio.constants import ICONS, icon_html

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"
SHORTCODE = re.compile(r"^:material/([a-z0-9_]+):$")


@pytest.mark.parametrize("concept", sorted(ICONS))
def test_every_icon_is_a_real_material_symbol(concept):
    match = SHORTCODE.match(ICONS[concept])
    assert match, f"{concept}: {ICONS[concept]!r} is not a :material/…: shortcode"
    assert match.group(1) in ALL_MATERIAL_ICONS, f"{concept}: no such icon"


def test_icon_html_carries_the_ligature_not_the_shortcode():
    assert icon_html("warning") == (
        '<span class="sps-icon" aria-hidden="true">warning</span>'
    )


def test_subtab_labels_are_built_from_the_registry():
    assert constants.SUBTAB_EXPORT == f"{ICONS['export']} Export"
    assert constants.SUBTAB_ANNOTATIONS.startswith(ICONS["annotations"])


def _icon_literals(path: Path) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            value = kw.value
            if (
                kw.arg == "icon"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                found.append((node.lineno, value.value))
    return found


def test_no_icon_argument_is_a_literal():
    # Not even a correct `:material/…:` one: a literal is invisible to the
    # registry, so the next swap would miss it.
    offenders = {
        path.name: hits
        for path in sorted(PACKAGE.glob("*.py"))
        if (hits := _icon_literals(path))
    }
    assert not offenders, f"use constants.ICONS for icon=: {offenders}"
