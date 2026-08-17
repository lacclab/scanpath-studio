"""Tests for the command-line interface (scanpath_studio.cli)."""

import pytest

from scanpath_studio import __version__, cli


def test_version(capsys):
    cli.main(["--version"])
    assert capsys.readouterr().out.strip() == __version__


def test_help(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "render" in out
    assert "streamlit run" in out


def test_default_launches_app(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "launch_app", lambda args: calls.append(args))
    cli.main([])
    cli.main(["run", "--server.port", "8502"])
    # Backward compat: bare streamlit flags forward to the app launcher.
    cli.main(["--server.port", "8502"])
    assert calls == [[], ["--server.port", "8502"], ["--server.port", "8502"]]


def test_render_requires_input_choice():
    with pytest.raises(SystemExit):
        cli.main(["render", "-o", "out.html"])  # neither --sample nor files
    with pytest.raises(SystemExit):
        cli.main(["render", "--sample", "--words", "w.csv", "-o", "out.html"])


def test_render_requires_output():
    with pytest.raises(SystemExit):
        cli.main(["render", "--sample"])


def test_render_list_trials(capsys):
    cli.main(["render", "--sample", "--list-trials"])
    out = capsys.readouterr().out
    assert "participant_id" in out
    assert "trial_id" in out


def test_render_sample_html(tmp_path, capsys):
    out_file = tmp_path / "scanpath.html"
    cli.main(["render", "--sample", "-o", str(out_file)])
    assert out_file.is_file()
    err = capsys.readouterr().err
    assert "Rendering participant=" in err


def test_render_thumbnail_flags(tmp_path):
    """The thumbnail-control flags parse and flow into the figure build."""
    import scanpath_studio as sps

    pid, tid = sps.list_trials(*sps.load_sample_data()).iloc[0]
    out_file = tmp_path / "thumb.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            pid,
            "-t",
            tid,
            "--marker-size-range",
            "4",
            "12",
            "--heatmap-colorscale",
            "Greens",
            "--fixation-colorscale",
            "Blues",
            "--width",
            "900",
            "--height",
            "600",
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()


def test_render_explicit_trial_with_flags(tmp_path):
    import scanpath_studio as sps

    pid, tid = sps.list_trials(*sps.load_sample_data()).iloc[0]
    out_file = tmp_path / "scanpath.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            pid,
            "-t",
            tid,
            "--no-heatmap",
            "--saccade-arrows",
            "--canvas",
            "2560x1440",
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()


def test_render_forwards_saccade_styling(tmp_path, monkeypatch):
    # The --saccade-* flags must reach the figure builder via plot_scanpath.
    from scanpath_studio import api

    captured = {}

    def fake_plot(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        [
            "render",
            "--sample",
            "--saccade-color",
            "#ff0000",
            "--saccade-style",
            "dash",
            "--saccade-width",
            "6",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["saccade_color"] == "#ff0000"
    assert captured["saccade_style"] == "dash"
    assert captured["saccade_width"] == 6.0


def test_render_forwards_saccade_color_by_type(tmp_path, monkeypatch):
    # --saccade-color-by-type flips the mode; --saccade-type-color overrides a
    # class colour and implies the mode (VIZ-8).
    from scanpath_studio import api

    captured = {}

    def fake_plot(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        [
            "render",
            "--sample",
            "--saccade-type-color",
            "regression=#000000",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["saccade_color_mode"] == "By type"
    assert captured["saccade_class_colors"]["regression"] == "#000000"
    # Untouched classes keep their default palette colour.
    assert captured["saccade_class_colors"]["forward"] != "#000000"


def test_render_forwards_heatmap_norm(tmp_path, monkeypatch):
    # --heatmap-norm log reaches the figure builder as "Log" (VIZ-3).
    from scanpath_studio import api

    captured = {}

    def fake_plot(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        ["render", "--sample", "--heatmap-norm", "log", "-o", str(tmp_path / "x.html")]
    )
    assert captured["heatmap_norm"] == "Log"


def test_render_forwards_linear_reading_flags(tmp_path, monkeypatch):
    # VIZ-9: --saccade-arcs / --snap-fixations reach the figure builder.
    from scanpath_studio import api

    captured = {}

    def fake_plot(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        [
            "render",
            "--sample",
            "--saccade-arcs",
            "--snap-fixations",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert captured["saccade_render_mode"] == "Arc"
    assert captured["fixation_snap_to_word"] is True


def test_render_saccade_type_color_rejects_bad_class(tmp_path):
    with pytest.raises(SystemExit):
        cli.main(
            [
                "render",
                "--sample",
                "--saccade-type-color",
                "nonsense=#000000",
                "-o",
                str(tmp_path / "x.html"),
            ]
        )


def test_render_animate_forwards_saccade_styling(tmp_path, monkeypatch):
    # The animation builder honors the saccade trio too, so --animate forwards it.
    from scanpath_studio import api

    captured = {}

    def fake_anim(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "animate_scanpath", fake_anim)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--saccade-color",
            "#00ff00",
            "--saccade-width",
            "5",
            "-o",
            str(tmp_path / "a.html"),
        ]
    )
    assert captured["saccade_color"] == "#00ff00"
    assert captured["saccade_width"] == 5.0


def test_render_animate_html(tmp_path):
    out_file = tmp_path / "anim.html"
    cli.main(["render", "--sample", "--animate", "-o", str(out_file)])
    assert out_file.is_file()


def test_render_animate_autoplays_by_default(tmp_path):
    # VIZ-10: the saved interactive HTML auto-starts the replay (kickoff script).
    out_file = tmp_path / "anim.html"
    cli.main(["render", "--sample", "--animate", "-o", str(out_file)])
    assert "Plotly.animate" in out_file.read_text(encoding="utf-8")


def test_render_animate_no_autoplay_flag(tmp_path):
    # VIZ-10: --no-autoplay saves a figure that opens paused (no kickoff).
    out_file = tmp_path / "anim.html"
    cli.main(["render", "--sample", "--animate", "--no-autoplay", "-o", str(out_file)])
    assert "Plotly.animate" not in out_file.read_text(encoding="utf-8")


def test_render_animate_rejects_non_html(tmp_path):
    with pytest.raises(SystemExit, match="html"):
        cli.main(["render", "--sample", "--animate", "-o", str(tmp_path / "a.png")])


def test_render_unknown_trial_exits():
    with pytest.raises(SystemExit):
        cli.main(
            ["render", "--sample", "-p", "nobody", "-t", "nothing", "-o", "x.html"]
        )


def test_render_unknown_trial_without_participant_exits(tmp_path):
    # Regression: a mistyped -t without -p must error, not silently render
    # the dataset's first trial.
    out_file = tmp_path / "x.html"
    with pytest.raises(SystemExit, match="No trial matches"):
        cli.main(["render", "--sample", "-t", "no_such_trial", "-o", str(out_file)])
    assert not out_file.exists()


def test_render_trial_only_resolves_matching_participant(tmp_path, capsys):
    # A valid -t without -p picks a participant that actually has that trial.
    import scanpath_studio as sps

    combos = sps.list_trials(*sps.load_sample_data())
    _pid, tid = combos.iloc[-1]
    out_file = tmp_path / "x.html"
    cli.main(["render", "--sample", "-t", tid, "-o", str(out_file)])
    assert out_file.is_file()
    assert f"trial={tid}" in capsys.readouterr().err


def test_render_bad_canvas_exits():
    with pytest.raises(SystemExit, match="--canvas"):
        cli.main(["render", "--sample", "--canvas", "huge", "-o", "x.html"])
    with pytest.raises(SystemExit, match="positive"):
        cli.main(["render", "--sample", "--canvas", "0x1440", "-o", "x.html"])


def test_render_animate_warns_on_unsupported_flags(tmp_path, capsys):
    out_file = tmp_path / "anim.html"
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--no-heatmap",
            "--color-by",
            "pass_index",
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()
    err = capsys.readouterr().err
    assert "ignoring" in err
    assert "color_by" in err and "show_heatmap" in err


_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000100052301e20000000049454e44ae"
    "426082"
)


def test_render_stimulus_image_embeds_and_dims(tmp_path):
    # VIZ-4: --stimulus-image overlays an image; --stimulus-image-opacity dims it.
    img = tmp_path / "stim.png"
    img.write_bytes(_PNG_1x1)
    out_file = tmp_path / "out.html"
    cli.main(
        [
            "render",
            "--sample",
            "--stimulus-image",
            str(img),
            "--stimulus-image-opacity",
            "0.3",
            "-o",
            str(out_file),
        ]
    )
    html = out_file.read_text(encoding="utf-8")
    assert "data:image/png;base64" in html  # the image is embedded
    assert '"opacity":0.3' in html or '"opacity": 0.3' in html


def test_render_stimulus_image_origin_and_size(tmp_path):
    # VIZ-4: explicit size + origin place a crop in fixation coordinates.
    img = tmp_path / "stim.png"
    img.write_bytes(_PNG_1x1)
    out_file = tmp_path / "out.html"
    cli.main(
        [
            "render",
            "--sample",
            "--stimulus-image",
            str(img),
            "--stimulus-image-size",
            "1310x991",
            "--stimulus-image-origin",
            "305,44",
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()


def test_render_stimulus_image_bad_origin_exits(tmp_path):
    img = tmp_path / "stim.png"
    img.write_bytes(_PNG_1x1)
    with pytest.raises(SystemExit, match="X,Y"):
        cli.main(
            [
                "render",
                "--sample",
                "--stimulus-image",
                str(img),
                "--stimulus-image-origin",
                "nope",
                "-o",
                str(tmp_path / "x.html"),
            ]
        )


def test_render_animate_forwards_stimulus_image(tmp_path):
    # VIZ-4: the animation honours the stimulus image too.
    img = tmp_path / "stim.png"
    img.write_bytes(_PNG_1x1)
    out_file = tmp_path / "anim.html"
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--stimulus-image",
            str(img),
            "-o",
            str(out_file),
        ]
    )
    assert "data:image/png;base64" in out_file.read_text(encoding="utf-8")


def test_render_separable_layers(tmp_path, monkeypatch):
    # VIZ-5: --separable-layers writes a <output>_layers/ folder. Stub the writers
    # to avoid Kaleido/Chrome; assert the CLI targets the right dir + format.
    from pathlib import Path

    from scanpath_studio import api

    captured = {}
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: Path(path))

    def fake_layers(fig, directory, **k):
        captured["dir"] = str(directory)
        captured["fmt"] = k.get("fmt")
        return {"word_boxes": Path(directory) / "word_boxes.svg"}

    monkeypatch.setattr(api, "save_figure_layers", fake_layers)
    cli.main(
        ["render", "--sample", "--separable-layers", "-o", str(tmp_path / "fig.svg")]
    )
    assert captured["dir"].endswith("fig_layers")
    assert captured["fmt"] == "svg"


def test_render_separable_layers_skips_html(tmp_path, monkeypatch, capsys):
    # A non-image output (or --animate) can't be split into vector layers.
    from pathlib import Path

    from scanpath_studio import api

    called = []
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: Path(path))
    monkeypatch.setattr(
        api, "save_figure_layers", lambda *a, **k: called.append(1) or {}
    )
    cli.main(
        ["render", "--sample", "--separable-layers", "-o", str(tmp_path / "fig.html")]
    )
    assert called == []  # skipped
    assert "separable-layers" in capsys.readouterr().err


def test_render_from_files(tmp_path):
    from scanpath_studio import data as data_module

    words_raw, fix_raw = data_module.load_sample_data()
    words_path = tmp_path / "ia.csv"
    fix_path = tmp_path / "fix.csv"
    words_raw.to_csv(words_path, index=False)
    fix_raw.to_csv(fix_path, index=False)

    out_file = tmp_path / "out.html"
    cli.main(
        [
            "render",
            "--words",
            str(words_path),
            "--fixations",
            str(fix_path),
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()


def test_render_multipart_manifest_lists_and_renders_all_screens(tmp_path, capsys):
    import json

    from scanpath_studio.synthetic import make_multipart_synthetic_data

    words, fixations = make_multipart_synthetic_data()
    words["page_code"] = words.pop("screen_id")
    fixations["page_code"] = fixations.pop("screen_id")
    words = words.drop(columns=["screen_index", "canvas_width", "canvas_height"])
    fixations = fixations.drop(
        columns=["screen_index", "canvas_width", "canvas_height"]
    )
    words_path, fixations_path = tmp_path / "words.csv", tmp_path / "fixations.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fixations_path, index=False)
    manifest = {
        "trials": [
            {
                "participant_id": "synthetic",
                "trial_id": "multipart_demo",
                "parts": [
                    {
                        "screen_id": screen,
                        "screen_index": index,
                        "canvas_width": width,
                        "canvas_height": height,
                        "words": {"page_code": screen},
                        "fixations": {"page_code": screen},
                    }
                    for index, (screen, (width, height)) in enumerate(
                        (("intro", (640, 480)), ("question", (800, 600))), start=1
                    )
                ],
            }
        ]
    }
    manifest_path = tmp_path / "parts.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    common = [
        "render",
        "--words",
        str(words_path),
        "--fixations",
        str(fixations_path),
        "--trial-parts-manifest",
        str(manifest_path),
    ]
    cli.main([*common, "--list-parts"])
    assert "intro" in capsys.readouterr().out

    output = tmp_path / "parent.html"
    cli.main([*common, "--all-screens", "-o", str(output)])
    assert (tmp_path / "parent__screen-001-intro.html").is_file()
    assert (tmp_path / "parent__screen-002-question.html").is_file()


def test_render_fixations_only_multifile(tmp_path):
    """Fixations-only, multi-file glob input renders without a words table."""
    from scanpath_studio import data as data_module

    _, fix_raw = data_module.load_sample_data()
    for pid, group in fix_raw.groupby("participant_id"):
        group.to_csv(tmp_path / f"{pid}.csv", index=False)

    out_file = tmp_path / "out.html"
    cli.main(["render", "--fixations", str(tmp_path / "*.csv"), "-o", str(out_file)])
    assert out_file.is_file()


def test_render_potec_conflicts_with_other_inputs():
    with pytest.raises(SystemExit, match="exactly one input"):
        cli.main(["render", "--potec", "d", "--sample", "-o", "out.html"])


def test_render_authoring_json(tmp_path):
    from scanpath_studio.authoring import authoring_json, default_events, layout_text

    words = layout_text("alpha beta")
    source = tmp_path / "authored.json"
    source.write_text(
        authoring_json("alpha beta", default_events(words)), encoding="utf-8"
    )
    output = tmp_path / "authored.html"
    cli.main(["render", "--authoring", str(source), "-o", str(output)])
    assert output.is_file()


def test_analyze_and_corpus_commands(tmp_path):
    import pandas as pd

    from scanpath_studio import data as data_module

    words, fixations = data_module.load_sample_data()
    words_path = tmp_path / "ia.csv"
    fixations_path = tmp_path / "fixations.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fixations_path, index=False)
    output_dir = tmp_path / "analysis"
    cli.main(
        [
            "analyze",
            "--words",
            str(words_path),
            "--fixations",
            str(fixations_path),
            "--output-dir",
            str(output_dir),
        ]
    )
    assert (output_dir / "saccades.csv").is_file()
    assert (output_dir / "sentence_measures.csv").is_file()
    assert (output_dir / "run_config.json").is_file()

    tidy = tmp_path / "tidy.csv"
    pd.DataFrame({"value": [100.0, 120.0, 140.0]}).to_csv(tidy, index=False)
    figure = tmp_path / "corpus.html"
    cli.main(
        [
            "corpus",
            "--input",
            str(tidy),
            "--kind",
            "distribution",
            "--output",
            str(figure),
        ]
    )
    assert figure.is_file()


# ENG-30 — `scanpath-studio cache` is the terminal view of the on-device
# recovery cache the app writes on localhost/desktop.


def _seed_cache(state_dir):
    """Write a cache the way a local app session would."""
    import pandas as pd

    from scanpath_studio import persistence

    session = {
        "_datasets": {
            "Corpus": {
                "words": pd.DataFrame({"trial_id": ["t1"], "text": ["hello"]}),
                "fixations": pd.DataFrame({"trial_id": ["t1"], "duration_ms": [120]}),
                "raw_gaze": pd.DataFrame(),
            }
        },
        "global_show_heatmap": True,
    }
    persistence.save_state(session, state_dir)


def test_cache_reports_nothing_stored(tmp_path, monkeypatch, capsys):
    # Both env vars pinned: the reported folder AND whether a local run would
    # save must not depend on the developer's shell.
    monkeypatch.delenv("SCANPATH_STUDIO_PERSIST", raising=False)
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
    cli.main(["cache"])
    out = capsys.readouterr().out
    assert str(tmp_path) in out
    assert "Saving:  enabled" in out
    assert "Stored:  nothing" in out


def test_cache_reports_what_is_stored_and_clears_it(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SCANPATH_STUDIO_PERSIST", raising=False)
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
    _seed_cache(tmp_path)

    cli.main(["cache"])
    out = capsys.readouterr().out
    assert "1 dataset(s): Corpus" in out
    assert "2 rows" in out

    cli.main(["cache", "--clear"])
    assert "Cleared" in capsys.readouterr().out
    assert not (tmp_path / "manifest.json").exists()

    cli.main(["cache", "--clear"])
    assert "Nothing stored" in capsys.readouterr().out


def test_cache_path_and_json_output(tmp_path, monkeypatch, capsys):
    import json as json_module

    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
    _seed_cache(tmp_path)

    cli.main(["cache", "--path"])
    assert capsys.readouterr().out.strip() == str(tmp_path)

    cli.main(["cache", "--json"])
    status = json_module.loads(capsys.readouterr().out)
    assert status["readable"] and status["rows"] == 2
    assert status["directory"] == str(tmp_path)


def test_cache_reports_the_env_override(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SCANPATH_STUDIO_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "0")
    cli.main(["cache"])
    out = capsys.readouterr().out
    assert "Saving:  disabled (SCANPATH_STUDIO_PERSIST=off)" in out


def test_no_persist_flag_is_consumed_before_streamlit(monkeypatch):
    """`--no-persist` is ours: it sets the env var and never reaches streamlit.

    Streamlit would reject the unknown flag, so the launcher has to strip it —
    assert on the `sys.argv` handed to `streamlit run`, not just the env var.
    """
    import os

    # setenv (not delenv) so monkeypatch records the variable and restores it at
    # teardown — launch_app writes the real os.environ, and an unrecorded write
    # would leak "persistence off" into every test that runs after this one.
    monkeypatch.setenv("SCANPATH_STUDIO_PERSIST", "1")
    monkeypatch.setattr("streamlit.web.cli.main", lambda: 0)
    monkeypatch.setattr(cli.sys, "argv", [])

    with pytest.raises(SystemExit):
        cli.launch_app(["--no-persist", "--server.port", "8502"])

    assert os.environ["SCANPATH_STUDIO_PERSIST"] == "0"
    assert "--no-persist" not in cli.sys.argv
    assert cli.sys.argv[-2:] == ["--server.port", "8502"]


def test_python_dash_m_reaches_the_cli(tmp_path):
    """``python -m scanpath_studio`` is a documented entry point (README, docs).

    Run it as a real subprocess rather than importing ``__main__``: the thing
    that can break is the ``if __name__ == "__main__"`` wiring itself, and an
    import never executes that branch. ``--version`` is the cheapest command
    that proves the dispatch reached ``cli.main``.
    """
    import subprocess
    import sys

    from scanpath_studio import __version__

    result = subprocess.run(
        [sys.executable, "-m", "scanpath_studio", "--version"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=tmp_path,  # outside the repo, so it runs the installed package
    )
    assert result.returncode == 0, result.stderr
    assert __version__ in (result.stdout + result.stderr)


# --- CMP-9: compare mode on the CLI -----------------------------------------
# Compare existed only in the app and the share link; these pin the headless
# spelling. `_SAMPLE_TRIAL_*` are two real trials of the bundled demo — a
# renamed sample would break these loudly rather than silently comparing a
# trial against itself.
_SAMPLE_PARTICIPANT = "l37_1129"
_SAMPLE_TRIAL_A = "l37_1129_2_1_1_Ele_r0"
_SAMPLE_TRIAL_B = "l37_1129_2_1_3_Adv_r0"


def test_render_compare_with_writes_a_figure(tmp_path):
    out = tmp_path / "cmp.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            _SAMPLE_PARTICIPANT,
            "-t",
            _SAMPLE_TRIAL_A,
            "--compare-with",
            f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
            "-o",
            str(out),
        ]
    )
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.parametrize("layout", ["overlay", "side-by-side", "stacked"])
def test_render_compare_layouts(tmp_path, layout):
    out = tmp_path / f"cmp_{layout}.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            _SAMPLE_PARTICIPANT,
            "-t",
            _SAMPLE_TRIAL_A,
            "--compare-with",
            f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
            "--compare-layout",
            layout,
            "-o",
            str(out),
        ]
    )
    assert out.exists()


def test_render_compare_forwards_layout_and_stimulus(tmp_path, monkeypatch):
    """The flags must reach `api.compare_scanpaths`, not just parse."""
    from scanpath_studio import api

    seen = {}
    real = api.compare_scanpaths

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "compare_scanpaths", spy)
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            _SAMPLE_PARTICIPANT,
            "-t",
            _SAMPLE_TRIAL_A,
            "--compare-with",
            f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
            "--compare-layout",
            "stacked",
            "--compare-stimulus",
            "b",
            "-o",
            str(tmp_path / "cmp.html"),
        ]
    )
    assert seen["layout"] == "stacked"
    assert seen["compare_stimulus"] == "b"


@pytest.mark.parametrize("bad", ["nocolon", ":t1", "p1:", ""])
def test_render_compare_with_rejects_a_malformed_pair(tmp_path, bad):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--sample",
                "--compare-with",
                bad,
                "-o",
                str(tmp_path / "cmp.html"),
            ]
        )
    assert "PARTICIPANT:TRIAL" in str(excinfo.value)


def test_render_compare_with_splits_on_the_last_colon():
    assert cli._parse_compare_with("p01:t03") == ("p01", "t03")
    # A participant id containing a colon still resolves — the trial is the tail.
    assert cli._parse_compare_with("lab:p01:t03") == ("lab:p01", "t03")


def test_render_compare_across_two_datasets(tmp_path):
    """B from a second pair of tables — the cross-dataset half of CMP-9."""
    from scanpath_studio import api

    words, fixations = api.load_sample_data()
    words_path = tmp_path / "words_b.csv"
    fix_path = tmp_path / "fix_b.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)

    out = tmp_path / "cross.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            _SAMPLE_PARTICIPANT,
            "-t",
            _SAMPLE_TRIAL_A,
            "--compare-with",
            f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
            "--compare-words",
            str(words_path),
            "--compare-fixations",
            str(fix_path),
            "--compare-canvas",
            "2560x1440",
            "--canvas",
            "2560x1440",
            "--compare-dataset-name",
            "Second corpus",
            "-o",
            str(out),
        ]
    )
    assert out.exists() and out.stat().st_size > 0


def test_render_compare_overlay_refuses_two_different_screens(tmp_path):
    """Headless refuses rather than silently handing back a split layout."""
    from scanpath_studio import api

    words, fixations = api.load_sample_data()
    words_path = tmp_path / "words_b.csv"
    fix_path = tmp_path / "fix_b.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--sample",
                "-p",
                _SAMPLE_PARTICIPANT,
                "-t",
                _SAMPLE_TRIAL_A,
                "--compare-with",
                f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
                "--compare-words",
                str(words_path),
                "--compare-fixations",
                str(fix_path),
                "--canvas",
                "2560x1440",
                "--compare-canvas",
                "1680x1050",
                "--compare-layout",
                "overlay",
                "-o",
                str(tmp_path / "cross.html"),
            ]
        )
    message = str(excinfo.value)
    assert "1680" in message and "side_by_side" in message


def test_compare_setup_snapshot_without_a_canvas_is_not_a_known_screen():
    """`--monitor-mm` alone must not report a *known* screen.

    `_compare_setup_snapshot` returns a snapshot as soon as *any* geometry flag
    is set, and `api._compare_setup` then trusts it without consulting the data —
    so the canvas it carries is the bare default. Marking that ESTIMATED claimed
    a screen the caller never stated. It is ASSUMED, which since 2026-08-12 means
    the overlay is drawn *with a caution* rather than refused.
    """
    from scanpath_studio.experimental_setup import (
        Provenance,
        SetupSnapshot,
        setups_comparable,
    )

    snapshot = cli._compare_setup_snapshot(None, 520.0, None)
    assert snapshot.screen_provenance is Provenance.ASSUMED
    real = SetupSnapshot(
        canvas_width=snapshot.canvas_width,
        canvas_height=snapshot.canvas_height,
        screen_provenance=Provenance.MEASURED,
    )
    allowed, note = setups_comparable(snapshot, real)
    assert allowed is True
    assert note, "a default canvas passed the gate with nothing said about it"

    # A stated canvas is a known screen, and says nothing.
    stated = cli._compare_setup_snapshot((1680, 1050), None, None)
    assert stated.screen_provenance is Provenance.MEASURED
    assert setups_comparable(stated, stated) == (True, "")


def test_render_compare_with_rejects_all_screens(tmp_path):
    """Regression: this combination used to die on an UnboundLocalError."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--sample",
                "--compare-with",
                f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
                "--all-screens",
                "-o",
                str(tmp_path / "cmp.html"),
            ]
        )
    assert "--all-screens" in str(excinfo.value)


def test_render_animate_with_compare_co_animates(tmp_path, monkeypatch):
    """Regression: `--animate --compare-with` silently dropped the comparison.

    The app renders a dual co-animation when both modes are on, so the CLI was
    the only surface that could not produce one — and it said nothing.
    """
    from scanpath_studio import api

    seen = {}
    real = api.animate_scanpath

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "animate_scanpath", spy)
    out = tmp_path / "dual.html"
    cli.main(
        [
            "render",
            "--sample",
            "-p",
            _SAMPLE_PARTICIPANT,
            "-t",
            _SAMPLE_TRIAL_A,
            "--compare-with",
            f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
            "--animate",
            "-o",
            str(out),
        ]
    )
    assert out.exists()
    assert seen.get("fixations_b") is not None and not seen["fixations_b"].empty
    assert seen.get("words_b") is not None


def test_render_animate_compare_rejects_two_screens(tmp_path):
    """A co-animation is an overlay on one clock, so it needs one screen."""
    from scanpath_studio import api

    words, fixations = api.load_sample_data()
    words_path = tmp_path / "words_b.csv"
    fix_path = tmp_path / "fix_b.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--sample",
                "-p",
                _SAMPLE_PARTICIPANT,
                "-t",
                _SAMPLE_TRIAL_A,
                "--compare-with",
                f"{_SAMPLE_PARTICIPANT}:{_SAMPLE_TRIAL_B}",
                "--compare-words",
                str(words_path),
                "--compare-fixations",
                str(fix_path),
                "--canvas",
                "2560x1440",
                "--compare-canvas",
                "1680x1050",
                "--animate",
                "-o",
                str(tmp_path / "dual.html"),
            ]
        )
    assert "1680" in str(excinfo.value)
