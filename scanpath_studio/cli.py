"""Command-line interface for scanpath-studio.

Subcommands:
    scanpath-studio                 # launch the Streamlit app (default)
    scanpath-studio run [args…]     # same, forwarding extra args to streamlit
    scanpath-studio render …        # headless: render one trial to a file

Anything that isn't a known subcommand is forwarded to ``streamlit run`` so
pre-existing invocations like ``scanpath-studio --server.port 8502`` keep
working.
"""

from __future__ import annotations

import argparse
import importlib.resources as resources
import sys
from typing import List, Optional

from . import __version__
from .constants import FONT_FAMILY


def launch_app(extra_args: List[str]) -> None:
    """Launch the Streamlit app via ``streamlit run``, forwarding extra args."""
    from streamlit.web import cli as stcli

    app_resource = resources.files(__package__).joinpath("app.py")
    with resources.as_file(app_resource) as app_path:
        sys.argv = ["streamlit", "run", str(app_path), *extra_args]
        sys.exit(stcli.main())


def _render_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scanpath-studio render",
        description=(
            "Render one trial's scanpath to a file without launching the app. "
            "HTML output is interactive and browser-free; PNG/SVG/PDF go "
            "through Kaleido and need a Chrome/Chromium binary "
            "(`plotly_get_chrome -y`)."
        ),
    )
    src = parser.add_argument_group("input (bundled sample, or words + fixations)")
    src.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled 3-participant OneStop demo data.",
    )
    src.add_argument(
        "--words", metavar="PATH", help="Words/IA table (csv/parquet/feather)."
    )
    src.add_argument(
        "--fixations", metavar="PATH", help="Fixations table (csv/parquet/feather)."
    )

    parser.add_argument(
        "-p", "--participant", help="Participant id (default: first available)."
    )
    parser.add_argument(
        "-t", "--trial", help="Trial id (default: first for the participant)."
    )
    parser.add_argument(
        "--list-trials",
        action="store_true",
        help="Print the available (participant, trial) combos and exit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Output file; format from extension (.html/.png/.svg/.pdf).",
    )
    parser.add_argument(
        "--animate",
        action="store_true",
        help="Render the animated replay instead of the static figure (HTML only).",
    )

    viz = parser.add_argument_group("visualization (defaults match the app)")
    viz.add_argument(
        "--no-words",
        dest="show_words",
        action="store_false",
        help="Hide word bounding boxes.",
    )
    viz.add_argument(
        "--no-labels",
        dest="show_word_labels",
        action="store_false",
        help="Hide the reading text.",
    )
    viz.add_argument(
        "--no-fixations",
        dest="show_fixations",
        action="store_false",
        help="Hide fixation markers.",
    )
    viz.add_argument(
        "--no-order",
        dest="show_order",
        action="store_false",
        help="Hide fixation index labels.",
    )
    viz.add_argument(
        "--no-saccades",
        dest="show_saccades",
        action="store_false",
        help="Hide saccade lines.",
    )
    viz.add_argument(
        "--no-heatmap",
        dest="show_heatmap",
        action="store_false",
        help="Hide the heatmap overlay.",
    )
    viz.add_argument(
        "--saccade-arrows",
        dest="show_saccade_arrows",
        action="store_true",
        help="Draw saccade direction arrowheads.",
    )
    viz.add_argument(
        "--color-by",
        metavar="FIELD",
        help="Fixation color field (default: duration_ms).",
    )
    viz.add_argument(
        "--heatmap-metric",
        choices=["duration_ms", "counts"],
        help="Heatmap weighting (default: duration_ms).",
    )
    viz.add_argument(
        "--canvas",
        metavar="WxH",
        help="Monitor size in px, e.g. 2560x1440 (default: estimated from data; "
        "the bundled sample uses 2560x1440 automatically).",
    )
    viz.add_argument(
        "--font-size",
        type=int,
        default=16,
        metavar="PX",
        help="Base figure font size (default: 16).",
    )
    viz.add_argument(
        "--font-family",
        default=None,
        metavar="NAME",
        help=f"Word label font (default: {FONT_FAMILY}).",
    )
    viz.add_argument(
        "--playback-speed",
        type=float,
        default=1.0,
        metavar="X",
        help="Animation speed multiplier for --animate (default: 1.0 = real time).",
    )
    return parser


def _parse_canvas(value: Optional[str]) -> Optional[tuple]:
    if not value:
        return None
    try:
        w, h = value.lower().split("x")
        return (int(w), int(h))
    except ValueError:
        raise SystemExit(f"--canvas expects WxH (e.g. 2560x1440), got {value!r}")


def render(argv: List[str]) -> None:
    args = _render_parser().parse_args(argv)
    if args.sample == bool(args.words or args.fixations):
        raise SystemExit("Provide either --sample or both --words and --fixations.")
    if not args.sample and not (args.words and args.fixations):
        raise SystemExit("Both --words and --fixations are required.")
    if not args.list_trials and not args.output:
        raise SystemExit("Missing -o/--output (or use --list-trials).")

    from . import api

    if args.sample:
        words, fixations = api.load_sample_data()
        canvas = _parse_canvas(args.canvas) or (2560, 1440)  # OneStop monitor
    else:
        words, fixations = api.load_scanpath_data(args.words, args.fixations)
        canvas = _parse_canvas(args.canvas)

    if args.list_trials:
        combos = api.list_trials(words, fixations)
        print(combos.to_string(index=False))
        return

    try:
        participant, trial = api._resolve_trial(
            words, fixations, args.participant, args.trial
        )
    except ValueError as exc:
        if args.participant is not None and args.trial is not None:
            raise SystemExit(str(exc))
        # Underspecified selection: fall back to the first combo, like the app.
        first = api.list_trials(words, fixations)
        if args.participant is not None:
            first = first[first["participant_id"] == str(args.participant)]
        if first.empty:
            raise SystemExit(str(exc))
        participant, trial = str(first.iloc[0, 0]), str(first.iloc[0, 1])
    print(f"Rendering participant={participant} trial={trial}", file=sys.stderr)

    overrides = {
        key: getattr(args, key)
        for key in (
            "show_words",
            "show_word_labels",
            "show_fixations",
            "show_order",
            "show_saccades",
            "show_heatmap",
            "show_saccade_arrows",
        )
    }
    if args.color_by:
        overrides["color_by"] = args.color_by
    if args.heatmap_metric:
        overrides["heatmap_metric"] = args.heatmap_metric

    common = dict(
        canvas_size=canvas,
        base_font_size=args.font_size,
        font_family=args.font_family or FONT_FAMILY,
    )
    try:
        if args.animate:
            if not args.output.lower().endswith(".html"):
                raise SystemExit(
                    "--animate writes interactive HTML — use a .html output "
                    "(GIF/MP4 are available via the Python API: "
                    "animation_export.export_animation)."
                )
            anim_keys = (
                "show_words",
                "show_word_labels",
                "show_saccades",
                "show_order",
            )
            fig = api.animate_scanpath(
                words,
                fixations,
                participant,
                trial,
                playback_speed=args.playback_speed,
                **{k: overrides[k] for k in anim_keys},
                **common,
            )
        else:
            fig = api.plot_scanpath(
                words, fixations, participant, trial, **overrides, **common
            )
        out = api.save_figure(fig, args.output)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc))
    print(f"Wrote {out}", file=sys.stderr)


_HELP = f"""scanpath-studio {__version__} — visualize eye-tracking-while-reading scanpaths

usage:
  scanpath-studio                  launch the interactive app (Streamlit)
  scanpath-studio run [args…]      same, forwarding args to `streamlit run`
  scanpath-studio render …         render one trial to .html/.png/.svg/.pdf
                                   (see `scanpath-studio render --help`)
  scanpath-studio --version        print the version

Unrecognized arguments are forwarded to `streamlit run` (e.g.
`scanpath-studio --server.port 8502`)."""


def main(argv: Optional[List[str]] = None) -> None:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if not argv:
        launch_app([])
    elif argv[0] == "run":
        launch_app(argv[1:])
    elif argv[0] == "render":
        render(argv[1:])
    elif argv[0] in ("-h", "--help"):
        print(_HELP)
    elif argv[0] in ("-V", "--version"):
        print(__version__)
    else:
        # Backward compatibility: bare streamlit flags launch the app.
        launch_app(argv)


if __name__ == "__main__":
    main()
