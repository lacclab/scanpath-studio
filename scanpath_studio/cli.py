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
import os.path
import sys
from typing import List, Optional

from . import __version__
from .constants import (
    DEFAULT_SACCADE_WIDTH,
    FONT_FAMILY,
    SACCADE_CLASS_COLORS,
    SACCADE_CLASS_EDITABLE,
    SACCADE_COLOR,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
)


def _theme_cli_flags() -> List[str]:
    """The branded theme as ``--theme.*`` CLI flags (BUG-6).

    Streamlit resolves ``.streamlit/config.toml`` relative to the launch
    directory, so ``python -m scanpath_studio`` from outside ``app/`` (or a
    ``pip``-installed console script) misses the bundled config and renders the
    default red accent. Passing the theme explicitly makes every launch path
    match. Values live in ``constants`` (kept in sync with the config file)."""
    from .constants import APP_THEME, APP_THEME_DARK

    flags = [f"--theme.{key}={value}" for key, value in APP_THEME.items()]
    flags += [f"--theme.dark.{key}={value}" for key, value in APP_THEME_DARK.items()]
    return flags


def launch_app(extra_args: List[str]) -> None:
    """Launch the Streamlit app via ``streamlit run``, forwarding extra args."""
    from streamlit.web import cli as stcli

    # Inject the branded theme unless the caller passes their own ``--theme.*``
    # (explicit flags win), so the app looks the same regardless of where it was
    # launched from (BUG-6).
    theme_args = (
        []
        if any(str(arg).startswith("--theme") for arg in extra_args)
        else _theme_cli_flags()
    )
    app_resource = resources.files(__package__).joinpath("app.py")
    with resources.as_file(app_resource) as app_path:
        sys.argv = ["streamlit", "run", str(app_path), *theme_args, *extra_args]
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
    src = parser.add_argument_group("input (bundled sample, or words and/or fixations)")
    src.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled 3-participant OneStop demo data.",
    )
    src.add_argument(
        "--words",
        metavar="PATH",
        nargs="+",
        help="Words/IA table(s) (csv/tsv/parquet/feather). Multiple paths or a "
        "quoted glob pattern concatenate multi-file datasets.",
    )
    src.add_argument(
        "--fixations",
        metavar="PATH",
        nargs="+",
        help="Fixations table(s) (csv/tsv/parquet/feather). Multiple paths or "
        "a quoted glob pattern concatenate multi-file datasets (e.g. one file "
        "per participant).",
    )
    src.add_argument(
        "--potec",
        metavar="DIR",
        help="Load the PoTeC corpus (DiLi-Lab/PoTeC) from DIR, downloading "
        "the needed files (~45 MB) on first use. Participants are the corpus's "
        "75 reader ids, trials are text ids (b0–b5, p0–p5).",
    )
    src.add_argument(
        "--onestop",
        metavar="DIR",
        help="Load the OneStop corpus from DIR. For the public variant the "
        "chosen regime + parts' reports are downloaded from OSF on first use "
        "(tens–hundreds MB each); the lacclab variant reads a local export. "
        "Tune with --onestop-regime / --onestop-part / --onestop-variant.",
    )
    src.add_argument(
        "--onestop-regime",
        metavar="REGIME",
        choices=[
            "ordinary",
            "information_seeking",
            "repeated",
            "information_seeking_repeated",
        ],
        default="ordinary",
        help="OneStop reading regime for --onestop (default: ordinary).",
    )
    src.add_argument(
        "--onestop-part",
        metavar="PART",
        action="append",
        choices=[
            "Title",
            "Question_Preview",
            "Paragraph",
            "Questions",
            "Answers",
            "QA",
            "Feedback",
        ],
        help="OneStop trial part(s) for --onestop; repeatable (default: "
        "Paragraph). Loading several makes each part its own trial.",
    )
    src.add_argument(
        "--onestop-variant",
        metavar="VARIANT",
        choices=["public", "lacclab"],
        default="public",
        help="OneStop source variant for --onestop: 'public' (OSF download) or "
        "'lacclab' (a local lab-processed export; no download).",
    )
    src.add_argument(
        "--source",
        metavar="NAME",
        choices=["multipleye"],
        help="Load a native server-bundle corpus from its RAW export instead of "
        "raw words/fixations tables. Currently only 'multipleye' — pair with "
        "--export DIR. Renders through the same native loader (correct word "
        "boxes/text/page layout, 1920x1080 monitor) as the interactive viewer.",
    )
    src.add_argument(
        "--export",
        metavar="DIR",
        help="Raw export root for --source (e.g. a MultiplEYE_*_* export dir with "
        "per-session scanpaths/ subfolders). Defaults to $MULTIPLEYE_DATA_DIR "
        "for --source multipleye.",
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

    viz = parser.add_argument_group(
        "visualization (renders the full canonical figure; use --no-* to hide layers)"
    )
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
        "--saccade-color",
        metavar="COLOR",
        help=f"Saccade line/arrow color, hex or CSS name (default: {SACCADE_COLOR}).",
    )
    viz.add_argument(
        "--saccade-style",
        choices=list(SACCADE_DASH_OPTIONS.values()),
        help="Saccade line dash style (default: solid).",
    )
    viz.add_argument(
        "--saccade-width",
        type=float,
        metavar="PX",
        help=f"Saccade line width in px, "
        f"{SACCADE_WIDTH_BOUNDS[0]:g}–{SACCADE_WIDTH_BOUNDS[1]:g} "
        f"(default: {DEFAULT_SACCADE_WIDTH:g}).",
    )
    viz.add_argument(
        "--saccade-color-by-type",
        dest="saccade_color_by_type",
        action="store_true",
        help="Colour each saccade by its reading type (forward / skip / "
        "refixation / return sweep / regression) instead of one uniform colour "
        "(VIZ-8).",
    )
    viz.add_argument(
        "--saccade-type-color",
        dest="saccade_type_colors",
        metavar="CLASS=COLOR",
        action="append",
        help="Override a reading-type colour, e.g. --saccade-type-color "
        "regression=#000000 (repeatable; classes: forward, skip, refixation, "
        "return_sweep, regression). Implies --saccade-color-by-type.",
    )
    viz.add_argument(
        "--no-saccade-type-legend",
        dest="saccade_type_legend",
        action="store_false",
        help="With --saccade-color-by-type: hide the saccade-type colour key on "
        "the figure (the coloured lines still draw). Legend shows by default "
        "(VIZ-8).",
    )
    viz.add_argument(
        "--saccade-arcs",
        dest="saccade_arcs",
        action="store_true",
        help="Draw saccades as upward arcs (the linear-reading diagram) instead "
        "of straight connectors (VIZ-9).",
    )
    viz.add_argument(
        "--snap-fixations",
        dest="snap_fixations",
        action="store_true",
        help="Snap each fixation above the word it lands on instead of its raw "
        "gaze point (VIZ-9).",
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
        "--heatmap-colorscale",
        metavar="NAME",
        help="Heatmap colorscale, e.g. Greens (default: the app's default).",
    )
    viz.add_argument(
        "--heatmap-norm",
        choices=["linear", "log"],
        help="Heatmap colour scaling: linear (default) or log — log compresses "
        "heavy-tailed dwell times so a few hot words don't wash out the rest "
        "(VIZ-3).",
    )
    viz.add_argument(
        "--fixation-colorscale",
        metavar="NAME",
        help="Fixation-marker colorscale, e.g. Blues (default: the app's default).",
    )
    viz.add_argument(
        "--marker-size-range",
        nargs=2,
        type=int,
        metavar=("MIN", "MAX"),
        help="Min/max fixation marker size in px, e.g. 4 12 (default: 8 24). "
        "Smaller ranges suit small thumbnails.",
    )
    viz.add_argument(
        "--canvas",
        metavar="WxH",
        help="Monitor size in px, e.g. 2560x1440 (default: estimated from data; "
        "the bundled sample uses 2560x1440 automatically).",
    )
    # VIZ-4: overlay an image stimulus (a screenshot of the reading screen) under
    # the scanpath. The API already supports background_image*; these expose it on
    # the CLI. Works with --animate too.
    viz.add_argument(
        "--stimulus-image",
        metavar="PATH",
        help="Draw an image (PNG/JPG) as the stimulus background under the "
        "scanpath (VIZ-4). By default it's stretched to the image's own pixel "
        "size (PNG) or the canvas; set --stimulus-image-size / -origin to place "
        "a crop precisely in fixation coordinates.",
    )
    viz.add_argument(
        "--stimulus-image-size",
        metavar="WxH",
        help="Stimulus-image size in px, e.g. 1310x991 (default: the PNG's own "
        "pixel size, else the canvas). Use with --stimulus-image.",
    )
    viz.add_argument(
        "--stimulus-image-origin",
        metavar="X,Y",
        help="Top-left of the stimulus image in monitor px, e.g. 305,44 (default: "
        "0,0). Use with --stimulus-image to align a centered crop to the "
        "fixation coordinates.",
    )
    viz.add_argument(
        "--stimulus-image-opacity",
        type=float,
        metavar="O",
        help="Stimulus-image opacity 0.1–1.0 (default: 1.0 = opaque). Lower it to "
        "dim a busy image so the fixations / saccades / word boxes read over it.",
    )
    viz.add_argument(
        "--width",
        type=int,
        metavar="PX",
        help="Raster output width in px (PNG/SVG/PDF; default: figure's "
        "intrinsic size). Use with --height for fixed-size thumbnails.",
    )
    viz.add_argument(
        "--height",
        type=int,
        metavar="PX",
        help="Raster output height in px (PNG/SVG/PDF; default: figure's "
        "intrinsic size).",
    )
    viz.add_argument(
        "--scale",
        type=float,
        default=2.0,
        metavar="X",
        help="Raster pixel-density multiplier (PNG/SVG/PDF; default: 2.0).",
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
        "--separable-layers",
        action="store_true",
        help="Also write the figure split into one file per layer (word boxes / "
        "fixations / saccades / heatmap / labels / stimulus image) in a "
        "`<output>_layers/` folder, so each can be restyled in Illustrator / "
        "Inkscape. Static image output only (.svg/.pdf/.png); the layers register "
        "when stacked (VIZ-5).",
    )
    viz.add_argument(
        "--playback-speed",
        type=float,
        default=1.0,
        metavar="X",
        help="Animation speed multiplier for --animate (default: 1.0 = real time).",
    )
    viz.add_argument(
        "--no-autoplay",
        dest="autoplay",
        action="store_false",
        help="With --animate: start the replay paused (press ▶ Play to run it). "
        "By default the saved HTML autoplays on load at the playback speed "
        "(VIZ-10).",
    )
    return parser


def _parse_canvas(value: Optional[str]) -> Optional[tuple]:
    if not value:
        return None
    try:
        w, h = (int(part) for part in value.lower().split("x"))
    except ValueError:
        raise SystemExit(f"--canvas expects WxH (e.g. 2560x1440), got {value!r}")
    if w <= 0 or h <= 0:
        raise SystemExit(f"--canvas dimensions must be positive, got {value!r}")
    return (w, h)


def _parse_xy(value: Optional[str]) -> Optional[tuple]:
    """Parse an ``X,Y`` origin (VIZ-4 --stimulus-image-origin) to floats."""
    if not value:
        return None
    try:
        x, y = (float(part) for part in value.split(","))
    except ValueError:
        raise SystemExit(
            f"--stimulus-image-origin expects X,Y (e.g. 305,44), got {value!r}"
        )
    return (x, y)


def _load_multipleye_render(
    export: Optional[str],
    participant: Optional[str],
    trial: Optional[str],
    *,
    list_only: bool = False,
):
    """Native MultiplEYE load for `render --source multipleye`.

    Loads the same normalized frames as the interactive viewer's MultiplEYE
    server-bundle source (correct word boxes/text + image-origin coordinate
    offsets), straight from the RAW export — never the review app's reshaped
    per-pid parquet.

    ``export`` is the raw export root (defaults to ``$MULTIPLEYE_DATA_DIR``).
    ``participant`` is the session label, resolved case-insensitively (the review
    app passes it lowercased, e.g. ``001_zh_ch_1_et2``; export ids are uppercase).

    ``trial`` selection (so a thumbnail matches the viewer's per-page view):
      * a literal per-page trial id (``Lit_Alchemist_4__page_01``) is used as-is;
      * an integer N (the review app's trial number) selects the stimulus whose
        ``trial_num == N`` and renders its **first reading page** — the single
        representative page a thumbnail shows.

    Returns ``(words, fixations, participant_id, trial_id)`` — the resolved ids
    are passed straight to ``api.plot_scanpath``. With ``list_only`` the trial is
    left unresolved (the caller just prints the combos).
    """
    import os

    from .datasets import multipleye_inventory

    root = (export or os.environ.get("MULTIPLEYE_DATA_DIR", "")).strip()
    if not root:
        raise SystemExit(
            "--source multipleye needs --export DIR (or $MULTIPLEYE_DATA_DIR) "
            "pointing at a MultiplEYE raw export root."
        )

    # Resolve the (possibly lowercased) pid to the export's canonical session id.
    sessions, _ = multipleye_inventory(root, fixation_source="scanpaths")
    if not sessions:
        raise FileNotFoundError(
            f"No MultiplEYE sessions under {root} — expected a raw export root "
            "with per-session subfolders under scanpaths/."
        )
    session = None
    if participant is not None:
        want = str(participant).strip().lower()
        session = next((s for s in sessions if s.lower() == want), None)
        if session is None:
            raise ValueError(
                f"No MultiplEYE session matching participant {participant!r} "
                f"(available: {', '.join(sessions)})."
            )

    from .datasets import load_multipleye

    # Load only the requested session (sub-second); all sessions for --list-trials
    # without a -p. Normalized frames, exactly like the viewer.
    words, fixations = load_multipleye(
        root,
        sessions=[session] if session else None,
        fixation_source="scanpaths",
    )
    if list_only:
        return words, fixations, session, None

    pid = session
    tid = trial
    if trial is not None and "__page_" not in str(trial):
        # An integer trial number (the review app's id): map trial_num → stimulus
        # → its first reading page (the page a single thumbnail represents).
        try:
            trial_num = int(str(trial))
        except (TypeError, ValueError):
            raise ValueError(
                f"--trial {trial!r} is neither a per-page trial id "
                "(e.g. Lit_Alchemist_4__page_01) nor an integer trial number."
            )
        if "trial_num" not in fixations.columns:
            raise ValueError(
                "MultiplEYE fixations carry no 'trial_num' column — pass a "
                "per-page trial id to --trial instead."
            )
        match = fixations[fixations["trial_num"].astype("Int64") == trial_num]
        if match.empty:
            avail = sorted(
                fixations["trial_num"].dropna().astype(int).unique().tolist()
            )
            raise ValueError(
                f"No MultiplEYE trial_num={trial_num} for session {session!r} "
                f"(available: {avail})."
            )
        tid = sorted(match["trial_id"].astype(str).unique())[0]

    return words, fixations, pid, tid


def render(argv: List[str]) -> None:
    args = _render_parser().parse_args(argv)
    # Validate everything derivable from argv before the (possibly minutes-long
    # on full corpora) data load.
    if (
        sum(
            [
                args.sample,
                bool(args.words or args.fixations),
                bool(args.potec),
                bool(args.onestop),
                bool(args.source),
            ]
        )
        != 1
    ):
        raise SystemExit(
            "Provide exactly one input: --sample, --potec DIR, --onestop DIR, "
            "--source NAME [--export DIR], or your own tables (--words and/or "
            "--fixations; one of them is enough for single-report datasets)."
        )
    if not args.list_trials and not args.output:
        raise SystemExit("Missing -o/--output (or use --list-trials).")
    canvas = _parse_canvas(args.canvas)
    if args.animate and args.output and not args.output.lower().endswith(".html"):
        raise SystemExit(
            "--animate writes interactive HTML — use a .html output "
            "(GIF/MP4 are available via the Python API: "
            "animation_export.export_animation)."
        )

    from . import api

    if args.sample:
        words, fixations = api.load_sample_data()
        canvas = canvas or (2560, 1440)  # OneStop monitor
    elif args.potec:
        from .datasets import load_potec

        try:
            words, fixations = load_potec(
                args.potec,
                # Narrow the 900-file load when the trial (= text id) is
                # known; reader ids always need the full reader list for
                # --list-trials so only narrow with an explicit -p.
                readers=[args.participant] if args.participant else None,
                texts=[args.trial] if args.trial else None,
                download=True,
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
        canvas = canvas or (1680, 1050)  # PoTeC monitor (DELL P2210)
    elif args.onestop:
        from .datasets import load_onestop

        try:
            words, fixations = load_onestop(
                args.onestop,
                regime=args.onestop_regime,
                parts=args.onestop_part,  # None → Paragraph default
                variant=args.onestop_variant,
                # The lacclab variant is local (no download); the public one
                # fetches the chosen regime + parts from OSF on first use.
                download=args.onestop_variant == "public",
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
        canvas = canvas or (2560, 1440)  # OneStop monitor (Dell U2715H)
    elif args.source == "multipleye":
        from .datasets import MULTIPLEYE_MONITOR

        try:
            words, fixations, args.participant, args.trial = _load_multipleye_render(
                args.export, args.participant, args.trial, list_only=args.list_trials
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
        # Same authoritative monitor the viewer's MultiplEYE bundle source snaps
        # to — coords are offset onto the centered stimulus on the real screen.
        canvas = canvas or MULTIPLEYE_MONITOR
    else:
        words, fixations = api.load_scanpath_data(args.words, args.fixations)

    if args.list_trials:
        combos = api.list_trials(words, fixations)
        print(combos.to_string(index=False))
        return

    try:
        # A given -p/-t must match exactly (mistyped ids are errors, never
        # silently swapped for another trial); only genuinely unspecified
        # parts default to the first available combo, like the app.
        participant, trial = api._resolve_trial(
            words, fixations, args.participant, args.trial, default_first=True
        )
    except ValueError as exc:
        raise SystemExit(str(exc))
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
    if args.heatmap_colorscale:
        overrides["heatmap_colorscale"] = args.heatmap_colorscale
    if args.heatmap_norm:
        overrides["heatmap_norm"] = args.heatmap_norm.capitalize()  # linear→Linear
    if args.fixation_colorscale:
        overrides["fixation_colorscale"] = args.fixation_colorscale
    if args.marker_size_range:
        overrides["marker_size_range"] = tuple(args.marker_size_range)
    if args.saccade_color:
        overrides["saccade_color"] = args.saccade_color
    if args.saccade_style:
        overrides["saccade_style"] = args.saccade_style
    if args.saccade_width is not None:
        overrides["saccade_width"] = args.saccade_width
    # VIZ-8: colour saccades by reading type. Either flag turns the mode on; each
    # CLASS=COLOR pair overrides one class colour; --no-saccade-type-legend hides
    # the colour key.
    if args.saccade_color_by_type or args.saccade_type_colors:
        overrides["saccade_color_mode"] = "By type"
    if not args.saccade_type_legend:
        overrides["saccade_type_legend"] = False
    if args.saccade_type_colors:
        class_colors = dict(SACCADE_CLASS_COLORS)
        for pair in args.saccade_type_colors:
            cls_name, _, color = pair.partition("=")
            cls_name = cls_name.strip()
            if not color or cls_name not in SACCADE_CLASS_EDITABLE:
                raise SystemExit(
                    f"--saccade-type-color expects CLASS=COLOR with CLASS one of "
                    f"{', '.join(SACCADE_CLASS_EDITABLE)}; got {pair!r}."
                )
            class_colors[cls_name] = color.strip()
        overrides["saccade_class_colors"] = class_colors
    # VIZ-9: linear-reading mode.
    if args.saccade_arcs:
        overrides["saccade_render_mode"] = "Arc"
    if args.snap_fixations:
        overrides["fixation_snap_to_word"] = True
    # VIZ-4: image stimulus background. make_scanpath_figure only draws the image
    # when a size is known, so default to the PNG's own pixel size, then the
    # canvas.
    if args.stimulus_image:
        from .plots import _png_pixel_size

        overrides["background_image"] = args.stimulus_image
        overrides["background_image_size"] = (
            _parse_canvas(args.stimulus_image_size)
            or _png_pixel_size(args.stimulus_image)
            or canvas
        )
        overrides["background_image_origin"] = _parse_xy(
            args.stimulus_image_origin
        ) or (0.0, 0.0)
    if args.stimulus_image_opacity is not None:
        overrides["background_image_opacity"] = args.stimulus_image_opacity

    common = dict(
        canvas_size=canvas,
        base_font_size=args.font_size,
        font_family=args.font_family or FONT_FAMILY,
    )
    try:
        if args.animate:
            # The animation builder supports a subset of the static layers;
            # warn (rather than silently ignore) flags it can't honor.
            anim_keys = (
                "show_words",
                "show_word_labels",
                "show_saccades",
                "show_order",
            )
            # Saccade styling is honored by the animation builder too.
            saccade_keys = ("saccade_color", "saccade_style", "saccade_width")
            static_defaults = {
                "show_fixations": True,
                "show_heatmap": True,
                "show_saccade_arrows": False,
            }
            ignored = [
                key
                for key, default in static_defaults.items()
                if overrides[key] != default
            ] + [
                key
                for key in (
                    "color_by",
                    "heatmap_metric",
                    "heatmap_colorscale",
                    "heatmap_norm",
                    "fixation_colorscale",
                    "marker_size_range",
                    "saccade_color_mode",
                    "saccade_class_colors",
                    "saccade_render_mode",
                    "fixation_snap_to_word",
                )
                if key in overrides
            ]
            if ignored:
                print(
                    f"Warning: not supported with --animate, ignoring: "
                    f"{', '.join(sorted(ignored))}",
                    file=sys.stderr,
                )
            anim_kwargs = {k: overrides[k] for k in anim_keys}
            anim_kwargs.update(
                {k: overrides[k] for k in saccade_keys if k in overrides}
            )
            # VIZ-4: the stimulus-image background is honoured by the animation too.
            image_keys = (
                "background_image",
                "background_image_size",
                "background_image_origin",
                "background_image_opacity",
            )
            anim_kwargs.update({k: overrides[k] for k in image_keys if k in overrides})
            fig = api.animate_scanpath(
                words,
                fixations,
                participant,
                trial,
                playback_speed=args.playback_speed,
                autoplay=args.autoplay,
                **anim_kwargs,
                **common,
            )
        else:
            fig = api.plot_scanpath(
                words, fixations, participant, trial, **overrides, **common
            )
        out = api.save_figure(
            fig, args.output, scale=args.scale, width=args.width, height=args.height
        )
        # VIZ-5: also drop a per-layer breakdown next to the output.
        layer_paths = None
        if args.separable_layers:
            suffix = os.path.splitext(args.output)[1].lower().lstrip(".")
            if args.animate or suffix not in ("svg", "pdf", "png"):
                print(
                    "Warning: --separable-layers needs a static image output "
                    "(.svg/.pdf/.png) and no --animate; skipping the layer split.",
                    file=sys.stderr,
                )
            else:
                layer_dir = f"{os.path.splitext(args.output)[0]}_layers"
                layer_paths = api.save_figure_layers(
                    fig,
                    layer_dir,
                    fmt=suffix,
                    scale=int(args.scale),
                    width=args.width,
                    height=args.height,
                )
    except (ValueError, RuntimeError, OSError) as exc:
        raise SystemExit(str(exc))
    print(f"Wrote {out}", file=sys.stderr)
    if layer_paths:
        print(
            f"Wrote {len(layer_paths)} layer files to {os.path.splitext(args.output)[0]}"
            "_layers/",
            file=sys.stderr,
        )


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
