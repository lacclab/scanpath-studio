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
    CUSTOM_PALETTE,
    DEFAULT_PALETTE,
    FIXATION_GLYPH_SYMBOLS,
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

    @pytest.mark.parametrize(
        "symbol", [s for s in FIXATION_SYMBOLS if s not in FIXATION_GLYPH_SYMBOLS]
    )
    def test_every_offered_symbol_reaches_the_marker(
        self, normalized_words_df, normalized_fixations_df, symbol
    ):
        fig = _fig(normalized_words_df, normalized_fixations_df, fixation_symbol=symbol)
        assert _fixation_marker(fig).symbol == symbol

    @pytest.mark.parametrize("symbol", list(FIXATION_GLYPH_SYMBOLS))
    def test_glyph_shapes_render_as_sized_text(
        self, normalized_words_df, normalized_fixations_df, symbol
    ):
        """Plotly's symbol enum has no ♥, so glyph shapes are drawn as text —
        with a per-point size array, so duration→size still holds."""
        fig = _fig(normalized_words_df, normalized_fixations_df, fixation_symbol=symbol)
        trace = next(t for t in fig.data if t.name == "Fixations")
        assert trace.mode == "text"
        assert set(trace.text) == {FIXATION_GLYPH_SYMBOLS[symbol]}
        assert len(trace.textfont.size) == len(trace.x)

    def test_a_glyph_shape_keeps_the_fixation_index_labels(
        self, normalized_words_df, normalized_fixations_df
    ):
        """One Scatter has one text field, so the indices get their own trace."""
        fig = _fig(
            normalized_words_df,
            normalized_fixations_df,
            fixation_symbol="heart",
            show_order=True,
        )
        assert any(t.name == "Fixation index" for t in fig.data)

    def test_the_animation_falls_back_rather_than_raising_on_a_glyph(
        self, normalized_words_df, normalized_fixations_df
    ):
        """The trail restates a Plotly marker per frame, which can't take ♥."""
        fig = api.animate_scanpath(
            normalized_words_df,
            normalized_fixations_df,
            canvas_size=(1000, 600),
            fixation_symbol="heart",
        )
        symbols = {
            getattr(t.marker, "symbol", None) for t in fig.data if hasattr(t, "marker")
        }
        assert "heart" not in symbols

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
        settings = palette_settings(DEFAULT_PALETTE)
        settings["saccade_class_colors"]["forward"] = "#000000"
        assert PALETTES[DEFAULT_PALETTE]["saccade_class_colors"]["forward"] != "#000000"

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

        state = palette_state("Default (colourblind-safe)")
        assert state["global_fixation_color"] == "#0072B2"
        assert state["global_saccade_class_color_regression"] == "#D55E00"
        # `other` is not user-editable, so it gets no session key.
        assert "global_saccade_class_color_other" not in state


class TestTheSelectorStopsClaimingAPalette:
    """VIZ-18 follow-up. A palette is one-way — it writes the ordinary colour
    keys and never reads them back — so without a derived "which palette is
    actually active?" the dropdown keeps reading *Default (colourblind-safe)* after you've
    hand-edited one of its colours. Same rule VIZ-12 applies to the Quick views."""

    @pytest.fixture
    def state(self, monkeypatch):
        """A bare dict standing in for `st.session_state`."""
        from scanpath_studio import controls

        store: dict = {}
        monkeypatch.setattr(controls.st, "session_state", store)
        return store

    @pytest.mark.parametrize("name", list(PALETTES))
    def test_a_freshly_applied_palette_reports_itself(self, state, name):
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette(name)
        assert _active_palette() == name

    def test_editing_one_colour_drops_it_to_custom(self, state):
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette("Default (colourblind-safe)")
        state["global_saccade_color"] = "#123456"
        assert _active_palette() is None

    def test_editing_a_colorscale_drops_it_to_custom(self, state):
        """The colourscales are part of the palette too — this is the half of
        the question that isn't obvious from looking at the figure."""
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette("Print / greyscale")
        state["global_heatmap_colorscale"] = "Turbo"
        assert _active_palette() is None

    def test_editing_a_saccade_class_colour_drops_it_to_custom(self, state):
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette("High contrast")
        state["global_saccade_class_color_regression"] = "#010203"
        assert _active_palette() is None

    def test_putting_the_colour_back_restores_the_name(self, state):
        """Custom is derived, not sticky — undo your edit and the palette
        returns, so the option disappears from the list again."""
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette("Default (colourblind-safe)")
        original = state["global_saccade_color"]
        state["global_saccade_color"] = "#123456"
        assert _active_palette() is None
        state["global_saccade_color"] = original
        assert _active_palette() == "Default (colourblind-safe)"

    def test_a_lowercased_hex_still_matches(self, state):
        """`st.color_picker` hands colours back lowercase; the registry spells
        the Okabe-Ito hues in caps. Without normalizing, every palette would
        read Custom the first time its own picker was touched."""
        from scanpath_studio.controls import _active_palette, apply_palette

        apply_palette("Default (colourblind-safe)")
        state["global_fixation_color"] = state["global_fixation_color"].lower()
        assert _active_palette() == "Default (colourblind-safe)"

    def test_empty_state_is_not_silently_a_palette(self, state):
        from scanpath_studio.controls import _active_palette

        assert _active_palette() is None

    def test_reselecting_custom_does_not_overwrite_your_colours(self, state):
        """`Custom` names the absence of a palette. Applying it must be a no-op,
        or picking it would wipe the very colours it stands for."""
        from scanpath_studio.controls import apply_palette

        apply_palette("Default (colourblind-safe)")
        state["global_saccade_color"] = "#123456"
        apply_palette(CUSTOM_PALETTE)
        assert state["global_saccade_color"] == "#123456"

    def test_custom_is_not_offered_as_a_real_palette(self):
        """It must stay out of the registry: `--palette`'s choices, the API's
        expansion and the deep link all iterate PALETTES."""
        from scanpath_studio.cli import _render_parser

        assert CUSTOM_PALETTE not in PALETTES
        assert CUSTOM_PALETTE not in _render_parser().format_help()

    def test_viz_settings_report_custom_rather_than_a_stale_name(
        self, state, normalized_words_df, normalized_fixations_df
    ):
        """The name reaches Share, Save & restore and the export caption. It has
        to be derived there too, or a hand-edited figure is exported labelled
        with a palette it doesn't use. Goes through the real non-rendering reader
        (`viz_settings_from_state`) so this covers the path those surfaces use."""
        from scanpath_studio.controls import apply_palette, viz_settings_from_state

        def settings():
            return viz_settings_from_state(
                normalized_fixations_df, 12, words=normalized_words_df
            )

        apply_palette("Print / greyscale")
        assert settings()["palette"] == "Print / greyscale"
        state["global_fixation_color"] = "#ff0000"
        assert settings()["palette"] == CUSTOM_PALETTE

    @pytest.mark.timeout(120)
    def test_the_rail_selector_says_custom_after_you_edit_a_colour(self):
        """End to end through the real rail: the unit tests above pin the
        derivation, this pins that the *widget* shows it — which is the whole
        point of the item."""
        streamlit_testing = pytest.importorskip("streamlit.testing.v1")

        at = streamlit_testing.AppTest.from_file("streamlit_app.py")
        at.query_params["source"] = "synthetic"
        at.run(timeout=60)

        def picker():
            return next(s for s in at.selectbox if s.label == "Palette")

        picker().set_value("Default (colourblind-safe)").run(timeout=60)
        assert picker().value == "Default (colourblind-safe)"
        assert CUSTOM_PALETTE not in picker().options

        # Hand-edit one of the palette's colours, exactly as the colour picker
        # in the Saccades popover would.
        at.session_state["global_saccade_color"] = "#123456"
        at.run(timeout=60)
        assert picker().value == CUSTOM_PALETTE
        assert CUSTOM_PALETTE in picker().options

    @pytest.mark.parametrize(
        ("saved", "expect_skipped"),
        [
            (CUSTOM_PALETTE, False),
            ("Default (colourblind-safe)", False),
            ("Nope", True),
        ],
    )
    def test_restoring_a_custom_config_is_not_reported_as_skipped(
        self, monkeypatch, saved, expect_skipped
    ):
        """A config saved from hand-edited colours round-trips through the
        explicit colour keys, so its `Custom` is a valid value — flagging it as
        an unknown palette would warn the user about their own good file. A
        genuinely bad name must still be flagged."""
        import pandas as pd

        from scanpath_studio import url_state

        monkeypatch.setattr(url_state.st, "session_state", {})
        monkeypatch.setattr(url_state.st, "toast", lambda *a, **k: None)
        _, skipped = url_state._restore_plot_config(
            {"coloring": {"palette": saved}}, pd.DataFrame(), pd.DataFrame()
        )
        assert ("palette" in skipped) is expect_skipped


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
