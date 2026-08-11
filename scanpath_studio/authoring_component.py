"""Bidirectional browser canvas for the VIZ-33 authoring document."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st


_HTML = """
<div class="authoring-toolbar">
  <span>Click empty space to add · drag a fixation to move · click to select</span>
  <button type="button" class="delete" disabled>Delete selected</button>
</div>
<svg class="authoring-canvas" role="img" aria-label="Interactive fixation authoring canvas"></svg>
"""

_CSS = """
:host { display: block; color: var(--st-text-color); font-family: var(--st-font); }
.authoring-toolbar { display: flex; align-items: center; justify-content: space-between;
  gap: .75rem; margin: 0 0 .4rem; font-size: .82rem; color: var(--st-text-color); }
.delete { border: 1px solid color-mix(in srgb, var(--st-text-color) 25%, transparent);
  border-radius: .4rem; padding: .25rem .55rem; color: var(--st-text-color);
  background: var(--st-secondary-background-color); cursor: pointer; }
.delete:disabled { opacity: .45; cursor: default; }
.authoring-canvas { display: block; width: 100%; max-height: 580px; min-height: 240px;
  border: 1px solid color-mix(in srgb, var(--st-text-color) 22%, transparent);
  border-radius: .45rem; background: white; touch-action: none; user-select: none; }
.word-box { fill: #f7f8fa; stroke: #b7bec9; stroke-width: 1; }
.word-label { fill: #222; font: 16px sans-serif; dominant-baseline: middle;
  pointer-events: none; }
.fixation { fill: #2f6fed; fill-opacity: .78; stroke: white; stroke-width: 3;
  cursor: grab; }
.fixation.selected { fill: #f59e0b; stroke: #111827; stroke-width: 4; }
.fixation:focus { outline: none; stroke: #111827; stroke-width: 5; }
.order { fill: white; font: bold 12px sans-serif; dominant-baseline: middle;
  text-anchor: middle; pointer-events: none; }
"""

_JS = r"""
export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const svg = parentElement.querySelector('.authoring-canvas');
  const deleteButton = parentElement.querySelector('.delete');
  const ns = 'http://www.w3.org/2000/svg';
  const width = Number(data.canvas_width || 1200);
  const height = Number(data.canvas_height || 700);
  const selected = data.selected_fixation_id == null ? null : Number(data.selected_fixation_id);
  // Streamlit v2 reuses the component host across reruns. Rebuild the SVG
  // rather than appending another copy of every word/fixation and stacking a
  // second canvas-level pointer handler.
  svg.replaceChildren();
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('preserveAspectRatio', 'xMidYMin meet');
  svg.style.aspectRatio = `${width} / ${height}`;

  const make = (tag, attrs, text) => {
    const element = document.createElementNS(ns, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (text != null) element.textContent = String(text);
    svg.appendChild(element);
    return element;
  };
  const point = (event) => {
    const value = svg.createSVGPoint();
    value.x = event.clientX;
    value.y = event.clientY;
    const local = value.matrixTransform(svg.getScreenCTM().inverse());
    return { x: Math.round(local.x * 10) / 10, y: Math.round(local.y * 10) / 10 };
  };

  (data.words || []).forEach((word) => {
    make('rect', { class: 'word-box', x: word.x, y: word.y, width: word.width, height: word.height });
    make('text', { class: 'word-label', x: Number(word.x) + 3,
      y: Number(word.y) + Number(word.height) / 2 }, word.text);
  });

  let dragged = null;
  const finishDrag = (pointerEvent) => {
    if (!dragged) return false;
    const next = point(pointerEvent);
    setTriggerValue('event', dragged.moved
      ? { type: 'move', fixation_id: dragged.id, x: next.x, y: next.y }
      : { type: 'select', fixation_id: dragged.id });
    dragged = null;
    return true;
  };
  (data.events || []).forEach((event) => {
    const id = Number(event.fixation_id);
    const circle = make('circle', {
      class: `fixation${id === selected ? ' selected' : ''}`,
      cx: event.x, cy: event.y, r: 18, tabindex: 0,
      'aria-label': `Fixation ${id}, order ${event.order_in_trial}`,
      'data-fixation-id': id,
    });
    make('text', { class: 'order', x: event.x, y: event.y }, event.order_in_trial);
    circle.addEventListener('pointerdown', (pointerEvent) => {
      pointerEvent.stopPropagation();
      circle.setPointerCapture(pointerEvent.pointerId);
      dragged = { id, circle, start: point(pointerEvent), moved: false };
    });
    circle.addEventListener('pointermove', (pointerEvent) => {
      if (!dragged || dragged.id !== id) return;
      const next = point(pointerEvent);
      if (Math.hypot(next.x - dragged.start.x, next.y - dragged.start.y) > 2) {
        dragged.moved = true;
      }
      circle.setAttribute('cx', next.x);
      circle.setAttribute('cy', next.y);
    });
    circle.addEventListener('pointerup', (pointerEvent) => {
      if (!dragged || dragged.id !== id) return;
      finishDrag(pointerEvent);
    });
    circle.addEventListener('keydown', (keyEvent) => {
      if (keyEvent.key === 'Delete' || keyEvent.key === 'Backspace') {
        keyEvent.preventDefault();
        setTriggerValue('event', { type: 'delete', fixation_id: id });
      }
    });
  });

  svg.onpointerup = (pointerEvent) => {
    // Pointer capture is not guaranteed in every embedded browser. A release
    // that lands elsewhere on the SVG must still commit the drag instead of
    // leaving only a transient local marker move.
    if (finishDrag(pointerEvent)) return;
    if (pointerEvent.target !== svg) return;
    const next = point(pointerEvent);
    setTriggerValue('event', { type: 'add', x: next.x, y: next.y });
  };
  deleteButton.disabled = selected == null;
  deleteButton.onclick = () => {
    if (selected != null) setTriggerValue('event', { type: 'delete', fixation_id: selected });
  };
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
    selected_fixation_id: Optional[int],
) -> Any:
    """Mount the editor and return its compact ``result.event`` trigger value."""
    word_fields = ["word_id", "text", "line_idx", "x", "y", "width", "height"]
    event_fields = ["fixation_id", "order_in_trial", "x", "y", "duration_ms"]
    result = _spatial_editor()(
        key="authoring_spatial_editor",
        data={
            "words": words[word_fields].to_dict("records") if not words.empty else [],
            "events": events[event_fields].to_dict("records")
            if not events.empty
            else [],
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "selected_fixation_id": selected_fixation_id,
        },
        on_event_change=lambda: None,
        height="content",
    )
    return getattr(result, "event", None)
