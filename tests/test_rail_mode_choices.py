"""Rail choices that must mean the same thing on every layer and in every mode.

Each test drives the real plot rail (`controls.render_plot_controls`) under
AppTest over a tiny three-word, two-line trial, then builds the figure the Scanpath view
would build from what the rail returned — so a gate in the collector, not just
in the builder, is what is under test.
"""

from __future__ import annotations

import pytest

from scanpath_studio import plots, tabs

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

#: A 1×1 PNG — a stand-in stimulus screenshot.
PIXEL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="
)


def _frames():
    import pandas as pd

    words = pd.DataFrame(
        {
            "participant_id": ["p"] * 3,
            "trial_id": ["t"] * 3,
            "text_id": ["text"] * 3,
            "word_id": [1, 2, 3],
            "text": ["One", "Two", "Three"],
            "line_idx": [0, 0, 1],
            "x": [100, 200, 100],
            "y": [100, 100, 150],
            "width": [80, 80, 80],
            "height": [20, 20, 20],
            "flag": [True, False, False],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p"] * 4,
            "trial_id": ["t"] * 4,
            "text_id": ["text"] * 4,
            "x": [110, 120, 210, 120],
            "y": [110, 110, 110, 160],
            "duration_ms": [100, 200, 300, 300],
            "timestamp_ms": [0, 100, 300, 600],
            "order_in_trial": [1, 2, 3, 4],
            "fixation_id": [1, 2, 3, 4],
            "word_id": [1, 1, 2, 3],
            "eye": ["L", "R", "L", "R"],
            "pupil_size": [2.1, 2.2, 2.3, 2.4],
        }
    )
    return words, fixations


def _rail_app():
    import streamlit as st

    from scanpath_studio import controls
    from tests.test_rail_mode_choices import _frames

    words, fixations = _frames()
    st.session_state["_viz"] = controls.render_plot_controls(
        fixations, 16, words=words, fix_range_fixations=fixations
    )


def _rail(**state) -> AppTest:
    at = AppTest.from_function(_rail_app)
    for key, value in state.items():
        at.session_state[key] = value
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _rerun(at: AppTest) -> AppTest:
    at.run(timeout=60)
    assert not at.exception, at.exception
    return at


def _settings(viz: dict, **overrides) -> plots.FigureSettings:
    return plots.FigureSettings.from_mapping(
        tabs._build_figure_settings(viz, False),
        canvas_width=800,
        canvas_height=600,
        base_font_size=16,
        **overrides,
    )


def _static(at: AppTest, **overrides):
    words, fixations = _frames()
    viz = at.session_state["_viz"]
    return plots.make_scanpath_figure(
        words, fixations, settings=_settings(viz, **overrides)
    )


def _span_outlines(fig) -> list:
    """The span outline shapes — drawn in the border colour, unlike the frame."""
    return [
        s
        for s in fig.layout.shapes or ()
        if s.type == "rect" and s.line.color == "#123456"
    ]


# --- Highlight → Mark border is its own layer --------------------------------

BORDER = {
    "global_show_stimulus": True,
    "global_show_labels": False,
    "global_show_words": False,
    "global_highlight_column": "flag",
    "global_critical_span_style": "Mark border",
    "global_span_border_color": "#123456",
}


def test_mark_border_draws_with_text_and_word_boxes_off():
    at = _rail(**BORDER)
    viz = at.session_state["_viz"]
    assert viz["highlight_column"] == "flag"
    assert len(_span_outlines(_static(at))) == 1


def test_mark_border_draws_over_a_screenshot():
    at = _rail(**BORDER)
    fig = _static(at, background_image=PIXEL, background_image_size=(800, 600))
    assert fig.layout.images, "the screenshot layer is drawn"
    assert len(_span_outlines(fig)) == 1


def test_stimulus_master_switch_suppresses_and_restores_the_border():
    at = _rail(**{**BORDER, "global_show_stimulus": False})
    assert at.session_state["_viz"]["highlight_column"] is None
    assert _span_outlines(_static(at)) == []
    at.session_state["global_show_stimulus"] = True
    _rerun(at)
    assert len(_span_outlines(_static(at))) == 1


def test_mark_text_stays_inactive_while_text_is_hidden():
    at = _rail(**{**BORDER, "global_critical_span_style": "Mark text"})
    assert at.session_state["_viz"]["highlight_column"] is None
    at.session_state["global_show_labels"] = True
    _rerun(at)
    assert at.session_state["_viz"]["highlight_column"] == "flag"


# --- Color by in Compare and the co-animation --------------------------------


def _pair():
    """A and B: two readers of one text, B's eyes in a different order."""
    import pandas as pd

    words, fixations = _frames()
    words_b, fixations_b = words.copy(), fixations.copy()
    words_b["participant_id"] = "q"
    fixations_b["participant_id"] = "q"
    fixations_b["eye"] = ["R", "R", "B", "L"]
    fixations_b["duration_ms"] = [400, 150, 250, 300]
    return (
        pd.concat([words, words_b], ignore_index=True),
        pd.concat([fixations, fixations_b], ignore_index=True),
        (words_b, fixations_b),
    )


def _compare(viz: dict, layout: str, **overrides):
    words, fixations, _ = _pair()
    return plots.make_comparison_figure(
        words,
        fixations,
        ("p", "t"),
        ("q", "t"),
        settings=_settings(viz, layout=layout, **overrides),
    )


def _scanpath_markers(fig) -> list:
    """The two scanpaths' marker traces (they carry the per-fixation hover)."""
    return [
        t
        for t in fig.data
        if t.mode
        and "markers" in t.mode
        and t.customdata is not None
        and len(t.x) == 4
        and t.x[0] is not None
    ]


def _trails(fig) -> list:
    """A replay's trail traces (the frames restate them by position)."""
    return [
        t
        for t in fig.data
        if t.customdata is not None and t.name in ("Scanpath A", "Scanpath B")
    ]


def _category_entries(fig) -> list:
    return [t.name for t in fig.data if t.showlegend and ": " in str(t.name)]


LAYOUTS = ["overlay", "side_by_side", "stacked"]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_compare_colours_a_categorical_column_on_one_shared_mapping(layout):
    at = _rail(global_color_by="eye", single_compare_toggle=True)
    assert not at.selectbox(key="global_color_by").disabled
    a, b = _scanpath_markers(_compare(at.session_state["_viz"], layout))
    # A reads L R L R, B reads R R B L: one colour per eye on both scanpaths.
    assert a.marker.color[0] == a.marker.color[2] == b.marker.color[3]
    assert a.marker.color[1] == b.marker.color[0] == b.marker.color[1]
    assert len(set(a.marker.color) | set(b.marker.color)) == 3
    # A and B stay apart by their outline, which no category wears.
    outlines = {a.marker.line.color, b.marker.line.color}
    assert len(outlines) == 2
    assert not outlines & (set(a.marker.color) | set(b.marker.color))
    assert _category_entries(_compare(at.session_state["_viz"], layout)) == [
        "eye: L",
        "eye: R",
        "eye: B",
    ]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_compare_colours_by_line(layout):
    at = _rail(global_color_by="line", single_compare_toggle=True)
    fig = _compare(at.session_state["_viz"], layout)
    a, b = _scanpath_markers(fig)
    # The last fixation of each reading is on the second line.
    assert a.marker.color[0] == a.marker.color[2] != a.marker.color[3]
    assert list(a.marker.color) == list(b.marker.color)
    assert _category_entries(fig) == ["line: Line 1", "line: Line 2"]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_compare_numeric_colouring_is_unchanged(layout):
    at = _rail(global_color_by="duration_ms", single_compare_toggle=True)
    a, b = _scanpath_markers(_compare(at.session_state["_viz"], layout))
    assert list(a.marker.color) == [100, 200, 300, 300]
    assert (a.marker.cmin, a.marker.cmax) == (b.marker.cmin, b.marker.cmax)
    assert (a.marker.cmin, a.marker.cmax) == (100.0, 400.0)
    assert a.marker.line.color != b.marker.line.color
    assert _category_entries(_compare(at.session_state["_viz"], layout)) == []


@pytest.mark.parametrize("color_by", ["eye", "line", "duration_ms"])
@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_colour_choice_changes_the_comparison(color_by, layout):
    at = _rail(global_color_by=color_by, single_compare_toggle=True)
    viz = at.session_state["_viz"]
    coloured = _compare(viz, layout).to_json()
    uniform = _compare(
        viz, layout, color_by=plots.UNIFORM_COLOR_FIELD, color_by_line=False
    ).to_json()
    assert coloured != uniform


def test_leaving_compare_keeps_the_static_choice():
    at = _rail(global_color_by="eye", single_compare_toggle=True)
    at.session_state["single_compare_toggle"] = False
    _rerun(at)
    assert at.session_state["global_color_by"] == "eye"
    static = next(t for t in _static(at).data if t.name == "Fixations")
    assert len(set(static.marker.color)) == 2


@pytest.mark.parametrize("color_by", ["eye", "line", "duration_ms"])
def test_the_co_animation_colours_like_the_comparison(color_by):
    at = _rail(global_color_by=color_by, single_compare_toggle=True)
    words, fixations = _frames()
    _, _, (words_b, fixations_b) = _pair()
    fig = plots.make_scanpath_animation(
        words,
        fixations,
        settings=_settings(at.session_state["_viz"], show_legend=True),
        fixations_b=fixations_b,
        words_b=words_b,
    )
    a, b = _trails(fig)
    assert a.marker.line.color != b.marker.line.color
    if color_by == "duration_ms":
        assert list(b.marker.color) == [400, 150, 250, 300]
        assert (a.marker.cmin, a.marker.cmax) == (b.marker.cmin, b.marker.cmax)
    else:
        assert len(set(a.marker.color) | set(b.marker.color)) > 1
        assert fig.frames[-1].data[0].marker.color == a.marker.color
        assert _category_entries(fig)


@pytest.mark.parametrize("color_by", ["eye", "line"])
def test_the_single_replay_colours_discrete_choices(color_by):
    at = _rail(global_color_by=color_by, single_animate=True)
    words, fixations = _frames()
    fig = plots.make_scanpath_animation(
        words, fixations, settings=_settings(at.session_state["_viz"])
    )
    (trail,) = _trails(fig)
    assert len(set(trail.marker.color)) == 2
    assert _category_entries(fig)


# --- ♥ is a heart on every render path ----------------------------------------


def _hearts(fig) -> list:
    return [t for t in fig.data if t.mode == "text" and "♥" in set(t.text or ())]


def _no_heart_markers(fig) -> bool:
    """Nothing hands Plotly a ``heart`` symbol, and no fixation falls back to a
    circle marker: the markers left are legend swatches and decorations."""
    for trace in fig.data:
        marker = getattr(trace, "marker", None)
        if marker is None or not trace.mode or "markers" not in trace.mode:
            continue
        assert marker.symbol != "heart"
        if trace.customdata is not None:
            return False
    return True


@pytest.mark.parametrize("mode", [{}, {"single_animate": True}])
def test_heart_in_the_static_figure_and_the_replay(mode):
    at = _rail(global_fixation_symbol="heart", global_fixation_opacity=0.5, **mode)
    assert not at.selectbox(key="global_fixation_symbol").disabled
    words, fixations = _frames()
    settings = _settings(at.session_state["_viz"])
    for fig in (
        plots.make_scanpath_figure(words, fixations, settings=settings),
        plots.make_scanpath_animation(words, fixations, settings=settings),
    ):
        assert _no_heart_markers(fig)
        (heart,) = _hearts(fig)
        assert heart.opacity == 0.5
        # Duration → size: the two 300 ms fixations draw the same size, larger
        # than the 100 ms one.
        sizes = list(heart.textfont.size)
        assert len(sizes) == 4
        assert sizes[2] == sizes[3] > sizes[0]


@pytest.mark.parametrize("layout", LAYOUTS)
def test_heart_in_every_comparison_layout(layout):
    at = _rail(global_fixation_symbol="heart", single_compare_toggle=True)
    assert not at.selectbox(key="global_fixation_symbol").disabled
    viz = at.session_state["_viz"]
    flat = _compare(viz, layout)
    assert _no_heart_markers(flat)
    a, b = _hearts(flat)
    # Flat: each scanpath's own colour, nothing under it.
    assert isinstance(a.textfont.color, str)
    assert a.textfont.color != b.textfont.color
    # Coloured: the category fills the heart, and the scanpath colour outlines
    # it as a larger heart underneath.
    coloured = _compare(viz, layout, color_by="eye")
    outline_a, fill_a, outline_b, _fill_b = _hearts(coloured)
    assert outline_a.textfont.color == a.textfont.color
    assert outline_b.textfont.color == b.textfont.color
    assert list(fill_a.textfont.color) != [a.textfont.color] * 4
    assert all(o > f for o, f in zip(outline_a.textfont.size, fill_a.textfont.size))


def test_heart_in_the_co_animation():
    at = _rail(global_fixation_symbol="heart", single_compare_toggle=True)
    words, fixations = _frames()
    _, _, (words_b, fixations_b) = _pair()
    fig = plots.make_scanpath_animation(
        words,
        fixations,
        settings=_settings(at.session_state["_viz"], show_legend=True),
        fixations_b=fixations_b,
        words_b=words_b,
    )
    assert _no_heart_markers(fig)
    hearts = _hearts(fig)
    assert {h.name for h in hearts} == {"Scanpath A", "Scanpath B"}
    # Every frame restates the hearts (and only moves them).
    last = fig.frames[-1]
    for heart in hearts:
        index = list(fig.data).index(heart)
        restated = last.data[list(last.traces).index(index)]
        assert set(restated.text) == {"♥"}
    # The A/B legend still names both readings.
    assert {t.name for t in fig.data if t.showlegend} >= {"Scanpath A", "Scanpath B"}


def test_a_numeric_colour_bar_survives_the_heart():
    at = _rail(
        global_fixation_symbol="heart",
        global_color_by="duration_ms",
        global_show_colorbars=True,
    )
    fig = _static(at)
    bars = [t for t in fig.data if t.marker is not None and t.marker.showscale]
    assert len(bars) == 1
    assert (bars[0].marker.cmin, bars[0].marker.cmax) == (100.0, 300.0)


# --- Color by offers the dataset's other numeric columns ----------------------


def test_color_by_offers_retained_numeric_columns_after_the_familiar_ones():
    from scanpath_studio.controls import color_field_options

    _, fixations = _frames()
    fixations = fixations.assign(saccade_ok=True, label=["a", "b", "c", "d"])
    options = color_field_options(fixations)
    assert options.index("pupil_size") > options.index("timestamp_ms")
    # Identifiers, positions, flags and text are not colour scales.
    for column in ("x", "y", "fixation_id", "saccade_ok", "label"):
        assert column not in options
    # Bookkeeping never shows (DATA-49).
    assert "_timestamp_synthesized" not in color_field_options(
        fixations.assign(_timestamp_synthesized=False)
    )


def test_the_rail_offers_and_draws_a_retained_column_by_its_own_name():
    from scanpath_studio import column_names as cn

    names = cn.ColumnNames({"pupil_size": cn.SourceName(("PUPIL_DIAMETER",))})
    at = _rail(
        **{
            cn.ACTIVE_COLUMN_NAMES_KEY: {"fixations": names.to_payload()},
            "global_color_by": "pupil_size",
        }
    )
    picker = at.selectbox(key="global_color_by")
    assert "PUPIL_DIAMETER" in picker.options
    assert picker.value == "pupil_size"
    static = next(t for t in _static(at).data if t.name == "Fixations")
    assert list(static.marker.color) == [2.1, 2.2, 2.3, 2.4]
    assert static.marker.colorscale


def _share_app():
    """The rail over the demo with a retained `pupil_size`, then its Share link."""
    from urllib.parse import parse_qs

    import streamlit as st

    from scanpath_studio import api, controls
    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    _apply_url_preset()
    # The rail works in the canonical names the app normalizes to.
    words, fixations = api.load_sample_data(names="canonical")
    fixations = fixations.assign(pupil_size=fixations["duration_ms"] / 100.0)
    pid, tid = fixations.iloc[0][["participant_id", "trial_id"]]
    trial_fix = fixations[
        (fixations["participant_id"] == pid) & (fixations["trial_id"] == tid)
    ]
    st.session_state["_viz"] = controls.render_plot_controls(
        fixations, 16, words=words, fix_range_fixations=trial_fix
    )
    st.session_state["_share_selection"] = {"participant_id": pid, "trial_id": tid}
    query, _caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_params"] = parse_qs(query)


def test_a_retained_colour_column_round_trips_a_share_link():
    at = AppTest.from_function(_share_app)
    at.session_state["global_color_by"] = "pupil_size"
    at.run(timeout=60)
    assert not at.exception, at.exception
    params = at.session_state["_params"]
    assert params["color_by"] == ["pupil_size"]

    opened = AppTest.from_function(_share_app)
    for key, values in params.items():
        opened.query_params[key] = values
    opened.run(timeout=60)
    assert not opened.exception, opened.exception
    assert opened.session_state["global_color_by"] == "pupil_size"
    assert opened.session_state["_viz"]["color_by"] == "pupil_size"


def _write_tables(tmp_path):
    words, fixations = _frames()
    words_csv, fixations_csv = tmp_path / "words.csv", tmp_path / "fixations.csv"
    words.to_csv(words_csv, index=False)
    fixations.to_csv(fixations_csv, index=False)
    return str(words_csv), str(fixations_csv)


def test_the_api_cli_and_snippet_colour_by_a_retained_column(tmp_path, monkeypatch):
    from scanpath_studio import api, cli
    from scanpath_studio import code_snippet as cs

    monkeypatch.chdir(tmp_path)  # the snippet saves its figure where it runs
    words_csv, fixations_csv = _write_tables(tmp_path)
    # Normalization drops a column it doesn't recognise unless told to keep it.
    _, dropped = api.load_scanpath_data(words=words_csv, fixations=fixations_csv)
    assert "pupil_size" not in dropped.columns
    words, fixations = api.load_scanpath_data(
        words=words_csv, fixations=fixations_csv, keep_columns=["pupil_size"]
    )
    assert "eye" in fixations.columns  # the recognised fields still come along
    fig = api.plot_scanpath(words, fixations, color_by="pupil_size")
    marker = next(t for t in fig.data if t.name == "Fixations").marker
    assert list(marker.color) == [2.1, 2.2, 2.3, 2.4]

    source = cs.SnippetSource(
        kind=cs.SOURCE_FILES,
        options={"words": [words_csv], "fixations": [fixations_csv]},
    )
    state = cs.FigureState(
        kind="static",
        settings={**api.figure_options("static"), "color_by": "pupil_size"},
        participant="p",
        trial="t",
    )
    code = cs.reproduction_code(source, state)
    namespace: dict = {}
    exec(compile(code.python, "<snippet>", "exec"), namespace)  # noqa: S102
    snippet_marker = next(
        t for t in namespace["fig"].data if t.name == "Fixations"
    ).marker
    assert list(snippet_marker.color) == [2.1, 2.2, 2.3, 2.4]
    command = code.cli.replace(" \\\n ", " ")
    assert "--color-by pupil_size" in command
    assert "--keep-columns pupil_size" in command
    assert not code.cli_unsupported

    rendered = []
    monkeypatch.setattr(
        api, "save_figure", lambda fig, path, **_kw: rendered.append(fig)
    )
    cli.main(
        [
            "render",
            "--words",
            words_csv,
            "--fixations",
            fixations_csv,
            "--keep-columns",
            "pupil_size",
            "--color-by",
            "pupil_size",
            "-o",
            str(tmp_path / "out.html"),
        ]
    )
    (cli_fig,) = rendered
    cli_marker = next(t for t in cli_fig.data if t.name == "Fixations").marker
    assert list(cli_marker.color) == [2.1, 2.2, 2.3, 2.4]
