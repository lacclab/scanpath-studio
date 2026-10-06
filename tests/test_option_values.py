"""#374 F4 — an enumerated figure option takes any spelling of a choice (the
app's label, the CLI's flag value, any case) and refuses anything else, rather
than silently drawing the default."""

from __future__ import annotations

import pytest

import scanpath_studio as sps
from scanpath_studio import plots


@pytest.fixture(scope="module")
def sample():
    return sps.load_sample_data(names="canonical")


@pytest.mark.parametrize(
    ("name", "spelling", "value"),
    [
        ("heatmap_norm", "log", "Log"),
        ("heatmap_norm", "LOG", "Log"),
        ("heatmap_style", "word-boxes", "Word boxes"),
        ("heatmap_style", "interpolated", "Interpolated"),
        ("critical_span_style", "mark-border", "Mark border"),
        ("critical_span_style", "mark_text", "Mark text"),
        ("critical_span_style", "none", "None"),
        ("critical_span_style", None, "None"),
        ("saccade_color_mode", "by-type", "By type"),
        ("saccade_color_mode", "by-direction", "Forward / regression"),
        ("saccade_render_mode", "arc", "Arc"),
        ("saccade_style", "Dashed", "dash"),
        ("saccade_style", "DOT", "dot"),
        ("marker_size_scale", "Linear", "linear"),
        ("fixation_colorbar_orientation", "horizontal", "Horizontal"),
        ("fixation_symbol", "Triangle-Up", "triangle-up"),
        ("color_by", "anything", "anything"),  # not enumerated: untouched
    ],
)
def test_option_values_take_any_spelling_of_a_choice(name, spelling, value):
    assert plots.normalize_option_value(name, spelling) == value


@pytest.mark.parametrize(
    ("name", "bad"),
    [
        ("heatmap_norm", "logarithmic"),
        ("heatmap_style", "gaussian"),
        ("critical_span_style", "bold"),
        ("saccade_render_mode", "curvy"),
        ("saccade_style", "dashed-ish"),
        ("fixation_colorbar_orientation", "diagonal"),
    ],
)
def test_an_unknown_option_value_raises_listing_the_choices(name, bad):
    with pytest.raises(ValueError, match=rf"Unknown {name} '{bad}'; choose one of"):
        plots.normalize_option_value(name, bad)


def test_style_dicts_are_read_too():
    out = plots.normalize_option_values({"style_b": {"saccade_style": "Dotted"}})
    assert out["style_b"]["saccade_style"] == "dot"


def test_plot_scanpath_draws_the_cli_spelling_and_refuses_a_misspelling(sample):
    words, fixations = sample
    pid, tid = sps.list_trials(words, fixations).iloc[0]

    def heat(norm):
        fig = sps.plot_scanpath(
            words, fixations, pid, tid, show_heatmap=True, heatmap_norm=norm
        )
        return fig.to_json()

    assert heat("log") == heat("Log") != heat("Linear")
    with pytest.raises(ValueError, match="choose one of Linear, Log"):
        sps.plot_scanpath(words, fixations, pid, tid, heatmap_norm="logarithmic")


def test_figure_options_lists_the_accepted_values():
    options = sps.figure_options(choices=True)
    assert options["heatmap_norm"] == {
        "default": "Linear",
        "choices": ("Linear", "Log"),
    }
    assert options["color_by"]["choices"] is None
    comparison = sps.figure_options("comparison", choices=True)
    every = set(options) | set(comparison)
    # `compare_stimulus` is a named parameter of `compare_scanpaths`.
    assert set(plots.FIGURE_OPTION_CHOICES) - {"compare_stimulus"} <= every


@pytest.mark.parametrize(
    ("spelling", "name"),
    [
        ("print", "Print / greyscale"),
        ("greyscale", "Print / greyscale"),
        ("high-contrast", "High contrast"),
        ("High contrast", "High contrast"),
        ("default", "Default (colourblind-safe)"),
    ],
)
def test_palettes_take_their_short_names(spelling, name):
    assert plots.normalize_palette(spelling) == name


def test_an_unknown_palette_lists_the_short_names():
    with pytest.raises(ValueError, match="choose one of default, print, high-contrast"):
        plots.normalize_palette("sepia")
