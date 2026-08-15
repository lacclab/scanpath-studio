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
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

from . import __version__
from .constants import (
    DEFAULT_FIXATION_COLOR,
    DEFAULT_FIXATION_SYMBOL,
    DEFAULT_SACCADE_WIDTH,
    FIXATION_SYMBOLS,
    FONT_FAMILY,
    PALETTES,
    SACCADE_CLASS_COLORS,
    SACCADE_CLASS_EDITABLE,
    SACCADE_CLASS_ORDER,
    SACCADE_COLOR,
    drift_correction_enabled,
    SACCADE_DASH_OPTIONS,
    SACCADE_WIDTH_BOUNDS,
    UNIFORM_COLOR_FIELD,
)


def _drift_algorithm(value: str) -> str:
    """Validate ``--drift-correction`` against :data:`alignment.ALGORITHMS`.

    Used as an argparse ``type=`` callable so the alignment import (which pulls
    in scipy, ~0.7 s) is paid only when the flag is actually passed — plain
    ``render`` and ``render --help`` stay instant. An unknown name raises
    ``ArgumentTypeError``, so argparse exits non-zero listing the valid ones
    instead of forwarding the string to the API.
    """
    from .alignment import ALGORITHMS

    name = str(value).strip().lower()
    if name not in ALGORITHMS:
        raise argparse.ArgumentTypeError(
            f"unknown algorithm {value!r}; choose one of {', '.join(ALGORITHMS)}."
        )
    return name


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


def _max_upload_cli_flags(extra_args) -> List[str]:
    """Raise the per-file upload cap past Streamlit's 200 MB default.

    Same reason as the theme above: ``.streamlit/config.toml`` is resolved
    against the *launch* directory, so a pip-installed ``scanpath-studio`` run
    from anywhere but the repo root never saw the bundled
    ``server.maxUploadSize`` and rejected any table over 200 MB — which is a
    normal size for a real fixation report. An explicit ``--server.*`` flag from
    the caller still wins.
    """
    from .constants import UPLOAD_MAX_SIZE_MB

    if any(str(arg).startswith("--server.maxUploadSize") for arg in extra_args):
        return []
    return [f"--server.maxUploadSize={UPLOAD_MAX_SIZE_MB}"]


def launch_app(extra_args: List[str]) -> None:
    """Launch the Streamlit app via ``streamlit run``, forwarding extra args."""
    from streamlit.web import cli as stcli

    # ENG-30: `--no-persist` is ours, not Streamlit's — consume it here (it would
    # otherwise reach `streamlit run` as an unknown flag) and set the env var the
    # app reads, so one launch runs without the on-device recovery cache.
    if "--no-persist" in extra_args:
        from .persistence import PERSIST_ENV_VAR

        extra_args = [arg for arg in extra_args if arg != "--no-persist"]
        os.environ[PERSIST_ENV_VAR] = "0"

    # Inject the branded theme unless the caller passes their own ``--theme.*``
    # (explicit flags win), so the app looks the same regardless of where it was
    # launched from (BUG-6).
    theme_args = (
        []
        if any(str(arg).startswith("--theme") for arg in extra_args)
        else _theme_cli_flags()
    )
    # Streamlit's usage stats default to ON, and `.streamlit/config.toml` is
    # resolved against the *launch* directory — which for a pip-installed
    # `scanpath-studio` is wherever the user happened to be. Opt out explicitly,
    # same override rule as the theme: an explicit flag from the caller wins
    # (DATA-12). The desktop launcher already passes this.
    stats_args = (
        []
        if any(str(arg).startswith("--browser.gatherUsageStats") for arg in extra_args)
        else ["--browser.gatherUsageStats=false"]
    )
    app_resource = resources.files(__package__).joinpath("app.py")
    with resources.as_file(app_resource) as app_path:
        sys.argv = [
            "streamlit",
            "run",
            str(app_path),
            *theme_args,
            *stats_args,
            *_max_upload_cli_flags(extra_args),
            *extra_args,
        ]
        sys.exit(stcli.main())


def _render_parser() -> argparse.ArgumentParser:
    from .alignment import ALGORITHMS

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
        "--authoring",
        metavar="PATH",
        help="Scanpath Studio authoring JSON created by the in-app editor.",
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
        "--image-root",
        metavar="DIR",
        help="Local stimulus-image folder. Files are matched per row using "
        "--image-pattern.",
    )
    src.add_argument(
        "--image-pattern",
        default="{text_id}.png",
        metavar="PATTERN",
        help="Relative filename pattern with row placeholders, for example "
        "'{text_id}.png' or '{participant_id}/{trial_id}.png'.",
    )
    src.add_argument(
        "--trial-parts-manifest",
        metavar="PATH",
        help="JSON manifest that assigns arbitrary source rows to ordered screens "
        "inside each logical trial. Use with --words/--fixations when the source "
        "tables have no explicit screen columns.",
    )
    src.add_argument(
        "--potec",
        metavar="DIR",
        help="Load the PoTeC corpus (DiLi-Lab/PoTeC) from DIR, downloading "
        "the needed files (~45 MB) on first use. Participants are the corpus's "
        "75 reader ids (sparse within 0–105; --list-trials shows them), trials "
        "are text ids (b0–b5, p0–p5).",
    )
    src.add_argument(
        "--eyegenbench",
        metavar="DIR",
        help="EyeGenBench bundle directory (built by "
        "scripts/prepare_eyegenbench.py). Pick the corpus with "
        "--eyegenbench-dataset.",
    )
    src.add_argument(
        "--eyegenbench-dataset",
        metavar="NAME",
        help="Which EyeGenBench corpus to render, e.g. PoTeC.",
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
    src.add_argument(
        "--no-question-screens",
        action="store_true",
        help="--source multipleye: load the reading pages only, leaving out the "
        "comprehension-question screens (they are included by default, as "
        "screens of the same trial).",
    )

    src.add_argument(
        "--participant-metadata",
        metavar="FILE",
        help="Participant-level metadata table (DATA-20): one row per reader, an "
        "id column plus anything known about them. The join is validated and "
        "reported against the loaded readers, and the fields are added to "
        "--list-trials output.",
    )

    parser.add_argument(
        "-p", "--participant", help="Participant id (default: first available)."
    )
    parser.add_argument(
        "-t", "--trial", help="Trial id (default: first for the participant)."
    )
    parser.add_argument(
        "--screen",
        help="Screen/part id inside a multipart trial (default: first screen).",
    )
    parser.add_argument(
        "--list-trials",
        action="store_true",
        help="Print the available (participant, trial) combos and exit.",
    )
    parser.add_argument(
        "--list-parts",
        action="store_true",
        help="Print ordered multipart screens, optionally narrowed by -p/-t, and exit.",
    )
    parser.add_argument(
        "--all-screens",
        action="store_true",
        help="Render every screen of the selected parent trial. Screen ids are "
        "inserted before the output extension.",
    )
    parser.add_argument(
        "--screen-transition",
        choices=["instant", "recorded"],
        default="instant",
        help="For --all-screens --animate, record zero or observed inter-screen "
        "delay in each output's metadata (default: instant).",
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
        "--word-hover-fields",
        metavar="FIELDS",
        help="Comma-separated word columns shown on hover (e.g. "
        "text,word_id,gpt2_surprisal).",
    )
    viz.add_argument(
        "--fixation-hover-fields",
        metavar="FIELDS",
        help="Comma-separated fixation columns shown on hover (e.g. "
        "order_in_trial,duration_ms,eye).",
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
        "--saccade-color-by-direction",
        dest="saccade_color_by_direction",
        action="store_true",
        help="Colour saccades forward vs. regression only — the two-way split "
        "between one uniform colour and the full --saccade-color-by-type "
        "breakdown (VIZ-19).",
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
        "--saccade-classes",
        dest="saccade_classes",
        metavar="CLASSES",
        help="VIZ-31: draw only these reading classes, comma-separated, e.g. "
        "--saccade-classes regression,return_sweep (classes: forward, skip, "
        "refixation, return_sweep, regression, other). Hidden classes lose "
        "their line and their direction arrow. Default: all.",
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
        "--illustration",
        action="store_true",
        help="Apply the clean schematic preset: snapped fixations, arced "
        "saccades, uniform colours, and no analytical overlays.",
    )
    viz.add_argument(
        "--illustration-label",
        choices=["auto", "show", "hide"],
        default="auto",
        help="Auto-label transformed/schematic figures, force the label, or "
        "explicitly hide it (default: auto).",
    )
    # PRE-3: vertical drift correction. The algorithm list below is spelled out
    # for `--help`; `alignment.ALGORITHMS` stays the source of truth (the flag
    # validates against it via _drift_algorithm, and a test pins the two lists
    # together).
    #
    # PRE-21: the flags are not *added* while the feature is gated off, so
    # `--help` doesn't advertise something that would then refuse, and passing
    # one is an ordinary argparse "unrecognized arguments" error. `args` still
    # carries the attributes below via `set_defaults`, so no downstream branch
    # needs to know whether the flag exists.
    if drift_correction_enabled():
        viz.add_argument(
            "--drift-correction",
            metavar="ALGORITHM",
            type=_drift_algorithm,
            default=None,
            help="Correct vertical drift before plotting (PRE-3): snap each "
            "fixation to its assigned text line and colour the fixations by "
            "line, exactly like the app's Fixations ⚙️ → Drift correction. "
            f"ALGORITHM is one of: {', '.join(ALGORITHMS)} "
            "(default: no correction). Static figures only — not honored with "
            "--animate.",
        )
        viz.add_argument(
            "--drift-connectors",
            dest="drift_connectors",
            action="store_true",
            help="With --drift-correction: draw a faint line from each "
            "fixation's original y to its corrected one, so the size of the "
            "shift stays visible (PRE-3).",
        )
    else:
        viz.set_defaults(drift_correction=None, drift_connectors=False)
    viz.add_argument(
        "--palette",
        choices=list(PALETTES),
        help="Colour palette for the marks (VIZ-18): Default (colourblind-safe) "
        "(Okabe–Ito), Print / greyscale (hue-free, survives a B&W print), or "
        "High contrast. Individual --*-color flags override it.",
    )
    viz.add_argument(
        "--color-by",
        metavar="FIELD",
        help=f"Fixation color field, e.g. duration_ms or gpt2_surprisal "
        f"(default: {UNIFORM_COLOR_FIELD} — one flat colour, since marker size "
        f"already shows duration).",
    )
    viz.add_argument(
        "--fixation-color",
        metavar="COLOR",
        help=f"Flat fixation marker colour used when --color-by is "
        f"{UNIFORM_COLOR_FIELD} (default: {DEFAULT_FIXATION_COLOR}).",
    )
    viz.add_argument(
        "--fixation-symbol",
        choices=list(FIXATION_SYMBOLS),
        help="Fixation marker shape (VIZ-15). Unlike colour, shape survives a "
        f"greyscale print (default: {DEFAULT_FIXATION_SYMBOL}).",
    )
    viz.add_argument(
        "--heatmap-metric",
        choices=["duration_ms", "counts"],
        help="Heatmap weighting (default: duration_ms).",
    )
    viz.add_argument(
        "--heatmap-style",
        choices=["word-boxes", "interpolated", "duration-mass"],
        help="Heatmap geometry (default: word-boxes).",
    )
    viz.add_argument(
        "--duration-mass-sigma",
        type=float,
        metavar="CHARS",
        help="Gaussian sigma in character widths for --heatmap-style duration-mass.",
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
    viz.add_argument(
        "--coordinate-grid",
        action="store_true",
        help="Overlay a monitor-pixel X/Y grid on the scanpath (VIZ-34).",
    )
    viz.add_argument(
        "--coordinate-grid-spacing",
        type=float,
        metavar="PX",
        help="Pin the major coordinate-grid interval in pixels. Implies "
        "--coordinate-grid; omit for automatic 1/2/5×10ⁿ spacing.",
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
        "--title",
        default=None,
        metavar="TEXT",
        help="Title band stamped on the figure (EXP-5); off by default. The "
        "figure grows to make room rather than shrinking the plot.",
    )
    viz.add_argument(
        "--caption",
        default=None,
        metavar="TEXT",
        help="Caption band stamped on the figure (EXP-5); off by default.",
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
    viz.add_argument(
        "--anim-grid-step-ms",
        type=float,
        default=None,
        metavar="MS",
        help="With --animate: emit a frame every MS of reading time (default: "
        "100). Smaller is smoother and larger to export.",
    )
    viz.add_argument(
        "--anim-max-frames",
        type=int,
        default=None,
        metavar="N",
        help="With --animate: cap the frame count at N (default: 360). A long "
        "reading coarsens the grid to stay under it.",
    )

    # CMP-9 — compare mode's CLI surface. B comes either from the dataset
    # already loaded (--compare-with alone) or from a second pair of tables.
    # Deliberately files-only for the second dataset: twinning every source flag
    # (--compare-potec, --compare-onestop + its regime/part/variant, …) would
    # roughly double this parser for a narrow case, and `api.compare_scanpaths`
    # takes B's frames directly, so a Python caller has no such limit.
    cmp_group = parser.add_argument_group(
        "comparison (CMP-9): draw a second scanpath beside or over the first"
    )
    cmp_group.add_argument(
        "--compare-with",
        metavar="PID:TRIAL",
        help="Compare against a second scanpath, named as participant:trial. "
        "Taken from the loaded dataset unless --compare-words/--compare-fixations "
        "name a second one.",
    )
    cmp_group.add_argument(
        "--compare-layout",
        choices=["overlay", "side-by-side", "stacked"],
        default="overlay",
        help="How the two scanpaths are arranged (default: overlay). Across two "
        "datasets, overlay needs both to have been recorded on the same known "
        "screen — otherwise it is refused rather than silently split, so pass "
        "side-by-side or stacked for a mismatched pair.",
    )
    cmp_group.add_argument(
        "--compare-stimulus",
        choices=["both", "a", "b"],
        default="both",
        help="On an overlay, whose word boxes and text to draw (default: both). "
        "Two datasets' AOIs coincide only when the text is identical.",
    )
    cmp_group.add_argument(
        "--compare-words",
        metavar="PATH",
        nargs="+",
        help="Words/IA table(s) for the SECOND dataset. Same formats and "
        "globbing as --words.",
    )
    cmp_group.add_argument(
        "--compare-fixations",
        metavar="PATH",
        nargs="+",
        help="Fixations table(s) for the SECOND dataset. Same formats and "
        "globbing as --fixations.",
    )
    cmp_group.add_argument(
        "--compare-dataset-name",
        metavar="NAME",
        default="Dataset B",
        help="Label for the second dataset, used in the trace names (default: "
        "'Dataset B').",
    )
    cmp_group.add_argument(
        "--compare-canvas",
        metavar="WxH",
        help="Second dataset's monitor size in px, e.g. 1680x1050. Read off its "
        "data when omitted. Overlay compares this against --canvas.",
    )
    # These two are accepted and recorded on the setup snapshots but are not read
    # by the current render path: CMP-11 shipped as a gate, not a rescaling, so
    # nothing converts to degrees. They exist because SetupSnapshot is on the CLI
    # surface now and a half-populated one is worse than a complete one.
    cmp_group.add_argument(
        "--monitor-mm",
        type=float,
        default=None,
        metavar="MM",
        help="Physical width of the FIRST dataset's monitor, in millimetres.",
    )
    cmp_group.add_argument(
        "--viewing-distance",
        type=float,
        default=None,
        metavar="MM",
        help="Eye-to-screen distance for the FIRST dataset, in millimetres.",
    )
    cmp_group.add_argument(
        "--compare-monitor-mm",
        type=float,
        default=None,
        metavar="MM",
        help="Physical width of the SECOND dataset's monitor, in millimetres.",
    )
    cmp_group.add_argument(
        "--compare-viewing-distance",
        type=float,
        default=None,
        metavar="MM",
        help="Eye-to-screen distance for the SECOND dataset, in millimetres.",
    )
    return parser


def _parse_compare_with(value: str) -> tuple:
    """``"p01:t03"`` → ``("p01", "t03")``, or a clear SystemExit.

    Split on the LAST colon: a participant id may legitimately contain one
    (MultiplEYE's ``001_ZH_CH_1_ET1`` style ids do not, but composite trial ids
    joined with ``_`` sit next to corpora that use colons), while a trial id
    naming a screen never trails one.
    """
    text = str(value or "")
    participant, sep, trial = text.rpartition(":")
    if not sep or not participant.strip() or not trial.strip():
        raise SystemExit(
            f"--compare-with expects PARTICIPANT:TRIAL, got {value!r}. "
            "Use --list-trials to see the available pairs."
        )
    return participant.strip(), trial.strip()


def _compare_second_dataset(api, args, words, fixations):
    """``(words_b, fixations_b)`` for the comparison — A's frames unless given.

    Returns the *whole* second dataset, not one trial; both callers slice it.
    """
    if not (args.compare_words or args.compare_fixations):
        return words, fixations, False
    try:
        return (
            *api.load_scanpath_data(args.compare_words, args.compare_fixations),
            True,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise SystemExit(f"--compare-words/--compare-fixations: {exc}")


def _compare_animation_frames(api, args, words, fixations, canvas) -> dict:
    """B's single-trial frames for a dual co-animation, gated like the overlay.

    A co-animation draws both readings on one clock in one coordinate space —
    i.e. an overlay — so it is refused for two different screens on exactly the
    same terms `compare_scanpaths` refuses `layout="overlay"`, rather than
    quietly replaying scanpath A alone (which is what happened before CMP-9
    reached this branch at all).
    """
    from .experimental_setup import setups_comparable
    from .utils import extract_trial, qualify_for_compare

    participant_b, trial_b = _parse_compare_with(args.compare_with)
    words_b, fixations_b, cross_dataset = _compare_second_dataset(
        api, args, words, fixations
    )
    trial_words_b = extract_trial(words_b, participant_b, trial_b)
    trial_fix_b = extract_trial(fixations_b, participant_b, trial_b)
    if trial_fix_b.empty:
        raise SystemExit(
            f"No fixations for the compared scanpath participant={participant_b!r}, "
            f"trial={trial_b!r}. Use --list-trials to see the available pairs."
        )
    if cross_dataset:
        setup_a = _compare_setup_snapshot(
            canvas, args.monitor_mm, args.viewing_distance
        )
        setup_b = _compare_setup_snapshot(
            _parse_canvas(args.compare_canvas),
            args.compare_monitor_mm,
            args.compare_viewing_distance,
        )
        if setup_a is not None and setup_b is not None:
            comparable, note = setups_comparable(setup_a, setup_b)
            if not comparable:
                raise SystemExit(
                    f"{note} An animated comparison replays both readings on one "
                    f"clock in one coordinate space, so it needs the same screen. "
                    f"Drop --animate to compare them as separate panels."
                )
            if note:
                # Allowed, but the matching canvas is a shared default rather than
                # a recorded screen. Same stream as the other render warnings.
                print(f"Warning: {note}", file=sys.stderr)
        trial_words_b = qualify_for_compare(trial_words_b, args.compare_dataset_name)
        trial_fix_b = qualify_for_compare(trial_fix_b, args.compare_dataset_name)
    return {"words_b": trial_words_b, "fixations_b": trial_fix_b}


def _compare_setup_snapshot(
    canvas: Optional[tuple],
    monitor_mm: Optional[float],
    viewing_distance: Optional[float],
):
    """A `SetupSnapshot` from the CLI's geometry flags, or ``None`` if silent.

    ``None`` lets `api.compare_scanpaths` infer the screen from the data, which
    is the right default — inventing a canvas here would be a claim the caller
    never made.
    """
    from .experimental_setup import Provenance, SetupSnapshot

    if canvas is None and monitor_mm is None and viewing_distance is None:
        return None
    fields: dict = {}
    if canvas is not None:
        fields.update(canvas_width=int(canvas[0]), canvas_height=int(canvas[1]))
    if monitor_mm is not None:
        fields["monitor_width_mm"] = float(monitor_mm)
    if viewing_distance is not None:
        fields["viewing_distance_mm"] = float(viewing_distance)
    return SetupSnapshot(
        **fields,
        # No canvas given means the snapshot carries the *default* one, so it must
        # say ASSUMED — `setups_comparable` treats that as "screen unknown" and
        # refuses the overlay. Reporting ESTIMATED here let `--monitor-mm 520`
        # alone launder a default 2560x1440 into a screen the caller never stated,
        # and it would then compare equal to a real 2560x1440.
        screen_provenance=(
            Provenance.MEASURED if canvas is not None else Provenance.ASSUMED
        ),
        geometry_provenance=(
            Provenance.MEASURED
            if (monitor_mm is not None and viewing_distance is not None)
            else Provenance.ASSUMED
        ),
    )


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
    include_question_screens: bool = True,
):
    """Native MultiplEYE load for `render --source multipleye`.

    Loads the same normalized frames as the interactive viewer's MultiplEYE
    server-bundle source (correct word boxes/text + image-origin coordinate
    offsets), straight from the RAW export — never the review app's reshaped
    per-pid parquet.

    ``export`` is the raw export root (defaults to ``$MULTIPLEYE_DATA_DIR``).
    ``participant`` is the session label, resolved case-insensitively (the review
    app passes it lowercased, e.g. ``001_zh_ch_1_et2``; export ids are uppercase).

    ``trial`` selection (DATA-24: a trial is one *reading of a stimulus*, and its
    pages / question screens are screens inside it, picked with ``--screen``):
      * a literal trial id — the stimulus, ``Lit_Alchemist_4`` — is used as-is;
      * an integer N (the review app's trial number) selects the stimulus whose
        ``trial_num == N``. With no ``--screen`` that renders its first screen,
        i.e. reading page 1 — the single representative page a thumbnail shows.

    ``include_question_screens`` mirrors the loader kwarg (``--no-question-screens``).

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
        include_question_screens=include_question_screens,
    )
    if list_only:
        return words, fixations, session, None

    pid = session
    tid = trial
    known = set(fixations["trial_id"].astype(str)) if not fixations.empty else set()
    if trial is not None and str(trial) not in known:
        # An integer trial number (the review app's id): map trial_num → the
        # stimulus trial it names. Its screens are selected with --screen /
        # --all-screens; with neither, the first screen (reading page 1) renders,
        # which is the single representative page a thumbnail shows.
        try:
            trial_num = int(str(trial))
        except (TypeError, ValueError):
            raise ValueError(
                f"--trial {trial!r} is neither a MultiplEYE trial id (the "
                "stimulus, e.g. Lit_Alchemist_4) nor an integer trial number."
            )
        if "trial_num" not in fixations.columns:
            raise ValueError(
                "MultiplEYE fixations carry no 'trial_num' column — pass the "
                "stimulus trial id to --trial instead."
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
    parser = _render_parser()
    args = parser.parse_args(argv)
    # Validate everything derivable from argv before the (possibly minutes-long
    # on full corpora) data load.
    if (
        sum(
            [
                args.sample,
                bool(args.authoring),
                bool(args.words or args.fixations),
                bool(args.potec),
                bool(args.eyegenbench),
                bool(args.onestop),
                bool(args.source),
            ]
        )
        != 1
    ):
        raise SystemExit(
            "Provide exactly one input: --sample, --authoring PATH, --potec DIR, "
            "--eyegenbench DIR --eyegenbench-dataset NAME, --onestop DIR, "
            "--source NAME [--export DIR], or your own tables (--words and/or "
            "--fixations; one of them is enough for single-report datasets)."
        )
    if not (args.list_trials or args.list_parts) and not args.output:
        raise SystemExit("Missing -o/--output (or use --list-trials/--list-parts).")
    if args.trial_parts_manifest and not (args.words or args.fixations):
        raise SystemExit("--trial-parts-manifest requires --words and/or --fixations.")
    # A comparison is one figure of two readings; --all-screens writes one figure
    # per child screen of a multipart trial. There is no defined pairing between
    # the two, and without this guard the compare branch left `figures` unbound
    # and the run died on an UnboundLocalError instead of saying so.
    if args.compare_with is not None and args.all_screens:
        raise SystemExit(
            "--compare-with cannot be combined with --all-screens: a comparison "
            "is a single figure of two readings. Render one screen at a time with "
            "--screen SCREEN_ID."
        )
    canvas = _parse_canvas(args.canvas)
    if args.coordinate_grid_spacing is not None and args.coordinate_grid_spacing <= 0:
        raise SystemExit("--coordinate-grid-spacing must be a positive number.")
    if args.animate and args.output and not args.output.lower().endswith(".html"):
        raise SystemExit(
            "--animate writes interactive HTML — use a .html output "
            "(GIF/MP4 are available via the Python API: "
            "animation_export.export_animation)."
        )
    # PRE-3: the connectors draw *between* the original and corrected y, so on
    # their own there is nothing to connect. Warn rather than fail — the render
    # is still valid, just uncorrected.
    if args.drift_connectors and not args.drift_correction:
        print(
            "Warning: --drift-connectors has no effect without "
            "--drift-correction ALGORITHM; ignoring it.",
            file=sys.stderr,
        )

    from . import api

    if args.sample:
        words, fixations = api.load_sample_data()
        canvas = canvas or (2560, 1440)  # OneStop monitor
    elif args.authoring:
        try:
            words, fixations = api.load_authored_scanpath(args.authoring)
        except (ValueError, OSError) as exc:
            raise SystemExit(str(exc)) from exc
        canvas = canvas or (1200, 800)
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
    elif args.eyegenbench:
        if not args.eyegenbench_dataset:
            parser.error("--eyegenbench requires --eyegenbench-dataset NAME")
        from .eyegenbench import eyegenbench_monitor, load_eyegenbench

        try:
            words, fixations = load_eyegenbench(
                args.eyegenbench, dataset=args.eyegenbench_dataset
            )
            # `eyegenbench_monitor` answers None for a corpus whose manifest
            # only carries the invented default screen, so `render` falls back
            # to the data's own extents there — the same call the app's picker
            # entry makes (I3). Before this the CLI drew those corpora at
            # 1920x1080 while the app drew them at data extents.
            canvas = canvas or eyegenbench_monitor(
                args.eyegenbench, args.eyegenbench_dataset
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
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
                args.export,
                args.participant,
                args.trial,
                list_only=args.list_trials,
                include_question_screens=not args.no_question_screens,
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
        # Same authoritative monitor the viewer's MultiplEYE bundle source snaps
        # to — coords are offset onto the centered stimulus on the real screen.
        canvas = canvas or MULTIPLEYE_MONITOR
    else:
        manifest = None
        if args.trial_parts_manifest:
            try:
                manifest = json.loads(
                    Path(args.trial_parts_manifest).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                raise SystemExit(f"Could not read trial-parts manifest: {exc}") from exc
        words, fixations = api.load_scanpath_data(
            args.words,
            args.fixations,
            image_root=args.image_root,
            image_pattern=args.image_pattern,
            trial_parts_manifest=manifest,
        )

    if args.image_root and not (args.words or args.fixations):
        from .data import resolve_stimulus_image_paths

        try:
            words = resolve_stimulus_image_paths(
                words, args.image_root, args.image_pattern
            )
            fixations = resolve_stimulus_image_paths(
                fixations, args.image_root, args.image_pattern
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    # DATA-20: attaching a participant table headlessly is worth doing for the
    # join report alone — a mistyped id column or a cohort file from the wrong
    # study is exactly what you want to hear about before rendering 300 figures.
    if args.participant_metadata:
        try:
            attached = api.load_participant_metadata(
                args.participant_metadata, participants=fixations
            )
        except (ValueError, FileNotFoundError, OSError) as exc:
            raise SystemExit(str(exc))
        report = attached.report
        print(
            f"Participant metadata: {len(attached.fields)} field(s) "
            f"({', '.join(attached.names)}) for {len(report.matched)} reader(s).",
            file=sys.stderr,
        )
        for label, ids in (
            ("no row in the table", report.only_in_data),
            ("not in the data", report.only_in_table),
            ("rows that disagree (left empty)", report.conflicting),
        ):
            if ids:
                print(f"  {len(ids)} {label}: {', '.join(ids)}", file=sys.stderr)

    if args.list_trials:
        combos = api.list_trials(words, fixations)
        if args.participant_metadata:
            from scanpath_studio import metadata as _metadata

            combos = _metadata.project(attached, combos)
        print(combos.to_string(index=False))
        return
    if args.list_parts:
        parts = api.list_parts(words, fixations, args.participant, args.trial)
        if parts.empty:
            print("No multipart screens (the selected data is single-screen).")
        else:
            print(parts.to_string(index=False))
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
    if args.coordinate_grid or args.coordinate_grid_spacing is not None:
        overrides["show_coordinate_grid"] = True
        overrides["coordinate_grid_spacing"] = args.coordinate_grid_spacing
    if args.word_hover_fields is not None:
        overrides["word_hover_fields"] = [
            field.strip()
            for field in args.word_hover_fields.split(",")
            if field.strip()
        ]
    if args.fixation_hover_fields is not None:
        overrides["fixation_hover_fields"] = [
            field.strip()
            for field in args.fixation_hover_fields.split(",")
            if field.strip()
        ]
    # VIZ-18: the palette rides along as an override; api._expand_palette turns
    # it into colour kwargs and lets any explicit --*-color below win.
    if args.palette:
        overrides["palette"] = args.palette
    if args.color_by:
        overrides["color_by"] = args.color_by
    if args.fixation_color:  # VIZ-17 flat fixation colour
        overrides["fixation_color"] = args.fixation_color
    if args.fixation_symbol:  # VIZ-15 marker shape
        overrides["fixation_symbol"] = args.fixation_symbol
    if args.heatmap_metric:
        overrides["heatmap_metric"] = args.heatmap_metric
    if args.heatmap_style:
        overrides["heatmap_style"] = {
            "word-boxes": "Word boxes",
            "interpolated": "Interpolated",
            "duration-mass": "Duration mass",
        }[args.heatmap_style]
    if args.duration_mass_sigma is not None:
        overrides["duration_mass_sigma_chars"] = args.duration_mass_sigma
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
    # VIZ-19: --saccade-color-by-direction is the two-way fold; the full five-way
    # split wins if both are given (it's the more specific request).
    if args.saccade_color_by_direction:
        overrides["saccade_color_mode"] = "Forward / regression"
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
    # VIZ-31: the reading-class filter. Independent of the colour mode above —
    # "only the regressions, in one colour" is as valid as "all of them, coloured
    # by type" — so it is its own flag rather than a mode.
    if args.saccade_classes:
        names = [p.strip() for p in args.saccade_classes.split(",") if p.strip()]
        unknown = [n for n in names if n not in SACCADE_CLASS_ORDER]
        if unknown or not names:
            raise SystemExit(
                f"--saccade-classes expects a comma-separated subset of "
                f"{', '.join(SACCADE_CLASS_ORDER)}; got "
                f"{args.saccade_classes!r}."
            )
        overrides["saccade_classes"] = [
            cls for cls in SACCADE_CLASS_ORDER if cls in set(names)
        ]
    # VIZ-9: linear-reading mode.
    if args.saccade_arcs:
        overrides["saccade_render_mode"] = "Arc"
    if args.snap_fixations:
        overrides["fixation_snap_to_word"] = True
    if args.illustration:
        overrides.update(
            show_words=False,
            show_word_labels=True,
            show_fixations=True,
            show_order=False,
            show_saccades=True,
            show_saccade_arrows=False,
            show_heatmap=False,
            color_by=UNIFORM_COLOR_FIELD,
            saccade_color_mode="Uniform",
            saccade_render_mode="Arc",
            fixation_snap_to_word=True,
            fixation_opacity=1.0,
        )
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
        title=args.title or "",
        caption=args.caption or "",
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
                    "saccade_classes",
                    "saccade_render_mode",
                    "fixation_snap_to_word",
                )
                if key in overrides
            ]
            # PRE-3 drift correction is a plot_scanpath-only parameter (the
            # animation builder has no line-snapping path), so name it here too.
            if args.drift_correction:
                ignored.append("drift_correction")
            if args.drift_connectors:
                ignored.append("drift_connectors")
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
            anim_kwargs.update(
                {
                    k: overrides[k]
                    for k in ("show_coordinate_grid", "coordinate_grid_spacing")
                    if k in overrides
                }
            )
            anim_kwargs.update(
                {
                    k: overrides[k]
                    for k in ("word_hover_fields", "fixation_hover_fields")
                    if k in overrides
                }
            )
            # CMP-9/CMP-11: `--animate --compare-with` is the *dual* co-animation
            # the app renders when both modes are on — both readings on one clock.
            # That is an overlay, so it needs one coordinate space, and it is gated
            # on the same `setups_comparable` predicate the static overlay uses.
            if args.compare_with is not None:
                anim_kwargs.update(
                    _compare_animation_frames(api, args, words, fixations, canvas)
                )
                anim_kwargs["compare_stimulus"] = args.compare_stimulus
            animation_options = dict(
                playback_speed=args.playback_speed,
                autoplay=args.autoplay,
                anim_grid_step_ms=args.anim_grid_step_ms,
                anim_max_frames=args.anim_max_frames,
                **anim_kwargs,
                **common,
            )
            if args.all_screens:
                figures = api.render_parent_trial(
                    words,
                    fixations,
                    participant,
                    trial,
                    animate=True,
                    transition_mode=args.screen_transition,
                    **animation_options,
                )
                fig = next(iter(figures.values()))
            else:
                fig = api.animate_scanpath(
                    words,
                    fixations,
                    participant,
                    trial,
                    screen=args.screen,
                    **animation_options,
                )
        elif args.compare_with is not None:
            # `is not None`, not truthiness: `--compare-with ""` is a malformed
            # request, and falling through here would silently render an ordinary
            # single-trial figure for someone who asked for a comparison.
            # CMP-9. Compare owns the whole figure, so it is a peer of the
            # animate/static branches rather than an option on one of them: the
            # comparison builder takes neither `--animate`'s playback settings
            # nor the static path's per-layer extras.
            compare_participant, compare_trial = _parse_compare_with(args.compare_with)
            loaded_b, loaded_fix_b, cross_dataset = _compare_second_dataset(
                api, args, words, fixations
            )
            # None keeps `compare_scanpaths` on its same-dataset path, which is
            # what skips the namespacing.
            words_b = loaded_b if cross_dataset else None
            fixations_b = loaded_fix_b if cross_dataset else None
            fig = api.compare_scanpaths(
                words,
                fixations,
                (participant, trial),
                (compare_participant, compare_trial),
                words_b=words_b,
                fixations_b=fixations_b,
                dataset_b=args.compare_dataset_name,
                layout=args.compare_layout,
                compare_stimulus=args.compare_stimulus,
                setup=_compare_setup_snapshot(
                    canvas, args.monitor_mm, args.viewing_distance
                ),
                setup_b=_compare_setup_snapshot(
                    _parse_canvas(args.compare_canvas),
                    args.compare_monitor_mm,
                    args.compare_viewing_distance,
                ),
                drift_correction=args.drift_correction,
                **overrides,
                **common,  # carries canvas_size / fonts / title / caption
            )
        else:
            static_options = dict(
                drift_correction=args.drift_correction,
                drift_connectors=args.drift_connectors,
                illustration_label=args.illustration_label,
                **overrides,
                **common,
            )
            if args.all_screens:
                figures = api.render_parent_trial(
                    words,
                    fixations,
                    participant,
                    trial,
                    **static_options,
                )
                fig = next(iter(figures.values()))
            else:
                fig = api.plot_scanpath(
                    words,
                    fixations,
                    participant,
                    trial,
                    screen=args.screen,
                    **static_options,
                )
        if args.all_screens:
            target = Path(args.output)
            written = []
            for position, (screen_id, screen_figure) in enumerate(
                figures.items(), start=1
            ):
                safe_screen = "".join(
                    char if char.isalnum() or char in "-_" else "_"
                    for char in str(screen_id)
                )
                screen_path = target.with_name(
                    f"{target.stem}__screen-{position:03d}-{safe_screen}{target.suffix}"
                )
                written.append(
                    api.save_figure(
                        screen_figure,
                        screen_path,
                        scale=args.scale,
                        width=args.width,
                        height=args.height,
                    )
                )
            print(
                f"Wrote {len(written)} screen figure(s): "
                + ", ".join(str(path) for path in written),
                file=sys.stderr,
            )
            return
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


def analyze(argv: List[str]) -> None:
    """Preprocess data and export the complete EXP-3 analysis family."""
    parser = argparse.ArgumentParser(
        prog="scanpath-studio analyze",
        description="Write fixation, saccade, word, sentence, trial, reader, "
        "character, and cleaning-QA tables without launching the app.",
    )
    parser.add_argument("--words", nargs="+", required=True)
    parser.add_argument("--fixations", nargs="+", required=True)
    parser.add_argument(
        "--trial-parts-manifest",
        help="JSON manifest assigning source rows to ordered screens.",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--short-policy",
        choices=["off", "merge", "merge-then-discard", "discard"],
        default="off",
    )
    parser.add_argument("--short-threshold-ms", type=float, default=80.0)
    parser.add_argument("--merge-distance-chars", type=float, default=1.0)
    parser.add_argument("--discard-blink-adjacent", action="store_true")
    parser.add_argument("--pixels-per-degree", type=float)
    args = parser.parse_args(argv)

    from . import api

    manifest = None
    if args.trial_parts_manifest:
        try:
            manifest = json.loads(
                Path(args.trial_parts_manifest).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"Could not read trial-parts manifest: {exc}") from exc
    words, fixations = api.load_scanpath_data(
        args.words,
        args.fixations,
        trial_parts_manifest=manifest,
    )
    policy = {
        "off": "Off",
        "merge": "Merge",
        "merge-then-discard": "Merge then discard",
        "discard": "Discard",
    }[args.short_policy]
    words, fixations, qa = api.preprocess_data(
        words,
        fixations,
        enabled=policy != "Off" or args.discard_blink_adjacent,
        short_policy=policy,
        short_threshold_ms=args.short_threshold_ms,
        merge_distance_chars=args.merge_distance_chars,
        discard_blink_adjacent=args.discard_blink_adjacent,
    )
    tables = api.analysis_tables(
        words, fixations, pixels_per_degree=args.pixels_per_degree
    )
    tables["cleaning_qa"] = qa
    destination = Path(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(destination / f"{name}.csv", index=False)
    config = {
        "short_policy": policy,
        "short_threshold_ms": args.short_threshold_ms,
        "merge_distance_chars": args.merge_distance_chars,
        "discard_blink_adjacent": args.discard_blink_adjacent,
        "pixels_per_degree": args.pixels_per_degree,
    }
    (destination / "run_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(tables)} tables + run_config.json to {destination}")


def corpus(argv: List[str]) -> None:
    """Render a styled corpus figure from a tidy CSV (AN-29)."""
    parser = argparse.ArgumentParser(prog="scanpath-studio corpus")
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--kind", choices=["profile", "distribution", "difference"], required=True
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--measure-label", default="Value")
    parser.add_argument("--series-col", default="series")
    parser.add_argument("--value-col", default="value")
    parser.add_argument("--primary-color", default="#1f77b4")
    parser.add_argument("--secondary-color", default="#e45756")
    args = parser.parse_args(argv)
    from . import api

    data = pd.read_csv(args.input)
    fig = api.plot_corpus_figure(
        data,
        kind=args.kind,
        measure_label=args.measure_label,
        series_col=args.series_col,
        value_col=args.value_col,
        colors=(args.primary_color, args.secondary_color),
    )
    out = api.save_figure(fig, args.output)
    print(f"Wrote {out}")


def cache(argv: List[str]) -> None:
    """Inspect or clear the on-device recovery cache (ENG-30).

    The terminal counterpart of the app's 🗄️ Recovery cache panel, so the
    storage a local run creates can be found, measured and deleted without
    launching the app (or after closing it).
    """
    parser = argparse.ArgumentParser(
        prog="scanpath-studio cache",
        description="Show what a local run has stored on this computer "
        "(uploaded datasets, mappings, view settings, annotations), where it "
        "lives, and delete it. The hosted app stores nothing.",
    )
    parser.add_argument(
        "--path", action="store_true", help="print the cache folder and exit"
    )
    parser.add_argument("--json", action="store_true", help="print the status as JSON")
    parser.add_argument(
        "--clear", action="store_true", help="delete the stored session"
    )
    args = parser.parse_args(argv)
    from .persistence import PERSIST_ENV_VAR, cache_status, clear_local_state
    from .persistence import human_size as _human_size

    # A local run is what this cache belongs to, so report enablement for one
    # (the env override still wins) rather than for the CLI process itself.
    status = cache_status(url="http://localhost")
    if args.path:
        print(status["directory"])
        return
    if args.clear:
        existed = status["exists"]
        clear_local_state()
        print(
            f"Cleared {status['directory']}"
            if existed
            else f"Nothing stored in {status['directory']}"
        )
        return
    if args.json:
        print(json.dumps(status, indent=2))
        return

    print(f"Folder:  {status['directory']}")
    print(
        "Saving:  "
        + ("enabled" if status["enabled"] else "disabled")
        + (f" ({PERSIST_ENV_VAR}={status['override']})" if status["override"] else "")
        + " for local runs"
    )
    if not status["exists"]:
        print("Stored:  nothing")
        return
    if not status["readable"]:
        print("Stored:  unreadable (wrong schema or incomplete) — ignored on startup")
        print(f"Size:    {_human_size(status['bytes'])}")
        return
    names = ", ".join(entry["name"] for entry in status["datasets"]) or "none"
    print(f"Stored:  {len(status['datasets'])} dataset(s): {names}")
    # rows is None for a cache written before the manifest carried row counts
    # (the app backfills it on its next save) — don't print a false 0.
    rows = f"{status['rows']:,} rows" if status["rows"] is not None else "rows unknown"
    print(
        f"         {rows} · {status['annotations']} annotated "
        f"trial(s) · {status['settings']} setting(s)"
    )
    print(f"Size:    {_human_size(status['bytes'])}")
    print(f"Written: {status['saved_at']}")
    print("Delete with `scanpath-studio cache --clear`.")


_HELP = f"""scanpath-studio {__version__} — visualize eye-tracking-while-reading scanpaths

usage:
  scanpath-studio                  launch the interactive app (Streamlit)
  scanpath-studio run [args…]      same, forwarding args to `streamlit run`
  scanpath-studio [run] --no-persist
                                   launch without the on-device recovery cache
                                   (this run only; see `cache` below)
  scanpath-studio render …         render one trial to .html/.png/.svg/.pdf
                                   (see `scanpath-studio render --help`)
  scanpath-studio analyze …        export preprocessing + the full measure family
  scanpath-studio corpus …         render a styled corpus-analysis figure
  scanpath-studio cache …          show / clear the on-device recovery cache
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
    elif argv[0] == "analyze":
        analyze(argv[1:])
    elif argv[0] == "corpus":
        corpus(argv[1:])
    elif argv[0] == "cache":
        cache(argv[1:])
    elif argv[0] in ("-h", "--help"):
        print(_HELP)
    elif argv[0] in ("-V", "--version"):
        print(__version__)
    else:
        # Backward compatibility: bare streamlit flags launch the app.
        launch_app(argv)


if __name__ == "__main__":
    main()
