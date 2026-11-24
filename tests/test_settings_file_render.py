"""A settings file saved in the app draws the same figure in a script.

Share → File records the figure in the API's own vocabulary
(`code_snippet.settings_file_calls`, the same keywords Share → Code writes),
and `plot_scanpath` / `animate_scanpath` / `compare_scanpaths` take it as
``settings=``, as `render --settings` does. Pinned here: the record survives
JSON with every figure option off its default, a file draws exactly what its
keywords draw, what a call passes wins over the file, and a file without the
record says how to get one.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from scanpath_studio import api, cli
from scanpath_studio import code_snippet as cs
from tests.test_render_every_option import OTHER, TRIAL, _maximal_state

_BUILDERS = {
    "static": "plot_scanpath",
    "animation": "animate_scanpath",
    "comparison": "compare_scanpaths",
}


@pytest.fixture(scope="module")
def frames():
    return api.load_sample_data(names="canonical")


def _state(kind: str, *, maximal: bool = True) -> cs.FigureState:
    """``kind``'s figure with every option off its default (``maximal``), or an
    ordinary one: the defaults with a heatmap and a red fixation colour.

    The maximal replay keeps its fixations on: with fixations and saccades both
    off, a replay has nothing to draw and refuses to."""
    if maximal:
        state = _maximal_state(kind)
        if kind == "animation":
            state = replace(state, settings={**state.settings, "show_fixations": True})
        return state
    return cs.FigureState(
        kind=kind,
        settings={
            **api.figure_options(kind),
            "show_heatmap": True,
            "fixation_color": "#aa0000",
        },
        participant=TRIAL[0],
        trial=TRIAL[1],
    )


def _file(
    kind: str, tmp_path, *, maximal: bool = True, **changes
) -> tuple[dict, object]:
    """A settings file holding ``kind``'s figure, written and read back as JSON."""
    record = cs.settings_file_calls(_state(kind, maximal=maximal))
    config = {"schema": 10, "layers": {}, "api": record, **changes}
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8")), path


def _direct_keywords(kind: str, *, maximal: bool = True) -> dict:
    """What Share → Code passes for the same figure, in Python."""
    state = _state(kind, maximal=maximal)
    keywords = dict(cs._call_kwargs(state, explicit=True))
    keywords.pop("screen", None)
    keywords.update(
        cs.figure_kwargs(state.settings, kind, explicit=True, compare=state.compare)
    )
    if kind == "comparison":
        keywords["layout"] = state.compare.layout
        keywords["compare_stimulus"] = state.compare.compare_stimulus
        keywords["trial_a"] = TRIAL
        keywords["trial_b"] = OTHER
    else:
        keywords["participant"], keywords["trial"] = TRIAL
        if kind == "animation" and state.compare is not None:
            keywords["trial_b"] = OTHER
    return keywords


def _from_file(path, function: str, **given) -> dict:
    """The keywords a file gives ``function`` beside what the call passed."""
    import inspect

    accepted = set(inspect.signature(getattr(api, function)).parameters)
    return api._settings_keywords(path, function, accepted, given)


@pytest.mark.parametrize("kind", cs.KINDS)
def test_every_option_round_trips_through_the_file(kind, frames, tmp_path):
    words, fixations = frames
    builder = getattr(api, _BUILDERS[kind])
    _, path = _file(kind, tmp_path)
    from_file = builder(words, fixations, settings=path)
    direct = builder(words, fixations, **_direct_keywords(kind))
    assert from_file.to_json() == direct.to_json()


def test_the_record_survives_json(tmp_path):
    for kind in cs.KINDS:
        record = cs.settings_file_calls(_maximal_state(kind))
        assert json.loads(json.dumps(record)) == json.loads(json.dumps(record))
        assert set(record["calls"]) >= {"static", "animation"}


def test_what_the_call_passes_wins_over_the_file(frames, tmp_path):
    words, fixations = frames
    _, path = _file("static", tmp_path)
    _, path = _file("static", tmp_path, maximal=False)
    figure = api.plot_scanpath(
        words,
        fixations,
        *OTHER,
        settings=path,
        show_heatmap=False,
        canvas_size=(1000, 800),
    )
    expected = api.plot_scanpath(
        words,
        fixations,
        **{
            **_direct_keywords("static", maximal=False),
            "participant": OTHER[0],
            "trial": OTHER[1],
            "show_heatmap": False,
            "canvas_size": (1000, 800),
        },
    )
    assert figure.to_json() == expected.to_json()


def test_the_file_names_the_reading_when_the_call_does_not(tmp_path):
    _, path = _file("static", tmp_path, maximal=False)
    values = _from_file(path, "plot_scanpath")
    assert (values["participant"], values["trial"]) == TRIAL
    assert "participant" not in _from_file(path, "plot_scanpath", participant="x")


def test_a_static_file_still_draws_a_replay(frames, tmp_path):
    """The kind is the builder's: a static file's look on a replay of A alone."""
    words, fixations = frames
    _, path = _file("static", tmp_path, maximal=False)
    values = _from_file(path, "animate_scanpath")
    assert values["fixation_color"] == "#aa0000"
    assert "trial_b" not in values
    assert api.animate_scanpath(words, fixations, settings=path).frames


def test_a_file_without_b_needs_trial_b_for_a_comparison(frames, tmp_path):
    words, fixations = frames
    _, path = _file("static", tmp_path, maximal=False)
    with pytest.raises(ValueError, match="trial_b"):
        api.compare_scanpaths(words, fixations, settings=path)
    values = _from_file(path, "compare_scanpaths", trial_b=OTHER)
    assert values["trial_a"] == TRIAL and "trial_b" not in values
    assert values["fixation_color"] == "#aa0000"
    api.compare_scanpaths(words, fixations, trial_b=OTHER, settings=path)


def test_a_comparison_needs_its_readings_without_a_file(frames):
    words, fixations = frames
    with pytest.raises(TypeError, match="trial_a"):
        api.compare_scanpaths(words, fixations)


def test_b_from_another_dataset_asks_for_its_tables(frames, tmp_path):
    words, fixations = frames
    config, path = _file("comparison", tmp_path)
    config["api"]["compare"]["dataset"] = "Study B"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="words_b"):
        api.compare_scanpaths(words, fixations, settings=path)


@pytest.mark.parametrize(
    "config",
    [{"schema": 9, "layers": {"words": True}}, {"api": {"version": 1}}, []],
    ids=["older-file", "no-calls", "not-a-settings-file"],
)
def test_a_file_without_the_record_says_how_to_get_one(frames, tmp_path, config):
    words, fixations = frames
    path = tmp_path / "old.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="Share → File"):
        api.plot_scanpath(words, fixations, *TRIAL, settings=path)


def test_an_option_this_build_does_not_know_is_left_out(frames, tmp_path, caplog):
    words, fixations = frames
    config, path = _file("static", tmp_path)
    config["api"]["calls"]["static"]["show_something_new"] = True
    path.write_text(json.dumps(config), encoding="utf-8")
    figure = api.plot_scanpath(words, fixations, settings=path)
    assert figure is not None
    assert "show_something_new" in caplog.text


def test_settings_is_in_each_builders_signature():
    import inspect

    for name in _BUILDERS.values():
        assert "settings" in inspect.signature(getattr(api, name)).parameters


class TestRenderSettings:
    def _render(self, monkeypatch, argv) -> dict:
        seen = {}

        def spy(name):
            original = getattr(api, name)

            def wrapped(*args, **kwargs):
                seen["name"] = name
                seen["kwargs"] = kwargs
                return original(*args, **kwargs)

            return wrapped

        for name in _BUILDERS.values():
            monkeypatch.setattr(api, name, spy(name))
        cli.main(["render", *argv])
        return seen

    def test_render_draws_the_files_figure(self, monkeypatch, tmp_path):
        _, path = _file("static", tmp_path)
        out = tmp_path / "fig.html"
        seen = self._render(
            monkeypatch, ["--sample", "--settings", str(path), "-o", str(out)]
        )
        assert seen["name"] == "plot_scanpath"
        assert seen["kwargs"]["settings"] == str(path)
        assert out.exists()

    def test_a_flag_on_the_line_wins(self, monkeypatch, tmp_path):
        _, path = _file("static", tmp_path)
        out = tmp_path / "fig.html"
        seen = self._render(
            monkeypatch,
            [
                "--sample",
                "--settings",
                str(path),
                "--no-heatmap",
                "--font-size",
                "16",
                "-o",
                str(out),
            ],
        )
        assert seen["kwargs"]["show_heatmap"] is False
        assert seen["kwargs"]["base_font_size"] == 16

    def test_unflagged_defaults_leave_the_files_values(self, monkeypatch, tmp_path):
        _, path = _file("static", tmp_path)
        out = tmp_path / "fig.html"
        seen = self._render(
            monkeypatch, ["--sample", "--settings", str(path), "-o", str(out)]
        )
        # A flag's default is not a choice: the file's value stands.
        for key in ("base_font_size", "show_heatmap", "canvas_size", "font_family"):
            assert key not in seen["kwargs"], key

    @pytest.mark.parametrize("kind", cs.KINDS)
    def test_render_draws_what_the_api_draws(self, kind, frames, tmp_path, monkeypatch):
        """`render --settings` is `plot_scanpath(settings=…)` (or the replay's,
        or the comparison's) on the same reading, every option off its default."""
        from tests.test_render_every_option import _figures

        words, fixations = frames
        _, path = _file(kind, tmp_path)
        argv = ["render", "--sample", "--settings", str(path), "-o", "a.html"]
        if kind == "animation":
            argv.append("--animate")
        if kind != "static":
            argv += ["--compare-with", f"{OTHER[0]}:{OTHER[1]}"]
        (from_cli,) = _figures(monkeypatch, [argv])
        builder = getattr(api, _BUILDERS[kind])
        from_api = builder(words, fixations, settings=path)
        assert from_cli.to_json() == from_api.to_json()

    def test_a_missing_file_is_a_message(self, tmp_path):
        with pytest.raises(SystemExit, match="settings"):
            cli.main(
                [
                    "render",
                    "--sample",
                    "--settings",
                    str(tmp_path / "nope.json"),
                    "-o",
                    str(tmp_path / "f.html"),
                ]
            )
