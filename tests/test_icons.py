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

from scanpath_studio import constants, controls, fields, styles
from scanpath_studio.constants import ICONS, icon_html, icons_to_html

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


def test_icons_to_html_draws_every_shortcode_in_a_label():
    assert icons_to_html(f"{ICONS['axes']} Axes & grid") == (
        '<span class="sps-icon" aria-hidden="true">grid_on</span> Axes & grid'
    )


class _Host:
    """Records what a helper writes; enough of a DeltaGenerator for these two."""

    def __init__(self):
        self.written: list[str] = []

    def markdown(self, body, **_kwargs):
        self.written.append(body)

    def caption(self, body, **_kwargs):
        self.written.append(body)

    def container(self):
        return self


def test_a_rail_subheading_draws_its_icon_inside_the_html_block():
    # `_rail_subsection` writes a `<div>` line — a raw HTML block, where
    # Streamlit leaves a shortcode as literal text.
    host = _Host()
    controls._rail_subsection(host, f"{ICONS['screen']} Screen & framing")
    assert ":material/" not in host.written[0]
    assert "desktop_windows</span> Screen & framing" in host.written[0]


def test_a_row_tooltip_never_spells_out_a_shortcode():
    # The label keeps its icon (an inline span, which markdown still parses);
    # the plain-text tooltip drops it — from the gate reason in the help too.
    host = _Host()
    fields.row_label(
        host,
        f"{ICONS['favorite']} Favorite",
        f"Mark this trial.\n\n{ICONS['warning']} **Fixations** is off.",
    )
    (body,) = host.written
    tip = re.search(r'data-tip="([^"]*)"', body).group(1)
    assert ":material/" not in tip
    assert tip.startswith("Favorite — Mark this trial.")
    assert f">{ICONS['favorite']} Favorite</span>" in body


def test_subtab_labels_are_built_from_the_registry():
    assert constants.SUBTAB_EXPORT == f"{ICONS['export']} Export"
    assert constants.SUBTAB_ANNOTATIONS.startswith(ICONS["annotations"])


def test_the_rail_heading_is_sized_by_its_key_not_its_text():
    # BUG-88: Streamlit derives a heading's id from its text, the icon's name
    # included, so the icon turned `#plot-controls` into `#tune-plot-controls`
    # and the size pin silently stopped matching — a 36px heading, two lines.
    css = styles.get_app_css()
    assert ".st-key-plot_controls_header h2" in css
    assert "#plot-controls" not in css
    assert 'key="plot_controls_header"' in (PACKAGE / "tabs.py").read_text()


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
