"""BUG-108: every popover trigger has an accessible name.

The mode and rail-section triggers draw only Streamlit's chevron (UX-80 r2), and
until BUG-108 they did so by passing an empty label — which left nine unnamed
buttons for a screen reader to choose between. Each is now named ("Fixation
settings"), and `styles.py` clips the label off screen so the chevron is still
all that is drawn. Verified in the browser: the button's text and its dialog's
``aria-label`` read "Fixation settings", and the label's box is 1×1 px.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scanpath_studio.styles import get_app_css

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"


def test_no_popover_is_created_without_a_label():
    blank = []
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "popover"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and not str(node.args[0].value).strip()
            ):
                blank.append(f"{path.name}:{node.lineno}")
    assert not blank, blank


def test_the_chevron_only_triggers_clip_their_label_off_screen():
    css = re.sub(r"\s+", " ", get_app_css())
    rule = (
        '[class*="st-key-split_mode_"] [data-testid="stPopoverButton"] '
        '[data-testid="stMarkdownContainer"] {'
    )
    assert rule in css
    body = css.split(rule, 1)[1].split("}", 1)[0]
    assert "clip-path: inset(50%)" in body and "position: absolute" in body
