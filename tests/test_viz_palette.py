"""VIZ-15 / VIZ-17 / VIZ-18 / VIZ-19 — marker shape, uniform fixation colour,
selectable palettes, and the two-way saccade split.

Each has to hold on all four surfaces (UI state → figure, deep link, CLI,
headless API), so these check the figure output and the plumbing rather than the
widgets.
"""

from __future__ import annotations

import pytest

from scanpath_studio import api
from scanpath_studio.constants import (
    DEFAULT_PALETTE,
    FIXATION_SYMBOLS,
    PALETTES,
    SACCADE_COLOR_MODES,
    UNIFORM_COLOR_FIELD,
    palette_settings,
)


def _fig(normalized_words_df, normalized_fixations_df, **kwargs):
    """One trial's static figure with the app's defaults, plus ``kwargs``.

    Goes through ``plot_scanpath`` rather than the raw builder so these also
    exercise the headless surface's defaults.
    """
    return api.plot_scanpath(
        normalized_words_df,
        normalized_fixations_df,
        canvas_size=(1000, 600),
        **kwargs,
    )


def _fixation_marker(fig):
    """The marker dict of the main fixation trace."""
    for trace in fig.data:
        if getattr(trace, "name", None) == "Fixations":
            return trace.marker
    raise AssertionError("no fixation trace in the figure")


class TestUniformFixationColor:
    """VIZ-17: size already encodes duration, so hue is free by default."""

    def test_uniform_paints_one_flat_colour(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = _fig(
            normalized_words_df,
            normalized_fixations_df,
            color_by=UNIFORM_COLOR_FIELD,
            fixation_color="#123456",
        )
        assert _fixation_marker(fig).color == "#123456"

    def test_a_real_column_still_maps_to_hue(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = _fig(normalized_words_df, normalized_fixations_df, color_by="duration_ms")
        color = _fixation_marker(fig).color
        # A per-point array, not one colour.
        assert hasattr(color, "__len__") and not isinstance(color, str)

    def test_headless_default_is_uniform(self):
        assert api.CANONICAL_FIGURE_DEFAULTS["color_by"] == UNIFORM_COLOR_FIELD

    def test_uniform_option_leads_the_picker(self, normalized_fixations_df):
        from scanpath_studio.controls import color_field_options

        assert color_field_options(normalized_fixations_df)[0] == UNIFORM_COLOR_FIELD


class TestMarkerSymbol:
    """VIZ-15: shape as a second channel that survives greyscale."""

    @pytest.mark.parametrize("symbol", list(FIXATION_SYMBOLS))
    def test_every_offered_symbol_reaches_the_marker(
        self, normalized_words_df, normalized_fixations_df, symbol
    ):
        fig = _fig(normalized_words_df, normalized_fixations_df, fixation_symbol=symbol)
        assert _fixation_marker(fig).symbol == symbol

    def test_animation_honours_the_symbol(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = api.animate_scanpath(
            normalized_words_df,
            normalized_fixations_df,
            canvas_size=(1000, 600),
            fixation_symbol="diamond",
        )
        assert any(
            getattr(t.marker, "symbol", None) == "diamond"
            for t in fig.data
            if hasattr(t, "marker")
        )


class TestPalettes:
    """VIZ-18: a palette is a preset over the ordinary colour keys."""

    @pytest.mark.parametrize("name", list(PALETTES))
    def test_every_palette_is_complete(self, name):
        settings = palette_settings(name)
        for key in (
            "fixation_color",
            "fixation_colorscale",
            "heatmap_colorscale",
            "saccade_color",
            "saccade_class_colors",
            "word_label_color",
            "highlight_text_color",
        ):
            assert key in settings, f"{name} is missing {key}"

    def test_settings_are_copies_not_registry_references(self):
        settings = palette_settings("Default")
        settings["saccade_class_colors"]["forward"] = "#000000"
        assert PALETTES["Default"]["saccade_class_colors"]["forward"] != "#000000"

    def test_api_expands_a_palette_into_colours(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = api.plot_scanpath(
            normalized_words_df,
            normalized_fixations_df,
            canvas_size=(1000, 600),
            palette="Print / greyscale",
        )
        expected = palette_settings("Print / greyscale")["fixation_color"]
        assert _fixation_marker(fig).color == expected

    def test_an_explicit_colour_beats_the_palette(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = api.plot_scanpath(
            normalized_words_df,
            normalized_fixations_df,
            canvas_size=(1000, 600),
            palette="Print / greyscale",
            fixation_color="#ff0000",
        )
        assert _fixation_marker(fig).color == "#ff0000"

    def test_unknown_palette_raises_rather_than_silently_defaulting(
        self, normalized_words_df, normalized_fixations_df
    ):
        with pytest.raises(ValueError, match="Unknown palette"):
            api.plot_scanpath(
                normalized_words_df,
                normalized_fixations_df,
                canvas_size=(1000, 600),
                palette="Nope",
            )

    def test_greyscale_palette_is_actually_greyscale(self):
        """Every mark colour has R == G == B, so a B&W conversion loses nothing."""
        settings = palette_settings("Print / greyscale")
        colors = [
            settings["fixation_color"],
            settings["saccade_color"],
            *settings["saccade_class_colors"].values(),
        ]
        for hex_color in colors:
            r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
            assert r == g == b, f"{hex_color} is not a grey"

    def test_palette_maps_onto_session_keys(self):
        from scanpath_studio.controls import palette_state

        state = palette_state("Colourblind-safe")
        assert state["global_fixation_color"] == "#0072B2"
        assert state["global_saccade_class_color_regression"] == "#D55E00"
        # `other` is not user-editable, so it gets no session key.
        assert "global_saccade_class_color_other" not in state


class TestSaccadeDirectionMode:
    """VIZ-19: forward vs. regression, between Uniform and the five-way split."""

    def test_mode_sits_between_the_other_two(self):
        assert SACCADE_COLOR_MODES == ("Uniform", "Forward / regression", "By type")

    def _saccade_legend(self, fig):
        return {
            t.name
            for t in fig.data
            if getattr(t, "legendgroup", None) == "saccade_type"
        }

    def test_two_way_draws_two_buckets_not_five(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = _fig(
            normalized_words_df,
            normalized_fixations_df,
            saccade_color_mode="Forward / regression",
        )
        names = self._saccade_legend(fig)
        assert names <= {"Forward", "Regression", "Other"}
        assert "Skip" not in names and "Return sweep" not in names

    def test_by_type_still_splits_five_ways(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = _fig(
            normalized_words_df, normalized_fixations_df, saccade_color_mode="By type"
        )
        names = self._saccade_legend(fig)
        assert names <= {
            "Forward",
            "Skip",
            "Refixation",
            "Return sweep",
            "Regression",
            "Other",
        }

    def test_uniform_draws_a_single_trace(
        self, normalized_words_df, normalized_fixations_df
    ):
        fig = _fig(
            normalized_words_df, normalized_fixations_df, saccade_color_mode="Uniform"
        )
        assert not self._saccade_legend(fig)
        assert sum(1 for t in fig.data if getattr(t, "name", "") == "saccades") == 1

    def test_folding_preserves_every_saccade(
        self, normalized_words_df, normalized_fixations_df
    ):
        """The two-way split must not drop segments the five-way one drew."""

        def points(mode):
            fig = _fig(
                normalized_words_df,
                normalized_fixations_df,
                saccade_color_mode=mode,
            )
            return sum(
                len(t.x)
                for t in fig.data
                if getattr(t, "legendgroup", None) == "saccade_type"
            )

        assert points("Forward / regression") == points("By type")


class TestDeepLinkAndCli:
    def test_palette_url_param_expands_to_colours(self):
        from scanpath_studio.controls import palette_state
        from scanpath_studio.url_state import _URL_PRESETS

        for key in ("palette", "fixation_color", "fixation_symbol"):
            assert key in _URL_PRESETS, f"{key} is not deep-linkable"
        assert palette_state("High contrast")["global_saccade_color"] == "#cc0000"

    def test_cli_exposes_the_new_flags(self):
        from scanpath_studio.cli import _render_parser

        help_text = _render_parser().format_help()
        for flag in (
            "--palette",
            "--fixation-color",
            "--fixation-symbol",
            "--saccade-color-by-direction",
        ):
            assert flag in help_text, f"{flag} missing from the CLI"

    def test_default_palette_is_registered(self):
        assert DEFAULT_PALETTE in PALETTES
