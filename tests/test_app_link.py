"""A link a script writes (`api.app_link`, `scanpath-studio open`).

It opens the local app on a dataset added from a script, at the reading it
names, with the figure its options describe — the same link 🔗 Share writes
for that view.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

import scanpath_studio.api as sps
from scanpath_studio import cli, code_snippet, persistence, script_link, url_state
from scanpath_studio.code_snippet import _comparable
from tests.conftest import APP_SCRIPT
from tests.test_render_every_option import NON_DEFAULT

#: Every option a link carries, off its default.
LINKED = {
    key: value
    for key, value in NON_DEFAULT.items()
    if key in script_link.LINKED_OPTIONS
}


@pytest.fixture(autouse=True)
def cache_dir(tmp_path, monkeypatch) -> Path:
    """A private cache folder, with saving on: a link reads the saved work,
    never the user's own."""
    root = tmp_path / "cache"
    monkeypatch.setenv(persistence.STATE_DIR_ENV_VAR, str(root))
    monkeypatch.setenv(persistence.PERSIST_ENV_VAR, "1")
    return root


def _query(url: str) -> dict:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _rail_figure(query: dict, monkeypatch) -> tuple[dict, dict, dict]:
    """The figure keywords the app builds once it has read ``query``: the
    reader seeds the session keys, the rail collects them, and the Scanpath
    view turns them into the builder's keywords."""
    import streamlit as st

    from scanpath_studio import controls, tabs

    words, fixations = sps.load_sample_data(names="canonical")
    first = fixations.iloc[0]
    mask = (fixations["participant_id"] == first["participant_id"]) & (
        fixations["trial_id"] == first["trial_id"]
    )
    state: dict = {}
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "query_params", query)
    url_state._apply_url_preset()
    viz = controls._collect_viz_settings(fixations[mask], words)
    figure = tabs._snippet_settings_at_api_defaults(
        tabs._build_figure_settings(viz, viz["show_raw_gaze"])
    )
    return figure, viz, state


def _flags(figure: dict) -> dict:
    return {
        cat: (spec["mode"], spec.get("threshold_ms"))
        for cat, spec in (figure or {}).items()
        if spec.get("mode", "Off") != "Off"
    }


@pytest.mark.parametrize("color_by_line", [False, True])
def test_the_app_draws_the_figure_the_options_describe(color_by_line, monkeypatch):
    """Every option a link carries reaches the figure the app builds as the
    value the script gave it."""
    from scanpath_studio.plots import normalize_legend_layout

    options = dict(LINKED)
    # Two spellings of the colour field: each on its own.
    if color_by_line:
        options.pop("color_by")
        options.pop("fixation_color_range")  # scales a numeric field only
    else:
        options.pop("color_by_line")
    # The layers the other options style: saccade arrows are drawn on
    # saccades, and a colour range scales the fixations.
    options["show_saccades"] = True
    options["show_fixations"] = True
    figure, viz, state = _rail_figure(_query(sps.app_link("D", **options)), monkeypatch)

    # The settings the Scanpath view draws from the canvas and the rail, not
    # the builder's keywords.
    off_figure = {
        "line_spacing": state.get("global_line_spacing"),
        "scale_text_to_boxes": state.get("global_scale_text_to_boxes"),
        "background_image_opacity": state.get("global_stimulus_image_opacity"),
        "anim_grid_step_ms": viz["anim_grid_step_ms"],
        "anim_max_frames": viz["anim_max_frames"],
        "grow_fixations": viz["anim_grow_fixations"],
        "fade_fixations": viz["anim_fade_fixations"],
        "grow_start": viz["anim_grow_start"],
        "fade_opacity": viz["anim_fade_opacity"],
        "palette": state.get("global_palette"),
    }
    for key, value in options.items():
        got = (
            off_figure[key]
            if key in off_figure
            else figure.get(key, viz.get(key, "<missing>"))
        )
        if key == "fixation_flags":
            assert _flags(got) == _flags(value), key
        elif key == "legend_layout":
            assert normalize_legend_layout(got) == normalize_legend_layout(value)
        elif key == "saccade_class_colors":
            # The rail colours every class but *other*.
            assert {cls: value[cls] for cls in got} == got, key
        else:
            assert _comparable(got) == _comparable(value), key


def test_a_link_and_share_write_the_same_view_alike(monkeypatch):
    """What 🔗 Share writes for a view that the script's options describe is
    the script's link, setting for setting."""
    import streamlit as st

    options = {
        "show_heatmap": True,
        "heatmap_sigma_px": 12.0,
        "saccade_style": "dot",
        "fixation_flags": {"long": {"mode": "Hide", "threshold_ms": 700}},
        "legend_layout": {"saccades": {"position": "right-outside"}},
    }
    linked = _query(sps.app_link("D", "p1", "t1", **options))
    state = {
        **script_link.options_state(options),
        "global_marker_size_scale": "sqrt",
        "_share_selection": {"participant_id": "p1", "trial_id": "t1"},
    }
    monkeypatch.setattr(st, "session_state", state)
    shared = dict(parse_qsl(url_state._build_share_query("not an upload")[0]))
    shared.pop("setup_provenance", None)
    linked.pop("dataset")
    assert shared == linked


def test_an_option_a_link_cannot_carry_is_named():
    with pytest.raises(TypeError, match="background_image .*image file"):
        sps.app_link("D", background_image="page.png")
    with pytest.raises(TypeError, match="no figure option is called show_wrods"):
        sps.app_link("D", show_wrods=True)
    with pytest.raises(ValueError, match="fixation_opacity=7"):
        sps.app_link("D", fixation_opacity=7)
    with pytest.raises(ValueError, match="screen belongs to a trial"):
        sps.app_link("D", screen="intro")
    with pytest.raises(ValueError, match="port"):
        sps.app_link("D", port=0)
    with pytest.raises(ValueError, match="other"):
        sps.app_link("D", saccade_class_colors={"other": "#123456"})
    with pytest.raises(TypeError, match="title .*pattern"):
        sps.app_link("D", title="Pilot")
    # Values the app would read otherwise than `plot_scanpath` draws them.
    with pytest.raises(ValueError, match="draws no saccades"):
        sps.app_link("D", saccade_classes=[])
    with pytest.raises(ValueError, match="whole number"):
        sps.app_link(
            "D", fixation_flags={"short": {"mode": "Hide", "threshold_ms": 80.5}}
        )
    with pytest.raises(ValueError, match="at most 2,000"):
        sps.app_link("D", illustration_text="x" * 3000)


def test_a_replay_without_fixations_reopens_without_them(monkeypatch):
    """As Share writes it: a replay link with the fixations off says so."""
    query = _query(sps.app_link("D", animate=True, show_fixations=False))
    assert query["replay_fixations"] == "0"
    _, _, state = _rail_figure(query, monkeypatch)
    assert state["single_animate"] is True
    assert state["global_show_fix"] is False


def test_ids_are_spelled_as_the_app_spells_them():
    query = _query(sps.app_link("D", 7.0, 101.0))
    assert (query["participant"], query["trial_id"]) == ("7", "101")
    with pytest.raises(TypeError, match="show_legend .*comparison"):
        sps.app_link("D", show_legend=False)


def test_none_keeps_the_app_s_own_value():
    """``None`` names no setting, as a keyword left out names none — except
    where it is the API's own choice."""
    assert _query(
        sps.app_link(
            "D",
            show_word_labels=None,
            background_color=None,
            saccade_style=None,
            highlight_column=None,
        )
    ) == {"dataset": "D"}
    assert _query(sps.app_link("D", heatmap_metric=None))["heatmap_metric"] == "counts"


def test_illustration_is_plot_scanpath_s_design():
    assert _query(sps.app_link("D", illustration=True, show_order=True)) == _query(
        sps.app_link("D", **{**sps.ILLUSTRATION_PRESET, "show_order": True})
    )


def test_the_link_names_the_dataset_reading_and_port():
    url = sps.app_link(
        "Pilot 3", "p 7", "t&12", screen="intro", port=8600, animate=True
    )
    assert url.startswith("http://localhost:8600/?")
    assert _query(url) == {
        "dataset": "Pilot 3",
        "participant": "p 7",
        "trial_id": "t&12",
        "screen": "intro",
        "tab": "animation",
    }
    assert _query(sps.app_link("Pilot 3")) == {"dataset": "Pilot 3"}


def test_the_link_opens_comparisons_on_a_match_field(capsys):
    """`match=` goes on the link as given; `open --match` writes the same."""
    url = sps.app_link("Pilot 3", "p7", match="source_trial", show_heatmap=True)
    assert _query(url)["match"] == "source_trial"
    assert _query(sps.app_link("Pilot 3", match="same_text"))["match"] == "same_text"
    assert "match" not in _query(sps.app_link("Pilot 3"))
    cli.main(
        ["open", "Pilot 3", "-p", "p7", "--match", "source_trial", "--heatmap"]
        + ["--print"]
    )
    assert capsys.readouterr().out.strip() == url


@pytest.mark.parametrize(("match", "error"), [("", ValueError), (3, TypeError)])
def test_a_match_that_names_no_field_is_refused(match, error):
    with pytest.raises(error, match="match"):
        sps.app_link("Pilot 3", match=match)


def test_the_link_opens_comparisons_in_its_overlay(capsys):
    """`match_view=` rides beside `match=`; `open --match-view` writes the same."""
    url = sps.app_link("Pilot 3", match="source_trial", match_view="Overlay")
    assert _query(url)["match_view"] == "overlay"
    cli.main(
        ["open", "Pilot 3", "--match", "source_trial", "--match-view", "overlay"]
        + ["--print"]
    )
    assert capsys.readouterr().out.strip() == url


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"match_view": "overlay"}, "pass match="),
        ({"match": "x", "match_view": "pile"}, "one of"),
    ],
)
def test_a_match_view_needs_a_match_and_a_view(kwargs, message):
    with pytest.raises(ValueError, match=message):
        sps.app_link("Pilot 3", **kwargs)


# ---------------------------------------------------------------------------
# scanpath-studio open
# ---------------------------------------------------------------------------
def _render_flags(options: dict) -> list[str]:
    """The `render` flags the Share → Code snippet writes for ``options``."""
    defaults = sps.figure_options("static")
    state = code_snippet.FigureState(
        kind="static",
        settings={**defaults, **options},
        participant="p",
        trial="t",
    )
    source = code_snippet.SnippetSource(kind=code_snippet.SOURCE_DEMO, label="demo")
    command, unsupported = code_snippet.cli_snippet(source, state)
    assert unsupported == []
    argv = shlex.split(command.replace(" \\\n", " "))
    # Drop the input, the reading and the output: `open` names its own.
    out, words = [], iter(argv[2:])
    for word in words:
        if word in ("--sample", "--show-raw-gaze", "--sample-raw-gaze"):
            continue
        if word in ("-p", "-t", "-o", "--output"):
            next(words)
            continue
        out.append(word)
    return out


def test_open_takes_render_s_figure_flags_as_they_are(capsys):
    """The `render` flags the code snippet writes for a figure give `open` the
    link `app_link` writes for that figure's options."""
    options = {
        **{k: v for k, v in LINKED.items() if k != "palette"},
        "show_fixations": True,
        "show_saccades": True,
    }
    # The options the snippet writes a flag for: the rest style a layer that
    # is off, or belong to the replay.
    written = code_snippet.figure_kwargs(
        {**sps.figure_options("static"), **options}, "static"
    )
    assert set(options) - set(written) <= {
        "anim_grid_step_ms",
        "anim_max_frames",
        "grow_fixations",
        "fade_fixations",
        "grow_start",
        "fade_opacity",
        "heatmap_range",
        "highlight_text_color",
        "plot_frame_color",
        "show_fixations",
        "show_raw_gaze",
        "show_saccades",
    }
    replay = [
        "--anim-grid-step-ms",
        "50",
        "--anim-max-frames",
        "200",
        "--grow-fixations",
        "--fade-fixations",
        "--grow-start",
        "0.4",
        "--fade-opacity",
        "0.5",
    ]
    cli.main(
        ["open", "D", "-p", "p", "-t", "t", "--print", *_render_flags(options), *replay]
    )
    printed = capsys.readouterr().out.strip()
    assert _query(printed) == _query(
        sps.app_link(
            "D",
            "p",
            "t",
            **written,
            anim_grid_step_ms=50.0,
            anim_max_frames=200,
            grow_fixations=True,
            fade_fixations=True,
            grow_start=0.4,
            fade_opacity=0.5,
        )
    )


def test_open_carries_the_window_and_the_player(capsys):
    cli.main(
        [
            "open",
            "D",
            "--print",
            "--animate",
            "--fix-index-range",
            "2:9",
            "--illustration-label",
            "show",
            "--playback-speed",
            "2",
            "--no-autoplay",
        ]
    )
    assert _query(capsys.readouterr().out.strip()) == _query(
        sps.app_link(
            "D",
            animate=True,
            fix_index_range=(2, 9),
            illustration_label="show",
            playback_speed=2.0,
            autoplay=False,
        )
    )


def test_open_refuses_a_none_it_cannot_carry(capsys):
    with pytest.raises(SystemExit):
        cli.main(["open", "D", "--highlight-column", "", "--print"])
    assert "--highlight-column '': a link can't say none" in capsys.readouterr().err


def test_open_refuses_render_s_own_flags(capsys):
    with pytest.raises(SystemExit):
        cli.main(["open", "D", "--sample", "--stimulus-image", "x.png", "--print"])
    err = capsys.readouterr().err
    assert "--sample, --stimulus-image: render's, not open's" in err
    # `--stimulus-image` is not read as `--stimulus-image-opacity`.
    with pytest.raises(SystemExit):
        cli.main(["open", "D", "--stimulus-image", "0.5", "--print"])


def test_open_opens_the_link_in_a_running_app(monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(cli, "_app_running", lambda port, timeout=1.0: True)
    monkeypatch.setattr("webbrowser.open", opened.append)
    monkeypatch.setattr(cli, "launch_app", lambda args: pytest.fail("started"))
    cli.main(["open", "D", "-t", "t1", "--port", "8600", "--heatmap"])
    assert opened == [capsys.readouterr().out.strip()]
    assert opened[0].startswith("http://localhost:8600/?dataset=D&trial_id=t1")


def test_open_starts_the_app_when_none_is_running(monkeypatch):
    started, waiting = [], []
    monkeypatch.setattr(cli, "_app_running", lambda port, timeout=1.0: False)
    monkeypatch.setattr(cli, "launch_app", started.append)
    monkeypatch.setattr(
        cli, "_open_when_ready", lambda url, port: waiting.append((url, port))
    )

    class _Inline:
        """The waiting thread, run where it is started."""

        def __init__(self, target, args, daemon):
            self._run = lambda: target(*args)

        def start(self):
            self._run()

    monkeypatch.setattr("threading.Thread", _Inline)
    cli.main(["open", "D", "--port", "8600"])
    assert started == [["--server.port=8600", "--server.headless=true"]]
    assert waiting == [("http://localhost:8600/?dataset=D", 8600)]


# ---------------------------------------------------------------------------
# End to end: a dataset a script added, opened by the link a script wrote
# ---------------------------------------------------------------------------


@pytest.mark.timeout(400)
def test_an_added_dataset_opens_on_the_linked_reading(cache_dir):
    from streamlit.testing.v1 import AppTest

    words, fixations = sps.load_sample_data(names="canonical")
    sps.add_dataset("Linked pilot", words, fixations, select=False)
    trials = sps.list_trials(words, fixations)
    second = trials.iloc[1]
    url = sps.app_link(
        "Linked pilot",
        second["participant_id"],
        second["trial_id"],
        show_heatmap=True,
        saccade_style="dot",
    )

    # Named as Share names it, so the app checks the tables rather than
    # asking whether they are the sender's.
    query = _query(url)
    assert query["dataset_id"] and query["dataset_digest"]

    at = AppTest.from_file(APP_SCRIPT)
    for key, value in query.items():
        at.query_params[key] = value
    at.run(timeout=240)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    assert not [i.value for i in at.info if "link" in i.value]
    assert not [w.value for w in at.warning if "link" in w.value]
    assert at.session_state["data_source_choice"] == "Linked pilot"
    selection = at.session_state["_share_selection"]
    assert (selection["participant_id"], selection["trial_id"]) == (
        str(second["participant_id"]),
        str(second["trial_id"]),
    )
    assert at.session_state["global_show_heatmap"] is True
    assert at.session_state["global_saccade_style"] == "Dotted"


def test_a_dataset_not_saved_here_is_named_alone(cache_dir):
    """Nothing saved under the name: the link names it, and the app says it is
    missing when it opens the link."""
    assert _query(sps.app_link("Elsewhere")) == {"dataset": "Elsewhere"}


def test_a_saved_dataset_is_named_as_its_list_shows_it(cache_dir):
    words, fixations = sps.load_sample_data(names="canonical")
    sps.add_dataset("Pilot 3", words, fixations)
    query = _query(sps.app_link("pilot 3"))
    assert query["dataset"] == "Pilot 3"
    assert set(query) == {"dataset", "dataset_id", "dataset_digest"}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Bundled demo", {"source": "demo"}),
        ("bundled DEMO", {"source": "demo"}),
        ("PoTeC", {"source": "corpus", "corpus": "potec"}),
        (
            "PoTeC — Potsdam Textbook Corpus",
            {"source": "corpus", "corpus": "potec"},
        ),
        ("OneStop · Ordinary reading", {"source": "onestop_ordinary"}),
        ("onestop · repeated reading", {"source": "onestop_repeated"}),
    ],
)
def test_a_dataset_the_app_ships_is_named_as_share_names_it(name, expected):
    """The app reads ``?dataset=`` as one someone added, so the demo and the
    public corpora travel as ``?source=``, as 🔗 Share writes them. A name is
    the one the list shows: a public corpus's short name."""
    assert _query(sps.app_link(name)) == expected


def test_a_renamed_dataset_the_app_ships_is_found_by_its_new_name():
    renamed = {"Bundled demo": "Wolf pilot"}
    assert script_link.builtin_source_params("wolf PILOT", renamed) == {
        "source": "demo"
    }
    assert script_link.builtin_source_params("Wolf pilot") is None


def test_the_saved_names_reach_the_link(cache_dir):
    """A built-in renamed in the app is saved as an alias in the session, and
    the link finds it by that name."""
    import json

    from scanpath_studio.constants import DATASET_ALIASES_KEY

    words, fixations = sps.load_sample_data(names="canonical")
    sps.add_dataset("Pilot 3", words, fixations, select=False)
    manifest_path = cache_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["session"][DATASET_ALIASES_KEY] = {"Bundled demo": "Wolf pilot"}
    manifest_path.write_text(json.dumps(manifest))

    assert persistence.stored_dataset_aliases() == {"Bundled demo": "Wolf pilot"}
    assert _query(sps.app_link("Wolf pilot")) == {"source": "demo"}


@pytest.mark.parametrize("kind", ["static", "comparison"])
def test_every_figure_option_is_linked_or_named_unlinkable(kind):
    """A new figure option a link drops would make `app_link` and `open`
    refuse it as unknown, though `figure_options` lists it."""
    missing = (
        set(sps.figure_options(kind))
        - script_link.LINKED_OPTIONS
        - set(script_link.UNLINKABLE_OPTIONS)
    )
    assert not missing, sorted(missing)
