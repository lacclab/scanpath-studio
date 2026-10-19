"""Where each legend sits (📐 Figure & canvas → Legends).

Each legend kind can be moved to a spot of its own, laid out as a stack or a
row and given a text size, on top of its layer's own show/hide switch. Auto
throughout keeps the default placement. An outside spot grows the figure
so the equal-aspect plot region — and the true-to-scale text — keeps its size.
"""

from __future__ import annotations

import plotly.graph_objects as go
import pytest

from scanpath_studio import plots
from scanpath_studio.plots import (
    apply_legend_layout,
    legend_spec_text,
    normalize_legend_layout,
    parse_legend_spec,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _plot_region(fig) -> tuple[float, float]:
    m = fig.layout.margin
    return (
        fig.layout.width - (m.l or 0) - (m.r or 0),
        fig.layout.height - (m.t or 0) - (m.b or 0),
    )


def _figure(*, comparing: bool = False) -> go.Figure:
    """A bare figure carrying one entry of each legend kind."""
    fig = go.Figure()
    for name in ("forward", "regression"):
        fig.add_trace(
            go.Scatter(x=[None], y=[None], name=name, legendgroup="saccade_type")
        )
    fig.add_trace(
        go.Scatter(x=[None], y=[None], name="line: 1", meta=plots._COLORS_LEGEND_META)
    )
    if comparing:
        for label in ("A · p1", "B · p2"):
            fig.add_trace(go.Scatter(x=[None], y=[None], name=label, legendgroup=label))
    fig.update_layout(width=800, height=600, margin=dict(l=0, r=0, t=60, b=0))
    return fig


class TestTheLayoutValue:
    def test_auto_everywhere_is_the_default(self):
        layout = normalize_legend_layout(None)
        assert set(layout) == set(plots.LEGEND_KINDS)
        assert all(not plots._legend_is_moved(spec) for spec in layout.values())

    @pytest.mark.parametrize(
        "bad",
        [
            {"sacades": {"position": "right"}},
            {"saccades": {"position": "middle"}},
            {"saccades": {"arrangement": "diagonal"}},
            {"saccades": {"size": 0}},
            {"saccades": {"colour": "red"}},
        ],
    )
    def test_a_typo_raises_rather_than_drawing_the_default(self, bad):
        with pytest.raises(ValueError):
            normalize_legend_layout(bad)

    def test_the_spec_text_round_trips(self):
        spec = parse_legend_spec("right-outside,14,stacked")
        assert spec == {
            "position": "right-outside",
            "arrangement": "stacked",
            "size": 14,
        }
        full = normalize_legend_layout({"saccades": spec})["saccades"]
        assert parse_legend_spec(legend_spec_text(full)) == spec

    def test_every_spot_is_offered_inside_and_outside(self):
        spots = {
            "top-left",
            "top-center",
            "top-right",
            "left",
            "right",
            "bottom-left",
            "bottom-center",
            "bottom-right",
        }
        assert set(plots.LEGEND_POSITIONS) == {"auto"} | {
            f"{spot}-{side}" for spot in spots for side in ("outside", "inside")
        }

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ("above", "top-right-outside"),
            ("below", "bottom-left-outside"),
            ("left", "left-outside"),
            ("right", "right-outside"),
            ("top-left", "top-left-inside"),
            ("bottom-right", "bottom-right-inside"),
        ],
    )
    def test_an_old_position_reads_as_its_spot(self, old, new):
        """Links, settings files and scripts written before the eight spots."""
        assert parse_legend_spec(old)["position"] == new
        layout = normalize_legend_layout({"colors": {"position": old}})
        assert layout["colors"]["position"] == new


class TestMovingTraceLegends:
    def test_auto_moves_no_entry_and_blackens_the_text(self):
        fig = _figure()
        before = [t.legend for t in fig.data]
        apply_legend_layout(fig, None)
        assert [t.legend for t in fig.data] == before
        assert fig.layout.legend.font.color == "#000000"
        assert "legend2" not in fig.to_dict()["layout"]

    @pytest.mark.parametrize(
        "position", [p for p in plots.LEGEND_POSITIONS if p.endswith("-outside")]
    )
    def test_an_outside_spot_keeps_the_plot_region(self, position):
        fig = _figure()
        region = _plot_region(fig)
        apply_legend_layout(fig, {"saccades": {"position": position}})
        assert _plot_region(fig) == pytest.approx(region)
        assert {t.legend for t in fig.data if t.legendgroup == "saccade_type"} == {
            "legend3"
        }

    @pytest.mark.parametrize(
        "position", [p for p in plots.LEGEND_POSITIONS if p.endswith("-inside")]
    )
    def test_inside_spots_do_not_grow_the_figure(self, position):
        fig = _figure()
        apply_legend_layout(fig, {"saccades": {"position": position}})
        # The plot keeps its size; only the default legend's strip can shrink.
        assert _plot_region(fig) == pytest.approx((800, 540))
        assert fig.layout.width == 800 and fig.layout.height <= 600
        legend = fig.layout.legend3
        assert 0 <= legend.x <= 1 and 0 <= legend.y <= 1

    @pytest.mark.parametrize(
        ("position", "xanchor", "yanchor", "x", "y"),
        [
            ("top-left-inside", "left", "top", 0, 1),
            ("top-center-inside", "center", "top", 0.5, 1),
            ("top-center-outside", "center", "bottom", 0.5, 1),
            ("bottom-right-outside", "right", "top", 1, 0),
            ("bottom-center-inside", "center", "bottom", 0.5, 0),
            ("left-outside", "right", "middle", 0, 0.5),
            ("left-inside", "left", "middle", 0, 0.5),
            ("right-outside", "left", "middle", 1, 0.5),
        ],
    )
    def test_each_spot_anchors_its_legend(self, position, xanchor, yanchor, x, y):
        fig = _figure()
        apply_legend_layout(fig, {"saccades": {"position": position}})
        legend = fig.layout.legend3
        assert (legend.xanchor, legend.yanchor) == (xanchor, yanchor)
        # An outside spot sits off the plot, on its own edge (past the default
        # legend, above it); along that edge it is where the spot says.
        if position.endswith("outside") and yanchor == "middle":
            assert (legend.x < 0) if x == 0 else (legend.x > 1)
            assert legend.y == pytest.approx(y)
        elif position.endswith("outside"):
            assert (legend.y > 1) if y == 1 else (legend.y < 0)
            assert legend.x == pytest.approx(x)
        else:
            assert legend.x == pytest.approx(x, abs=0.05)
            assert legend.y == pytest.approx(y, abs=0.05)

    def test_the_sides_run_down_and_the_middles_across(self):
        """Left and right stack down the side; top and bottom centre make a row."""
        fig = _figure(comparing=True)
        apply_legend_layout(
            fig,
            {
                "compare": {"position": "left-outside"},
                "saccades": {"position": "bottom-center-outside"},
                "colors": {"position": "right-inside"},
            },
            comparing=True,
        )
        assert fig.layout.legend2.orientation == "v"
        assert fig.layout.legend3.orientation == "h"
        assert fig.layout.legend4.orientation == "v"

    def test_arrangement_and_size_reach_the_legend(self):
        fig = _figure()
        apply_legend_layout(
            fig,
            {
                "saccades": {
                    "position": "right",
                    "arrangement": "side-by-side",
                    "size": 20,
                }
            },
        )
        assert fig.layout.legend3.orientation == "h"
        assert fig.layout.legend3.font.size == 20

    def test_compare_entries_are_told_from_the_colour_entries(self):
        fig = _figure(comparing=True)
        apply_legend_layout(
            fig,
            {
                "compare": {"position": "left-outside"},
                "colors": {"position": "bottom-left-outside"},
            },
            comparing=True,
        )
        by_name = {t.name: t.legend for t in fig.data}
        assert by_name["A · p1"] == by_name["B · p2"] == "legend2"
        assert by_name["line: 1"] == "legend4"
        # The saccade types were not moved: they stay in the default legend.
        assert by_name["forward"] is None

    @pytest.mark.parametrize(
        ("position", "axis"),
        [
            ("right-outside", "x"),
            ("left-inside", "x"),
            ("top-center-outside", "y"),
            ("bottom-right-inside", "y"),
        ],
    )
    def test_two_legends_on_one_spot_stack(self, position, axis):
        fig = _figure(comparing=True)
        apply_legend_layout(
            fig,
            {"compare": {"position": position}, "saccades": {"position": position}},
            comparing=True,
        )
        first, second = fig.layout.legend2, fig.layout.legend3
        assert getattr(first, axis) != getattr(second, axis)


class TestTheEmptyLegendStrip:
    """Once every entry has left the default legend, its strip above the plot
    goes too — the Compare overlay's as well as a single trial's."""

    def test_the_overlay_hands_its_strip_back(self):
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        (p1, t1), (p2, t2) = sps.list_trials(words, fixations).iloc[:2].values.tolist()
        kept = sps.compare_scanpaths(words, fixations, (p1, t1), (p2, t2))
        moved = sps.compare_scanpaths(
            words,
            fixations,
            (p1, t1),
            (p2, t2),
            legend_layout={"compare": {"position": "right-outside"}},
        )
        assert moved.layout.margin.t == 0
        assert _plot_region(moved) == pytest.approx(_plot_region(kept))

    def test_legends_above_stand_on_the_text_not_the_plot_edge(self):
        """The plot reaches past the text; a legend above it sits just over
        the topmost word or fixation instead of floating at the plot's edge."""
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        (p1, t1), (p2, t2) = sps.list_trials(words, fixations).iloc[:2].values.tolist()
        fig = sps.compare_scanpaths(
            words,
            fixations,
            (p1, t1),
            (p2, t2),
            legend_layout={"compare": {"position": "top-left-outside"}},
        )
        inset = plots._content_top_inset(fig)
        assert inset > 0
        _w, plot_h = _plot_region(fig)
        # The legend's bottom is a gap above the content's top, inside the plot.
        expected = 1.0 + (plots._LEGEND_GAP_PX - inset) / plot_h
        assert fig.layout.legend2.y == pytest.approx(expected)
        assert fig.layout.legend2.y < 1


class TestTheSizeKey:
    def _key(self, layout=None):
        fig = go.Figure()
        fig.update_layout(width=800, height=600, margin=dict(l=0, r=0, t=0, b=0))
        plots._add_duration_size_key(
            fig, (8, 24), "sqrt", (50.0, 600.0), legend_layout=layout
        )
        return fig

    @staticmethod
    def _diameters(fig):
        return sorted(
            round(float(s.x1) - float(s.x0), 6)
            for s in fig.layout.shapes
            if s.type == "circle"
        )

    def test_auto_is_inside_bottom_right(self):
        fig = self._key()
        circles = [s for s in fig.layout.shapes if s.type == "circle"]
        assert {(s.xanchor, s.yanchor) for s in circles} == {(1, 0)}
        assert all(float(s.x1) <= 0 and float(s.y0) >= 0 for s in circles)

    @pytest.mark.parametrize(
        "spec",
        [
            {"position": "left-outside", "arrangement": "stacked", "size": 18},
            {"position": "top-left-inside"},
            {"position": "bottom-center-outside", "size": 14},
            {"position": "right-inside"},
        ],
    )
    def test_the_circles_keep_their_true_size(self, spec):
        assert self._diameters(self._key({"size_key": spec})) == self._diameters(
            self._key()
        )

    def test_its_labels_take_the_text_size(self):
        fig = self._key({"size_key": {"position": "right-outside", "size": 18}})
        assert {a.font.size for a in fig.layout.annotations} == {18}

    def test_an_outside_spot_keeps_the_plot_region(self):
        fig = self._key({"size_key": {"position": "right-outside"}})
        assert _plot_region(fig) == pytest.approx((800, 600))
        assert fig.layout.margin.r > 0

    def test_centre_spots_centre_the_key(self):
        fig = self._key({"size_key": {"position": "top-center-inside"}})
        circles = [s for s in fig.layout.shapes if s.type == "circle"]
        assert {(s.xanchor, s.yanchor) for s in circles} == {(0.5, 1)}
        left = min(float(s.x0) for s in circles)
        right = max(float(s.x1) for s in circles)
        assert left < 0 < right

    def test_it_stacks_past_a_legend_on_its_spot(self):
        fig = _figure()
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        layout = {
            "saccades": {"position": "bottom-right-inside"},
            "size_key": {"position": "bottom-right-inside"},
        }
        apply_legend_layout(fig, layout)
        plots._add_duration_size_key(
            fig, (8, 24), "sqrt", (50.0, 600.0), legend_layout=layout
        )
        circles = [s for s in fig.layout.shapes if s.type == "circle"]
        # The legend holds the corner; the key sits above it.
        assert min(float(s.y0) for s in circles) > 20


class TestTheBuilders:
    def test_every_builder_takes_it(self):
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        (p1, t1), (p2, t2) = sps.list_trials(words, fixations).iloc[:2].values.tolist()
        layout = {
            "saccades": {"position": "right-outside"},
            "size_key": {"position": "top-left-inside"},
        }
        static = sps.plot_scanpath(
            words,
            fixations,
            p1,
            t1,
            saccade_color_mode="By type",
            saccade_type_legend=True,
            legend_layout=layout,
        )
        assert any(t.legend == "legend3" for t in static.data)
        anim = sps.animate_scanpath(words, fixations, p1, t1, legend_layout=layout)
        assert any(s.type == "circle" and s.yanchor == 1 for s in anim.layout.shapes), (
            "the size key went to the top-left corner"
        )
        compare = sps.compare_scanpaths(
            words,
            fixations,
            (p1, t1),
            (p2, t2),
            legend_layout={"compare": {"position": "bottom-center-outside"}},
        )
        assert any(t.legend == "legend2" for t in compare.data)


def _cli_parse(argv):
    from scanpath_studio.cli import _parse_legend_layout

    return _parse_legend_layout(argv)


class TestTheCli:
    def test_a_spec_per_flag(self):
        assert _cli_parse(["saccades=right-outside,stacked,14", "size-key=below"]) == {
            "saccades": {
                "position": "right-outside",
                "arrangement": "stacked",
                "size": 14,
            },
            "size_key": {"position": "bottom-left-outside"},
        }

    def test_a_bad_spec_is_refused(self):
        with pytest.raises(SystemExit):
            _cli_parse(["saccades=middle"])


def _link_round_trip_app():
    from urllib.parse import parse_qs

    import streamlit as st

    from scanpath_studio.url_state import _apply_url_legends, _legend_query

    for key, value in st.session_state["_given"].items():
        st.session_state[key] = value
    params: dict = {}
    _legend_query(params)
    st.session_state["_params"] = params
    for key in list(st.session_state["_given"]):
        del st.session_state[key]
    _apply_url_legends(
        {
            k: v[0]
            for k, v in parse_qs(
                "&".join(f"{k}={v}" for k, v in params.items())
            ).items()
        }
    )


class TestTheLink:
    def test_only_moved_legends_travel_and_they_round_trip(self):
        given = {
            "global_legend_saccades_position": "right-outside",
            "global_legend_saccades_arrangement": "stacked",
            "global_legend_saccades_size": 14,
            "global_legend_compare_position": "auto",
            "global_legend_compare_arrangement": "auto",
            "global_legend_compare_size": None,
        }
        at = AppTest.from_function(_link_round_trip_app)
        at.session_state["_given"] = given
        at.run(timeout=30)
        assert not at.exception, at.exception
        assert at.session_state["_params"] == {
            "legend_saccades": "right-outside,stacked,14"
        }
        for key in (
            "global_legend_saccades_position",
            "global_legend_saccades_arrangement",
            "global_legend_saccades_size",
        ):
            assert at.session_state[key] == given[key]


class TestStoredValues:
    """Designs and the recovery cache go through `sanitize_session_value`."""

    def test_the_two_lists_of_kinds_agree(self):
        from scanpath_studio import session_keys
        from scanpath_studio.constants import LEGEND_KINDS

        assert session_keys.LEGEND_KIND_NAMES == LEGEND_KINDS

    @pytest.mark.parametrize(
        ("key", "value", "expected"),
        [
            ("global_legend_saccades_size", 999, 72),
            ("global_legend_saccades_size", 2, 6),
            ("global_legend_saccades_size", None, None),
            ("global_legend_compare_position", "left-inside", "left-inside"),
            ("global_legend_compare_position", "left", "left-outside"),
            ("global_legend_size_key_arrangement", "stacked", "stacked"),
        ],
    )
    def test_a_stored_value_is_clamped_or_kept(self, key, value, expected):
        from scanpath_studio.url_state import sanitize_session_value

        assert sanitize_session_value(key, value) == expected

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("global_legend_compare_position", "bogus"),
            ("global_legend_colors_arrangement", "diagonal"),
            ("global_legend_colors_size", True),
        ],
    )
    def test_a_stored_value_outside_the_vocabulary_is_refused(self, key, value):
        from scanpath_studio.url_state import sanitize_session_value

        with pytest.raises((ValueError, TypeError)):
            sanitize_session_value(key, value)

    def test_the_export_record_lists_every_legend(self):
        from scanpath_studio import export

        record = export._plot_config_dict(
            "p1",
            "t1",
            800,
            600,
            "x",
            "y",
            {"legend_layout": {"saccades": {"position": "right"}}},
        )
        assert set(record["legends"]) == set(plots.LEGEND_KINDS)
        assert record["legends"]["saccades"]["position"] == "right-outside"
        assert record["legends"]["compare"]["position"] == "auto"


def _linked_keys_app():
    import streamlit as st

    from scanpath_studio.url_state import linked_state_keys

    st.query_params["legend_saccades"] = "right"
    st.session_state["_linked"] = sorted(linked_state_keys())


def test_a_linked_legend_counts_as_a_departure_from_the_design():
    at = AppTest.from_function(_linked_keys_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert {
        "global_legend_saccades_position",
        "global_legend_saccades_arrangement",
        "global_legend_saccades_size",
    } <= set(at.session_state["_linked"])


class TestTheColourLegendSwitch:
    def test_off_hides_only_the_colour_entries(self):
        fig = _figure()
        apply_legend_layout(fig, None, show_colors=False)
        shown = {t.name: t.showlegend for t in fig.data}
        assert shown["line: 1"] is False
        assert shown["forward"] is not False


def _drawn_app():
    import streamlit as st

    from scanpath_studio.controls import _legends_drawn

    for key, value in st.session_state["_given"].items():
        st.session_state[key] = value
    st.session_state["_drawn"] = _legends_drawn(
        show_fix=True,
        show_saccades=True,
        animating=st.session_state.get("_animating", False),
        comparing=st.session_state.get("_comparing", False),
        numeric_fields=["duration_ms"],
    )


def _drawn(given, **flags):
    at = AppTest.from_function(_drawn_app)
    at.session_state["_given"] = given
    for key, value in flags.items():
        at.session_state[key] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    return at.session_state["_drawn"]


class TestOnlyTheLegendsDrawnGetARow:
    def test_a_plain_figure_has_only_the_size_key(self):
        assert _drawn({"global_color_by": "duration_ms"}) == ["size_key"]

    def test_a_highlight_adds_the_fixation_colours(self):
        drawn = _drawn({"global_fixclass_short_mode": "Highlight"})
        assert "colors" in drawn

    def test_a_categorical_colour_adds_them_too(self):
        assert "colors" in _drawn({"global_color_by": "line"})

    def test_saccade_types_only_on_the_static_figure(self):
        by_type = {"global_saccade_color_mode": "By type"}
        assert "saccades" in _drawn(by_type)
        assert "saccades" not in _drawn(by_type, _animating=True)
        assert "saccades" not in _drawn(by_type, _comparing=True)

    def test_compare_only_while_comparing(self):
        assert "compare" not in _drawn({})
        assert "compare" in _drawn({}, _comparing=True)

    def test_a_relative_scale_has_no_size_key(self):
        assert "size_key" not in _drawn({"global_marker_size_scale": "relative"})


class TestTheContentTop:
    """A legend above the plot stands on the top of the highest marker, not its
    centre — on the centre, its background would wash out the top of that
    fixation."""

    @staticmethod
    def _inset(size):
        fig = go.Figure(
            go.Scatter(x=[100], y=[100], mode="markers", marker={"size": size})
        )
        fig.update_layout(
            width=800,
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            yaxis={"range": [600, 0]},
        )
        return plots._content_top_inset(fig)

    def test_a_markers_radius_counts(self):
        assert self._inset(0) == pytest.approx(100)
        assert self._inset(40) == pytest.approx(80)

    def test_a_marker_at_the_edge_leaves_no_inset(self):
        assert self._inset(400) == 0


class TestTheSizeKeyAboveThePlot:
    """A size key above the plot sits right on the screen's top line, wherever
    the text and the other legends are."""

    @staticmethod
    def _key(y, size=10, layout=None):
        fig = go.Figure(
            go.Scatter(x=[780], y=[y], mode="markers", marker={"size": size})
        )
        fig.update_layout(
            width=800,
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis={"range": [0, 800]},
            yaxis={"range": [600, 0]},
        )
        layout = layout or {"size_key": {"position": "top-right-outside"}}
        apply_legend_layout(fig, layout)
        plots._add_duration_size_key(
            fig, (8, 24), "sqrt", (50.0, 600.0), legend_layout=layout
        )
        return fig

    @staticmethod
    def _lowest_text(fig):
        return min(
            float(a.yshift) - float(a.font.size) / 2
            for a in fig.layout.annotations
            if a.name == plots._SIZE_KEY_NAME
        )

    @pytest.mark.parametrize("y", [5, 100, 400])
    def test_its_labels_stand_right_on_the_line(self, y):
        assert self._lowest_text(self._key(y)) == pytest.approx(
            plots._SIZE_KEY_LINE_GAP_PX
        )

    def test_a_legend_beside_it_does_not_move_it(self):
        fig = self._key(
            300,
            layout={
                "compare": {"position": "top-left-outside"},
                "size_key": {"position": "top-right-outside"},
            },
        )
        assert self._lowest_text(fig) == pytest.approx(plots._SIZE_KEY_LINE_GAP_PX)

    def test_the_figure_grows_to_hold_it(self):
        fig = self._key(300)
        assert fig.layout.margin.t > 0
        assert _plot_region(fig) == pytest.approx((800, 600))


class TestTheHighlightNote:
    """The note naming the highlighted words is a Legends row of its own:
    Show hides it, Position moves it, Text size sizes it; Auto leaves it in
    the plot's bottom-left corner."""

    @staticmethod
    def _fig():
        fig = _figure()
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        plots._add_highlight_key(fig, "is_in_aspan", "#d55e00")
        return fig

    @staticmethod
    def _notes(fig):
        return [
            a for a in fig.layout.annotations if a.name == plots._HIGHLIGHT_KEY_NAME
        ]

    def test_auto_leaves_it_where_it_was(self):
        fig = self._fig()
        before = self._notes(fig)[0].to_plotly_json()
        apply_legend_layout(fig, None)
        assert self._notes(fig)[0].to_plotly_json() == before

    def test_show_off_removes_it(self):
        fig = self._fig()
        apply_legend_layout(fig, None, show_highlight=False)
        assert self._notes(fig) == []

    def test_a_spot_moves_it_and_a_size_sizes_it(self):
        fig = self._fig()
        apply_legend_layout(
            fig, {"highlight": {"position": "top-center-outside", "size": 16}}
        )
        (note,) = self._notes(fig)
        assert (note.x, note.xanchor, note.yanchor) == (0.5, "center", "bottom")
        assert note.font.size == 16
        assert _plot_region(fig) == pytest.approx((800, 600))

    def test_every_builder_honours_the_switch(self):
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        p, t = sps.list_trials(words, fixations).iloc[0].tolist()
        kwargs = dict(highlight_column="is_in_aspan")
        drawn = sps.plot_scanpath(words, fixations, p, t, **kwargs)
        hidden = sps.plot_scanpath(
            words, fixations, p, t, show_highlight_legend=False, **kwargs
        )
        assert self._notes(drawn) and not self._notes(hidden)


def test_a_compare_legend_that_wraps_grows_its_band_instead_of_covering_the_text():
    """Two labels too long for one row wrap to two; the band above the plot
    grows to hold them, the plot region keeping its size, so Plotly has no
    reason to push the legend down onto the text."""
    import scanpath_studio as sps

    words, fixations = sps.load_sample_data()
    a = ("l37_1129", "l37_1129_2_2_1_Adv")
    b = ("l7_1090", "l7_1090_2_2_1_Adv")
    short = sps.compare_scanpaths(words, fixations, a, b, labels=("A", "B"))
    long = sps.compare_scanpaths(
        words,
        fixations,
        a,
        b,
        labels=(
            "A very long custom label naming the first reading in detail",
            "And another very long custom label for reading B",
        ),
    )
    assert _plot_region(long) == _plot_region(short)
    assert long.layout.margin.t > short.layout.margin.t
    # The legend stands on the text's top: the margin plus the gap down to the
    # text has room for every row.
    room = long.layout.margin.t + plots._content_top_inset(long)
    assert room >= plots._default_legend_height(long)
