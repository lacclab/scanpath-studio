"""Reproducible EXP-6 export benchmark matrix.

The default run covers the planned static, animation, and bulk matrix.  Pass
``--quick`` for a representative smoke profile while developing.  Results are
printed as JSON so a measured run can be copied into the tracker without the
benchmark mutating repository files.
"""

from __future__ import annotations

import argparse
import json
import resource
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from typing import Callable

import pandas as pd
import plotly.graph_objects as go

from scanpath_studio.animation_export import export_animation
from scanpath_studio.export import (
    ExportOptions,
    _figure_renderer,
    bulk_export,
    render_static_figure_bytes,
)
from scanpath_studio.export_status import ExportStatus, static_export_signature


@dataclass
class Measurement:
    name: str
    elapsed_s: float
    python_peak_mib: float
    process_max_rss_mib: float
    output_kib: float
    stage_elapsed_s: dict[str, float]


def _representative_figure(frame_count: int = 0) -> go.Figure:
    fig = go.Figure()
    for index, word in enumerate(
        "A measured export should stay honest and useful".split()
    ):
        x = 60 + index * 95
        fig.add_shape(
            type="rect",
            x0=x - 36,
            y0=190,
            x1=x + 36,
            y1=222,
            line={"color": "#9aa4b2", "width": 1},
        )
        fig.add_annotation(x=x, y=206, text=word, showarrow=False)
    xs = [60, 150, 245, 340, 435, 530, 625, 720]
    ys = [206, 205, 209, 203, 207, 204, 208, 205]
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines+markers",
            marker={"size": [18, 22, 17, 28, 19, 24, 21, 20]},
            line={"width": 2},
            name="scanpath",
        )
    )
    fig.update_layout(
        width=800,
        height=450,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        showlegend=False,
    )
    fig.update_xaxes(range=[0, 800], visible=False)
    fig.update_yaxes(range=[450, 0], visible=False)
    if frame_count:
        fig.frames = [
            go.Frame(
                name=str(index),
                traces=[0],
                data=[
                    go.Scatter(
                        x=xs[: (index % len(xs)) + 1],
                        y=ys[: (index % len(ys)) + 1],
                        mode="lines+markers",
                    )
                ],
            )
            for index in range(frame_count)
        ]
    return fig


def _stage_durations(statuses: list[ExportStatus], total: float) -> dict[str, float]:
    """Turn cumulative callback times into best-effort stage intervals."""
    if not statuses:
        return {}
    result: dict[str, float] = {}
    for index, status in enumerate(statuses):
        next_elapsed = (
            statuses[index + 1].elapsed_s if index + 1 < len(statuses) else total
        )
        delta = max(0.0, next_elapsed - status.elapsed_s)
        key = status.stage.value
        result[key] = round(result.get(key, 0.0) + delta, 4)
    return result


def _measure(
    name: str,
    operation: Callable[[list[ExportStatus]], bytes],
) -> Measurement:
    statuses: list[ExportStatus] = []
    tracemalloc.start()
    started = time.perf_counter()
    payload = operation(statuses)
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # macOS reports ru_maxrss in bytes; Linux reports KiB.
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    process_mib = max_rss / (1024 * 1024)
    return Measurement(
        name=name,
        elapsed_s=round(elapsed, 4),
        python_peak_mib=round(peak / (1024 * 1024), 3),
        process_max_rss_mib=round(process_mib, 3),
        output_kib=round(len(payload) / 1024, 3),
        stage_elapsed_s=_stage_durations(statuses, elapsed),
    )


def _static_matrix(*, quick: bool) -> list[Measurement]:
    fig = _representative_figure()
    formats = ("png",) if quick else ("png", "svg", "pdf")
    rows: list[Measurement] = []
    for fmt in formats:
        rendered: dict[str, bytes] = {}

        def cold_render(statuses, *, selected_format=fmt):
            data = render_static_figure_bytes(
                fig,
                fmt=selected_format,
                width=800,
                height=450,
                scale=2,
                status_callback=statuses.append,
            )
            rendered["data"] = data
            return data

        rows.append(
            _measure(
                f"static_{fmt}_cold",
                cold_render,
            )
        )
        # This models the pre-EXP-6 repeat path: another complete render.
        rows.append(
            _measure(
                f"static_{fmt}_uncached_repeat",
                lambda statuses, fmt=fmt: render_static_figure_bytes(
                    fig,
                    fmt=fmt,
                    width=800,
                    height=450,
                    scale=2,
                    status_callback=statuses.append,
                ),
            )
        )
        # EXP-6 stores these exact bytes by the same deterministic signature.
        signature = static_export_signature(
            fig, fmt=fmt, width=800, height=450, scale=2
        )
        cache: dict[str, bytes] = {signature: rendered["data"]}
        rows.append(
            _measure(
                f"static_{fmt}_cached_repeat",
                lambda _statuses, fmt=fmt: cache[
                    static_export_signature(
                        fig, fmt=fmt, width=800, height=450, scale=2
                    )
                ],
            )
        )

    if not quick:
        with _figure_renderer(True) as render:
            for fmt in formats:
                samples: list[float] = []
                payload = b""
                for _ in range(3):
                    started = time.perf_counter()
                    payload = render(fig, fmt, 800, 450, 2)
                    samples.append(time.perf_counter() - started)
                rows.append(
                    Measurement(
                        name=f"static_{fmt}_warm_shared_renderer_median",
                        elapsed_s=round(statistics.median(samples), 4),
                        python_peak_mib=0.0,
                        process_max_rss_mib=round(
                            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                            / (1024 * 1024),
                            3,
                        ),
                        output_kib=round(len(payload) / 1024, 3),
                        stage_elapsed_s={"rasterizing": round(sum(samples), 4)},
                    )
                )
    return rows


def _animation_matrix(*, quick: bool) -> list[Measurement]:
    rows: list[Measurement] = []
    cases = (
        [("gif", 4)]
        if quick
        else [
            ("gif", 12),
            ("gif", 80),
            ("mp4", 12),
            ("mp4", 80),
        ]
    )
    for fmt, frames in cases:
        fig = _representative_figure(frames)
        rows.append(
            _measure(
                f"animation_{fmt}_{frames}_frames",
                lambda statuses, fig=fig, fmt=fmt: export_animation(
                    fig,
                    fmt=fmt,
                    frame_duration_ms=80,
                    scale=0.5 if quick else 1.0,
                    status_callback=statuses.append,
                ),
            )
        )
    return rows


def _bulk_frames(count: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    trial_ids = [f"t{index + 1}" for index in range(count)]
    combos = pd.DataFrame({"participant_id": "p1", "trial_id": trial_ids})
    words = pd.DataFrame(
        {
            "participant_id": "p1",
            "trial_id": trial_ids,
            "word_id": 1,
            "text": "benchmark",
            "x": 100.0,
            "y": 100.0,
            "width": 90.0,
            "height": 28.0,
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": "p1",
            "trial_id": trial_ids,
            "x": 140.0,
            "y": 114.0,
            "duration_ms": 160.0,
            "timestamp_ms": 0.0,
            "word_id": 1,
            "order_in_trial": 1,
        }
    )
    return combos, words, fixations


def _bulk_matrix(*, quick: bool) -> list[Measurement]:
    counts = (1,) if quick else (1, 10, 100)
    rows: list[Measurement] = []
    for count in counts:
        combos, words, fixations = _bulk_frames(count)
        options = ExportOptions(
            include_png=True,
            include_svg=not quick,
            include_plot_config=True,
            include_fixations=True,
            include_measures=True,
            separable_layers=not quick,
        )

        def operation(statuses, *, frames=(combos, words, fixations), opts=options):
            payload, _progress = bulk_export(
                *frames,
                canvas_width=800,
                canvas_height=450,
                base_font_size=16,
                font_family="Arial",
                x_field="x",
                y_field="y",
                settings={},
                options=opts,
                status_callback=statuses.append,
            )
            return payload

        rows.append(_measure(f"bulk_{count}_trials", operation))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run one representative static, animation, and bulk case.",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    rows = [
        *_static_matrix(quick=args.quick),
        *_animation_matrix(quick=args.quick),
        *_bulk_matrix(quick=args.quick),
    ]
    print(
        json.dumps(
            {
                "mode": "quick" if args.quick else "full",
                "wall_time_s": round(time.perf_counter() - started, 3),
                "measurements": [asdict(row) for row in rows],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
