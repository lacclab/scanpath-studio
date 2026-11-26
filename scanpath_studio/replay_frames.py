"""Represent a replay by its completed traces and each reading's fixation onsets."""

from __future__ import annotations

from bisect import bisect_right

import pandas as pd

from .constants import DEFAULT_FADE_OPACITY, DEFAULT_GROW_START

# Private keys on a replay layout. A compact figure is used only inside the UI.
READINGS = "scanpath_fixation_steps"
COMPACT = "_scanpath_terminal_frame"


def reading(
    spec: dict,
    slots: dict,
    *,
    redact: bool,
    comparing: bool,
    grow: bool = False,
    fade: bool = False,
    order_colors: tuple[str, str] | None = None,
    grow_start: float = DEFAULT_GROW_START,
    fade_opacity: float = DEFAULT_FADE_OPACITY,
) -> dict:
    """Trace positions and recorded details for stepping through one reading."""
    from .measures import assign_fixations_to_words

    words = spec.get("words")
    assigned_words = []
    if (
        not redact
        and words is not None
        and {"word_id", "text"} <= set(words)
        and len(words)
    ):
        ids = assign_fixations_to_words(spec["ordered"], words)["word_id"]
        labels = (
            words.dropna(subset=["word_id"])
            .drop_duplicates("word_id")
            .set_index("word_id")["text"]
        )
        assigned_words = ids.map(labels).fillna("").astype(str).tolist()
    prefix = [
        *spec["idx_trails"],
        spec["idx_order"],
        *(o["idx"] for o in spec["flag_overlays"]),
    ]
    run = {
        "label": spec["label"] if comparing else "",
        "times": spec["onsets"].tolist(),
        "durations": [
            None if pd.isna(d) else float(d)
            for d in pd.to_numeric(spec["ordered"]["duration_ms"], errors="coerce")
        ],
        "ids": spec["order_text"],
        "words": assigned_words,
        "recorded": spec["recorded_clock"],
        "points": [slots[idx] for idx in prefix if idx is not None],
        "saccades": slots.get(spec["idx_sac"]),
        "arrows": slots.get(spec["idx_arrow"]),
        "segments": spec["arrow_seg"],
        "current": slots.get(spec["idx_curr"]),
        "sizes": (spec["sizes"] + 8).tolist() if spec["idx_curr"] is not None else [],
    }
    # Only a replay that grows or fades carries these keys; one that does
    # neither carries none of them. The flag highlights grow and fade with the
    # markers they ring.
    if grow or fade:
        run["trails"] = [
            slots[idx]
            for idx in [*spec["idx_trails"], *(o["idx"] for o in spec["flag_overlays"])]
            if slots.get(idx) is not None
        ]
        run["grow"] = bool(grow)
        run["fade"] = bool(fade)
        run["grow_start"] = float(grow_start)
        run["fade_opacity"] = float(fade_opacity)
    # The fixation numbers fade with their markers: ``(faded, full)`` colours.
    if fade and order_colors and slots.get(spec["idx_order"]) is not None:
        run["order"] = slots[spec["idx_order"]]
        run["order_colors"] = list(order_colors)
    return run


def growth(run: dict, i: int, time_ms: float) -> float:
    """How far fixation ``i`` has grown at ``time_ms``: its elapsed share of its
    own duration, from the run's ``grow_start`` to 1."""
    duration = run["durations"][i] if i < len(run["durations"]) else None
    if not duration or duration <= 0:
        return 1.0
    start = run.get("grow_start", DEFAULT_GROW_START)
    return min(1.0, max(start, (time_ms - run["times"][i]) / duration))


def _restyle_trail(trace: dict, i: int, frac: float, *, fade: float | None) -> dict:
    """The trail with fixation ``i`` grown to ``frac`` of its size and, with a
    ``fade`` share, every earlier fixation at that share of its opacity. One
    size for every point (a flag highlight's) is spread to one per point. A
    glyph trail's text layers carry no marker size and are left as they are."""
    marker = trace.get("marker") or {}
    sizes = marker.get("size")
    if isinstance(sizes, int | float) and not isinstance(sizes, bool):
        sizes = [sizes] * len(trace["x"])
    if not isinstance(sizes, list):
        return trace
    changes: dict = {}
    if frac < 1.0:
        sizes = list(sizes)
        sizes[i] = sizes[i] * frac
        changes["size"] = sizes
    if fade is not None:
        opacity = marker.get("opacity")
        full = 1.0 if opacity is None else float(opacity)
        changes["opacity"] = [full * fade] * i + [full] * (len(sizes) - i)
    if not changes:
        return trace
    return {**trace, "marker": {**marker, **changes}}


def at_time(terminal: dict, readings: list[dict], time_ms: float, name: str) -> dict:
    """Reveal only the coordinates reached by this time, retaining every trace style."""
    if not terminal.get("data"):
        return {**terminal, "name": name}
    data = terminal["data"].copy()

    def reveal(slot, count):
        trace = data[slot]
        data[slot] = {
            **trace,
            **{
                axis: trace[axis][:count] + [None] * (len(trace[axis]) - count)
                for axis in ("x", "y")
            },
        }

    for run in readings:
        count = max(1, bisect_right(run["times"], time_ms))
        for slot in run["points"]:
            reveal(slot, count)
        if run["saccades"] is not None:
            reveal(run["saccades"], 3 * (count - 1))
        if run["arrows"] is not None:
            reveal(run["arrows"], bisect_right(run["segments"], count - 2))
        frac = growth(run, count - 1, time_ms) if run.get("grow") else 1.0
        for slot in run.get("trails", ()):
            data[slot] = _restyle_trail(
                data[slot],
                count - 1,
                frac,
                fade=run["fade_opacity"] if run["fade"] else None,
            )
        if run.get("order") is not None:
            trace = data[run["order"]]
            faded, full = run["order_colors"]
            colors = [faded] * (count - 1) + [full] * (len(trace["x"]) - count + 1)
            data[run["order"]] = {
                **trace,
                "textfont": {**(trace.get("textfont") or {}), "color": colors},
            }
        if run["current"] is None:
            continue
        source = terminal["data"][run["points"][0]]
        current = data[run["current"]]
        data[run["current"]] = {
            **current,
            "x": [source["x"][count - 1]],
            "y": [source["y"][count - 1]],
            "marker": {
                **current["marker"],
                "size": [(run["sizes"][count - 1] - 8) * frac + 8],
            },
        }
    return {"name": name, "traces": terminal["traces"], "data": data}


def expand_figure(figure: dict) -> dict:
    """Materialize the UI's compact figure only when a movie needs its frames."""
    layout = figure.get("layout", {})
    meta = layout.get("meta") or {}
    if not meta.get(COMPACT):
        return figure
    terminal = figure["frames"][0]
    meta = dict(meta)
    del meta[COMPACT]
    return {
        **figure,
        "layout": {**layout, "meta": meta},
        "frames": [
            at_time(terminal, meta[READINGS], ms, str(i))
            for i, ms in enumerate(meta["scanpath_frame_times_ms"])
        ],
    }


# The browser needs the same view of the prototype for sub-frame stepping.
# Its output is checked trace for trace against the public Plotly figure.
FRAME_AT_JS = """function frameAtTime(terminal, readings, ms, name) {
  if (!terminal.data) { return Object.assign({}, terminal, {name: name}); }
  var data = terminal.data.slice();
  function upper(values, bound) {
    var lo = 0, hi = values.length;
    while (lo < hi) {
      var mid = (lo + hi) >>> 1;
      if (values[mid] <= bound) { lo = mid + 1; } else { hi = mid; }
    }
    return lo;
  }
  function reveal(slot, count) {
    var t = data[slot];
    function masked(values) {
      return values.slice(0, count).concat(Array(values.length - count).fill(null));
    }
    data[slot] = Object.assign({}, t, {x: masked(t.x), y: masked(t.y)});
  }
  readings.forEach(function (run) {
    var count = Math.max(1, upper(run.times, ms)), i = count - 1;
    run.points.forEach(function (slot) { reveal(slot, count); });
    if (run.saccades != null) { reveal(run.saccades, i * 3); }
    if (run.arrows != null) { reveal(run.arrows, upper(run.segments, i - 1)); }
    var frac = 1;
    if (run.grow) {
      var d = run.durations[i];
      if (d && d > 0) { frac = Math.min(1, Math.max(run.grow_start, (ms - run.times[i]) / d)); }
    }
    (run.trails || []).forEach(function (slot) {
      var g = data[slot], m = g.marker || {}, changes = {};
      var sizes = typeof m.size === 'number' ? g.x.map(function () { return m.size; }) : m.size;
      if (!Array.isArray(sizes)) { return; }
      if (frac < 1) {
        changes.size = sizes.slice();
        changes.size[i] = changes.size[i] * frac;
      }
      if (run.fade) {
        var full = m.opacity == null ? 1 : +m.opacity;
        changes.opacity = sizes.map(function (_, k) { return k < i ? full * run.fade_opacity : full; });
      }
      if (changes.size || changes.opacity) {
        data[slot] = Object.assign({}, g, {marker: Object.assign({}, m, changes)});
      }
    });
    if (run.order != null) {
      var o = data[run.order], c = run.order_colors;
      var colors = o.x.map(function (_, k) { return k < i ? c[0] : c[1]; });
      data[run.order] = Object.assign({}, o, {textfont: Object.assign({}, o.textfont || {}, {color: colors})});
    }
    if (run.current == null) { return; }
    var source = terminal.data[run.points[0]];
    var t = data[run.current];
    data[run.current] = Object.assign({}, t, {
      x: [source.x[i]], y: [source.y[i]], marker: Object.assign({}, t.marker, {size: [(run.sizes[i] - 8) * frac + 8]})
    });
  });
  return {name: name, traces: terminal.traces, data: data};
}"""
