"""EXP-7 — the API / CLI code that reproduces the figure on screen.

The load-bearing tests here are the two round-trips: the emitted Python is
*executed* and its figure compared against the one the settings describe, and
the emitted CLI is *parsed and run* through ``cli.main``. Everything else in
this module only checks that the snippet reads well; those two check it is
true."""

from __future__ import annotations

import ast
import inspect
import shlex

import pytest

from scanpath_studio import api, cli
from scanpath_studio import code_snippet as cs
from tests.conftest import APP_SCRIPT


def _state(kind: str = "static", **overrides) -> cs.FigureState:
    """A FigureState whose settings are the defaults plus ``figure=`` changes."""
    figure = overrides.pop("figure", {})
    return cs.FigureState(
        kind=kind,
        settings={**api.figure_options(kind), **figure},
        participant="p1",
        trial="t1",
        **overrides,
    )


DEMO = cs.SnippetSource(kind=cs.SOURCE_DEMO, label="Bundled Demo")


# ---------------------------------------------------------------------------
# Only the non-defaults
# ---------------------------------------------------------------------------
def test_untouched_settings_emit_no_figure_kwargs():
    assert figure_kwargs_of(_state()) == {}


def figure_kwargs_of(state: cs.FigureState, **kwargs) -> dict:
    return cs.figure_kwargs(state.settings, state.kind, **kwargs)


def test_only_the_changed_options_are_written():
    state = _state(figure={"show_heatmap": False, "color_by": "duration_ms"})
    assert figure_kwargs_of(state) == {
        "show_heatmap": False,
        "color_by": "duration_ms",
    }


def test_explicit_writes_every_option():
    state = _state(figure={"show_heatmap": False})
    explicit = figure_kwargs_of(state, explicit=True)
    # Every figure keyword except the derived ones this module refuses to quote.
    assert set(explicit) == set(api.figure_options("static")) - cs._DERIVED_SETTINGS
    assert explicit["show_heatmap"] is False


def test_a_list_and_a_tuple_of_the_same_numbers_are_the_same_figure():
    """The rail hands back a list where the builder's default is a tuple."""
    default = api.figure_options("static")["marker_size_range"]
    state = _state(figure={"marker_size_range": list(default)})
    assert "marker_size_range" not in figure_kwargs_of(state)


def test_derived_settings_are_never_quoted():
    """`connector_y` is one float per fixation — a snippet full of numbers
    that `drift_connectors=True` recomputes anyway."""
    state = _state(
        figure={"show_connectors": True, "connector_y": tuple(range(400))},
        drift_correction="warp",
        drift_connectors=True,
    )
    code = cs.reproduction_code(DEMO, state)
    assert "connector_y" not in code.python
    assert "drift_connectors=True" in code.python


# ---------------------------------------------------------------------------
# What the snippets can't promise
# ---------------------------------------------------------------------------
def test_an_uploaded_stimulus_image_becomes_a_placeholder():
    state = _state(figure={"background_image": "data:image/png;base64," + "A" * 5000})
    code = cs.reproduction_code(DEMO, state)
    assert "base64" not in code.python
    assert cs._IMAGE_PLACEHOLDER in code.python
    assert any("stimulus image" in note for note in code.caveats)


def test_raw_gaze_is_reported_rather_than_faked():
    """It needs a third frame, not a keyword — so it is a caveat, not a kwarg."""
    state = _state(figure={"show_raw_gaze": True})
    code = cs.reproduction_code(DEMO, state)
    assert "show_raw_gaze" not in code.python
    assert any("raw-gaze" in note for note in code.caveats)


def test_an_uploaded_dataset_says_it_cannot_name_the_files():
    source = cs.SnippetSource(kind=cs.SOURCE_UNKNOWN, note=cs.UNKNOWN_SOURCE_NOTE)
    code = cs.reproduction_code(source, _state())
    assert cs.UNKNOWN_SOURCE_NOTE in code.caveats
    assert "load_scanpath_data" in code.python


def test_settings_with_no_render_flag_are_named_not_dropped():
    state = _state(figure={"fixation_color_range": (1.0, 5.0)})
    code = cs.reproduction_code(DEMO, state)
    assert "fixation_color_range=(1.0, 5.0)" in code.python
    assert "fixation_color_range" in code.cli_unsupported
    assert "fixation_color_range" not in code.cli


def test_the_fixation_index_window_is_named_on_the_cli():
    """VIZ-7 is a `plot_scanpath` parameter with no `render` flag — widening it
    to the whole trial would silently be a different figure."""
    code = cs.reproduction_code(DEMO, _state(fix_index_range=(3, 9)))
    assert "fix_index_range=(3, 9)" in code.python
    assert "fix_index_range" in code.cli_unsupported


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------
def test_a_wrapped_command_never_splits_a_flag_from_its_value():
    state = _state(
        figure={
            "color_by": "duration_ms",
            "show_heatmap": False,
            "fixation_colorscale": "Blues",
            "heatmap_colorscale": "Greens",
            "saccade_color": "#123456",
            "fixation_symbol": "square",
        },
        canvas=(2560, 1440),
        title="A rather long figure title, to force the wrap",
    )
    command = cs.reproduction_code(DEMO, state).cli
    assert " \\\n" in command  # it did wrap
    for line in command.split(" \\\n"):
        tokens = shlex.split(line.strip())
        assert tokens, line
        # A continuation line always opens on a flag, never on a bare value that
        # belongs to the previous line's flag.
        assert tokens[0].startswith("-") or tokens[0] == "scanpath-studio"


def test_a_title_with_spaces_survives_the_shell():
    state = _state(title="Reader p1 — 'Adv' 1")
    command = cs.reproduction_code(DEMO, state).cli
    tokens = shlex.split(command.replace(" \\\n", " "))
    assert tokens[tokens.index("--title") + 1] == "Reader p1 — 'Adv' 1"


@pytest.mark.parametrize(
    "kind, func",
    [("static", "plot_scanpath"), ("animation", "animate_scanpath")],
)
def test_each_kind_calls_its_own_builder(kind, func):
    code = cs.reproduction_code(DEMO, _state(kind))
    assert f"sps.{func}(" in code.python


def test_a_comparison_names_both_scanpaths():
    state = _state(
        "comparison",
        compare=cs.CompareTarget(
            participant="p2", trial="t2", layout="side_by_side", compare_stimulus="a"
        ),
    )
    code = cs.reproduction_code(DEMO, state)
    assert "sps.compare_scanpaths(" in code.python
    assert "('p1', 't1')" in code.python
    assert "('p2', 't2')" in code.python
    assert "layout='side_by_side'" in code.python
    assert "--compare-with p2:t2" in code.cli
    # The settings vocabulary's `side_by_side` is `side-by-side` on the CLI.
    assert "--compare-layout side-by-side" in code.cli


def test_an_animation_carries_its_playback_settings():
    code = cs.reproduction_code(
        DEMO, _state("animation", playback_speed=2.0, autoplay=False)
    )
    assert "playback_speed=2.0" in code.python
    assert "autoplay=False" in code.python
    assert "--animate" in code.cli
    assert "--playback-speed 2" in code.cli
    assert "--no-autoplay" in code.cli


# ---------------------------------------------------------------------------
# The data half
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "source, expect_python, expect_cli",
    [
        (cs.SnippetSource(kind=cs.SOURCE_DEMO), "load_sample_data()", "--sample"),
        (
            cs.SnippetSource(kind=cs.SOURCE_POTEC, options={"root": "d/PoTeC"}),
            "load_potec(",
            "--potec d/PoTeC",
        ),
        (
            cs.SnippetSource(
                kind=cs.SOURCE_ONESTOP,
                options={"root": "d/OneStop", "regime": "repeated", "parts": ["QA"]},
            ),
            "load_onestop(",
            "--onestop-regime repeated",
        ),
        (
            cs.SnippetSource(kind=cs.SOURCE_MULTIPLEYE, options={"root": "d/MPE"}),
            "load_multipleye(",
            "--source multipleye --export d/MPE",
        ),
        (
            cs.SnippetSource(
                kind=cs.SOURCE_BENCHMARK, options={"root": "d/b", "dataset": "ZuCo"}
            ),
            "load_eyegenbench(",
            "--eyegenbench-dataset ZuCo",
        ),
        (
            cs.SnippetSource(
                kind=cs.SOURCE_FILES,
                options={"words": ["w.csv"], "fixations": ["f1.csv", "f2.csv"]},
            ),
            "load_scanpath_data(",
            "--fixations f1.csv f2.csv",
        ),
    ],
)
def test_each_source_writes_both_halves_of_its_loader(
    source, expect_python, expect_cli
):
    code = cs.reproduction_code(source, _state())
    assert expect_python in code.python
    assert expect_cli in code.cli.replace(" \\\n ", " ")


def test_a_source_with_no_render_flags_says_so():
    """The synthetic fixture is importable but not loadable from `render`."""
    code = cs.reproduction_code(cs.SnippetSource(kind=cs.SOURCE_SYNTHETIC), _state())
    assert "load_synthetic_data()" in code.python
    assert any("synthetic" in name for name in code.cli_unsupported)


# ---------------------------------------------------------------------------
# The emitter table can't drift from the parser
# ---------------------------------------------------------------------------
def test_every_cli_emitter_names_a_real_figure_option():
    valid = set(api.figure_options("static"))
    assert set(cs._CLI_EMITTERS) <= valid
    assert cs._CLI_IMPLICIT <= valid


def test_every_flag_a_snippet_can_emit_is_a_real_render_flag():
    """The one thing that would make a copied command fail outright."""
    parser = cli._render_parser()
    known = {option for action in parser._actions for option in action.option_strings}
    state = _state(
        figure={
            key: value
            for key, value in api.figure_options("static").items()
            if key not in cs._DERIVED_SETTINGS
        },
        # PRE-21's gated pair: emitted only when `_render_parser` also has them.
        drift_correction="warp",
        drift_connectors=True,
    )
    command = cs.reproduction_code(DEMO, state, explicit=True).cli
    emitted = {
        token
        for token in shlex.split(command.replace(" \\\n", " "))
        if token.startswith("--")
    }
    assert emitted <= known, sorted(emitted - known)


def _emitted_keywords(snippet: str) -> set[str]:
    """The keyword names of the `sps.<builder>(...)` call in a snippet."""
    tree = ast.parse(snippet)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in cs._API_FUNCTION.values()
        ):
            return {kw.arg for kw in node.keywords if kw.arg}
    raise AssertionError(f"no builder call in:\n{snippet}")


@pytest.mark.parametrize("kind", cs.KINDS)
def test_every_keyword_a_snippet_emits_is_one_its_builder_accepts(kind):
    """The failure this catches is a snippet that raises on its first line.

    `compare_scanpaths` takes neither `screen` nor `drift_connectors` — the app
    pre-slices each side's screen, and the connector layer is the static
    builder's alone — so a state carrying both used to emit a call that
    `_reject_unknown_options` refuses."""
    state = _state(
        kind,
        screen="page_1",
        canvas=(1920, 1080),
        base_font_size=20,
        font_family="Courier New",
        title="T",
        caption="C",
        fix_index_range=(1, 9),
        drift_correction="warp",
        drift_connectors=True,
        playback_speed=2.0,
        autoplay=False,
        compare=cs.CompareTarget(participant="p2", trial="t2"),
    )
    builder = getattr(api, cs._API_FUNCTION[kind])
    accepted = set(inspect.signature(builder).parameters) | set(
        api.figure_options(kind)
    )
    emitted = _emitted_keywords(
        cs.python_snippet(DEMO, state, explicit=True, output="out.png")
    )
    assert emitted <= accepted, sorted(emitted - accepted)


# ---------------------------------------------------------------------------
# The round-trips — the snippet is executed, not just read
# ---------------------------------------------------------------------------
def _figure_fingerprint(fig) -> tuple:
    """Enough of a figure to tell two renderings apart, and stable across runs.

    Deliberately reaches into marker/line **style**, not just the trace list: a
    dropped `fixation_symbol` or `saccade_color` changes neither the number of
    traces nor their names, so a coarser fingerprint would pass while the
    snippet quietly rebuilt a different-looking figure."""

    def style(trace) -> tuple:
        marker = getattr(trace, "marker", None)
        line = getattr(trace, "line", None)
        return (
            trace.type,
            str(trace.name),
            str(getattr(marker, "symbol", None)),
            str(getattr(marker, "color", None)),
            str(getattr(marker, "colorscale", None)),
            str(getattr(line, "color", None)),
            str(getattr(line, "width", None)),
            str(getattr(line, "dash", None)),
            len(
                getattr(trace, "x", None)
                if getattr(trace, "x", None) is not None
                else ()
            ),
        )

    return (
        tuple(sorted(style(trace) for trace in fig.data)),
        len(fig.layout.shapes or ()),
        len(fig.layout.annotations or ()),
        str(fig.layout.title.text),
    )


CHANGED = {
    "show_heatmap": False,
    "show_words": False,
    "color_by": "duration_ms",
    "fixation_symbol": "square",
    "saccade_color": "#123456",
    "saccade_width": 3.0,
}


@pytest.fixture()
def demo_trial():
    words, fixations = api.load_sample_data()
    combos = api.list_trials(words, fixations)
    row = combos.iloc[0]
    return words, fixations, str(row["participant_id"]), str(row["trial_id"])


def test_the_python_snippet_rebuilds_the_same_figure(demo_trial):
    words, fixations, participant, trial = demo_trial
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), **CHANGED},
        participant=participant,
        trial=trial,
        canvas=(2560, 1440),
        title="Round trip",
    )
    snippet = cs.python_snippet(DEMO, state)
    namespace: dict = {}
    exec(compile(snippet, "<snippet>", "exec"), namespace)  # noqa: S102

    expected = api.plot_scanpath(
        words,
        fixations,
        participant=participant,
        trial=trial,
        canvas_size=(2560, 1440),
        title="Round trip",
        **CHANGED,
    )
    assert _figure_fingerprint(namespace["fig"]) == _figure_fingerprint(expected)


def test_the_cli_snippet_parses_and_runs(tmp_path, demo_trial):
    _words, _fixations, participant, trial = demo_trial
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), **CHANGED},
        participant=participant,
        trial=trial,
        canvas=(2560, 1440),
    )
    out = tmp_path / "roundtrip.html"
    command = cs.cli_snippet(DEMO, state, output=str(out))[0]
    argv = shlex.split(command.replace(" \\\n", " "))
    assert argv[:2] == ["scanpath-studio", "render"]
    cli.main(argv[1:])
    assert out.exists() and out.stat().st_size > 0


def test_the_cli_prints_the_recipe_for_its_own_invocation(tmp_path, capsys):
    out = tmp_path / "printed.html"
    cli.main(
        [
            "render",
            "--sample",
            "--no-heatmap",
            "--color-by",
            "duration_ms",
            "--print-code",
            "both",
            "-o",
            str(out),
        ]
    )
    printed = capsys.readouterr().out
    assert "sps.plot_scanpath(" in printed
    assert "show_heatmap=False" in printed
    assert "--no-heatmap" in printed
    # `--print-code` is additive: the figure is still rendered.
    assert out.exists()


# ---------------------------------------------------------------------------
# The headless API
# ---------------------------------------------------------------------------
def test_figure_code_matches_the_module_it_wraps():
    python = api.figure_code(participant="p1", trial="t1", show_heatmap=False)
    assert python == cs.python_snippet(
        DEMO, _state(figure={"show_heatmap": False}), output="scanpath.png"
    )


def test_figure_code_flavours():
    both = api.figure_code(participant="p1", trial="t1", flavor="both")
    assert "sps.plot_scanpath(" in both
    assert "scanpath-studio render" in both
    assert api.figure_code(flavor="cli").startswith("scanpath-studio render")


def test_figure_code_rejects_a_misspelled_option():
    with pytest.raises(TypeError, match="show_heatmp"):
        api.figure_code(show_heatmp=False)


def test_figure_code_rejects_an_unknown_flavour():
    with pytest.raises(ValueError, match="flavor"):
        api.figure_code(flavor="perl")


def test_a_palette_is_expanded_not_named():
    """`palette` is a preset over colour keys, not a figure keyword — a snippet
    that named it would drift the moment the preset's values changed."""
    code = api.figure_code(palette="Print / greyscale")
    assert "palette=" not in code
    assert "saccade_color=" in code


# ---------------------------------------------------------------------------
# The Share subtab's block
# ---------------------------------------------------------------------------
def _snippet_panel_app():
    """Render the Share subtab body for the bundled demo."""
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _render_code_snippet_body

    _render_code_snippet_body(DEMO_CHOICE)


def _panel(**session):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_snippet_panel_app)
    for key, value in session.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def test_the_panel_says_what_to_do_before_a_figure_exists():
    at = _panel()
    copy = " ".join(element.value for element in at.caption)
    assert "Scanpath view" in copy
    assert "_snippet_code_current" not in at.session_state


def test_the_panel_writes_the_snippet_for_the_published_state():
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), "show_heatmap": False},
        participant="l7_101",
        trial="1_Adv_1",
        canvas=(2560, 1440),
    )
    at = _panel(**{cs.SNIPPET_STATE_KEY: state})
    code = at.session_state["_snippet_code_current"]
    assert "show_heatmap=False" in code.python
    assert "--no-heatmap" in code.cli
    # Python is the flavour on show by default; the CLI is one click away.
    assert at.code[0].language == "python"


def test_the_panel_switches_flavour():
    state = cs.FigureState(
        kind="static",
        settings=api.figure_options("static"),
        participant="p1",
        trial="t1",
    )
    at = _panel(
        **{
            cs.SNIPPET_STATE_KEY: state,
            "snippet_flavor": "⌨️ CLI",
        }
    )
    assert at.code[0].language == "bash"
    assert at.code[0].value.startswith("scanpath-studio render")


def test_the_panel_names_what_the_cli_cannot_say():
    state = cs.FigureState(
        kind="static",
        settings={
            **api.figure_options("static"),
            "fixation_color_range": (1.0, 5.0),
        },
        participant="p1",
        trial="t1",
    )
    at = _panel(**{cs.SNIPPET_STATE_KEY: state, "snippet_flavor": "⌨️ CLI"})
    copy = " ".join(element.value for element in at.caption)
    assert "fixation_color_range" in copy


# ---------------------------------------------------------------------------
# The running app publishes the state the panel reads
# ---------------------------------------------------------------------------
@pytest.mark.timeout(120)
def test_the_running_app_publishes_the_figure_it_drew():
    """The seam, end to end: the render path writes what the panel reads.

    The unit tests above would all pass on a `_publish_snippet_state` that is
    never called, which is the failure mode worth pinning."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    assert not at.exception, at.exception

    state = at.session_state[cs.SNIPPET_STATE_KEY]
    assert isinstance(state, cs.FigureState)
    assert state.kind == "static"
    assert state.participant and state.trial
    assert state.canvas and state.canvas[0] > 0
    # The published settings are the builder's own vocabulary, not the rail's.
    assert set(state.settings) >= {"show_words", "show_heatmap", "color_by"}

    # And they round-trip into a snippet naming that trial.
    code = cs.reproduction_code(cs.SnippetSource(kind=cs.SOURCE_SYNTHETIC), state)
    assert state.participant in code.python
    assert "load_synthetic_data()" in code.python


@pytest.mark.timeout(120)
def test_the_app_tracks_a_layer_the_user_turns_off():
    """A rail toggle has to reach the snippet, or it quotes a stale figure."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.run(timeout=90)
    assert not at.exception, at.exception
    before = at.session_state[cs.SNIPPET_STATE_KEY].settings["show_saccades"]

    at.session_state["global_show_saccades"] = not before
    at.run(timeout=90)
    assert not at.exception, at.exception
    assert at.session_state[cs.SNIPPET_STATE_KEY].settings["show_saccades"] != before


@pytest.mark.timeout(240)
def test_the_published_title_is_the_one_the_figure_actually_carries():
    """The snippet's `title=` has to be the figure's own text, not a re-render.

    `_publish_snippet_state` runs above the three render branches, and they do
    not render the pattern against the same context: the static branch passes
    the trial's `combo_row`, the **animation** branch passes none. So a
    combo-derived placeholder like `{difficulty_level}` resolves in the hoisted
    pair and is blank on the animated figure — a snippet quoting a title the
    figure does not carry. `_amend_snippet_title_caption` is the only thing
    that closes that gap, which is what makes this test discriminating: it
    fails if the amend is removed."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["global_show_title_caption"] = True
    at.session_state["global_title_pattern"] = "{participant_id}|{trial_index}"
    at.run(timeout=200)
    assert not at.exception, at.exception
    static = at.session_state[cs.SNIPPET_STATE_KEY]
    assert static.kind == "static"
    resolved = static.title.rpartition("|")[2]
    assert resolved, "the demo's combo row should resolve {trial_index}"

    # Same trial, animated: no combo_row reaches the pattern, so the figure's
    # own title drops that half — and the published one must drop it too.
    at.session_state["single_animate"] = True
    at.run(timeout=200)
    assert not at.exception, at.exception
    state = at.session_state[cs.SNIPPET_STATE_KEY]
    assert state.kind == "animation"
    assert state.title.rpartition("|")[2] != resolved, (
        f"published title still carries the static branch's context: {state.title!r}"
    )
    # And it reaches both flavours rather than stopping at the dataclass.
    code = cs.reproduction_code(cs.SnippetSource(kind=cs.SOURCE_DEMO), state)
    assert state.title in code.python and state.title in code.cli


@pytest.mark.timeout(180)
def test_turning_the_title_off_clears_the_published_one():
    """The amend runs above `_apply_title_caption`'s empty-pair early return,
    so a branch that renders no title clears the hoisted one rather than
    leaving a stale string in the snippet."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state["data_source_choice"] = "Synthetic test trial"
    at.session_state["global_show_title_caption"] = True
    at.session_state["global_title_pattern"] = "{participant_id}"
    at.run(timeout=150)
    assert not at.exception, at.exception
    assert at.session_state[cs.SNIPPET_STATE_KEY].title

    at.session_state["global_show_title_caption"] = False
    at.run(timeout=150)
    assert not at.exception, at.exception
    assert at.session_state[cs.SNIPPET_STATE_KEY].title == ""


#: Options no published state can carry, with the reason. `words_b` /
#: `fixations_b` are *frames* — a snippet quotes B's identity and a caveat
#: points at the `words_b=` seam, because a DataFrame repr means nothing in
#: another process.
_UNPUBLISHABLE = {"words_b", "fixations_b"}


@pytest.mark.timeout(300)
@pytest.mark.parametrize(
    ("label", "session"),
    [
        ("static", {}),
        ("animation", {"single_animate": True}),
        ("comparison", {"single_compare_toggle": True}),
    ],
)
def test_the_app_publishes_every_option_its_builder_accepts(label, session):
    """`figure_kwargs` skips any key the published dict never carried.

    That skip is silent, so an option the app applies *after* the publish —
    the comparison's per-scanpath `style_a` / `style_b` / `show_legend`, the
    animation's frame budget — reproduced at its default instead: a Compare
    figure hand-coloured in the rail came back in the stock palette. Each
    branch now amends the published settings with the ones it actually built
    from; this pins that they stay complete."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_SCRIPT)
    for key, value in session.items():
        at.session_state[key] = value
    at.run(timeout=250)
    assert not at.exception, at.exception

    state = at.session_state[cs.SNIPPET_STATE_KEY]
    assert state.kind == label
    missing = (
        set(api.figure_options(state.kind))
        - set(state.settings)
        - cs._DERIVED_SETTINGS
        - _UNPUBLISHABLE
    )
    assert not missing, f"{label} figure reproduces these at their default: {missing}"


# ---------------------------------------------------------------------------
# The app's source → the snippet's loader
# ---------------------------------------------------------------------------
def _source_app(**session):
    """Resolve `_snippet_source` for a data choice inside a script run."""
    import streamlit as st

    from scanpath_studio.url_state import _snippet_source

    st.session_state["_resolved_source"] = _snippet_source(
        st.session_state["_data_choice"]
    )


def _resolve_source(data_choice: str, **session) -> cs.SnippetSource:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_source_app)
    at.session_state["_data_choice"] = data_choice
    for key, value in session.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at.session_state["_resolved_source"]


def test_the_bundled_demo_maps_to_the_demo_loader():
    from scanpath_studio.constants import DEMO_CHOICE

    assert _resolve_source(DEMO_CHOICE).kind == cs.SOURCE_DEMO


def test_an_uploaded_dataset_maps_to_the_unnameable_source():
    source = _resolve_source("Some dataset I uploaded")
    assert source.kind == cs.SOURCE_UNKNOWN
    assert source.note == cs.UNKNOWN_SOURCE_NOTE


def test_a_public_corpus_carries_the_options_it_was_loaded_with():
    from scanpath_studio.constants import ONESTOP_PUBLIC_CHOICE

    source = _resolve_source(
        ONESTOP_PUBLIC_CHOICE,
        onestop_regime="repeated",
        onestop_parts=["Paragraph", "Questions"],
        onestop_public_dir="/data/OneStop",
    )
    assert source.kind == cs.SOURCE_ONESTOP
    assert source.options["regime"] == "repeated"
    assert source.options["parts"] == ["Paragraph", "Questions"]
    assert source.options["root"] == "/data/OneStop"


def test_the_onestop_server_bundle_says_which_loader_it_is_not():
    from scanpath_studio.constants import ONESTOP_CHOICE

    source = _resolve_source(ONESTOP_CHOICE)
    assert source.options["variant"] == "lacclab"
    assert "server-bundle" in source.note


def test_a_shared_deployment_never_quotes_the_servers_data_path(monkeypatch):
    """S2: on a hosted app the path box isn't the user's, so the snippet must
    not hand every visitor the server's layout."""
    from scanpath_studio.constants import ONESTOP_PUBLIC_CHOICE

    monkeypatch.setenv("SCANPATH_LOCAL_FS", "0")
    source = _resolve_source(
        ONESTOP_PUBLIC_CHOICE, onestop_public_dir="/srv/private/onestop"
    )
    assert "/srv/private" not in source.options["root"]
    assert "/srv/private" not in cs.reproduction_code(source, _state()).python


# ---------------------------------------------------------------------------
# What a copied command must not do (review follow-ups)
# ---------------------------------------------------------------------------
def test_the_drift_command_carries_the_variable_its_flags_need():
    """PRE-21 gates both flags behind SCANPATH_EXPERIMENTAL=1.

    Gating the *emission* on that variable would be no check at all — the
    settings collector already forces `align_algorithm` to "Off" unless it is
    open, so a state carrying a correction can only have come from a process
    where it was set. The command is pasted into another terminal, so it has to
    carry the variable with it or die on `unrecognized arguments` there."""
    state = _state(drift_correction="warp", drift_connectors=True)
    command, unsupported = cs.cli_snippet(DEMO, state)
    assert command.startswith("SCANPATH_EXPERIMENTAL=1 scanpath-studio render")
    assert "--drift-correction warp" in command and "--drift-connectors" in command
    assert "drift_correction" not in unsupported
    # And a figure with no correction is a plain command.
    assert not cs.cli_snippet(DEMO, _state())[0].startswith("SCANPATH_EXPERIMENTAL")


def test_a_comparison_command_omits_the_flags_its_render_path_ignores():
    """`render`'s compare branch passes neither to `compare_scanpaths`, and the
    Python form correctly omits both — so emitting them would be the two
    flavours of one recipe contradicting each other."""
    state = _state(
        kind="comparison",
        screen="s2",
        illustration_label="hide",
        compare=cs.CompareTarget(participant="p2", trial="t2"),
    )
    command = cs.reproduction_code(DEMO, state).cli
    assert "--illustration-label" not in command
    assert "--screen" not in command


def test_the_raster_geometry_reaches_both_flavours():
    """A translated invocation has to write the same-sized file, not just the
    same picture."""
    code = cs.reproduction_code(
        DEMO, _state(), save_kwargs={"width": 1600, "scale": 3.0}
    )
    assert "width=1600" in code.python and "scale=3.0" in code.python
    assert "--width 1600" in code.cli and "--scale 3" in code.cli


def test_a_dual_animation_says_where_scanpath_b_goes():
    """CMP-11: Animate + Compare is one figure with two readings, so `kind` is
    "animation" and B rides in `compare`. B's frames are frames, not options."""
    state = _state(
        kind="animation",
        compare=cs.CompareTarget(participant="p2", trial="t2"),
    )
    notes = " ".join(cs.reproduction_code(DEMO, state).caveats)
    assert "words_b=" in notes and "p2" in notes


def test_the_illustration_disclosure_choice_reaches_both_snippets():
    """`illustration_reasons` is derived; the *label mode* is the rail choice.

    Without it a snippet re-derives at "auto", so a figure whose disclosure was
    forced Hide reproduces with it showing."""
    state = _state(illustration_label="hide")
    code = cs.reproduction_code(DEMO, state)
    assert "illustration_label='hide'" in code.python
    assert "--illustration-label hide" in code.cli
    # The default stays silent, like every other non-default rule here.
    assert "illustration_label" not in cs.reproduction_code(DEMO, _state()).python


def test_a_cross_dataset_comparison_says_whose_reader_b_is():
    """CMP-8: B's participant id belongs to *its* corpus, not the loaded one."""
    state = _state(
        kind="comparison",
        compare=cs.CompareTarget(participant="reader_07", trial="t9", dataset="PoTeC"),
    )
    notes = " ".join(cs.reproduction_code(DEMO, state).caveats)
    assert "PoTeC" in notes and "reader_07" in notes
    # A same-dataset comparison has nothing to warn about.
    same = _state(
        kind="comparison", compare=cs.CompareTarget(participant="p2", trial="t1")
    )
    assert not any(
        "second dataset" in n for n in cs.reproduction_code(DEMO, same).caveats
    )
