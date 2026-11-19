"""Bidirectional browser canvas for the authoring document."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

_HTML = """
<div class="tools">
  <div role="group" aria-label="Canvas mode">
    <button class="draw" type="button">Draw</button>
    <button class="edit" type="button">Select &amp; move</button>
  </div>
  <button class="preview" type="button">Play preview</button>
  <label>Zoom <select class="zoom">
    <option value="fit">Fit</option><option value="1">100%</option>
    <option value="1.5">150%</option><option value="2">200%</option>
  </select></label>
</div>
<p class="hint"></p>
<div class="viewport" tabindex="0" aria-label="Drawing area">
  <svg class="authoring-canvas" role="group" aria-label="Interactive fixation authoring canvas"></svg>
</div>
<div class="tools selection">
  <label>Fixation <select class="visits"></select></label>
  <label>Duration (ms) <input class="duration" type="number" min="1" step="any"></label>
  <button type="button" class="delete">Delete selected</button>
</div>
"""

_CSS = """
:host {display:block;color:var(--st-text-color);font-family:var(--st-font)}
.tools,.tools [role=group],label {display:flex;align-items:center;gap:.4rem;flex-wrap:wrap}
.tools {gap:.75rem}
button,select,input {font:inherit;font-size:.9rem;color:inherit;background:var(--st-background-color);
  border:1px solid var(--st-border-color,#aaa);border-radius:.4rem;min-height:2rem;padding:.15rem .55rem}
button,select {cursor:pointer}
button[aria-pressed=true] {background:var(--st-primary-color,#176bad);color:white}
button:disabled,input:disabled,select:disabled {opacity:.55}
.hint {margin:.35rem 0;font-size:.88rem}
.viewport {overflow:auto;max-height:62vh;background:white;border:1px solid #adb5bd;border-radius:.45rem}
.authoring-canvas {display:block;user-select:none;cursor:crosshair}
.authoring-canvas.edit-mode {cursor:default}
.edit-mode .fixation {cursor:grab;touch-action:none}
.word-box {fill:#f7f8fa;stroke:#b7bec9}
.word-label {fill:#222;font:16px sans-serif;dominant-baseline:middle;pointer-events:none}
.path {fill:none;stroke:#5a79a5;stroke-width:2;pointer-events:none}
.fixation {fill:#225b9e;fill-opacity:.85;stroke:white;stroke-width:2}
.authoring-canvas:not(.replaying) .fixation.selected,.fixation.playing {fill:#9e470b;stroke:#172330;stroke-width:3}
.fixation:focus-visible {stroke:#101722;stroke-width:4}
.order {fill:white;font:bold 11px sans-serif;dominant-baseline:middle;text-anchor:middle;pointer-events:none}
.selection {margin-top:.5rem}
.duration {width:6rem}
"""

_JS = r"""
export default function (component) {
    const { data, parentElement, setTriggerValue } = component;
    const get = selector => parentElement.querySelector(selector);
    const svg = get('.authoring-canvas');
    const visits = get('.visits'), duration = get('.duration'), preview = get('.preview');
    const events = data.events, words = data.words;
    // A second click can arrive while Streamlit is applying the first.
    // Send the next edit when the server mounts the updated table revision.
    const state = svg.editorState ??= { mode: 'draw', zoom: window.matchMedia('(max-width: 600px)').matches ? '1' : 'fit', pending: [], sent: null };
    clearTimeout(state.timer);
    const sendNext = () => {
        if (state.sent === null && state.pending.length && data.editable) {
            state.sent = data.revision;
            setTriggerValue('event', state.pending.shift());
        }
    };
    if (state.sent !== data.revision)
        state.sent = null;
    const emit = event => { state.pending.push(event); sendNext(); };
    const make = (tag, attrs, text) => {
        const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [key, value] of Object.entries(attrs))
            node.setAttribute(key, value);
        if (text != null)
            node.textContent = text;
        svg.appendChild(node);
        return node;
    };
    const point = e => {
        const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM().inverse());
        return { x: Math.round(p.x * 10) / 10, y: Math.round(p.y * 10) / 10 };
    };
    const width = data.canvas_width, height = data.canvas_height;
    svg.replaceChildren();
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const zoom = get('.zoom');
    const resize = () => {
        state.zoom = zoom.value;
        svg.style.width = state.zoom === 'fit' ? '100%' : `${width * Number(state.zoom)}px`;
        svg.style.aspectRatio = `${width} / ${height}`;
    };
    zoom.value = state.zoom;
    zoom.onchange = resize;
    resize();
    const viewport = get('.viewport');
    if (data.right_to_left && !state.wasRTL)
        viewport.scrollLeft = viewport.scrollWidth;
    state.wasRTL = data.right_to_left;
    const mode = value => {
        state.mode = value;
        get('.draw').setAttribute('aria-pressed', value === 'draw');
        get('.edit').setAttribute('aria-pressed', value === 'edit');
        svg.classList.toggle('edit-mode', value === 'edit');
        get('.hint').textContent = value === 'draw' ? 'Click each landing point in reading order. Click a word again to revisit it.' :
            'Select a fixation or drag it. Use the fixation list to reach overlapping visits.';
    };
    get('.draw').onclick = () => mode('draw');
    get('.edit').onclick = () => mode('edit');
    mode(state.mode);
    const labels = new Map(words.map(w => [Number(w.word_id), w.text]));
    for (const w of words) {
        make('rect', { class: 'word-box', x: w.x, y: w.y, width: w.width, height: w.height });
        make('text', { class: 'word-label', x: w.x + 3, y: w.y + w.height / 2 }, w.text);
    }
    make('polyline', { class: 'path', points: events.map(e => `${e.x},${e.y}`).join(' ') });
    visits.replaceChildren(new Option('Select a fixation', ''));
    const markers = new Map();
    for (const e of events) {
        const id = e.fixation_id, order = e.order_in_trial;
        const word = labels.get(e.word_id);
        const description = `${order}. ${word ?? 'No target word'} · ${e.duration_ms} ms (ID ${id})`;
        visits.add(new Option(description, id));
        const circle = make('circle', { class: 'fixation', cx: e.x, cy: e.y, r: e.diameter / 2, tabindex: 0,
            'aria-label': description, 'data-fixation-id': id });
        const label = make('text', { class: 'order', x: e.x, y: e.y }, order);
        markers.set(id, { circle, label });
        let start;
        circle.onpointerdown = ev => {
            if (state.mode !== 'edit' || !data.editable)
                return;
            start = point(ev);
            circle.setPointerCapture(ev.pointerId);
        };
        circle.onpointermove = ev => {
            if (!start)
                return;
            const { x, y } = point(ev);
            circle.setAttribute('cx', x);
            circle.setAttribute('cy', y);
            label.setAttribute('x', x);
            label.setAttribute('y', y);
        };
        circle.onpointercancel = () => {
            start = null;
            circle.setAttribute('cx', e.x);
            circle.setAttribute('cy', e.y);
            label.setAttribute('x', e.x);
            label.setAttribute('y', e.y);
        };
        circle.onpointerup = ev => {
            if (!start)
                return;
            const pos = point(ev);
            emit(Math.hypot(pos.x - start.x, pos.y - start.y) > 2
                ? { type: 'move', fixation_id: id, ...pos } : { type: 'select', fixation_id: id });
            start = null;
        };
        circle.onkeydown = ev => {
            if (!data.editable)
                return;
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                emit({ type: 'select', fixation_id: id });
            }
            if (ev.key === 'Delete' || ev.key === 'Backspace') {
                ev.preventDefault();
                emit({ type: 'delete', fixation_id: id });
            }
        };
    }
    svg.onclick = ev => {
        if (!data.editable || state.mode !== 'draw')
            return;
        const { x, y } = point(ev);
        const w = words.find(w => w.x <= x && x < w.x + w.width && w.y <= y && y < w.y + w.height);
        emit({ type: 'add', x, y, word_id: w?.word_id ?? null });
    };
    const selected = events.find(e => e.fixation_id === data.selected_fixation_id);
    const editable = Boolean(selected) && data.editable;
    visits.disabled = !events.length || !data.editable;
    visits.value = selected?.fixation_id ?? '';
    visits.onchange = () => { if (visits.value)
        emit({ type: 'select', fixation_id: Number(visits.value) }); };
    duration.disabled = !editable;
    duration.value = selected?.duration_ms ?? '';
    duration.onchange = () => {
        if (selected && duration.value && duration.reportValidity())
            emit({ type: 'update', fixation_id: selected.fixation_id, duration_ms: duration.valueAsNumber });
    };
    get('.delete').disabled = !editable;
    get('.delete').onclick = () => { if (selected)
        emit({ type: 'delete', fixation_id: selected.fixation_id }); };
    if (selected) {
        const marker = markers.get(selected.fixation_id);
        marker.circle.classList.add('selected');
        svg.append(marker.circle, marker.label);
    }
    let playing = null;
    svg.classList.remove('replaying');
    const stop = () => {
        clearTimeout(state.timer);
        playing?.remove();
        playing = null;
        svg.classList.remove('replaying');
        preview.textContent = 'Play preview';
    };
    preview.textContent = 'Play preview';
    preview.disabled = !events.length;
    preview.onclick = () => {
        if (playing) {
            stop();
            return;
        }
        const play = i => {
            playing?.remove();
            if (i === events.length) {
                stop();
                return;
            }
            svg.classList.add('replaying');
            const marker = markers.get(events[i].fixation_id);
            playing = make('g', { 'pointer-events': 'none', 'aria-hidden': true });
            const dot = marker.circle.cloneNode();
            dot.removeAttribute('tabindex');
            dot.removeAttribute('data-fixation-id');
            dot.setAttribute('class', 'fixation playing');
            playing.append(dot, marker.label.cloneNode(true));
            preview.textContent = `Stop preview (${i + 1}/${events.length})`;
            state.timer = setTimeout(() => play(i + 1), events[i].duration_ms);
        };
        play(0);
    };
    sendNext();
    return () => clearTimeout(state.timer);
}
"""


def _spatial_editor() -> Any:
    """Register once per script run (the v2 registry is run-scoped in AppTest)."""
    return st.components.v2.component(
        "scanpath_authoring_canvas",
        html=_HTML,
        css=_CSS,
        js=_JS,
    )


def render_authoring_canvas(
    words: pd.DataFrame,
    events: pd.DataFrame,
    *,
    canvas_width: int,
    canvas_height: int,
    selected_fixation_id: int | None,
    revision: int,
    editable: bool,
    source: str,
    right_to_left: bool,
) -> Any:
    """Mount the editor and return its compact ``result.event`` trigger value."""
    from .plots import _compute_marker_sizes

    word_fields = ["word_id", "text", "line_idx", "x", "y", "width", "height"]
    event_fields = ["fixation_id", "order_in_trial", "x", "y", "duration_ms", "word_id"]
    rows = events[event_fields].copy()
    rows["diameter"] = (
        _compute_marker_sizes(rows["duration_ms"], size_range=(20, 38))
        if not rows.empty
        else []
    )
    records = rows.astype(object).where(rows.notna(), None).to_dict("records")
    result = _spatial_editor()(
        key=f"authoring_spatial_editor_{source}",
        data={
            "words": words[word_fields].to_dict("records") if not words.empty else [],
            "events": records,
            "right_to_left": right_to_left,
            "revision": revision,
            "editable": editable,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "selected_fixation_id": selected_fixation_id,
        },
        on_event_change=lambda: None,
        height="content",
    )
    return getattr(result, "event", None)
