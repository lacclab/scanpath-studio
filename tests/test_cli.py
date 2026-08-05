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
    import scanpath_studio.api as api

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
    import scanpath_studio.api as api

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
    import scanpath_studio.api as api

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
    import scanpath_studio.api as api

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
    import scanpath_studio.api as api

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
    assert "Plotly.animate" in out_file.read_text()


def test_render_animate_no_autoplay_flag(tmp_path):
    # VIZ-10: --no-autoplay saves a figure that opens paused (no kickoff).
    out_file = tmp_path / "anim.html"
    cli.main(["render", "--sample", "--animate", "--no-autoplay", "-o", str(out_file)])
    assert "Plotly.animate" not in out_file.read_text()


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
    pid, tid = combos.iloc[-1]
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
    html = out_file.read_text()
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
    assert "data:image/png;base64" in out_file.read_text()


def test_render_separable_layers(tmp_path, monkeypatch):
    # VIZ-5: --separable-layers writes a <output>_layers/ folder. Stub the writers
    # to avoid Kaleido/Chrome; assert the CLI targets the right dir + format.
    from pathlib import Path

    import scanpath_studio.api as api

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

    import scanpath_studio.api as api

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
