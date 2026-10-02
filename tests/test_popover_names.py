"""BUG-108 + UX-200: every icon-only button and popover has an accessible name.

The mode and rail-section triggers draw only Streamlit's chevron (UX-80 r2), and
until BUG-108 they did so by passing an empty label — which left nine unnamed
buttons for a screen reader to choose between. Each is now named ("Fixation
settings"), and `styles.py` clips the label off screen so the chevron is still
all that is drawn. Verified in the browser: the button's text and its dialog's
``aria-label`` read "Fixation settings", and the label's box is 1×1 px.

UX-200 extended that to every other control drawn as a glyph or icon alone: the
◀ ▶ steps, the ⇅ sorts, the folder pickers, ✏️, 🗑, ✨, + and the previews. Two
techniques, because Streamlit names the two differently:

- a **button** is named by its content alone, so it appends
  ``constants.spoken(name)`` to its label: an ``<em>`` that `styles.py` clips;
- a **popover** also copies its raw label into its dialog's ``aria-label``, so
  an ``<em>`` would be read out with its asterisks. It takes a plain label,
  ``icon=`` for the icon, and a key `styles.py` clips the label by
  (``iconpop_*``, or the ones listed in ``_KEYED_POPOVERS``).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scanpath_studio.constants import spoken
from scanpath_studio.styles import get_app_css

PACKAGE = Path(__file__).resolve().parents[1] / "scanpath_studio"
_BUTTONS = {"button", "download_button", "form_submit_button", "link_button"}
_SHORTCODE = re.compile(r":material/\w+:")
#: Popovers that keep a key from before UX-200 and are clipped by it.
_KEYED_POPOVERS = ("add_dataset_menu",)
_NAMED = "\x00named\x00"


def _label_text(node) -> str | None:
    """The label's text as far as the source says, or ``None`` when it is
    computed at run time (a variable, a call) and so presumably words."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Subscript) and getattr(node.value, "id", "") == "ICONS":
        return ""
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "spoken":
        return _NAMED
    if isinstance(node, ast.JoinedStr):
        parts = []
        for part in node.values:
            text = (
                part.value
                if isinstance(part, ast.Constant)
                else _label_text(part.value)
            )
            if text is None:
                return None
            parts.append(text)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _label_text(node.left), _label_text(node.right)
        return None if left is None or right is None else left + right
    return None


def _calls():
    for path in sorted(PACKAGE.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _BUTTONS | {"popover"}
                and node.args
            ):
                yield f"{path.name}:{node.lineno}", node


def _keyword(node, name):
    return next((k.value for k in node.keywords if k.arg == name), None)


def _visible_words(text: str) -> str:
    return re.sub(r"\W", "", _SHORTCODE.sub("", text))


def test_no_popover_is_created_without_a_label():
    blank = [
        where
        for where, node in _calls()
        if node.func.attr == "popover"
        and isinstance(node.args[0], ast.Constant)
        and not str(node.args[0].value).strip()
    ]
    assert not blank, blank


def test_every_icon_only_button_says_what_it_does():
    unnamed = []
    for where, node in _calls():
        if node.func.attr not in _BUTTONS:
            continue
        text = _label_text(node.args[0])
        if text is None or _NAMED in text:
            continue
        if not _visible_words(text):
            unnamed.append(where)
    assert not unnamed, f"icon-only buttons with no accessible name: {unnamed}"


def test_every_popover_has_a_plain_name():
    """No popover is drawn as an icon or glyph alone, and none uses `spoken`."""
    problems = []
    for where, node in _calls():
        if node.func.attr != "popover":
            continue
        text = _label_text(node.args[0])
        if text is not None and _NAMED in text:
            problems.append(f"{where}: a popover label is an aria-label; no spoken()")
        elif text is not None and not _visible_words(text):
            problems.append(f"{where}: icon-only popover label")
    assert not problems, problems


def test_the_clipped_popovers_are_named_in_plain_words():
    """A popover whose label `styles.py` clips shows its icon via ``icon=``
    (or, for the ⇅ sorts, the stylesheet), never inside the clipped label."""
    clipped = 0
    for where, node in _calls():
        key = _keyword(node, "key")
        source = ast.unparse(key) if key is not None else ""
        if node.func.attr != "popover" or not (
            "iconpop_" in source or any(k in source for k in _KEYED_POPOVERS)
        ):
            continue
        clipped += 1
        text = _label_text(node.args[0])
        assert text and _visible_words(text) and not _SHORTCODE.search(text), where
        assert _keyword(node, "icon") is not None or "iconpop_sort_" in source, where
    # The + menu, the four previews, the chip fields and the two sorts.
    assert clipped == 8


def test_no_button_label_uses_emphasis_but_spoken():
    """The clipping rule hides *every* ``<em>`` in a button label."""
    stray = []
    for where, node in _calls():
        for part in ast.walk(node.args[0]):
            if (
                isinstance(part, ast.Constant)
                and isinstance(part.value, str)
                and re.search(r"(?<![*\\])\*(?!\*)[^*]+(?<![*\\])\*(?!\*)", part.value)
            ):
                stray.append(where)
    assert not stray, stray


def test_spoken_escapes_markdown():
    assert spoken("Rename design *draft* v1.2") == (r"*Rename design \*draft\* v1\.2*")
    assert spoken("Next trial") == "*Next trial*"


def _rule_body(css: str, selector: str) -> str:
    assert selector in css, selector
    return css.split(selector, 1)[1].split("{", 1)[1].split("}", 1)[0]


def test_the_names_are_clipped_off_screen():
    css = re.sub(r"\s+", " ", get_app_css())
    for selector in (
        '[class*="st-key-split_mode_"] [data-testid="stPopoverButton"] '
        '[data-testid="stMarkdownContainer"]',
        '[class*="st-key-iconpop_"] [data-testid="stPopoverButton"] '
        '[data-testid="stMarkdownContainer"]',
        '.st-key-add_dataset_menu [data-testid="stPopoverButton"] '
        '[data-testid="stMarkdownContainer"]',
        'button [data-testid="stMarkdownContainer"] em',
    ):
        body = _rule_body(css, selector)
        assert "clip-path: inset(50%)" in body and "position: absolute" in body
    sort_glyph = _rule_body(
        css, '[class*="st-key-iconpop_sort_"] [data-testid="stPopoverButton"]::before'
    )
    assert 'content: "⇅" / ""' in sort_glyph


def test_the_rail_triggers_keep_a_focus_ring():
    """Their `box-shadow: none` took Streamlit's own ring (UX-200)."""
    css = re.sub(r"\s+", " ", get_app_css())
    body = _rule_body(
        css,
        '[data-testid="stHorizontalBlock"][class*="st-key-split_mode_"] '
        '[data-testid="stPopover"] button:focus-visible',
    )
    assert "outline: 2px solid var(--sps-accent)" in body
