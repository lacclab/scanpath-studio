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
    # EXP-10: this test used to pin `color_by` as unsupported, which it never
    # was — `animate_scanpath` colours the replay by it. The heatmap and the
    # arc schematic are what the replay genuinely cannot draw.
    out_file = tmp_path / "anim.html"
    cli.main(
        [
            "render",
            "--sample",
            "--animate",
            "--no-heatmap",
            "--saccade-arcs",
            # EXP-17: a real column — the demo's fixations carry no
            # `pass_index`, which this test used to colour by, silently flat.
            "--color-by",
            "duration_ms",
            "-o",
            str(out_file),
        ]
    )
    assert out_file.is_file()
    err = capsys.readouterr().err
    assert "ignoring" in err
    assert "show_heatmap" in err and "saccade_render_mode" in err
    assert "color_by" not in err


def test_render_animate_forwards_every_option_the_replay_takes(tmp_path, monkeypatch):
    """EXP-10: the forwarded set is `figure_options("animation")`, not a list.

    The hand-kept list silently dropped the marker shape, the flat colour and
    the palette, and refused three options the builder honours — so an
    animation snippet copied from the app replayed a different figure."""
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
            "--fixation-symbol",
            "diamond",
            "--fixation-color",
            "#ff0000",
            "--palette",
            "High contrast",
            "--color-by",
            "duration_ms",
            "--marker-size-range",
            "4",
            "12",
            "--fixation-colorscale",
            "Blues",
            "-o",
            str(tmp_path / "a.html"),
        ]
    )
    assert captured["fixation_symbol"] == "diamond"
    assert captured["fixation_color"] == "#ff0000"
    assert captured["palette"] == "High contrast"
    assert captured["color_by"] == "duration_ms"
    assert captured["marker_size_range"] == (4, 12)
    assert captured["fixation_colorscale"] == "Blues"
    # Nothing outside the replay's own option set is handed to it.
    assert set(captured) - {"palette"} <= set(api.figure_options("animation")) | {
        "playback_speed",
        "autoplay",
        "fix_index_range",
        "illustration_label",
        "canvas_size",
        "base_font_size",
        "font_family",
        "title",
        "caption",
        "screen",
    }


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


# ---------------------------------------------------------------------------
# The three settings the Python form used to carry alone (the four-surface rule)
# ---------------------------------------------------------------------------
def _captured_static(tmp_path, monkeypatch, argv):
    """Run ``render`` with a stubbed builder and return its keyword arguments."""
    from scanpath_studio import api

    captured = {}

    def fake_plot(words, fixations, participant=None, trial=None, **kwargs):
        captured.update(kwargs)
        return "FIG"

    monkeypatch.setattr(api, "plot_scanpath", fake_plot)
    monkeypatch.setattr(api, "animate_scanpath", fake_plot)
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **k: path)
    cli.main(["render", "--sample", *argv, "-o", str(tmp_path / "x.html")])
    return captured


def test_render_forwards_the_fixation_index_window(tmp_path, monkeypatch):
    """VIZ-7 had no `render` flag at all, so the CLI silently drew the whole
    trial where the Python form drew a window — a different figure."""
    captured = _captured_static(tmp_path, monkeypatch, ["--fix-index-range", "3:9"])
    assert captured["fix_index_range"] == (3, 9)


def test_the_replay_takes_the_fixation_index_window_too(tmp_path, monkeypatch):
    captured = _captured_static(
        tmp_path, monkeypatch, ["--animate", "--fix-index-range", "2:5"]
    )
    assert captured["fix_index_range"] == (2, 5)


def test_a_comparison_takes_the_fixation_index_window_too(tmp_path, monkeypatch):
    """EXP-11: `compare_scanpaths` has always taken `fix_index_range`, but the
    compare branch never passed it, so `--compare-with --fix-index-range 1:10`
    drew both whole trials."""
    from scanpath_studio import api

    captured = {}
    real = api.compare_scanpaths

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(api, "compare_scanpaths", spy)
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
            "--fix-index-range",
            "1:10",
            "-o",
            str(out),
        ]
    )
    assert captured["fix_index_range"] == (1, 10)
    assert out.exists()


@pytest.mark.parametrize("bad", ["3", "0:9", "9:3", "a:b"])
def test_a_malformed_fixation_index_window_is_refused(tmp_path, monkeypatch, bad):
    with pytest.raises(SystemExit):
        _captured_static(tmp_path, monkeypatch, ["--fix-index-range", bad])


def test_render_forwards_the_critical_span_pair(tmp_path, monkeypatch):
    captured = _captured_static(
        tmp_path,
        monkeypatch,
        ["--highlight-column", "is_critical", "--critical-span-style", "mark-border"],
    )
    assert captured["highlight_column"] == "is_critical"
    assert captured["critical_span_style"] == "Mark border"


def test_an_empty_highlight_column_means_highlight_nothing(tmp_path, monkeypatch):
    """Not the same as omitting the flag: the default is OneStop's answer span,
    so "mark nothing" has to be sayable."""
    captured = _captured_static(tmp_path, monkeypatch, ["--highlight-column", ""])
    assert captured["highlight_column"] is None


def test_render_forwards_fixation_flags_one_category_per_flag(tmp_path, monkeypatch):
    captured = _captured_static(
        tmp_path,
        monkeypatch,
        [
            "--fixation-flag",
            "short=discard,threshold_ms=80",
            "--fixation-flag",
            "oob=highlight,symbol=x,color=#ff0000",
        ],
    )
    flags = captured["fixation_flags"]
    assert flags["short"] == {"mode": "Discard", "threshold_ms": 80.0}
    assert flags["oob"] == {"mode": "Highlight", "symbol": "x", "color": "#ff0000"}
    # A category nobody named is absent, which the builder reads as Off.
    assert "long" not in flags


@pytest.mark.parametrize(
    "bad",
    [
        "nosuch=discard",
        "short=nosuch",
        "short",
        "oob=discard,threshold_ms=80",  # oob has no duration threshold
        "short=discard,color=red",  # not #RRGGBB
        "short=discard,symbol=wiggle",
    ],
)
def test_a_malformed_fixation_flag_is_refused(tmp_path, monkeypatch, bad):
    with pytest.raises(SystemExit):
        _captured_static(tmp_path, monkeypatch, ["--fixation-flag", bad])


# ---------------------------------------------------------------------------
# EXP-13 — a user-triggerable mistake is a message, never a traceback
# ---------------------------------------------------------------------------
def _renamed_sample(tmp_path):
    """The raw demo with its id/box columns renamed past auto-detection."""
    from scanpath_studio import data as data_module

    words, fixations = data_module.load_sample_data()
    words = words.rename(
        columns={
            "unique_trial_id": "reading",
            "IA_ID": "tok",
            "IA_LEFT": "l",
            "IA_RIGHT": "r",
            "IA_TOP": "t",
            "IA_BOTTOM": "b",
        }
    ).drop(columns=["paragraph_id", "trial_index"], errors="ignore")
    fixations = fixations.rename(
        columns={"unique_trial_id": "reading", "CURRENT_FIX_DURATION": "dur"}
    ).drop(columns=["paragraph_id", "trial_index"], errors="ignore")
    words_path, fix_path = tmp_path / "ia.csv", tmp_path / "fix.csv"
    words.to_csv(words_path, index=False)
    fixations.to_csv(fix_path, index=False)
    return words_path, fix_path


def test_render_a_missing_table_is_a_message(tmp_path):
    missing = tmp_path / "nope.csv"
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["render", "--words", str(missing), "-o", str(tmp_path / "x.html")])
    assert str(missing) in str(excinfo.value)


def test_render_unrecognised_columns_point_at_the_schema_flag(tmp_path):
    """The API's hint names `word_schema={…}`, which a shell cannot pass."""
    words_path, fix_path = _renamed_sample(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--words",
                str(words_path),
                "--fixations",
                str(fix_path),
                "-o",
                str(tmp_path / "x.html"),
            ]
        )
    message = str(excinfo.value)
    assert "--word-schema '{" in message
    assert "word_schema=" not in message
    assert "Word/IA ID" in message


def test_render_maps_unrecognised_columns_with_the_schema_flags(tmp_path):
    """Inline JSON for one table, a .json file for the other."""
    import json

    words_path, fix_path = _renamed_sample(tmp_path)
    word_schema = {
        "participant": "participant_id",
        "trial": "reading",
        "word_id": "tok",
        "text": "IA_LABEL",
        "left": "l",
        "right": "r",
        "top": "t",
        "bottom": "b",
    }
    fix_schema_path = tmp_path / "fix_schema.json"
    fix_schema_path.write_text(
        json.dumps(
            {
                "participant": "participant_id",
                "trial": "reading",
                "duration": "dur",
                "x": "CURRENT_FIX_X",
                "y": "CURRENT_FIX_Y",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "mapped.html"
    cli.main(
        [
            "render",
            "--words",
            str(words_path),
            "--fixations",
            str(fix_path),
            "--word-schema",
            json.dumps(word_schema),
            "--fix-schema",
            str(fix_schema_path),
            "-o",
            str(out),
        ]
    )
    assert out.is_file()


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--sample", "--word-schema", "{}"], "--words"),
        (["--words", "w.csv", "--word-schema", "{not json"], "not valid JSON"),
        (["--words", "w.csv", "--word-schema", '["trial"]'], "JSON object"),
        (["--words", "w.csv", "--word-schema", "no/such.json"], "readable file"),
    ],
)
def test_a_malformed_schema_flag_is_refused(tmp_path, argv, expected):
    with pytest.raises(SystemExit, match=expected):
        cli.main(["render", *argv, "-o", str(tmp_path / "x.html")])


def test_a_mistyped_mapped_column_points_at_the_flag(tmp_path):
    words_path, _ = _renamed_sample(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        cli.main(
            [
                "render",
                "--words",
                str(words_path),
                "--word-schema",
                '{"trial": "readng", "word_id": "tok", "left": "l", "right": "r", '
                '"top": "t", "bottom": "b"}',
                "-o",
                str(tmp_path / "x.html"),
            ]
        )
    message = str(excinfo.value)
    assert "--word-schema['trial'] = 'readng'" in message
    assert "'reading'" in message  # the closest real column


def test_analyze_takes_the_schema_flags_and_reports_cleanly(tmp_path):
    words_path, fix_path = _renamed_sample(tmp_path)
    base = [
        "analyze",
        "--words",
        str(words_path),
        "--fixations",
        str(fix_path),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    with pytest.raises(SystemExit, match="--word-schema"):
        cli.main(base)
    with pytest.raises(SystemExit, match="nope.csv"):
        cli.main([*base[:2], str(tmp_path / "nope.csv"), *base[3:]])


def test_corpus_reports_a_missing_input_and_a_missing_column(tmp_path):
    import pandas as pd

    with pytest.raises(SystemExit, match="--input"):
        cli.main(
            [
                "corpus",
                "--input",
                str(tmp_path / "nope.csv"),
                "--kind",
                "profile",
                "--output",
                str(tmp_path / "x.html"),
            ]
        )
    tidy = tmp_path / "tidy.csv"
    pd.DataFrame({"word_id": [1, 2], "val": [3.0, 4.0]}).to_csv(tidy, index=False)
    with pytest.raises(SystemExit, match="'value'.*--value-col"):
        cli.main(
            [
                "corpus",
                "--input",
                str(tidy),
                "--kind",
                "profile",
                "--output",
                str(tmp_path / "x.html"),
            ]
        )


@pytest.mark.parametrize("flag", ["--heatmap-colorscale", "--fixation-colorscale"])
def test_an_unknown_colorscale_is_refused_before_the_load(tmp_path, capsys, flag):
    out = tmp_path / "x.html"
    with pytest.raises(SystemExit):
        cli.main(["render", "--sample", flag, "Viridiss", "-o", str(out)])
    assert not out.exists()
    err = capsys.readouterr().err
    assert "unknown colorscale 'Viridiss'" in err and "viridis" in err


def test_a_reversed_or_lowercase_colorscale_is_accepted():
    parser = cli._render_parser()
    args = parser.parse_args(
        [
            "--sample",
            "--heatmap-colorscale",
            "greens",
            "--fixation-colorscale",
            "Viridis_r",
        ]
    )
    assert args.heatmap_colorscale == "greens"
    assert args.fixation_colorscale == "Viridis_r"


@pytest.mark.parametrize("layout", ["side-by-side", "stacked"])
def test_compare_stimulus_on_a_split_layout_is_named_as_ignored(
    tmp_path, capsys, layout
):
    """ENG-53: each split panel draws its own stimulus, so the choice does
    nothing there — and the docs' example claimed it did."""
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
            "--compare-stimulus",
            "b",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    err = capsys.readouterr().err
    assert "--compare-stimulus b only applies to --compare-layout overlay" in err


def test_compare_stimulus_on_an_overlay_is_not_warned_about(tmp_path, capsys):
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
            "--compare-stimulus",
            "b",
            "-o",
            str(tmp_path / "x.html"),
        ]
    )
    assert "--compare-stimulus" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# EXP-16 — no empty artefacts from a successful exit
# ---------------------------------------------------------------------------
def test_analyze_writes_a_readable_cleaning_qa_with_preprocessing_off(tmp_path):
    """The default `--short-policy off` wrote `cleaning_qa.csv` as a single
    newline, which `pd.read_csv` refuses — the bundle writes one "Off" row per
    trial instead, and so does `analyze` now."""
    import pandas as pd

    from scanpath_studio import data as data_module

    words, fixations = data_module.load_sample_data()
    words.to_csv(tmp_path / "ia.csv", index=False)
    fixations.to_csv(tmp_path / "fix.csv", index=False)
    out = tmp_path / "analysis"
    cli.main(
        [
            "analyze",
            "--words",
            str(tmp_path / "ia.csv"),
            "--fixations",
            str(tmp_path / "fix.csv"),
            "--output-dir",
            str(out),
        ]
    )
    qa = pd.read_csv(out / "cleaning_qa.csv")
    assert not qa.empty
    assert set(qa["short_policy"]) == {"Off"}
    assert (qa["n_excluded"] == 0).all()
    # Every table `analyze` writes has at least a header.
    for path in out.glob("*.csv"):
        assert path.stat().st_size > 1, path.name


def test_analyze_keeps_the_preprocessing_report_when_it_ran(tmp_path):
    import pandas as pd

    from scanpath_studio import data as data_module

    words, fixations = data_module.load_sample_data()
    words.to_csv(tmp_path / "ia.csv", index=False)
    fixations.to_csv(tmp_path / "fix.csv", index=False)
    out = tmp_path / "analysis"
    cli.main(
        [
            "analyze",
            "--words",
            str(tmp_path / "ia.csv"),
            "--fixations",
            str(tmp_path / "fix.csv"),
            "--output-dir",
            str(out),
            "--short-policy",
            "discard",
        ]
    )
    qa = pd.read_csv(out / "cleaning_qa.csv")
    assert set(qa["short_policy"]) == {"Discard"}


def test_corpus_difference_without_a_diff_column_is_refused(tmp_path):
    """The builder's "no data" placeholder is right for the app's empty states,
    but headlessly it was an empty figure behind an exit code of 0."""
    import pandas as pd

    tidy = tmp_path / "tidy.csv"
    pd.DataFrame({"word_id": [1, 2], "value": [3.0, 4.0]}).to_csv(tidy, index=False)
    out = tmp_path / "x.html"
    with pytest.raises(SystemExit, match="'diff'"):
        cli.main(
            [
                "corpus",
                "--input",
                str(tidy),
                "--kind",
                "difference",
                "--output",
                str(out),
            ]
        )
    assert not out.exists()


@pytest.mark.parametrize(
    ("flag", "value"), [("--color-by", "nosuchfield"), ("--highlight-column", "nosuch")]
)
def test_render_refuses_a_column_the_data_does_not_have(tmp_path, flag, value):
    """EXP-17: both used to exit 0 with a flat-coloured / unmarked figure."""
    out = tmp_path / "x.html"
    with pytest.raises(SystemExit, match=f"{flag} on the CLI"):
        cli.main(["render", "--sample", flag, value, "-o", str(out)])
    assert not out.exists()


# ---------------------------------------------------------------------------
# ENG-54 — the package root and the command line say what they mean
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("word", ["rendr", "analyse", "foo"])
def test_a_mistyped_command_is_refused_not_forwarded(monkeypatch, word):
    """A bare word reached `streamlit run` as a script argument — dying on
    "No such option" when flags followed, launching the app when none did."""
    calls = []
    monkeypatch.setattr(cli, "launch_app", lambda args: calls.append(args))
    with pytest.raises(SystemExit, match=f"unknown command {word!r}"):
        cli.main([word, "--sample"])
    assert calls == []


def test_a_near_miss_command_is_named(monkeypatch):
    monkeypatch.setattr(cli, "launch_app", lambda args: None)
    with pytest.raises(SystemExit, match="did you mean 'render'"):
        cli.main(["rendr", "--sample"])


def test_streamlit_flags_and_script_paths_still_launch_the_app(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "launch_app", lambda args: calls.append(args))
    cli.main(["--server.headless", "true"])
    cli.main(["streamlit_app.py"])
    assert calls == [["--server.headless", "true"], ["streamlit_app.py"]]


def test_the_sample_help_does_not_promise_three_renderable_readers(capsys):
    """Three readers' word boxes ship, but only two have fixations."""
    with pytest.raises(SystemExit):
        cli.main(["render", "--help"])
    out = " ".join(capsys.readouterr().out.split())
    assert "3-participant" not in out
    assert "fixations — so trials to render — for 2 of them" in out


# ---------------------------------------------------------------------------
# ENG-55 — a local launch listens on this computer only
# ---------------------------------------------------------------------------
def _launch_argv(monkeypatch, tmp_path, extra_args, *, config: str | None = None):
    """`launch_app`'s argv with Streamlit stubbed and its config files pinned
    to one temp file, so a developer's own ~/.streamlit cannot leak in."""
    from streamlit import config as st_config
    from streamlit.web import cli as st_cli

    config_path = tmp_path / "config.toml"
    if config is not None:
        config_path.write_text(config, encoding="utf-8")
    monkeypatch.setattr(st_config, "get_config_files", lambda name: [str(config_path)])
    monkeypatch.delenv("STREAMLIT_SERVER_ADDRESS", raising=False)
    seen: dict = {}

    def fake_main():
        seen["argv"] = list(cli.sys.argv)
        return 0

    monkeypatch.setattr(st_cli, "main", fake_main)
    monkeypatch.setattr(cli.sys, "exit", lambda *a, **k: None)
    monkeypatch.setattr(cli.sys, "argv", list(cli.sys.argv))
    cli.launch_app(extra_args)
    return seen["argv"]


def test_a_launch_binds_loopback_by_default(monkeypatch, tmp_path):
    """Streamlit's default is 0.0.0.0, and the app has no login."""
    argv = _launch_argv(monkeypatch, tmp_path, [])
    assert "--server.address=127.0.0.1" in argv


@pytest.mark.parametrize(
    "extra", [["--server.address", "0.0.0.0"], ["--server.address=0.0.0.0"]]
)
def test_an_address_flag_the_user_passes_wins(monkeypatch, tmp_path, extra):
    argv = _launch_argv(monkeypatch, tmp_path, extra)
    assert "--server.address=127.0.0.1" not in argv
    assert argv[-len(extra) :] == extra


def test_an_address_from_the_environment_or_config_wins(monkeypatch, tmp_path):
    argv = _launch_argv(
        monkeypatch, tmp_path, [], config='[server]\naddress = "0.0.0.0"\n'
    )
    assert not any(arg.startswith("--server.address") for arg in argv)

    from streamlit import config as st_config
    from streamlit.web import cli as st_cli

    monkeypatch.setattr(st_config, "get_config_files", lambda name: [])
    monkeypatch.setenv("STREAMLIT_SERVER_ADDRESS", "0.0.0.0")
    monkeypatch.setattr(st_cli, "main", lambda: 0)
    cli.launch_app([])
    assert not any(arg.startswith("--server.address") for arg in cli.sys.argv)


def test_the_address_flag_is_a_real_streamlit_option():
    from streamlit import config as st_config

    st_config.get_config_options()
    assert "server.address" in st_config._config_options_template
