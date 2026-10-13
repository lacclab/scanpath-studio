"""#439 — downloads from the desktop app's own window open a Save-as dialog.

The desktop app opens in a Chrome / Edge ``--app`` window (ENG-85). Current
Chromium reports a download in the toolbar's download bubble, and an app window
has no toolbar, so a download there either saves silently or shows up in some
other browser window: clicking ⬇ Download GIF (or HTML, or anything else)
looked like it did nothing.

Every download in the app ends in a click on an ``<a download>`` the page made
— ``st.download_button`` on a ``/media/…`` URL, the figure's PNG/SVG button
(`tabs._image_download_component`) on a ``blob:`` URL. Inside an app window
(``display-mode: standalone``) this takes that click instead: it asks the
browser's own Save-as dialog (``showSaveFilePicker``) where the file goes,
streams the file there and says so. A cancelled dialog saves nothing. Where
the dialog can't open (no user gesture left, an older browser), and in every
ordinary browser tab, the click is the browser's own, unchanged.

Browser-only, like `color_picker_commit`: no session state and no setting, so
nothing to expose on the deep link / CLI / headless API. Installed once into
the parent document for the reason given there.
"""

from __future__ import annotations

import json

from scanpath_studio.html_embed import embed_html_iframe

SCRIPT_ID = "sps-save-dialog"

# Runs in the parent document, where Streamlit and the v2 components make their
# download links, so patching the prototype's click reaches all of them.
_PARENT_JS = r"""
(function () {
    if (typeof window.showSaveFilePicker !== "function") return;
    const appWindow = () => window.matchMedia("(display-mode: standalone)").matches;
    const nativeClick = HTMLAnchorElement.prototype.click;

    const nameFrom = (disposition) => {
        if (!disposition) return "";
        const star = /filename\*\s*=\s*[^']*''([^;]+)/i.exec(disposition);
        if (star) {
            try { return decodeURIComponent(star[1].trim()); } catch (_e) { /* fall through */ }
        }
        const plain = /filename\s*=\s*"([^"]*)"|filename\s*=\s*([^;]+)/i.exec(disposition);
        return plain ? (plain[1] || plain[2] || "").trim() : "";
    };

    const toast = (text, failed) => {
        const note = document.createElement("div");
        note.textContent = text;
        note.setAttribute("role", "status");
        note.style.cssText = [
            "position:fixed", "right:1rem", "bottom:1rem", "z-index:1000001",
            "max-width:28rem", "padding:0.6rem 0.9rem", "border-radius:0.5rem",
            "font:14px/1.4 'Source Sans Pro',sans-serif", "color:#fff",
            "box-shadow:0 4px 14px rgba(0,0,0,0.25)",
            "background:" + (failed ? "#b3261e" : "#1e6e43"),
        ].join(";");
        document.body.appendChild(note);
        setTimeout(() => note.remove(), failed ? 8000 : 4000);
    };

    async function save(link, url) {
        let name = link.getAttribute("download") || "";
        if (!name && url.protocol !== "blob:") {
            const head = await fetch(url, { method: "HEAD" });
            name = nameFrom(head.headers.get("Content-Disposition"));
        }
        if (!name) name = decodeURIComponent(url.pathname.split("/").pop() || "download");
        // Throws before anything is written: no gesture left, or cancelled.
        const handle = await window.showSaveFilePicker({ suggestedName: name });
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error("the app answered " + response.status);
            await response.body.pipeTo(await handle.createWritable());
        } catch (err) {
            toast("Couldn't save " + handle.name + " (" + ((err && err.message) || err) + "). Try again.", true);
            return;
        }
        toast("Saved " + handle.name);
    }

    HTMLAnchorElement.prototype.click = function () {
        if (!this.hasAttribute("download") || !appWindow()) return nativeClick.call(this);
        let url;
        try { url = new URL(this.href, window.location.href); } catch (_e) { return nativeClick.call(this); }
        if (url.protocol !== "blob:" && url.origin !== window.location.origin) {
            return nativeClick.call(this);
        }
        const link = this;
        save(link, url).catch((err) => {
            if (err && err.name === "AbortError") return;  // the dialog was cancelled
            nativeClick.call(link);  // the dialog could not open: the browser's own download
        });
    };
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


def save_dialog_script() -> str:
    """The same-origin ``<script>`` that installs the hook once."""
    body = _JS.replace("__ID__", json.dumps(SCRIPT_ID)).replace(
        "__BODY__", json.dumps(_PARENT_JS)
    )
    return f"<script>{body}</script>"


def render_save_dialog() -> None:
    """Install the hook (a no-op in the browser after the first run)."""
    embed_html_iframe(save_dialog_script(), height=0)
