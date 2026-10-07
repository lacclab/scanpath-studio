"""Where each legend sits (📐 Figure & canvas → Legends).

Each legend kind can be moved to a spot of its own, laid out as a stack or a
row and given a text size, on top of its layer's own show/hide switch. Auto
throughout draws the figure exactly as before. An outside spot grows the figure
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
        spec = parse_legend_spec("right,14,stacked")
        assert spec == {"position": "right", "arrangement": "stacked", "size": 14}
        full = normalize_legend_layout({"saccades": spec})["saccades"]
        assert parse_legend_spec(legend_spec_text(full)) == spec


class TestMovingTraceLegends:
    def test_auto_leaves_the_figure_untouched(self):
        fig = _figure()
        before = fig.to_dict()
        apply_legend_layout(fig, None)
        assert fig.to_dict() == before

    @pytest.mark.parametrize("position", ["above", "below", "left", "right"])
    def test_an_outside_spot_keeps_the_plot_region(self, position):
        fig = _figure()
        region = _plot_region(fig)
        apply_legend_layout(fig, {"saccades": {"position": position}})
        assert _plot_region(fig) == pytest.approx(region)
        assert {t.legend for t in fig.data if t.legendgroup == "saccade_type"} == {
            "legend3"
        }

    def test_inside_spots_do_not_grow_the_figure(self):
        fig = _figure()
        apply_legend_layout(fig, {"saccades": {"position": "bottom-left"}})
        assert (fig.layout.width, fig.layout.height) == (800, 600)
        assert fig.layout.legend3.xanchor == "left"
        assert fig.layout.legend3.yanchor == "bottom"

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
            {"compare": {"position": "left"}, "colors": {"position": "below"}},
            comparing=True,
        )
        by_name = {t.name: t.legend for t in fig.data}
        assert by_name["A · p1"] == by_name["B · p2"] == "legend2"
        assert by_name["line: 1"] == "legend4"
        # The saccade types were not moved: they stay in the default legend.
        assert by_name["forward"] is None

    def test_two_legends_on_one_side_do_not_overlap(self):
        fig = _figure(comparing=True)
        apply_legend_layout(
            fig,
            {"compare": {"position": "right"}, "saccades": {"position": "right"}},
            comparing=True,
        )
        assert fig.layout.legend2.y != fig.layout.legend3.y


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
            {"position": "left", "arrangement": "stacked", "size": 18},
            {"position": "top-left"},
            {"position": "below", "size": 14},
        ],
    )
    def test_the_circles_keep_their_true_size(self, spec):
        assert self._diameters(self._key({"size_key": spec})) == self._diameters(
            self._key()
        )

    def test_its_labels_take_the_text_size(self):
        fig = self._key({"size_key": {"position": "right", "size": 18}})
        assert {a.font.size for a in fig.layout.annotations} == {18}

    def test_an_outside_spot_keeps_the_plot_region(self):
        fig = self._key({"size_key": {"position": "right"}})
        assert _plot_region(fig) == pytest.approx((800, 600))
        assert fig.layout.margin.r > 0


class TestTheBuilders:
    def test_every_builder_takes_it(self):
        import scanpath_studio as sps

        words, fixations = sps.load_sample_data()
        (p1, t1), (p2, t2) = sps.list_trials(words, fixations).iloc[:2].values.tolist()
        layout = {
            "saccades": {"position": "right"},
            "size_key": {"position": "top-left"},
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
            legend_layout={"compare": {"position": "below"}},
        )
        assert any(t.legend == "legend2" for t in compare.data)


def _cli_parse(argv):
    from scanpath_studio.cli import _parse_legend_layout

    return _parse_legend_layout(argv)


class TestTheCli:
    def test_a_spec_per_flag(self):
        assert _cli_parse(["saccades=right,stacked,14", "size-key=below"]) == {
            "saccades": {"position": "right", "arrangement": "stacked", "size": 14},
            "size_key": {"position": "below"},
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
            "global_legend_saccades_position": "right",
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
        assert at.session_state["_params"] == {"legend_saccades": "right,stacked,14"}
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
            ("global_legend_compare_position", "left", "left"),
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
        assert record["legends"]["saccades"]["position"] == "right"
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
