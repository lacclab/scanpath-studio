"""#422 — a color picked in a popover sticks when the popover is dismissed.

Streamlit's color picker sends its value when its own small dialog closes: on
a click outside it, on Escape, or on a second click on its swatch. Every rail
color sits inside an ``st.popover``, and a click on the page outside that
popover closes the popover on the same click — which unmounts the picker
before its own click handler runs. The swatch showed the new color, and it was
dropped without a rerun: "changing the box fill color doesn't change it".

So the press that starts any click outside an open picker (``pointerdown``,
which comes before both handlers' ``click``) first clicks the picker's swatch:
the picker's own close-and-send path. A press inside the picker — dragging in
the color field, typing a hex value — is left alone, and so is everything
else: a picker that would have sent its value still sends it, once.

Browser-only, like `truncation_tooltip`: no session state and no setting, so
nothing to expose on the deep link / CLI / headless API. Installed once into
the parent document for the reason given there (Streamlit re-mounts the embed
on every rerun, and a listener from a removed iframe belongs to a dead realm).
"""

from __future__ import annotations

import json

from scanpath_studio.html_embed import embed_html_iframe

SCRIPT_ID = "sps-color-picker-commit"

#: The open picker's swatch (the picker's own toggle button) and its dialog.
OPEN_SWATCH_SELECTOR = '.stColorPicker button[aria-expanded="true"]'
PICKER_DIALOG_SELECTOR = (
    '[data-testid="stColorPickerPopover"], [role="dialog"][aria-label$="color picker"]'
)

# Runs in the parent document. `window` capture runs before the popover's own
# capture listener on `document`, so the picker sends before anything closes.
_PARENT_JS = """
(function () {
    window.addEventListener("pointerdown", (ev) => {
        const swatch = document.querySelector(__SWATCH__);
        const target = ev.target;
        if (!swatch || !(target instanceof Node) || swatch.contains(target)) return;
        if (target instanceof Element && target.closest(__DIALOG__)) return;
        swatch.click();
    }, true);
})();
"""

_JS = """
(function () {
    const doc = window.parent.document;
    if (!doc.head || doc.getElementById(__ID__)) return;
    const script = doc.createElement("script");
    script.id = __ID__;
    script.textContent = __BODY__;
    doc.head.appendChild(script);
})();
"""


def commit_script() -> str:
    """The same-origin ``<script>`` that installs the listener once."""
    parent = _PARENT_JS.replace("__SWATCH__", json.dumps(OPEN_SWATCH_SELECTOR)).replace(
        "__DIALOG__", json.dumps(PICKER_DIALOG_SELECTOR)
    )
    body = _JS.replace("__ID__", json.dumps(SCRIPT_ID)).replace(
        "__BODY__", json.dumps(parent)
    )
    return f"<script>{body}</script>"


def render_color_picker_commit() -> None:
    """Install the listener (a no-op in the browser after the first run)."""
    embed_html_iframe(commit_script(), height=0)
