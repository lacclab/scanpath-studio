"""Tests for app.py utility functions."""

from urllib.parse import parse_qs

import pandas as pd
import pytest

from scanpath_studio import app as app_module
from scanpath_studio.app import (
    DEMO_CHOICE,
    UPLOAD_CHOICE,
    _apply_url_preset,
    _apply_url_trial_selection,
    _build_comparison_options,
    _build_share_query,
    build_combo_options,
)
from scanpath_studio.data import compute_canvas_size

# Imported from their real home (utils); app.py no longer re-exports these
# test-only helpers.
from scanpath_studio.utils import compute_trial_stats, gather_trial_metadata


class TestBuildComboOptions:
    """Tests for build_combo_options function."""

    def test_build_combo_options_basic(self):
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t1"],
                "text_id": ["para1", "para1", "para1"],
            }
        )
        combos, labels, label_to_combo = build_combo_options(fixations)
        assert len(combos) == 3
        assert len(labels) == 3
        assert len(label_to_combo) == 3
        assert "participant_id" in combos.columns
        assert "trial_id" in combos.columns
        assert "text_id" in combos.columns

    def test_build_combo_options_with_unique_ids(self):
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "unique_trial_id": ["ut1", "ut1"],
                "unique_text_id": ["up1", "up1"],
            }
        )
        combos, labels, label_to_combo = build_combo_options(fixations)
        assert "unique_trial_id" in combos.columns or "trial_id" in combos.columns

    def test_build_combo_options_with_trial_index(self):
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t2"],
                "text_id": ["para1", "para1"],
                "TRIAL_INDEX": [1, 2],
            }
        )
        combos, labels, label_to_combo = build_combo_options(fixations)
        assert len(combos) == 2


class TestComputeCanvasSize:
    """Tests for compute_canvas_size (replaces removed clamp_canvas_size)."""

    def test_canvas_size_uses_data_extent(
        self, normalized_words_df, normalized_fixations_df
    ):
        width, height = compute_canvas_size(
            normalized_words_df, normalized_fixations_df
        )
        # The fixture has words extending to x=350, y=100 — expect width≥350
        assert width >= 350
        assert height >= 100

    def test_canvas_size_floor(self):
        empty = pd.DataFrame()
        width, height = compute_canvas_size(empty, empty)
        assert width >= 100
        assert height >= 100


class TestComputeTrialStats:
    """Tests for compute_trial_stats function."""

    def test_compute_trial_stats_basic(
        self, normalized_words_df, normalized_fixations_df
    ):
        stats = compute_trial_stats(normalized_words_df, normalized_fixations_df)
        assert "total_reading_time_ms" in stats
        assert "total_reading_time_s" in stats
        assert "word_count" in stats
        assert "fixation_count" in stats
        assert stats["word_count"] == len(normalized_words_df)
        assert stats["fixation_count"] == len(normalized_fixations_df)

    def test_compute_trial_stats_with_dwell_time(self):
        words = pd.DataFrame(
            {
                "participant_id": ["p1"],
                "trial_id": ["t1"],
                "trial_dwell_time_ms": [5000],
            }
        )
        fixations = pd.DataFrame(
            {
                "participant_id": ["p1", "p1"],
                "trial_id": ["t1", "t1"],
                "duration_ms": [200, 250],
            }
        )
        stats = compute_trial_stats(words, fixations)
        assert stats["total_reading_time_ms"] == 5000

    def test_compute_trial_stats_empty_fixations(self, normalized_words_df):
        empty_fixations = pd.DataFrame()
        stats = compute_trial_stats(normalized_words_df, empty_fixations)
        assert stats["fixation_count"] == 0
        assert stats["total_reading_time_ms"] == 0


class TestGatherTrialMetadata:
    """Tests for gather_trial_metadata function."""

    def test_gather_trial_metadata_single_value(
        self, normalized_words_df, normalized_fixations_df
    ):
        normalized_words_df["difficulty_level"] = ["Adv", "Adv", "Adv"]
        metadata = gather_trial_metadata(
            normalized_words_df, normalized_fixations_df, ["difficulty_level"]
        )
        assert len(metadata) == 1
        assert metadata.iloc[0]["Field"] == "difficulty_level"
        assert "Adv" in str(metadata.iloc[0]["Value"])

    def test_gather_trial_metadata_numeric(
        self, normalized_words_df, normalized_fixations_df
    ):
        normalized_fixations_df["duration_ms"] = [200, 250, 180]
        metadata = gather_trial_metadata(
            normalized_words_df, normalized_fixations_df, ["duration_ms"]
        )
        assert len(metadata) == 1
        assert "mean" in str(metadata.iloc[0]["Value"]).lower()

    def test_gather_trial_metadata_missing_field(
        self, normalized_words_df, normalized_fixations_df
    ):
        metadata = gather_trial_metadata(
            normalized_words_df, normalized_fixations_df, ["nonexistent_field"]
        )
        assert len(metadata) == 0

    def test_gather_trial_metadata_multiple_fields(
        self, normalized_words_df, normalized_fixations_df
    ):
        normalized_words_df["difficulty_level"] = ["Adv", "Adv", "Adv"]
        normalized_fixations_df["pass_index"] = [1, 1, 1]
        metadata = gather_trial_metadata(
            normalized_words_df,
            normalized_fixations_df,
            ["difficulty_level", "pass_index"],
        )
        assert len(metadata) == 2


class TestBuildComparisonOptions:
    """Tests for _build_comparison_options function."""

    def test_build_comparison_options_text_mode(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t1"],
                "text_id": ["para1", "para1", "para1"],
            }
        )
        options = _build_comparison_options(combos, "Text", "p1", "t1", "para1")
        assert len(options) > 0
        # Should prioritize same participant, same text
        assert any("p1" in opt[2] for opt in options)

    def test_build_comparison_options_participant_mode(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p2", "p3"],
                "trial_id": ["t1", "t1", "t1"],
                "text_id": ["para1", "para1", "para2"],
            }
        )
        options = _build_comparison_options(combos, "Participant", "p1", "t1", "para1")
        assert len(options) > 0
        # Should prioritize same text, different participants
        assert any("para1" in opt[2] and "p2" in opt[2] for opt in options)

    def test_build_comparison_options_none_mode(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t1", "t1"],
                "text_id": ["para1", "para2"],
            }
        )
        options = _build_comparison_options(combos, "None", "p1", "t1", None)
        assert len(options) > 0
        # Should not include the primary trial
        assert not any(opt[0] == "p1" and opt[1] == "t1" for opt in options)

    def test_build_comparison_options_with_unique_text_id(self):
        combos = pd.DataFrame(
            {
                "participant_id": ["p1", "p2"],
                "trial_id": ["t1", "t1"],
                "unique_text_id": ["up1", "up1"],
            }
        )
        options = _build_comparison_options(combos, "Text", "p1", "t1", "up1")
        assert len(options) > 0


class _FakeSt:
    """Minimal stand-in for the ``streamlit`` module used by the Share helpers.

    ``_build_share_query`` / ``_apply_url_trial_selection`` only touch
    ``st.session_state`` and ``st.query_params`` (both dict-like), so swapping the
    module-level ``st`` for this lets us unit-test the link logic without a
    running Streamlit script.
    """

    def __init__(self):
        self.session_state = {}
        self.query_params = {}

    def warning(self, *args, **kwargs):  # noqa: D102 - no-op stand-in
        pass


@pytest.fixture
def fake_st(monkeypatch):
    fake = _FakeSt()
    # The share/deep-link helpers live in url_state now; patch its module-level
    # `st` (and app's, for any app-side callers) so the link logic runs headless.
    from scanpath_studio import url_state as url_state_module

    monkeypatch.setattr(app_module, "st", fake)
    monkeypatch.setattr(url_state_module, "st", fake)
    return fake


class TestBuildShareQuery:
    """The Share button's deep-link builder (inverse of the URL preset parser)."""

    def test_demo_source_selection_and_toggles(self, fake_st):
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p1", "trial_id": "t3"},
            "global_show_saccades": True,
            "global_show_heatmap": False,
            "global_fixation_colorscale": "Viridis",
            "single_animate": True,
        }
        query, caveats = _build_share_query(DEMO_CHOICE)
        parsed = parse_qs(query)
        assert parsed["source"] == ["demo"]
        assert parsed["participant"] == ["p1"]
        assert parsed["trial_id"] == ["t3"]
        # A layer left ON is shared as 1, a layer turned OFF as 0 (not dropped).
        assert parsed["show_saccades"] == ["1"]
        assert parsed["show_heatmap"] == ["0"]
        assert parsed["fixation_colorscale"] == ["Viridis"]
        assert parsed["tab"] == ["animation"]
        assert caveats == []

    def test_uploaded_source_warns_and_omits_source(self, fake_st):
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p1", "trial_id": "t1"},
        }
        query, caveats = _build_share_query(UPLOAD_CHOICE)
        parsed = parse_qs(query)
        # An uploaded dataset can't be rebuilt from a URL — no source param, and
        # the user is warned, but the selection/settings still go in the link.
        assert "source" not in parsed
        assert parsed["trial_id"] == ["t1"]
        assert len(caveats) == 1

    def test_no_selection_yields_settings_only(self, fake_st):
        fake_st.session_state = {"global_show_words": True}
        query, _ = _build_share_query(DEMO_CHOICE)
        parsed = parse_qs(query)
        assert "participant" not in parsed
        assert "trial_id" not in parsed
        assert parsed["show_words"] == ["1"]

    def test_serializes_full_viz_panel_and_round_trips(self, fake_st):
        # The whole Visualization-controls panel must travel in the link (not just
        # a handful of toggles) and survive a build → apply round-trip.
        fake_st.session_state = {
            "_share_selection": {"participant_id": "p1", "trial_id": "t3"},
            "global_show_words": False,
            "global_hollow_fixations": True,
            "global_show_saccade_arrows": True,
            "global_saccade_style": "Dashed",
            "global_saccade_color": "#123456",
            "global_saccade_width": 4.5,
            "global_text_color": "#0a0b0c",
            "global_highlight_text_color": "#fedcba",
            "global_color_by": "duration_ms",
            "global_heatmap_style": "Interpolated",
            "global_marker_size_range": (10, 30),
            "global_order_font_size": 18,
            "global_line_spacing": 2.5,
            "global_scale_text_to_boxes": False,
        }
        query, _ = _build_share_query(DEMO_CHOICE)
        parsed = parse_qs(query)
        assert parsed["hollow_fixations"] == ["1"]
        assert parsed["show_saccade_arrows"] == ["1"]
        assert parsed["saccade_style"] == ["Dashed"]
        assert parsed["saccade_color"] == ["#123456"]
        assert parsed["saccade_width"] == ["4.5"]
        assert parsed["text_color"] == ["#0a0b0c"]
        assert parsed["highlight_text_color"] == ["#fedcba"]
        assert parsed["color_by"] == ["duration_ms"]
        assert parsed["heatmap_style"] == ["Interpolated"]
        assert parsed["marker_size_range"] == ["10,30"]
        assert parsed["order_font_size"] == ["18"]
        assert parsed["line_spacing"] == ["2.5"]
        assert parsed["scale_text_to_boxes"] == ["0"]

        # Apply the same link into a fresh session → settings restored.
        fake_st.session_state = {}
        fake_st.query_params = {k: v[0] for k, v in parsed.items()}
        _apply_url_preset()
        ss = fake_st.session_state
        assert ss["global_show_words"] is False
        assert ss["global_hollow_fixations"] is True
        assert ss["global_show_saccade_arrows"] is True
        assert ss["global_saccade_style"] == "Dashed"
        assert ss["global_saccade_color"] == "#123456"
        assert ss["global_saccade_width"] == 4.5
        assert ss["global_text_color"] == "#0a0b0c"
        assert ss["global_highlight_text_color"] == "#fedcba"
        assert ss["global_color_by"] == "duration_ms"
        assert ss["global_heatmap_style"] == "Interpolated"
        assert ss["global_marker_size_range"] == (10, 30)
        assert ss["global_order_font_size"] == 18
        assert ss["global_line_spacing"] == 2.5
        assert ss["global_scale_text_to_boxes"] is False

    def test_out_of_bounds_url_values_are_clamped(self, fake_st):
        # A hand-crafted link with out-of-range values must NOT reach the widget
        # unclamped (Streamlit would raise on render). Clamp to widget bounds.
        fake_st.query_params = {
            "marker_size_range": "1,99",  # widget bounds [4, 40]
            "line_spacing": "999",  # bounds [1.0, 10.0]
            "saccade_width": "99",  # bounds [0.5, 10.0]
            "order_font_size": "1000",  # bounds [6, 72]
        }
        _apply_url_preset()
        ss = fake_st.session_state
        assert ss["global_marker_size_range"] == (4, 40)
        assert ss["global_line_spacing"] == 10.0
        assert ss["global_saccade_width"] == 10.0
        assert ss["global_order_font_size"] == 72

    def test_malformed_range_url_value_is_skipped(self, fake_st):
        # Malformed range params are caught and skipped (no crash, key not set).
        fake_st.query_params = {
            "marker_size_range": "notarange",
            "fixation_color_range": "10",  # only one value
        }
        _apply_url_preset()  # must not raise
        ss = fake_st.session_state
        assert "global_marker_size_range" not in ss
        assert "global_fixation_color_range" not in ss


class TestApplyUrlTrialSelection:
    """The ``?trial_id=`` deep link → trial-picker seeding (applied once)."""

    def _combos(self):
        return pd.DataFrame(
            {
                "participant_id": ["p1", "p1", "p2"],
                "trial_id": ["t1", "t2", "t3"],
            }
        )

    def test_lands_on_exact_trial_id(self, fake_st):
        fake_st.query_params = {"participant": "p1", "trial_id": "t2"}
        _apply_url_trial_selection(self._combos())
        assert fake_st.session_state["single_select_trial_mode"] == "Trial"
        assert fake_st.session_state["single_trial_id"] == "t2"
        assert fake_st.session_state["_url_trial_applied"] is True

    def test_seeds_every_selection_prefix(self, fake_st):
        # Both the Scanpath ("single") and Generations ("multi") pickers must be
        # seeded, or switching tabs after following a link lands on a different
        # trial (mirrors the _SELECTION_PREFIXES loop in _apply_url_preset).
        fake_st.query_params = {"trial_id": "t2"}
        _apply_url_trial_selection(self._combos())
        assert fake_st.session_state["single_trial_id"] == "t2"
        assert fake_st.session_state["multi_trial_id"] == "t2"

    def test_trial_id_alone_without_participant(self, fake_st):
        # A ?trial_id= link with no ?participant= must still land on the trial.
        fake_st.query_params = {"trial_id": "t3"}
        _apply_url_trial_selection(self._combos())
        assert fake_st.session_state["single_trial_id"] == "t3"
        assert fake_st.session_state["_url_trial_applied"] is True

    def test_noop_without_trial_id(self, fake_st):
        fake_st.query_params = {}
        _apply_url_trial_selection(self._combos())
        assert "single_trial_id" not in fake_st.session_state

    def test_unknown_trial_id_does_not_burn_guard(self, fake_st):
        # A trial id absent from combos must NOT stamp the once-flag, so a later
        # rerun (e.g. once an async shard finishes loading) can still land it.
        fake_st.query_params = {"trial_id": "nope"}
        _apply_url_trial_selection(self._combos())
        assert "single_trial_id" not in fake_st.session_state
        assert "_url_trial_applied" not in fake_st.session_state

    def test_applies_only_once(self, fake_st):
        # Once applied, a later rerun must not re-seed the picker (so the user's
        # in-app navigation after following the link sticks).
        fake_st.query_params = {"trial_id": "t2"}
        fake_st.session_state = {"_url_trial_applied": True, "single_trial_id": "t9"}
        _apply_url_trial_selection(self._combos())
        assert fake_st.session_state["single_trial_id"] == "t9"
