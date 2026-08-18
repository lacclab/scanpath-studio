"""The ``label | field`` row — one primitive, shared by every panel that has one.

UX-51 built this for the Scanpath rail's plot controls and UX-53 spread it over
the upload wizard, but both kept it private to :mod:`controls`. UX-69 needs the
same row in the Scanpath subtabs, and :mod:`controls` cannot supply it there:
it already imports :mod:`annotations` and :mod:`export`, so those two — which
render three of the subtabs between them — would import it back in a cycle.
Hence a module *below* all of them, holding nothing but the row.

The row is two columns: the field's name on the left, the control itself on the
right, vertically centered against each other. That buys back the line every
Streamlit widget spends on its label, which is what makes a panel of a dozen
fields fit on one screen — and it lines the controls up on a common left edge,
so a column of them reads as a form rather than as a ragged stack.

``help`` folds into the *title's* own hover tooltip rather than getting a `?`
icon beside it (see :func:`row_label`); the widget keeps its real label and
``help``, only ``label_visibility="collapsed"`` hides where Streamlit would
have drawn them.
"""

from __future__ import annotations

import html
import re

#: The label column's share of a ``label | field`` row in a **full-width** panel
#: — a Scanpath subtab body, which is 4/5 of the page (UX-69). About 180px at a
#: typical window: enough for "Participant fields to include" to survive, while
#: leaving the control the room a pills row or a path pattern wants.
PANEL_LABEL_W = 0.2

#: The same share in a **narrow** column: the rail's ~28rem popover (`styles.
#: get_app_css` pins `stPopoverBody`), or a subtab's side column. ~160px of
#: label — about 23 characters at the rail's 0.92rem — while leaving the field
#: wide enough for a multiselect's chips, or for a slider plus the UX-9 box you
#: type an exact value into.
NARROW_LABEL_W = 0.36

#: Tighter than the 1rem default: these rows are dense and the width is scarce.
LABEL_GAP = "xsmall"

#: Markdown emphasis, which a plain-text tooltip would show as literal
#: punctuation.
_MD_MARKS = re.compile(r"\*\*|`")
_WHITESPACE_RUN = re.compile(r"\s+")


def plain(text: str) -> str:
    """``text`` with markdown emphasis stripped, for a plain-text tooltip.

    Newlines collapse to spaces along with every other run of whitespace, and
    that is not cosmetic (UX-68): :func:`row_label` interpolates the result into
    an HTML attribute inside an ``st.markdown`` string, and a **blank line** ends
    a raw HTML block in markdown — so a two-paragraph help text (every
    ``controls._gated_help`` result is one) would split the opening ``<span …>``
    and render the rest of the tag as visible page text. A tooltip is one line
    anyway; the paragraph break has nothing to do there.
    """
    return _WHITESPACE_RUN.sub(" ", _MD_MARKS.sub("", text)).strip()


def row_label(host, label: str, help: str | None) -> None:
    """Render one row's title into its own (left) column.

    ``help`` folds into the title's own hover tooltip rather than getting a `?`
    icon beside it, and the title text is repeated at the head of that tooltip so
    a label the column had to truncate is still readable in full.

    The tooltip is CSS (``data-tip`` + ``styles.py``'s ``.sps-fhelp::after``),
    not the browser's native ``title=``. Native ``title`` waits about a second
    before it appears — fine for an occasional "what is this file", far too slow
    for a form whose every row hides its description there. The CSS one opens in
    ~120 ms, matching the `?` icons Streamlit draws elsewhere. ``aria-label``
    keeps the text reachable now that no ``title`` carries it.
    """
    text = plain(label)
    if not help:
        host.markdown(
            f'<span class="sps-flabel">{html.escape(text)}</span>',
            unsafe_allow_html=True,
        )
        return
    tip = html.escape(f"{text} — {plain(help)}", quote=True)
    host.markdown(
        f'<span class="sps-fhelp" data-tip="{tip}" aria-label="{tip}">'
        f'<span class="sps-flabel sps-flabel-help">{html.escape(text)}</span>'
        "</span>",
        unsafe_allow_html=True,
    )


def labeled(
    host,
    kind: str,
    label: str,
    *,
    display: str | None = None,
    help: str | None = None,
    label_width: float = NARROW_LABEL_W,
    align: str = "center",
    **kwargs,
):
    """Render one control as a ``label | field`` row; return the widget's value.

    ``kind`` names the Streamlit method to call (``"selectbox"``,
    ``"multiselect"``, ``"color_picker"``, …) and every other argument is
    forwarded untouched, so converting a call site is a matter of *naming* the
    widget instead of calling it. The widget still receives the real ``label``
    and ``help`` — only where they are drawn changes.

    ``display`` overrides the *visible* text without touching the widget's own
    label. Use it where the accessible name has to stay unique but would be far
    too long for the column — the per-scanpath comparison styling, whose rows are
    already captioned with the scanpath they belong to, or a checkbox whose label
    is a whole sentence (the title column is one ellipsized line, so the sentence
    belongs in ``help``, on the hover).

    ``label_width`` picks the column split: :data:`PANEL_LABEL_W` in a full-width
    panel, :data:`NARROW_LABEL_W` (the default) in the rail or a side column.
    ``align`` is the columns' ``vertical_alignment``; ``"top"`` suits a control
    that is many lines tall (a text area), where a centered title would float
    opposite the middle of an empty box.
    """
    label_col, field_col = host.columns(
        [label_width, 1.0 - label_width], gap=LABEL_GAP, vertical_alignment=align
    )
    row_label(label_col, display if display is not None else label, help)
    return getattr(field_col, kind)(
        label, help=help, label_visibility="collapsed", **kwargs
    )


def panel_field(host, kind: str, label: str, **kwargs):
    """:func:`labeled` at :data:`PANEL_LABEL_W` — the full-width-panel default."""
    kwargs.setdefault("label_width", PANEL_LABEL_W)
    return labeled(host, kind, label, **kwargs)
