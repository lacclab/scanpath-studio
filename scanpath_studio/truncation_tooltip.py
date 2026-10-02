"""UX-196 — hover a cut-off dropdown label to read all of it.

Streamlit's selectbox ends a label that does not fit with an ellipsis, in the
open list and in the closed box alike, and gives neither a ``title`` — so
"OneStop · Information seeking (repeated)" can only be told apart from
"OneStop · Information seeking" by picking it. Wrapping is not an option: the
list is virtualized, with fixed row heights (see
``styles.wide_dropdown_css``).

So this sets the native ``title`` tooltip on hover, and only when the label is
actually truncated. It applies to every selectbox and multiselect option in
the app, because the problem is the widget's rather than one picker's.

Browser-only, like the easter egg: there is no session state and no setting,
so nothing to expose on the deep link / CLI / headless API.

Two details that are load-bearing:

- **The listener runs in the parent's realm, not the iframe's.** Streamlit
  re-mounts this embed on every rerun; a listener created by the removed
  iframe's script belongs to a dead context. So the script injects a
  ``<script>`` element into the parent document, once (guarded by its id),
  and the code runs there.
- **It is one delegated ``mouseover`` listener.** The option rows are portalled
  and recycled by the virtualizer, so there is nothing stable to bind to — but
  every hover bubbles to the document.
"""

from __future__ import annotations

import json

from scanpath_studio.html_embed import embed_html_iframe

SCRIPT_ID = "sps-truncation-tooltip"

# What gets a tooltip: a dropdown row, or the closed box's current value (a
# react-aria combobox `<input>`, whose text is its `value`).
TARGET_SELECTOR = '[role="option"], input[role="combobox"]'

# Runs in the parent document. `title` is refreshed on every hover because the
# virtualizer recycles a row element for a different option as the list scrolls.
_PARENT_JS = """
(function () {
    const doc = document;
    const clipped = (el) =>
        [el, ...el.querySelectorAll("*")].some(
            (node) => node.scrollWidth > node.clientWidth + 1
        );
    doc.addEventListener("mouseover", (ev) => {
        const el = ev.target instanceof Element && ev.target.closest(__SELECTOR__);
        if (!el) return;
        const text = (el.value ?? el.innerText ?? "").trim();
        if (text && clipped(el)) el.title = text;
        else el.removeAttribute("title");
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


def tooltip_script() -> str:
    """The same-origin ``<script>`` that installs the hover listener once."""
    parent = _PARENT_JS.replace("__SELECTOR__", json.dumps(TARGET_SELECTOR))
    body = _JS.replace("__ID__", json.dumps(SCRIPT_ID)).replace(
        "__BODY__", json.dumps(parent)
    )
    return f"<script>{body}</script>"


def render_truncation_tooltips() -> None:
    """Install the listener (a no-op in the browser after the first run)."""
    embed_html_iframe(tooltip_script(), height=0)
