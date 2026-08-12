"""UX-39 — the app's one easter egg: triple-click the title and eyes pop up.

Triple-click the "Scanpath Studio" heading and a pair of oversized googly eyes
pops up beside it, blinks once, follows the cursor for a few seconds, and fades
out on its own. That is all it does.

It lives entirely in the browser because it is deliberately **not** a feature: a
same-origin ``st.iframe`` script (the technique ``tour.py`` uses to reach the
parent document) binds one ``click`` listener keyed on ``event.detail >= 3``, so
there is no session-state key, no rerun, and nothing to expose on the deep link
/ CLI / headless API (``AGENTS.md`` → *Exposing a feature on every surface*).

Four details that are load-bearing rather than decorative:

- **It anchors to the heading's text, not its element.** ``st.title`` renders an
  ``h1`` that spans the whole 4/5-width header column, so the eyes are placed
  against a ``Range`` over its contents instead — otherwise they would land far
  out to the right of "Studio", next to nothing.
- **It re-measures every frame.** A ``requestAnimationFrame`` loop re-anchors the
  overlay (``position: fixed``) and aims the pupils, so scrolling, a resize, or a
  rerun reflow can't leave the eyes stranded mid-page.
- **It cleans up after a removed iframe.** Streamlit re-mounts this embed on
  every rerun, killing the old JS context mid-animation, which would orphan its
  nodes in the parent DOM forever. The script drops any leftover ``.sps-egg``
  before wiring itself, and marks the heading (``dataset.spsEggWired``) so the
  re-mount doesn't stack a second listener on a surviving node.
- **It never blocks the app.** The overlay is ``pointer-events: none`` so it
  cannot swallow a click meant for the Corpus Analysis button beside it, and the
  handler clears the text selection a triple-click makes for free.
"""

from __future__ import annotations

import json

import streamlit as st

from scanpath_studio.html_embed import embed_html_iframe

# The app title in the *parent* document: `app._render_about_panel` wraps the
# header in `st.container(key="about_header")`, which Streamlit renders as
# `.st-key-about_header`.
TITLE_SELECTOR = ".st-key-about_header h1"

# Below the spotlight tour's card (999990) and backdrop (999980) — a tour step
# that dims the app must stay on top of a stray pair of eyes.
_Z_INDEX = 999950

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
    animation: sps-egg-pop 420ms cubic-bezier(0.2, 1.5, 0.4, 1) both;
}
.sps-egg--out { animation: sps-egg-away __FADE__ms ease-in both; }
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
    .sps-egg, .sps-egg__eye { animation: none !important; }
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
            // Beside the heading when its own column has room. The header's other
            // column holds the Corpus Analysis button, and eyes parked over the
            // app's only nav control read as a rendering bug rather than a joke —
            // so when it's tight they peek over the top of the title instead,
            // where the page has nothing but padding. Never shrink to fit: "big"
            // is the whole idea.
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

        const teardown = () => {
            win.cancelAnimationFrame(frame);
            doc.removeEventListener("mousemove", onMove);
            wrap.remove();
        };
        win.setTimeout(() => {
            wrap.classList.add("sps-egg--out");
            win.setTimeout(teardown, __FADE__);
        }, __LIFETIME__);
    };

    let tries = 0;
    (function wire() {
        const title = doc.querySelector(__SELECTOR__);
        if (!title) {
            // A one-shot bind during React hydration is silently lost.
            if (++tries < 30) win.setTimeout(wire, 100);
            return;
        }
        if (title.dataset.spsEggWired) return;
        title.dataset.spsEggWired = "1";
        title.addEventListener("click", (ev) => {
            if (ev.detail < 3) return;
            doc.getSelection()?.removeAllRanges();  // triple-click selects the text
            pop(title);
        });
    })();
})();
"""


def egg_script() -> str:
    """The same-origin ``<script>`` that arms the triple-click easter egg."""
    css = _CSS.replace("__Z__", str(_Z_INDEX)).replace("__FADE__", str(_FADE_MS))
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
    """Arm the easter egg for this run, unless the session suppresses it."""
    if egg_suppressed(st.query_params, st.session_state):
        return
    embed_html_iframe(egg_script(), height=0)
