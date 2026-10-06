"""#374 F21 — the CLI's errors are short and say what to do, its flags take
the app's names, and its default figure is the app's Scanpath design."""

from __future__ import annotations

import pytest

from scanpath_studio import cli


def test_a_misspelt_flag_is_three_lines_ending_in_a_suggestion(capsys):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["render", "--sample", "--no-heatmaps", "-o", "x.png"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert err == [
        "scanpath-studio render: error: unrecognized arguments: --no-heatmaps",
        "Did you mean --no-heatmap?",
        "`scanpath-studio render --help` lists every option.",
    ]


def test_an_invalid_choice_prints_no_usage_block(capsys):
    with pytest.raises(SystemExit):
        cli.main(["render", "--sample", "--heatmap-norm", "logarithmic"])
    err = capsys.readouterr().err
    assert "usage:" not in err
    assert len(err.strip().splitlines()) <= 3


@pytest.mark.parametrize(
    ("argv", "fix"),
    [
        (
            ["--sample", "render", "-o", "f.png"],
            "scanpath-studio render --sample -o f.png",
        ),
        (["--sample", "-o", "f.png"], "scanpath-studio render --sample -o f.png"),
        (["--words", "ia.csv", "check"], "scanpath-studio check --words ia.csv"),
    ],
)
def test_options_before_the_command_say_where_they_go(argv, fix):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert (
        str(excinfo.value) == f"scanpath-studio: put options after the command: {fix}"
    )


@pytest.mark.parametrize(
    "argv", [["--server.port", "8502"], ["--no-persist"], ["--theme.base=dark"]]
)
def test_streamlit_and_launch_flags_still_launch_the_app(argv):
    assert cli._refuse_misplaced_options(argv) is None


def test_both_spellings_of_colour_and_the_app_names_are_flags():
    args = cli._render_parser().parse_args(
        [
            "--sample",
            "--colour-by",
            "duration_ms",
            "--fixation-colour=#000000",
            "--no-word-boxes",
            "--no-text",
            "--heatmap",
            "--fixation-index",
        ]
    )
    assert args.color_by == "duration_ms"
    assert args.fixation_color == "#000000"
    assert args.show_words is False
    assert args.show_word_labels is False
    assert args.show_heatmap is True
    assert args.show_order is True


def test_layer_flags_left_out_are_not_given():
    """Only a flag on the line overrides the API's default design."""
    args = cli._render_parser().parse_args(["--sample"])
    for dest in (
        "show_words",
        "show_word_labels",
        "show_fixations",
        "show_order",
        "show_saccades",
        "show_heatmap",
        "show_saccade_arrows",
    ):
        assert getattr(args, dest) is None, dest


def test_list_trials_says_trials_and_shows_the_text_id(capsys):
    cli.main(["render", "--sample", "--list-trials"])
    captured = capsys.readouterr()
    assert captured.err.startswith("24 trials.")
    assert "combo" not in captured.err + captured.out
    header = captured.out.splitlines()[0].split()
    assert header == ["participant_id", "unique_trial_id", "unique_paragraph_id"]
