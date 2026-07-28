"""Structural smoke tests for the Corpus Analysis figure builders (AN-1 … AN-22).

One test per figure the Corpus Analysis view can draw, each built from the
bundled OneStop demo through the real ``aggregation.py`` helper that feeds it in
``tabs.py`` — so a change that breaks the aggregation→figure contract fails here
rather than in the browser. Assertions are structural (trace count and type,
axis/colorbar titles, bar counts derived from the input frame), not pixel
snapshots. The aggregation values themselves are pinned in
``tests/test_aggregation.py``.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import plots
from scanpath_studio.aggregation import (
    MEASURES,
    available_features,
    cohort_word_profile,
    ensure_fixation_enrichment,
    group_word_difference,
    grouped_metric_values,
    landing_positions,
    metric_by_trial_index,
    paired_group_summary,
    per_participant_trend,
    per_reader_word_measure,
    progressive_regressive_counts,
    reader_vs_cohort_values,
    saccade_vs_duration,
    two_group_word_profiles,
    word_box_aggregate,
    word_measure_vs_feature,
    word_rate_profile,
)
from scanpath_studio.constants import DEFAULT_MARKER_SIZE_RANGE
from scanpath_studio.data import (
    derive_trial_index,
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)

# Canvas/font args every analysis builder takes.
_FW = dict(canvas_width=700, base_font_size=12, font_family="Arial")

_TFD = MEASURES["tfd"]
_FIX_DUR = MEASURES["fix_dur"]
_SACC = MEASURES["sacc_amp"]


@pytest.fixture(scope="module")
def demo():
    """The bundled demo, normalized once, plus the text/reader each view uses."""
    words_raw, fixations_raw = load_sample_data()
    words = normalize_words(words_raw, infer_word_schema(words_raw))
    fixations = normalize_fixations(fixations_raw, infer_fix_schema(fixations_raw))
    fixations = ensure_fixation_enrichment(fixations, words)
    text_col = next(
        c
        for c in ("unique_text_id", "text_id", "unique_paragraph_id")
        if c in words.columns
    )
    text_id = words[text_col].iloc[0]
    participant = fixations["participant_id"].iloc[0]
    # `per_reader_word_measure` sorts its rows by participant, so the panel /
    # row order downstream is the sorted reader list.
    readers = sorted(
        str(p)
        for p in pd.unique(words.loc[words[text_col] == text_id, "participant_id"])
    )
    assert len(readers) >= 2, "the demo text needs several readers for these views"
    return SimpleNamespace(
        words=words,
        fixations=fixations,
        text_col=text_col,
        text_id=text_id,
        participant=participant,
        readers=readers,
    )


class TestLegacyTrendFigures:
    """The trial-index / fixation-index trends (``metric_by_*_index``)."""

    def test_trend_figure_band_and_line(self, demo):
        fx = demo.fixations.assign(trial_index=derive_trial_index(demo.fixations))
        df = metric_by_trial_index(fx, "duration_ms")
        assert not df.empty
        fig = plots.make_trend_figure(
            df,
            x_col="trial_index",
            y_label="Fixation duration (ms)",
            title="Duration by trial index",
            **_FW,
        )
        # Exactly two traces: the ±SEM envelope, then the line on top of it.
        assert [t.type for t in fig.data] == ["scatter", "scatter"]
        band, line = fig.data
        assert band.fill == "toself" and band.showlegend is False
        assert len(band.x) == 2 * len(df)  # forward then reversed
        assert line.mode == "lines+markers"
        assert list(line.x) == list(df["trial_index"])
        assert fig.layout.xaxis.title.text == "Trial Index"
        assert fig.layout.yaxis.title.text == "Fixation duration (ms)"

    def test_per_participant_lines_overlay_the_trend(self, demo):
        """The Groups subtab's "Per-reader behind" overlay (AN-17)."""
        fx = demo.fixations.assign(trial_index=derive_trial_index(demo.fixations))
        fig = plots.make_trend_figure(
            metric_by_trial_index(fx, "duration_ms"),
            x_col="trial_index",
            y_label="Fixation duration (ms)",
            title="Duration by trial index",
            **_FW,
        )
        per = per_participant_trend(fx, "duration_ms")
        readers = sorted(str(p) for p in pd.unique(per["participant_id"]))
        assert readers == sorted(
            str(p) for p in pd.unique(demo.fixations["participant_id"])
        )
        for rdr, grp in per.groupby("participant_id"):
            fig.add_scatter(x=grp["trial_index"], y=grp["value"], mode="lines")
        # Band + cohort line + one faint line per reader.
        assert len(fig.data) == 2 + len(readers)

    def test_aggregated_histogram_shares_bin_edges(self, demo):
        groups, dropped = grouped_metric_values(
            demo.fixations, "duration_ms", "difficulty_level"
        )
        assert dropped == 0 and set(groups) == {"Adv", "Ele"}
        fig = plots.make_aggregated_histogram(
            groups, metric_label="Fixation duration (ms)", bins=25, **_FW
        )
        assert [t.type for t in fig.data] == ["bar", "bar"]
        assert [t.name for t in fig.data] == ["Adv", "Ele"]
        # One shared set of bin centres, so the overlaid series line up.
        np.testing.assert_array_equal(fig.data[0].x, fig.data[1].x)
        assert len(fig.data[0].x) == 25
        # Binning is server-side: every value lands in a bin, none are dropped.
        for trace, name in zip(fig.data, ("Adv", "Ele")):
            assert int(np.sum(trace.y)) == groups[name].size
        assert fig.layout.barmode == "overlay"
        assert fig.layout.xaxis.title.text == "Fixation duration (ms)"
        assert fig.layout.yaxis.title.text == "Count"


class TestPerTextFigures:
    def test_small_multiples_one_panel_per_reader(self, demo):
        per = per_reader_word_measure(demo.words, demo.text_col, demo.text_id, _TFD)
        cohort = cohort_word_profile(demo.words, demo.text_col, demo.text_id, _TFD)[
            ["word_id", "value"]
        ]
        n = len(demo.readers)
        fig = plots.make_small_multiples_figure(
            per, measure_label=_TFD.axis_label, cohort=cohort, **_FW
        )
        # Per panel: the faint cohort overlay, then that reader's profile.
        assert len(fig.data) == 2 * n
        assert [t.name for t in fig.data[1::2]] == demo.readers
        assert all(t.name == "Cohort mean" for t in fig.data[0::2])
        # The cohort overlay is legended once, not once per panel.
        assert sum(bool(t.showlegend) for t in fig.data[0::2]) == 1
        # Reading order is on the bottom panel's axis only.
        assert fig.layout[f"xaxis{n}"].title.text == "Word (reading order)"
        assert _TFD.axis_label in fig.layout.title.text

    def test_small_multiples_reports_the_panel_cap(self, demo):
        per = per_reader_word_measure(demo.words, demo.text_col, demo.text_id, _TFD)
        fig = plots.make_small_multiples_figure(
            per, measure_label=_TFD.axis_label, max_panels=2, **_FW
        )
        assert len(fig.data) == 2  # no cohort overlay → one trace per panel
        assert f"showing 2 of {len(demo.readers)} readers" in fig.layout.title.text

    def test_word_matrix_heatmap(self, demo):
        per = per_reader_word_measure(demo.words, demo.text_col, demo.text_id, _TFD)
        n_words = per["word_id"].nunique()
        fig = plots.make_word_matrix_heatmap(
            per, row_col="participant_id", measure_label=_TFD.axis_label, **_FW
        )
        assert [t.type for t in fig.data] == ["heatmap"]
        hm = fig.data[0]
        assert np.asarray(hm.z).shape == (len(demo.readers), n_words)
        assert set(hm.y) == set(demo.readers)
        assert hm.colorbar.title.text == _TFD.axis_label
        assert fig.layout.xaxis.title.text == "Word (reading order)"
        # Readers read top-to-bottom, so the y axis is flipped.
        assert fig.layout.yaxis.autorange == "reversed"

    def test_word_matrix_heatmap_row_order(self, demo):
        per = per_reader_word_measure(demo.words, demo.text_col, demo.text_id, _TFD)
        pinned = list(reversed(demo.readers))
        fig = plots.make_word_matrix_heatmap(
            per,
            row_col="participant_id",
            measure_label=_TFD.axis_label,
            row_order=pinned,
            **_FW,
        )
        assert list(fig.data[0].y) == pinned

    def test_word_profile_single_and_overlaid(self, demo):
        prof = cohort_word_profile(
            demo.words, demo.text_col, demo.text_id, _TFD, spread="SD"
        )
        fig = plots.make_word_profile_figure(
            {"Cohort": prof}, measure_label=_TFD.axis_label, spread_label="SD", **_FW
        )
        # Band + mean line; a lone cohort needs no legend.
        assert [t.type for t in fig.data] == ["scatter", "scatter"]
        assert fig.data[0].fill == "toself"
        assert len(fig.data[0].x) == 2 * len(prof)
        assert list(fig.data[1].x) == list(prof.sort_values("word_id")["word_id"])
        assert fig.layout.showlegend is False
        assert "cohort mean ± SD" in fig.layout.title.text
        assert fig.layout.xaxis.title.text == "Word (reading order)"
        assert fig.layout.yaxis.title.text == _TFD.axis_label

        two = plots.make_word_profile_figure(
            {"A": prof, "B": prof}, measure_label=_TFD.axis_label, **_FW
        )
        assert len(two.data) == 4  # two bands + two lines
        assert [t.name for t in two.data[1::2]] == ["A", "B"]
        assert two.layout.showlegend is True

    def test_word_profile_without_a_band(self, demo):
        prof = cohort_word_profile(demo.words, demo.text_col, demo.text_id, _TFD)
        fig = plots.make_word_profile_figure(
            {"Cohort": prof[["word_id", "value"]]},
            measure_label=_TFD.axis_label,
            **_FW,
        )
        assert len(fig.data) == 1  # no lo/hi → line only

    def test_feature_scatter_numeric(self, demo):
        feats = available_features(demo.words)
        assert "GPT-2 surprisal" in feats, "the OneStop demo ships surprisal"
        col, categorical = feats["GPT-2 surprisal"]
        assert categorical is False
        df = word_measure_vs_feature(demo.words, demo.text_col, demo.text_id, _TFD, col)
        fig = plots.make_feature_scatter_figure(
            df,
            measure_label=_TFD.axis_label,
            feature_label="GPT-2 surprisal",
            categorical=False,
            **_FW,
        )
        # Word cloud + the OLS trend line, with Pearson r reported in the title.
        assert [t.type for t in fig.data] == ["scatter", "scatter"]
        assert fig.data[0].mode == "markers"
        assert len(fig.data[0].x) == len(df)
        assert fig.data[1].line.dash == "dash"
        assert "r = " in fig.layout.title.text
        assert f"n = {len(df)}" in fig.layout.title.text
        assert fig.layout.xaxis.title.text == "GPT-2 surprisal"
        assert fig.layout.yaxis.title.text == _TFD.axis_label

    def test_feature_scatter_categorical(self, demo):
        col, categorical = available_features(demo.words)["Part of speech"]
        assert categorical is True
        df = word_measure_vs_feature(demo.words, demo.text_col, demo.text_id, _TFD, col)
        cats = sorted(df["feature"].dropna().astype(str).unique())
        fig = plots.make_feature_scatter_figure(
            df,
            measure_label=_TFD.axis_label,
            feature_label="Part of speech",
            categorical=True,
            **_FW,
        )
        assert all(t.type == "box" for t in fig.data)
        assert [t.name for t in fig.data] == cats  # one box per POS tag, sorted
        assert fig.layout.showlegend is False
        assert fig.layout.xaxis.title.text == "Part of speech"

    def test_word_rate_figure(self, demo):
        rates = word_rate_profile(demo.words, demo.text_col, demo.text_id)
        fig = plots.make_word_rate_figure(rates, **_FW)
        assert [t.type for t in fig.data] == ["bar", "bar"]
        assert [t.name for t in fig.data] == ["Skip rate", "Regression-in rate"]
        assert len(fig.data[0].x) == len(rates)
        assert fig.layout.barmode == "group"
        assert fig.layout.yaxis.tickformat == ".0%"  # rates read as percentages
        assert fig.layout.xaxis.title.text == "Word (reading order)"

    def test_word_rate_figure_skips_absent_series(self, demo):
        rates = word_rate_profile(demo.words, demo.text_col, demo.text_id)
        fig = plots.make_word_rate_figure(
            rates.drop(columns=["regression_in_rate"]), **_FW
        )
        assert [t.name for t in fig.data] == ["Skip rate"]

    def test_word_difficulty_on_stimulus(self, demo):
        """AN-4: the aggregated frame tints the true-scale stimulus."""
        agg_words = word_box_aggregate(demo.words, demo.text_col, demo.text_id, _TFD)
        assert not agg_words.empty
        fig = plots.make_scanpath_figure(
            agg_words,
            pd.DataFrame(),
            canvas_width=900,
            canvas_height=600,
            base_font_size=12,
            font_family="Arial",
            x_field="x",
            y_field="y",
            show_words=True,
            show_word_labels=True,
            show_fixations=False,
            show_order=False,
            show_saccades=False,
            show_heatmap=True,
            color_by="value",
            heatmap_metric=None,
            marker_size_range=DEFAULT_MARKER_SIZE_RANGE,
            order_font_size=10,
            order_font_color="#111111",
            show_colorbars=True,
            fixation_color_range=None,
            heatmap_range=None,
            heatmap_style="Word boxes",
            word_heatmap_col="value",
            word_heatmap_title=_TFD.axis_label,
        )
        names = [t.name for t in fig.data]
        assert "words" in names  # the reading text, drawn as labels
        assert "heatmap colorbar" in names
        assert not any("fixation" in str(n).lower() for n in names)
        # One box shape per word, plus one tint per word that was actually read
        # — a zero-dwell word keeps its outline but stays uncoloured.
        shape_names = [s.name for s in fig.layout.shapes]
        assert sum("word_boxes" in str(n) for n in shape_names) == len(agg_words)
        read = int((pd.to_numeric(agg_words["value"], errors="coerce") > 0).sum())
        assert 0 < read < len(agg_words), "the demo text has some unread words"
        assert sum("heatmap" in str(n) for n in shape_names) == read
        colorbar = next(t for t in fig.data if t.name == "heatmap colorbar")
        assert colorbar.marker.colorbar.title.text == _TFD.axis_label


class TestPerReaderFigures:
    @pytest.mark.parametrize("kind,expected", [("violin", "violin"), ("box", "box")])
    def test_distribution_figure(self, demo, kind, expected):
        groups = reader_vs_cohort_values(demo.fixations, demo.participant, _FIX_DUR)
        assert set(groups) == {"This reader", "Cohort"}
        fig = plots.make_distribution_figure(
            groups, metric_label=_FIX_DUR.axis_label, kind=kind, **_FW
        )
        assert [t.type for t in fig.data] == [expected, expected]
        assert [t.name for t in fig.data] == ["This reader", "Cohort"]
        assert len(fig.data[0].y) == groups["This reader"].size
        assert fig.layout.yaxis.title.text == _FIX_DUR.axis_label
        assert fig.layout.showlegend is False

    def test_density_scatter(self, demo):
        df = saccade_vs_duration(demo.fixations, participant_id=demo.participant)
        fig = plots.make_density_scatter_figure(
            df,
            x_col="duration_ms",
            y_col="saccade_amplitude",
            x_label=_FIX_DUR.axis_label,
            y_label=_SACC.axis_label,
            **_FW,
        )
        assert [t.type for t in fig.data] == ["histogram2d"]
        assert len(fig.data[0].x) == len(df)
        assert f"n = {len(df)}" in fig.layout.title.text
        assert fig.layout.xaxis.title.text == _FIX_DUR.axis_label
        assert fig.layout.yaxis.title.text == _SACC.axis_label

    def test_progression_figure(self, demo):
        df = progressive_regressive_counts(
            demo.fixations, participant_id=demo.participant
        )
        assert not df.empty
        fig = plots.make_progression_figure(df, **_FW)
        assert [t.type for t in fig.data] == ["bar", "bar", "scatter"]
        assert [t.name for t in fig.data] == [
            "Progressive",
            "Regressive",
            "Regression share",
        ]
        assert len(fig.data[0].x) == len(df)
        assert fig.layout.barmode == "stack"  # counts stack to the trial total
        # The share rides a secondary axis pinned to 0–100 %.
        assert tuple(fig.layout.yaxis2.range) == (0, 1)
        assert fig.layout.yaxis2.tickformat == ".0%"

    def test_landing_curve(self, demo):
        vals = landing_positions(
            demo.words, demo.fixations, participant_id=demo.participant
        )
        assert vals.size and ((vals >= 0) & (vals <= 1)).all()
        fig = plots.make_landing_curve_figure(vals, **_FW)
        assert [t.type for t in fig.data] == ["histogram"]
        assert len(fig.data[0].x) == vals.size
        assert f"n = {vals.size}" in fig.layout.title.text
        assert "0 = start" in fig.layout.xaxis.title.text
        assert fig.layout.yaxis.title.text == "Count"

    def test_landing_curve_in_pixels(self, demo):
        px = landing_positions(
            demo.words,
            demo.fixations,
            participant_id=demo.participant,
            as_fraction=False,
        )
        # The px path is unclipped, so it carries real distances into the word
        # box rather than the 0–1 fractions of the default path.
        assert px.max() > 1.0
        fig = plots.make_landing_curve_figure(px, as_fraction=False, **_FW)
        assert len(fig.data[0].x) == px.size
        np.testing.assert_allclose(fig.data[0].x, px)
        assert "px" in fig.layout.xaxis.title.text


class TestGroupComparisonFigures:
    def test_paired_bars_one_subplot_per_measure(self, demo):
        df = paired_group_summary(
            demo.fixations,
            [_FIX_DUR, _SACC],
            {"difficulty_level": ["Adv"]},
            {"difficulty_level": ["Ele"]},
            words=demo.words,
            fixations=demo.fixations,
        )
        assert len(df) == 4  # 2 measures × 2 groups
        fig = plots.make_paired_bars_figure(df, **_FW)
        assert all(t.type == "bar" for t in fig.data)
        assert len(fig.data) == 4
        assert [a.text for a in fig.layout.annotations] == [
            _FIX_DUR.label,
            _SACC.label,
        ]
        # Each group is legended once, on the first subplot only.
        assert sum(bool(t.showlegend) for t in fig.data) == 2
        for trace in fig.data:
            assert trace.error_y.array[0] >= 0
            assert trace.error_y.arrayminus[0] >= 0

    def test_difference_profile(self, demo):
        diff = group_word_difference(
            demo.words,
            demo.text_col,
            demo.text_id,
            _TFD,
            {"participant_id": [demo.readers[0]]},
            {"participant_id": [demo.readers[1]]},
        )
        assert not diff.empty
        fig = plots.make_difference_profile_figure(
            diff,
            measure_label=_TFD.axis_label,
            label_a="Reader A",
            label_b="Reader B",
            **_FW,
        )
        assert [t.type for t in fig.data] == ["bar"]
        bar = fig.data[0]
        assert len(bar.x) == len(diff)
        # Diverging scale centred on zero so +/- differences read symmetrically.
        assert bar.marker.cmin == -bar.marker.cmax
        assert bar.marker.cmax == pytest.approx(
            float(np.nanmax(np.abs(diff["diff"].to_numpy())))
        )
        assert bar.marker.colorbar.title.text == "Reader A − Reader B"
        assert fig.layout.yaxis.title.text == f"Δ {_TFD.axis_label}"
        # A zero line separates "slower" from "faster".
        assert len(fig.layout.shapes) == 1

    def test_stacked_two_group_heatmap(self, demo):
        long = two_group_word_profiles(
            demo.words,
            demo.text_col,
            demo.text_id,
            _TFD,
            {"participant_id": [demo.readers[0]]},
            {"participant_id": [demo.readers[1]]},
            label_a="Group A",
            label_b="Group B",
        )
        fig = plots.make_word_matrix_heatmap(
            long,
            row_col="group",
            measure_label=_TFD.axis_label,
            row_order=["Group A", "Group B"],
            **_FW,
        )
        assert [t.type for t in fig.data] == ["heatmap"]
        assert list(fig.data[0].y) == ["Group A", "Group B"]
        assert np.asarray(fig.data[0].z).shape[0] == 2


class TestNoDataFallbacks:
    """Every builder degrades to a titled "(no data)" placeholder, never raises."""

    def test_empty_inputs(self):
        empty = pd.DataFrame()
        figs = [
            plots.make_trend_figure(
                empty, x_col="trial_index", y_label="y", title="Trend", **_FW
            ),
            plots.make_aggregated_histogram({}, metric_label="m", **_FW),
            plots.make_small_multiples_figure(empty, measure_label="m", **_FW),
            plots.make_word_matrix_heatmap(
                empty, row_col="participant_id", measure_label="m", **_FW
            ),
            plots.make_word_profile_figure({}, measure_label="m", **_FW),
            plots.make_feature_scatter_figure(
                empty,
                measure_label="m",
                feature_label="f",
                categorical=False,
                **_FW,
            ),
            plots.make_word_rate_figure(empty, **_FW),
            plots.make_distribution_figure({}, metric_label="m", **_FW),
            plots.make_density_scatter_figure(
                empty, x_col="a", y_col="b", x_label="a", y_label="b", **_FW
            ),
            plots.make_progression_figure(empty, **_FW),
            plots.make_paired_bars_figure(empty, **_FW),
            plots.make_landing_curve_figure(np.array([]), **_FW),
            plots.make_difference_profile_figure(empty, measure_label="m", **_FW),
        ]
        for fig in figs:
            assert len(fig.data) == 0
            assert "no data" in (fig.layout.title.text or "").lower()

    def test_all_nan_landing_values(self):
        fig = plots.make_landing_curve_figure(np.array([np.nan, np.nan]), **_FW)
        assert "no data" in (fig.layout.title.text or "").lower()
