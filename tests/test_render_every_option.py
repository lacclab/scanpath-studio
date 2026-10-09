"""EXP-20: `render` has a flag for every figure option.

EXP-7's reproduce-in-code block names, rather than drops, any setting the CLI
cannot say (`ReproductionCode.cli_unsupported`) — and that list used to be long:
fixation opacity, the text and background colours, colour-bar styling, raw gaze
(input and style), *Show full monitor*, the x/y fields, line spacing, Compare's
per-scanpath styles and legend. Every one has a flag now, and an emitter, so the
printed command draws the figure.

Three things are pinned here:

* **the guard** — a settings dict with *every* figure option off its default
  leaves `cli_unsupported` empty, and the table of those values must cover every
  option `api.figure_options` lists, so a future option without a flag fails
  here by name rather than quietly being named in the app;
* **each flag reaches the builder** under the keyword it stands for;
* **the round trip** (EXP-12's check): render with `--print-code cli`, run the
  printed command, and the two figures' JSON is identical.
"""

from __future__ import annotations

import shlex

import pytest

from scanpath_studio import api, cli
from scanpath_studio import code_snippet as cs
from scanpath_studio.constants import SACCADE_CLASS_COLORS

#: A 1x1 PNG, for the stimulus-image flags.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000100052301e20000000049454e44ae"
    "426082"
)

#: The one demo trial the bundled raw gaze covers, and a second reading of a
#: different reader to compare it with.
TRIAL = ("l37_1129", "l37_1129_2_2_2_Adv_r0")
OTHER = ("l7_1090", "l7_1090_2_2_2_Adv_r0")

#: Every figure option at a value that is *not* its default. The guard below
#: asserts this covers `api.figure_options(kind)` for every kind, so adding an
#: option means adding it here — and then giving it a `render` flag.
NON_DEFAULT = {
    "show_words": True,
    "show_word_labels": False,
    "show_fixations": False,
    "show_order": True,
    "show_saccades": False,
    "show_heatmap": True,
    "show_saccade_arrows": True,
    "show_raw_gaze": True,
    "heatmap_style": "Interpolated",
    "heatmap_norm": "Log",
    "heatmap_metric": None,  # "counts" at the figure level
    "heatmap_sigma_px": 15.0,
    "heatmap_colorscale": "Greens",
    "heatmap_range": (0.0, 900.0),
    "word_heatmap_col": "gpt2_surprisal",
    "word_heatmap_title": "Surprisal",
    "x_field": "order_in_trial",
    "y_field": "duration_ms",
    "color_by": "duration_ms",
    "color_by_line": True,
    "fixation_color": "#aa0000",
    "fixation_colorscale": "Viridis",
    "fixation_color_range": (100.0, 400.0),
    "fixation_symbol": "square",
    "fixation_opacity": 0.5,
    "hollow_fixations": True,
    "marker_size_range": (5, 20),
    "marker_size_scale": "log",
    "marker_duration_range": (80.0, 900.0),
    "duration_size_legend": False,
    "legend_layout": {
        "saccades": {
            "position": "right-outside",
            "arrangement": "stacked",
            "size": 14,
        },
        "size_key": {"position": "top-left-inside"},
    },
    "fixation_snap_to_word": True,
    "fixation_flags": {"short": {"mode": "Discard", "threshold_ms": 90.0}},
    # CMP-24 — the co-animation's B flags (`--compare-fixation-flag`).
    "fixation_flags_b": {"long": {"mode": "Highlight", "threshold_ms": 700.0}},
    "fixation_hover_fields": ["duration_ms"],
    "word_hover_fields": ["text"],
    "word_hover_measure": "first_fixation_ms",
    "order_font_size": 14,
    "order_font_color": "#222222",
    "saccade_color": "#123456",
    "saccade_style": "dash",
    "saccade_width": 3.0,
    "saccade_color_mode": "By type",
    "saccade_class_colors": {**SACCADE_CLASS_COLORS, "regression": "#abcdef"},
    "saccade_type_legend": False,
    "show_color_legend": False,
    "saccade_classes": ["forward", "regression"],
    "saccade_render_mode": "Arc",
    "critical_span_style": "Mark border",
    "highlight_column": None,
    "text_color": "#333333",
    "highlight_text_color": "#444444",
    "span_border_color": "#555555",
    "background_color": "#fafafa",
    "fit_to_monitor": False,
    "show_coordinate_grid": True,
    "coordinate_grid_spacing": 250.0,
    "line_spacing": 2.5,
    "scale_text_to_boxes": False,
    "show_fixation_colorbar": False,
    "fixation_colorbar_orientation": "Horizontal",
    "fixation_colorbar_tickangle": 30,
    "fixation_colorbar_tickfont_size": 14,
    "show_heatmap_colorbar": False,
    "heatmap_colorbar_orientation": "Horizontal",
    "heatmap_colorbar_tickangle": -30,
    "heatmap_colorbar_tickfont_size": 10,
    "background_image": "page.png",
    "background_image_size": (1200, 800),
    "background_image_origin": (10.0, 20.0),
    "background_image_opacity": 0.5,
    "raw_gaze_color": "#666666",
    "raw_gaze_marker_size": 3.0,
    "raw_gaze_opacity": 0.4,
    "word_box_color": "#777777",
    "word_box_fill_color": "#888888",
    "word_box_fill_opacity": 0.3,
    "word_box_line_opacity": 0.4,
    "illustration_text": "Schematic",
    # The replay's own.
    "anim_grid_step_ms": 50.0,
    "anim_max_frames": 200,
    # The comparison's (and the co-animation's).
    "show_legend": False,  # on by default since #374 F26
    "compare_stimulus": "b",
    "label_a": "A",
    "label_b": "B",
    "style_a": {"fix_color": "#aa0000", "opacity": 0.5},
    "style_b": {"saccade_style": "dot", "hollow": True},
    "background_image_b": "page_b.png",
    "background_image_size_b": (1000, 700),
    "background_image_origin_b": (5.0, 6.0),
}

#: What no settings dict can make a flag out of: the derived keywords the app
#: fills in itself (the drift connectors, the resolved disclosure), and B's
#: *frames*, which are data rather than options.
_NOT_OPTIONS = (cs._DERIVED_SETTINGS - {"show_raw_gaze"}) | {"words_b", "fixations_b"}

DEMO = cs.SnippetSource(kind=cs.SOURCE_DEMO, label="Bundled Demo")


def _maximal_state(kind: str) -> cs.FigureState:
    options = api.figure_options(kind)
    return cs.FigureState(
        kind=kind,
        settings={
            **options,
            **{key: value for key, value in NON_DEFAULT.items() if key in options},
        },
        participant=TRIAL[0],
        trial=TRIAL[1],
        # A comparison needs its B; so does the co-animation, whose B-side
        # options `render` refuses without `--compare-with`.
        compare=(
            cs.CompareTarget(participant=OTHER[0], trial=OTHER[1])
            if kind in ("comparison", "animation")
            else None
        ),
    )


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("kind", cs.KINDS)
def test_the_table_names_every_figure_option(kind):
    """The guard is only as good as its table: an option missing here is one the
    next test cannot see, so it fails first, by name."""
    missing = set(api.figure_options(kind)) - _NOT_OPTIONS - set(NON_DEFAULT)
    assert not missing, (
        f"figure options with no non-default value in NON_DEFAULT: {sorted(missing)}"
        " — add one, then give the option a `render` flag and an emitter in "
        "code_snippet._CLI_EMITTERS."
    )


@pytest.mark.parametrize("kind", cs.KINDS)
def test_every_non_default_option_has_a_render_flag(kind):
    """The EXP-20 promise: with every option changed, nothing is left for the
    CLI form to name instead of saying."""
    state = _maximal_state(kind)
    defaults = api.figure_options(kind)
    unchanged = [
        key
        for key in set(defaults) - _NOT_OPTIONS
        if cs._comparable(state.settings[key]) == cs._comparable(defaults[key])
    ]
    assert not unchanged, f"NON_DEFAULT restates a default: {unchanged}"

    command, unsupported = cs.cli_snippet(DEMO, state)
    assert unsupported == [], f"`render` has no flag for: {unsupported}"
    # …and every flag written is one the parser takes, with a value it accepts.
    argv = shlex.split(command.replace(" \\\n", " "))
    assert argv[:2] == ["scanpath-studio", "render"]
    cli._render_parser().parse_args(argv[2:])


def test_a_palette_is_named_only_when_the_figure_wears_it():
    """Every colour has a flag, so a palette is named only when it saves
    flags — and only when each colour it writes that the figure draws is the
    figure's (#374 F29)."""
    settings = {**api.figure_options("static"), "text_color": "#333333"}
    # *Print / greyscale*'s text colour, and nothing else of it: naming it would
    # turn the fixations, saccades and colour scales grey.
    command, _ = cs.cli_snippet(DEMO, cs.FigureState(kind="static", settings=settings))
    assert "--palette" not in command
    assert "--text-color '#333333'" in command

    from scanpath_studio.constants import palette_settings

    greyscale = palette_settings("Print / greyscale")
    settings = {
        **api.figure_options("static"),
        **{k: v for k, v in greyscale.items() if k != "word_label_color"},
        "text_color": greyscale["word_label_color"],
        # One colour moved back to its default after the palette was applied.
        "fixation_color": api.figure_options("static")["fixation_color"],
    }
    command, _ = cs.cli_snippet(DEMO, cs.FigureState(kind="static", settings=settings))
    # #374 F29: a palette one of whose colours the figure no longer wears is
    # not named — its colours are spelt out instead.
    assert "--palette" not in command
    assert "--text-color" in command
    settings["fixation_color"] = greyscale["fixation_color"]
    command, _ = cs.cli_snippet(DEMO, cs.FigureState(kind="static", settings=settings))
    assert "--palette print" in command
    assert "--fixation-color" not in command and "--text-color" not in command


# ---------------------------------------------------------------------------
# Each flag reaches the builder
# ---------------------------------------------------------------------------
def _spy(monkeypatch, name: str) -> dict:
    seen: dict = {}
    real = getattr(api, name)

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, name, spy)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **kwargs: path)
    return seen


_BASE = ["render", "--sample", "-p", TRIAL[0], "-t", TRIAL[1], "-o", "unused.html"]
_COMPARE = ["--compare-with", f"{OTHER[0]}:{OTHER[1]}"]


@pytest.mark.parametrize(
    ("flags", "kwarg", "expected"),
    [
        (["--fixation-opacity", "0.5"], "fixation_opacity", 0.5),
        (["--marker-size-scale", "linear"], "marker_size_scale", "linear"),
        (
            ["--marker-duration-range", "80", "900"],
            "marker_duration_range",
            (80.0, 900.0),
        ),
        (["--no-duration-size-legend"], "duration_size_legend", False),
        (["--no-color-legend"], "show_color_legend", False),
        (
            [
                "--legend",
                "saccades=right-outside,14,stacked",
                "--legend",
                "size-key=bottom-center-outside",
            ],
            "legend_layout",
            {
                "saccades": {
                    "position": "right-outside",
                    "arrangement": "stacked",
                    "size": 14,
                },
                "size_key": {"position": "bottom-center-outside"},
            },
        ),
        (["--hollow-fixations"], "hollow_fixations", True),
        (["--color-by-line"], "color_by_line", True),
        (["--fixation-color-range", "100", "400"], "fixation_color_range", (100, 400)),
        (["--heatmap-range", "0", "900"], "heatmap_range", (0.0, 900.0)),
        (["--order-font-size", "14"], "order_font_size", 14),
        (["--order-font-color", "#222222"], "order_font_color", "#222222"),
        (["--text-color", "#333333"], "text_color", "#333333"),
        (["--highlight-text-color", "#444444"], "highlight_text_color", "#444444"),
        (["--span-border-color", "#555555"], "span_border_color", "#555555"),
        (["--background-color", "#fafafa"], "background_color", "#fafafa"),
        (["--line-spacing", "2.5"], "line_spacing", 2.5),
        (["--no-scale-text-to-boxes"], "scale_text_to_boxes", False),
        (
            ["--word-hover-measure", "first_fixation_ms"],
            "word_hover_measure",
            "first_fixation_ms",
        ),
        (["--x-field", "order_in_trial"], "x_field", "order_in_trial"),
        (["--y-field", "duration_ms"], "y_field", "duration_ms"),
        (["--no-full-monitor"], "fit_to_monitor", False),
        (["--no-fixation-colorbar"], "show_fixation_colorbar", False),
        (
            ["--fixation-colorbar-orientation", "horizontal"],
            "fixation_colorbar_orientation",
            "Horizontal",
        ),
        (["--fixation-colorbar-tickangle", "-30"], "fixation_colorbar_tickangle", -30),
        (
            ["--fixation-colorbar-tickfont-size", "14"],
            "fixation_colorbar_tickfont_size",
            14,
        ),
        (["--no-heatmap-colorbar"], "show_heatmap_colorbar", False),
        (
            ["--heatmap-colorbar-orientation", "horizontal"],
            "heatmap_colorbar_orientation",
            "Horizontal",
        ),
        (["--heatmap-colorbar-tickangle", "-30"], "heatmap_colorbar_tickangle", -30),
        (
            ["--heatmap-colorbar-tickfont-size", "14"],
            "heatmap_colorbar_tickfont_size",
            14,
        ),
        (["--raw-gaze-color", "#666666"], "raw_gaze_color", "#666666"),
        (["--raw-gaze-marker-size", "3"], "raw_gaze_marker_size", 3.0),
        (["--raw-gaze-opacity", "0.4"], "raw_gaze_opacity", 0.4),
        (["--word-box-color", "#777777"], "word_box_color", "#777777"),
        (["--word-box-fill-color", "#888888"], "word_box_fill_color", "#888888"),
        (["--word-box-fill-opacity", "0.3"], "word_box_fill_opacity", 0.3),
        (["--word-box-line-opacity", "0.4"], "word_box_line_opacity", 0.4),
        (
            ["--word-heatmap-col", "gpt2_surprisal"],
            "word_heatmap_col",
            "gpt2_surprisal",
        ),
        (["--word-heatmap-title", "Surprisal"], "word_heatmap_title", "Surprisal"),
    ],
)
def test_each_static_flag_reaches_its_keyword(monkeypatch, flags, kwarg, expected):
    seen = _spy(monkeypatch, "plot_scanpath")
    cli.main([*_BASE, *flags])
    assert cs._comparable(seen[kwarg]) == cs._comparable(expected)


def test_a_bare_render_passes_none_of_them(monkeypatch):
    """A flag left off must leave the builder its own default — the switches
    in particular are passed only when flipped."""
    seen = _spy(monkeypatch, "plot_scanpath")
    cli.main(_BASE)
    new = set(cli._DIRECT_OPTION_FLAGS) | set(cli._SWITCH_OPTION_FLAGS)
    assert not new & set(seen), sorted(new & set(seen))
    assert seen["raw_gaze"] is None


def test_the_sample_raw_gaze_reaches_the_builder(monkeypatch):
    seen = _spy(monkeypatch, "plot_scanpath")
    cli.main([*_BASE, "--sample-raw-gaze"])
    frame = seen["raw_gaze"]
    assert set(frame["trial_id"]) == {TRIAL[1]}


def test_a_raw_gaze_file_reaches_the_builder(monkeypatch, tmp_path):
    path = tmp_path / "gaze.csv"
    api.load_sample_raw_gaze(names="canonical").to_csv(path, index=False)
    seen = _spy(monkeypatch, "plot_scanpath")
    cli.main([*_BASE, "--raw-gaze", str(path)])
    assert len(seen["raw_gaze"]) == len(api.load_sample_raw_gaze(names="canonical"))


def test_a_raw_gaze_mapping_names_the_columns(monkeypatch, tmp_path):
    """`--raw-gaze-schema` is `--fix-schema`'s twin: a table whose columns
    auto-detection can't read is mapped by hand."""
    path = tmp_path / "gaze.csv"
    frame = api.load_sample_raw_gaze(names="canonical").rename(
        columns={"x": "GX", "y": "GY", "trial_id": "TRIAL"}
    )
    frame.drop(columns=["unique_trial_id", "text_id"]).to_csv(path, index=False)
    with pytest.raises(SystemExit, match="--raw-gaze-schema"):
        cli.main([*_BASE, "--raw-gaze", str(path)])
    seen = _spy(monkeypatch, "plot_scanpath")
    schema = (
        '{"participant": "participant_id", "trial": "TRIAL", "x": "GX", "y": "GY", '
        '"timestamp": "timestamp_ms"}'
    )
    cli.main([*_BASE, "--raw-gaze", str(path), "--raw-gaze-schema", schema])
    assert len(seen["raw_gaze"]) == len(frame)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--sample-raw-gaze", "--raw-gaze", "x.csv"], "not both"),
        (["--raw-gaze-schema", "{}"], "pass --raw-gaze too"),
        (["--compare-legend"], "--compare-with"),
        (["--style-a", "opacity=0.5"], "--compare-with"),
        (["--stimulus-image-b", "b.png"], "--compare-with"),
    ],
)
def test_a_flag_without_what_it_describes_is_refused(argv, expected):
    with pytest.raises(SystemExit, match=expected):
        cli.main([*_BASE, *argv])


def test_the_sample_raw_gaze_needs_the_sample(tmp_path):
    with pytest.raises(SystemExit, match="needs --sample"):
        cli.main(
            [
                "render",
                "--words",
                "w.csv",
                "--sample-raw-gaze",
                "-o",
                str(tmp_path / "x.html"),
            ]
        )


def test_the_comparison_flags_reach_compare_scanpaths(monkeypatch, tmp_path):
    image = tmp_path / "b.png"
    image.write_bytes(_PNG_1x1)
    seen = _spy(monkeypatch, "compare_scanpaths")
    cli.main(
        [
            *_BASE,
            *_COMPARE,
            "--compare-layout",
            "side-by-side",
            "--compare-legend",
            "--style-a",
            "fix_color=#aa0000,saccade_style=dashdot",
            "--style-a",
            "opacity=0.5,marker_size_range=6:18,hollow=true",
            "--style-b",
            "saccade_color=#00aa00,saccade_width=2.5",
            "--stimulus-image-b",
            str(image),
            "--stimulus-image-size-b",
            "800x600",
            "--stimulus-image-origin-b",
            "10,20",
        ]
    )
    assert seen["show_legend"] is True
    assert seen["style_a"] == {
        "fix_color": "#aa0000",
        "saccade_style": "dashdot",
        "opacity": 0.5,
        "marker_size_range": (6, 18),
        "hollow": True,
    }
    assert seen["style_b"] == {"saccade_color": "#00aa00", "saccade_width": 2.5}
    assert seen["background_image_b"] == str(image)
    assert seen["background_image_size_b"] == (800, 600)
    assert seen["background_image_origin_b"] == (10.0, 20.0)


@pytest.mark.parametrize(
    "spec",
    [
        "fix_color=red",  # colours are #RRGGBB only
        "saccade_style=wavy",
        "marker_size_range=6",
        "hollow=maybe",
        "opacity",
        "bogus=1",
    ],
)
def test_a_bad_style_spec_is_a_message(spec):
    with pytest.raises(SystemExit, match="--style-a: can't read"):
        cli.main([*_BASE, *_COMPARE, "--style-a", spec])


def test_the_co_animation_flags_reach_animate_scanpath(monkeypatch):
    seen = _spy(monkeypatch, "animate_scanpath")
    cli.main(
        [
            *_BASE,
            *_COMPARE,
            "--animate",
            "--compare-legend",
            "--compare-stimulus",
            "b",
            "--fixation-opacity",
            "0.5",
        ]
    )
    assert seen["show_legend"] is True
    assert seen["compare_stimulus"] == "b"
    assert seen["fixation_opacity"] == 0.5
    assert seen["fixations_b"] is not None


# ---------------------------------------------------------------------------
# The round trip — the printed command draws the same figure
# ---------------------------------------------------------------------------
def _figures(monkeypatch, argv_list) -> list:
    figures: list = []

    def capture(fig, path, **_kwargs):
        figures.append(fig)
        return path

    monkeypatch.setattr(api, "save_figure", capture)
    for argv in argv_list:
        cli.main(argv)
    return figures


def _round_trip(monkeypatch, capsys, flags: list[str]):
    """Render ``flags`` with `--print-code cli`, then run what it printed."""
    original = [*_BASE[:-2], *flags, "--print-code", "cli", "-o", "a.html"]
    capsys.readouterr()
    (first,) = _figures(monkeypatch, [original])
    printed = capsys.readouterr().out.strip()
    assert "No `render` flag" not in printed, printed
    replay = shlex.split(printed.replace(" \\\n", " "))
    assert replay[:2] == ["scanpath-studio", "render"]
    (second,) = _figures(monkeypatch, [replay[1:]])
    return first, second, printed


#: Every new single-trial option, at once, on the demo trial the raw gaze covers.
STATIC_FLAGS = [
    # The layers the styling below applies to (#374 F21/F29: a layer that is off
    # takes no styling flags).
    "--word-boxes",
    "--heatmap",
    "--fixation-index",
    "--sample-raw-gaze",
    "--raw-gaze-color",
    "#666666",
    "--raw-gaze-marker-size",
    "3",
    "--raw-gaze-opacity",
    "0.4",
    "--word-box-color",
    "#777777",
    "--word-box-fill-color",
    "#888888",
    "--word-box-fill-opacity",
    "0.3",
    "--word-box-line-opacity",
    "0.4",
    "--fixation-opacity",
    "0.5",
    "--hollow-fixations",
    "--color-by",
    "duration_ms",
    "--fixation-color-range",
    "100",
    "400",
    "--heatmap-range",
    "0",
    "900",
    "--order-font-size",
    "14",
    "--order-font-color",
    "#222222",
    "--text-color",
    "#333333",
    "--highlight-text-color",
    "#444444",
    "--critical-span-style",
    "mark-border",
    "--span-border-color",
    "#555555",
    "--background-color",
    "#fafafa",
    "--line-spacing",
    "2.5",
    "--no-scale-text-to-boxes",
    "--word-hover-measure",
    "first_fixation_ms",
    "--no-full-monitor",
    "--no-fixation-colorbar",
    "--fixation-colorbar-orientation",
    "horizontal",
    "--fixation-colorbar-tickangle",
    "30",
    "--fixation-colorbar-tickfont-size",
    "14",
    "--no-heatmap-colorbar",
    "--heatmap-colorbar-orientation",
    "horizontal",
    "--heatmap-colorbar-tickangle",
    "30",
    "--heatmap-colorbar-tickfont-size",
    "14",
    "--saccade-color-by-direction",
    "--saccade-type-color",
    "regression=#abcdef",
]


def test_every_new_static_option_round_trips(monkeypatch, capsys):
    first, second, printed = _round_trip(monkeypatch, capsys, STATIC_FLAGS)
    for flag in (
        "--sample-raw-gaze",
        "--no-full-monitor",
        "--no-fixation-colorbar",
        "--no-heatmap-colorbar",
    ):
        assert flag in printed
    assert "Raw gaze" in {trace.name for trace in first.data}
    assert first.to_json() == second.to_json()


def test_the_color_by_line_and_axis_fields_round_trip(monkeypatch, capsys):
    """Kept apart from the rest: a non-spatial axis turns the scanpath into a
    chart, which would hide what the other options do."""
    first, second, _ = _round_trip(monkeypatch, capsys, ["--color-by-line"])
    assert first.to_json() == second.to_json()
    first, second, printed = _round_trip(
        monkeypatch,
        capsys,
        ["--x-field", "order_in_trial", "--y-field", "duration_ms"],
    )
    assert "--x-field order_in_trial" in printed
    assert first.to_json() == second.to_json()


def test_every_new_comparison_option_round_trips(monkeypatch, capsys, tmp_path):
    image = tmp_path / "b.png"
    image.write_bytes(_PNG_1x1)
    first, second, printed = _round_trip(
        monkeypatch,
        capsys,
        [
            *_COMPARE,
            "--compare-layout",
            "side-by-side",
            "--compare-legend",
            "--style-a",
            "fix_color=#aa0000,saccade_style=dashdot,opacity=0.5",
            "--style-b",
            "saccade_color=#00aa00,marker_size_range=6:18,hollow=true",
            "--stimulus-image-b",
            str(image),
            "--stimulus-image-size-b",
            "800x600",
            "--stimulus-image-origin-b",
            "10,20",
            "--fixation-opacity",
            "0.6",
            "--background-color",
            "#fafafa",
        ],
    )
    assert "--style-a" in printed and "--stimulus-image-b" in printed
    assert first.to_json() == second.to_json()


def test_the_co_animation_round_trips(monkeypatch, capsys):
    """`--compare-with` is now written for the two-reading replay too: the
    labels, the stimulus and the legend are refused without it."""
    first, second, printed = _round_trip(
        monkeypatch,
        capsys,
        [
            *_COMPARE,
            "--animate",
            "--compare-stimulus",
            "b",
            "--compare-legend",
            "--label-a",
            "Reader A",
            "--label-b",
            "Reader B",
            "--fixation-opacity",
            "0.5",
        ],
    )
    assert f"--compare-with {OTHER[0]}:{OTHER[1]}" in printed
    assert "--label-a 'Reader A'" in printed
    assert first.to_json() == second.to_json()


def test_a_palette_with_one_class_colour_changed_round_trips(monkeypatch):
    """A palette with one class colour changed: the command spells the
    colours out (#374 F29), and `render` draws the same figure from it."""
    from scanpath_studio.constants import palette_settings

    palette = palette_settings("High contrast")
    classes = {**palette["saccade_class_colors"], "regression": "#abcdef"}
    settings = {
        **api.figure_options("static"),
        **{k: v for k, v in palette.items() if k != "word_label_color"},
        "text_color": palette["word_label_color"],
        "saccade_color_mode": "By type",
        "saccade_class_colors": classes,
    }
    state = cs.FigureState(
        kind="static",
        settings=settings,
        participant=TRIAL[0],
        trial=TRIAL[1],
        canvas=(2560, 1440),
    )
    command, unsupported = cs.cli_snippet(DEMO, state, output="x.html")
    # #374 F29: the figure no longer wears the palette, so it is spelt out.
    assert "--palette" not in command and not unsupported
    (from_cli,) = _figures(
        monkeypatch, [shlex.split(command.replace(" \\\n", " "))[1:]]
    )
    words, fixations = api.load_sample_data()  # as `render --sample`, by its own names
    expected = api.plot_scanpath(
        words,
        fixations,
        *TRIAL,
        canvas_size=(2560, 1440),
        **cs.figure_kwargs(settings, "static"),
    )
    assert from_cli.to_json() == expected.to_json()


def test_an_integer_flag_is_printed_as_an_integer():
    """`--order-font-size` and the two colour-bar tick flags are `type=int`, so
    a settings dict holding `12.0` printed a command `render` refused."""
    command = api.figure_code(
        flavor="cli",
        show_order=True,
        show_heatmap=True,
        color_by="duration_ms",
        order_font_size=12.0,
        fixation_colorbar_tickangle=30.0,
        heatmap_colorbar_tickangle=30.0,
        fixation_colorbar_tickfont_size=14.0,
        heatmap_colorbar_tickfont_size=14.0,
    )
    argv = shlex.split(command.replace(" \\\n", " "))
    args = cli._render_parser().parse_args(argv[2:])
    assert (args.order_font_size, args.fixation_colorbar_tickangle) == (12, 30)
    assert args.heatmap_colorbar_tickfont_size == 14
    replay = api.figure_code(kind="animation", flavor="cli", anim_max_frames=200.0)
    argv = shlex.split(replay.replace(" \\\n", " "))
    assert cli._render_parser().parse_args(argv[2:]).anim_max_frames == 200


def test_no_hover_measure_is_an_empty_flag_not_a_missing_one(monkeypatch):
    """`word_hover_measure=None` (no measure on hover) is off its default, and
    `_valued` dropped `None` — so the command showed the default measure."""
    command = api.figure_code(flavor="cli", word_hover_measure=None)
    assert "--word-hover-measure ''" in command
    seen = _spy(monkeypatch, "plot_scanpath")
    cli.main([*_BASE, "--word-hover-measure", ""])
    assert seen["word_hover_measure"] is None
