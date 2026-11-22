"""Represent a replay by its completed traces and each reading's fixation onsets."""

from __future__ import annotations

from bisect import bisect_right

import pandas as pd

# Private keys on a replay layout. A compact figure is used only inside the UI.
READINGS = "scanpath_fixation_steps"
COMPACT = "_scanpath_terminal_frame"


def reading(spec: dict, slots: dict, *, redact: bool, comparing: bool) -> dict:
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
    return {
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
        "current": slots[spec["idx_curr"]],
        "sizes": (spec["sizes"] + 8).tolist(),
    }


def at_time(terminal: dict, readings: list[dict], time_ms: float, name: str) -> dict:
    """Reveal only the coordinates reached by this time, retaining every trace style."""
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
        source = terminal["data"][run["points"][0]]
        for slot in run["points"]:
            reveal(slot, count)
        if run["saccades"] is not None:
            reveal(run["saccades"], 3 * (count - 1))
        if run["arrows"] is not None:
            reveal(run["arrows"], bisect_right(run["segments"], count - 2))
        current = data[run["current"]]
        data[run["current"]] = {
            **current,
            "x": [source["x"][count - 1]],
            "y": [source["y"][count - 1]],
            "marker": {**current["marker"], "size": [run["sizes"][count - 1]]},
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
    var source = terminal.data[run.points[0]];
    run.points.forEach(function (slot) { reveal(slot, count); });
    if (run.saccades != null) { reveal(run.saccades, i * 3); }
    if (run.arrows != null) { reveal(run.arrows, upper(run.segments, i - 1)); }
    var t = data[run.current];
    data[run.current] = Object.assign({}, t, {
      x: [source.x[i]], y: [source.y[i]], marker: Object.assign({}, t.marker, {size: [run.sizes[i]]})
    });
  });
  return {name: name, traces: terminal.traces, data: data};
}"""
