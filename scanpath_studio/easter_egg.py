"""The app's one easter egg: triple-click the About heading and eyes pop up.

Triple-click "About Scanpath Studio", the heading of ❓ Help → About, and a
pair of oversized googly eyes pops up beside it, blinks once, follows the
cursor for a few seconds, and fades out on its own. That is all it does.

The header's wordmark would be the natural target, but it is a link that opens
the docs: the first click of a triple-click has already opened them.

It lives entirely in the browser because it is deliberately **not** a feature: a
same-origin ``st.iframe`` script (the technique ``tour.py`` uses to reach the
parent document) binds one ``click`` listener keyed on ``event.detail >= 3``, so
there is no session-state key, no rerun, and nothing to expose on the deep link
/ CLI / headless API (``AGENTS.md`` → *Exposing a feature on every surface*).
The About dialog draws the script (:func:`render_easter_egg`), so it runs only
while the heading is on screen.

Four details that are load-bearing rather than decorative:

- **It anchors to the heading's text, not its element.** The dialog's ``h2``
  spans the dialog's width, so the eyes are placed against a ``Range`` over its
  contents instead — otherwise they would land far out to the right of
  "Studio", next to nothing.
- **It re-measures every frame.** A ``requestAnimationFrame`` loop re-anchors the
  overlay (``position: fixed``) and aims the pupils, so scrolling, a resize, or a
  rerun reflow can't leave the eyes stranded mid-page.
- **It survives a removed iframe.** Streamlit re-mounts this embed on every
  rerun of the dialog and removes it when the dialog closes, killing its JS
  context mid-animation. The fade is pure CSS, so eyes orphaned that way still
  disappear; the next mount drops any leftover ``.sps-egg`` and replaces the
  heading's click handler (``__spsEgg``), whose old copy died with its frame.
- **It never blocks the app.** The overlay is ``pointer-events: none`` so it
  cannot swallow a click meant for a control beneath it, and the handler
  clears the text selection a triple-click makes for free.
"""

from __future__ import annotations

import json

import streamlit as st

from scanpath_studio.html_embed import embed_html_iframe

#: The container the script is drawn in. It sits in the About dialog's body,
#: which is how the selector below tells that dialog's heading from another's.
EGG_KEY = "about_egg"

#: The About dialog's heading, in the *parent* document.
TITLE_SELECTOR = f'[data-testid="stDialog"]:has(.st-key-{EGG_KEY}) h2'

# Above Streamlit's dialog (z-index 1000059), which holds the heading. A running
# tour or tutorial suppresses the egg, so nothing of theirs has to cover it.
_Z_INDEX = 1000100

# How long the eyes stay before they fade, and how long the fade takes.
_LIFETIME_MS = 4200
_FADE_MS = 520

_CSS = """
.sps-egg {
    position: fixed;
    z-index: __Z__;
    display: flex;
    gap: var(--sps-egg-gap, 6px);
    pointer-events: none;
    transform-origin: 50% 100%;
    filter: drop-shadow(0 3px 6px rgba(0, 0, 0, 0.35));
    animation:
        sps-egg-pop 420ms cubic-bezier(0.2, 1.5, 0.4, 1) both,
        sps-egg-away __FADE__ms ease-in __LIFETIME__ms forwards;
}
.sps-egg__eye {
    position: relative;
    width: var(--sps-egg-size, 48px);
    height: var(--sps-egg-size, 48px);
    border-radius: 50%;
    border: 2px solid rgba(0, 0, 0, 0.55);
    background: radial-gradient(circle at 32% 28%, #fff 0 55%, #e6e6ea 100%);
    overflow: hidden;
    animation: sps-egg-blink 260ms ease-in-out 1.05s 1;
}
.sps-egg__pupil {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 42%;
    height: 42%;
    margin: -21% 0 0 -21%;
    border-radius: 50%;
    background: #16181d;
    transform: translate(var(--sps-egg-px, 0px), var(--sps-egg-py, 0px));
}
.sps-egg__pupil::after {
    content: "";
    position: absolute;
    top: 14%;
    left: 16%;
    width: 30%;
    height: 30%;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.85);
}
@keyframes sps-egg-pop {
    from { transform: translateY(16px) scale(0.2); opacity: 0; }
    60% { transform: translateY(0) scale(1.15); opacity: 1; }
    to { transform: none; opacity: 1; }
}
@keyframes sps-egg-away {
    from { opacity: 1; }
    to { opacity: 0; transform: translateY(-10px) scale(0.75); }
}
@keyframes sps-egg-blink {
    40%, 60% { transform: scaleY(0.08); }
}
@media (prefers-reduced-motion: reduce) {
    .sps-egg__eye { animation: none !important; }
    /* No motion, but still gone on time: an instant fade, not none. */
    .sps-egg { animation: sps-egg-away 1ms linear __LIFETIME__ms forwards !important; }
}
"""

_MARKUP = (
    '<div class="sps-egg__eye"><div class="sps-egg__pupil"></div></div>'
    '<div class="sps-egg__eye"><div class="sps-egg__pupil"></div></div>'
)

# Placeholders rather than an f-string: the script is mostly braces, and
# doubling every one of them to satisfy `str.format` makes it unreviewable.
_JS = """
(function () {
    const doc = window.parent.document;
    const win = doc.defaultView;
    if (!doc.body) return;

    if (!doc.getElementById("sps-egg-style")) {
        const style = doc.createElement("style");
        style.id = "sps-egg-style";
        style.textContent = __CSS__;
        doc.head.appendChild(style);
    }

    // A rerun destroys the iframe that owns the running animation, so anything
    // still on screen from the previous run is now inert. Drop it.
    const clear = () => doc.querySelectorAll(".sps-egg").forEach((e) => e.remove());
    clear();

    // `st.title`'s h1 fills the header column; the glyphs are what we want to
    // sit beside, so measure a range over its contents instead.
    const textRect = (el) => {
        const range = doc.createRange();
        range.selectNodeContents(el);
        const rect = range.getBoundingClientRect();
        return rect.width ? rect : el.getBoundingClientRect();
    };

    const pop = (title) => {
        clear();
        const wrap = doc.createElement("div");
        wrap.className = "sps-egg";
        wrap.innerHTML = __MARKUP__;
        doc.body.appendChild(wrap);

        const fontPx = parseFloat(win.getComputedStyle(title).fontSize) || 32;
        const size = Math.max(26, Math.min(72, fontPx * 1.45));
        wrap.style.setProperty("--sps-egg-size", size + "px");
        wrap.style.setProperty("--sps-egg-gap", size * 0.14 + "px");

        const eyes = [...wrap.querySelectorAll(".sps-egg__eye")];
        let pointer = null;
        const onMove = (ev) => { pointer = { x: ev.clientX, y: ev.clientY }; };
        doc.addEventListener("mousemove", onMove);

        let frame = 0;
        const place = () => {
            const rect = textRect(title);
            const width = wrap.offsetWidth || size * 2;
            // Beside the heading when its own column has room; when it's tight
            // they peek over the top of the title instead, where the page has
            // nothing but padding, rather than spill into the header's other
            // column. Never shrink to fit: "big" is the whole idea.
            const colRight = Math.min(
                title.getBoundingClientRect().right, win.innerWidth
            );
            if (rect.right + size * 0.3 + width <= colRight - 4) {
                wrap.style.left = rect.right + size * 0.3 + "px";
                wrap.style.top = rect.top + rect.height / 2 - size / 2 + "px";
            } else {
                wrap.style.left =
                    Math.max(8, rect.left + (rect.width - width) / 2) + "px";
                wrap.style.top = Math.max(4, rect.top - size * 0.8) + "px";
            }
            eyes.forEach((eye) => {
                const box = eye.getBoundingClientRect();
                if (!pointer || !box.width) return;
                const dx = pointer.x - (box.left + box.width / 2);
                const dy = pointer.y - (box.top + box.height / 2);
                const dist = Math.hypot(dx, dy) || 1;
                // Reach the rim only once the cursor is a comfortable way off.
                const travel = size * 0.16 * Math.min(1, dist / 140);
                const pupil = eye.querySelector(".sps-egg__pupil");
                pupil.style.setProperty("--sps-egg-px", (dx / dist) * travel + "px");
                pupil.style.setProperty("--sps-egg-py", (dy / dist) * travel + "px");
            });
            frame = win.requestAnimationFrame(place);
        };
        place();

        // The CSS fades the eyes out; this only removes them once it has.
        const teardown = () => {
            win.cancelAnimationFrame(frame);
            doc.removeEventListener("mousemove", onMove);
            wrap.remove();
        };
        win.setTimeout(teardown, __LIFETIME__ + __FADE__);
    };

    let tries = 0;
    (function wire() {
        const title = doc.querySelector(__SELECTOR__);
        if (!title) {
            // A one-shot bind during React hydration is silently lost.
            if (++tries < 30) win.setTimeout(wire, 100);
            return;
        }
        // A rerun of the dialog re-mounts this script on a heading that
        // survives it, and the previous mount's handler died with its frame:
        // replace it, rather than stacking a second or keeping a dead one.
        if (title.__spsEgg) title.removeEventListener("click", title.__spsEgg);
        title.__spsEgg = (ev) => {
            if (ev.detail < 3) return;
            doc.getSelection()?.removeAllRanges();  // triple-click selects the text
            pop(title);
        };
        title.addEventListener("click", title.__spsEgg);
    })();
})();
"""


def egg_script() -> str:
    """The same-origin ``<script>`` that arms the triple-click easter egg."""
    css = (
        _CSS.replace("__Z__", str(_Z_INDEX))
        .replace("__FADE__", str(_FADE_MS))
        .replace("__LIFETIME__", str(_LIFETIME_MS))
    )
    body = (
        _JS.replace("__CSS__", json.dumps(css))
        .replace("__MARKUP__", json.dumps(_MARKUP))
        .replace("__SELECTOR__", json.dumps(TITLE_SELECTOR))
        .replace("__LIFETIME__", str(_LIFETIME_MS))
        .replace("__FADE__", str(_FADE_MS))
    )
    return f"<script>{body}</script>"


def egg_suppressed(query_params, session_state=None) -> bool:
    """True when this session shouldn't arm the egg.

    Embeds (``?embed=true``) are somebody else's UI — an external review tool
    frames this app and owns the surrounding chrome. A running tour or tutorial
    is mid-explanation, and the spotlight step that highlights the header would
    be competing with a pair of eyes for the same corner of the screen. Takes the
    params as a mapping (like :func:`tour.tour_suppressed`) because AppTest can't
    inject query params.
    """
    if (query_params.get("embed") or "").lower() in {"true", "1"}:
        return True
    state = session_state if session_state is not None else {}
    return bool(state.get("tour_mode") or state.get("tutorial_active"))


def render_easter_egg() -> None:
    """Arm the easter egg, unless the session suppresses it.

    Called from the About dialog's body: the keyed container it draws is what
    `TITLE_SELECTOR` finds that dialog by.
    """
    if egg_suppressed(st.query_params, st.session_state):
        return
    with st.container(key=EGG_KEY):
        embed_html_iframe(egg_script(), height=0)
