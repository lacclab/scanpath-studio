"""Switching the Scanpath view's subtabs keeps the tab bar where it is.

The subtabs under the plot draw only the selected panel (`tabs.py`, keyed
``st.tabs`` with ``on_change="rerun"``), so a switch swaps one panel's height
for another's. Scrolled to the bottom of a tall panel (Export), a switch to a
shorter one (Share) leaves the page too short for where it was scrolled. The
browser pulls the scroll position back, and the tab bar and everything under
it jump down the screen, then shift again as the new panel draws.

So the press that switches a subtab first gives the subtab area just enough
minimum height to fill the scroll box below where its bar sits now. Whatever
the new panel's height, the page is then long enough for the bar to stay put.
The reserve is blank space below the panel, and only as much as that switch
needs; the next switch sizes it again.

Browser-only, like `truncation_tooltip`: no session state and no setting, so
nothing to expose on the deep link / CLI / headless API. Installed once into
the parent document for the reason given there (Streamlit re-mounts the embed
on every rerun, and a listener from a removed iframe belongs to a dead realm).
"""

from __future__ import annotations

import json

from scanpath_studio.html_embed import embed_html_iframe

SCRIPT_ID = "sps-subtab-scroll"

#: The Scanpath view's subtab bar (`tabs.py`, ``key="single_subtab"``).
SUBTABS_SELECTOR = ".st-key-single_subtab"

# Runs in the parent document. Capture on `window` runs before the tab's own
# handlers, so the reserve is in place before the panels swap. Only a press
# that can switch sizes it: one on a tab that is not already selected, or a
# key that moves the selection along the bar.
_PARENT_JS = """
(function () {
    const scrollBox = (el) => {
        for (let node = el.parentElement; node; node = node.parentElement) {
            const overflow = getComputedStyle(node).overflowY;
            if (overflow === "auto" || overflow === "scroll") return node;
        }
        return document.scrollingElement;
    };
    const SWITCH_KEYS = new Set(["ArrowLeft", "ArrowRight", "Home", "End"]);
    const reserve = (ev) => {
        const target = ev.target;
        if (!(target instanceof Element)) return;
        const tab = target.closest('[role="tab"]');
        const area = tab && tab.closest(__SUBTABS__);
        if (!area) return;
        if (ev.type === "keydown" ? !SWITCH_KEYS.has(ev.key)
            : tab.getAttribute("aria-selected") === "true") return;
        const box = scrollBox(area);
        const viewTop = box === document.scrollingElement
            ? 0 : box.getBoundingClientRect().top;
        const areaRect = area.getBoundingClientRect();
        // The page under the subtab area (the main block's bottom padding)
        // also fills the box, so it counts toward the room needed.
        const below = box.scrollHeight - box.scrollTop
            - (areaRect.bottom - viewTop);
        const need = box.clientHeight - (areaRect.top - viewTop) - below;
        area.style.minHeight = need > 0 ? Math.ceil(need) + "px" : "";
    };
    window.addEventListener("pointerdown", reserve, true);
    window.addEventListener("keydown", reserve, true);
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


def scroll_script() -> str:
    """The same-origin ``<script>`` that installs the listener once."""
    parent = _PARENT_JS.replace("__SUBTABS__", json.dumps(SUBTABS_SELECTOR))
    body = _JS.replace("__ID__", json.dumps(SCRIPT_ID)).replace(
        "__BODY__", json.dumps(parent)
    )
    return f"<script>{body}</script>"


def render_subtab_scroll() -> None:
    """Install the listener (a no-op in the browser after the first run)."""
    embed_html_iframe(scroll_script(), height=0)
