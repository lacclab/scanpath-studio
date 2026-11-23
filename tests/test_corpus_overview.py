"""The whole-corpus comparison, its drill-downs and the published result."""

from __future__ import annotations

import functools
import json

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from scanpath_studio import aggregation as agg
from scanpath_studio import api, cli, data, tabs
from tests.conftest import APP_SCRIPT, pin_view


def test_overview_weights_readings_then_participants_and_retains_empty_groups():
    words = pd.DataFrame(
        {
            "text_id": ["X", "X", "X", "X", "X", "X", "Y"],
            "participant_id": ["a", "a", "a", "b", "b", "c", "c"],
            "trial_id": [1, 1, 2, 1, 1, 1, 2],
            "screen_id": ["one", "two", "one", "one", "one", "one", "one"],
            "total_fixation_duration_ms": [0, 20, 100, 200, np.inf, -np.inf, np.nan],
        }
    )
    texts = agg.corpus_overview(words, agg.MEASURES["tfd"], "text").set_index("text_id")
    # A's reading means are 10 and 100. A and B contribute 55 and 200 to X.
    assert texts.loc["X"].to_dict() == {
        "value": 127.5,
        "lo": 55,
        "hi": 200,
        "n_readings": 3,
        "n_participants": 2,
        "n_values": 4,
        "n_word_rows": 6,
    }
    assert texts.loc["Y", ["value", "lo", "hi"]].isna().all()
    assert texts.loc["Y", ["n_participants", "n_values", "n_word_rows"]].tolist() == [
        0,
        0,
        1,
    ]
    readers = agg.corpus_overview(words, agg.MEASURES["tfd"], "participant").set_index(
        "participant_id"
    )
    assert readers.loc["a", ["value", "lo", "hi", "n_readings"]].tolist() == [
        55,
        10,
        100,
        2,
    ]
    assert np.isnan(readers.loc["c", "value"])


def _overview_app():
    import streamlit as st

    from scanpath_studio.corpus_overview import render_corpus_overview

    render_corpus_overview(
        st.session_state["words"],
        group_by="participant",
        profile_host=st.container(),
        measure_host=st.container(),
        download=lambda *args, **kwargs: None,
        canvas_width=700,
        base_font_size=14,
        font_family="Arial",
        colors=("#0072B2", "#D55E00"),
    )


def test_unmapped_trial_numbers_and_nullable_empty_readings():
    measure = agg.MEASURES["tfd"]
    words = pd.DataFrame(
        {
            "participant_id": ["a", "b"],
            "trial_id": ["1", "1"],
            "text_id": ["1", "1"],
            data.TEXT_ID_MAPPED: [False, False],
            measure.column: pd.array([320, None], dtype="Float64"),
        }
    )
    with pytest.raises(ValueError, match="mapped Text ID"):
        agg.corpus_overview(words, measure, "text")
    at = AppTest.from_function(_overview_app)
    at.session_state["words"] = words
    at.run()
    assert not at.exception
    assert at.selectbox(key="corpus_inspect_participant").value is None
    assert at.button(key="corpus_open_profile").label == "Open participant profile"
    at.selectbox(key="corpus_inspect_participant").select("b").run()
    assert not at.exception
    assert any("no recorded values for this measure" in c.value for c in at.caption)
    # A mapped Text ID can legitimately equal a trial ID. Only that reader
    # belongs to text 1, even though the generated ID has the same spelling.
    mixed = words.assign(**{data.TEXT_ID_MAPPED: [True, False]})
    text = agg.corpus_overview(mixed, measure, "text").iloc[0]
    assert text["text_id"] == "1" and text["n_word_rows"] == 1


def test_shared_stimulus_values_do_not_enter_reading_summaries():
    measure = agg.MEASURES["tfd"]
    stimulus = pd.DataFrame(
        {
            "participant_id": [data.STIMULUS_PARTICIPANT],
            "trial_id": ["t"],
            "text_id": ["passage"],
            data.STIMULUS_WORDS_FLAG: [True],
            measure.column: [320],
        }
    )
    readings = pd.DataFrame(
        {
            "participant_id": ["a", "b"],
            "trial_id": ["t", "t"],
            "text_id": ["passage"] * 2,
        }
    )
    copies = data.broadcast_stimulus_words(stimulus, readings)
    assert len(copies) == 2
    for group in ("participant", "text"):
        assert agg.corpus_overview(copies, measure, group).empty
    at = AppTest.from_function(_overview_app)
    at.session_state["words"] = copies
    at.run()
    assert not at.exception
    assert "shared across readings" in at.info[0].value
    assert not at.metric
    own = readings.iloc[:1].assign(**{measure.column: 200})
    out = agg.corpus_overview(pd.concat([copies, own]), measure, "text").iloc[0]
    assert out[["value", "n_participants", "n_word_rows"]].tolist() == [200, 1, 1]


@pytest.mark.parametrize("group", ["Text", "Participant"])
def test_filtered_overview_replays_and_opens_selected_profile(
    group, tmp_path, monkeypatch
):
    captured = {}

    def capture(func, *args, **kwargs):
        callback = functools.partial(func, *args, **kwargs)
        if func is tabs._recipe_json and args[2].startswith("overview_"):
            captured["recipe"] = callback
        if func is tabs._tidy_csv and "n_word_rows" in args[0]:
            captured["csv"] = callback
        return callback

    monkeypatch.setattr(tabs, "partial", capture)
    at = AppTest.from_file(APP_SCRIPT, default_timeout=90).run()
    at.session_state["filter_participants"] = ["l7_183"]
    at.run()
    pin_view(at, "Corpus Analysis")
    at.run()
    at.selectbox(key="corpus_measure").select("ffd")
    at.segmented_control(key="corpus_destination").set_value(group + "s").run()
    assert not at.exception
    assert "csv" not in captured and not at.dataframe
    at.session_state["corpus_summary_table"] = True
    at.run()
    assert not at.exception
    assert at.session_state["corpus_subtab"] == "Overview"
    assert at.selectbox(key="corpus_measure").value == "ffd"
    saved = tmp_path / "overview.recipe.json"
    saved.write_text(captured["recipe"]())
    recipe = json.loads(saved.read_bytes())
    assert recipe["analysis"]["group_by"] == group.lower()
    assert recipe["selection"]["participants"] == ["l7_183"]
    expected = captured["csv"]()
    assert (
        api.run_analysis_recipe(saved, *api.load_sample_data())
        .to_csv(index=False)
        .encode()
        == expected
    )
    out = tmp_path / "overview.csv"
    cli.main(["recipe", str(saved), "--sample", "-o", str(out)])
    assert out.read_bytes() == expected
    recipe["analysis"]["aggregation"] = "median"
    with pytest.raises(ValueError, match="supports the mean"):
        api.run_analysis_recipe(recipe, *api.load_sample_data())
    selector = at.selectbox(key=f"corpus_inspect_{group.lower()}")
    selected = selector.options[-1]
    selector.select(selected).run()
    with monkeypatch.context() as profile:
        if group == "Participant":

            def unused_enrichment(*args, **kwargs):
                pytest.fail(
                    "Word distributions should read only the supplied word values."
                )

            profile.setattr(tabs, "_c_enrich_fix", unused_enrichment)
        at.button(key="corpus_open_profile").click().run()
    assert not at.exception
    if group == "Text":
        assert at.selectbox(key="ptext_text").value.startswith(f"{selected}  (")
        assert at.selectbox(key="ptext_view").value == "Cohort profile"
        assert at.selectbox(key="ptext_measure").value == agg.MEASURES["ffd"].label
        view_key, alternate = "ptext_view", "Measure on the stimulus"
    else:
        assert at.selectbox(key="prdr_pid").value == selected
        assert at.selectbox(key="prdr_measure").value == agg.MEASURES["ffd"].label
        view_key, alternate = "prdr_view", "Per-trial trend"
    # The first edit inside Chart settings must replace the drill-down default.
    at.selectbox(key=view_key).select(alternate).run()
    assert at.selectbox(key=view_key).value == alternate


def test_bookmarked_overview_opens_group_comparison_with_the_same_measure():
    from streamlit.util import calc_hash

    at = AppTest.from_file(APP_SCRIPT, default_timeout=90)
    at._page_hash = calc_hash("corpus-analysis")
    at.query_params.update(
        {"corpus_group_by": "Participant", "corpus_measure": agg.MEASURES["ffd"].label}
    )
    at.run()
    assert at.selectbox(key="corpus_measure").value == "ffd"
    assert at.segmented_control(key="corpus_destination").value == "Participants"
    at.segmented_control(key="corpus_destination").set_value("Groups").run()
    assert not at.exception
    assert at.toggle(key="groups_compare").value
    assert at.selectbox(key="cmp_view").value == "Group means & difference"
    assert at.selectbox(key="cmp_measure").value == agg.MEASURES["ffd"].label


def test_overview_figure_limits_only_the_chart_and_keeps_csv_identifiers(
    tmp_path, monkeypatch
):
    ids = ["001", "01", "NA", *map(str, range(11))]
    values = np.arange(len(ids), 0, -1)
    table = pd.DataFrame(
        {"Reader": ids, "value": values, "lo": values - 1, "hi": values + 2}
    )
    csv = tmp_path / "summary.csv"
    table.to_csv(csv, index=False)
    figures = []
    monkeypatch.setattr(
        api, "save_figure", lambda figure, path: figures.append(figure) or path
    )
    cli.main(
        [
            "corpus",
            "--input",
            str(csv),
            "--kind",
            "overview",
            "--series-col",
            "Reader",
            "-o",
            str(tmp_path / "figure.html"),
        ]
    )
    for fig in (
        figures[0],
        api.plot_corpus_figure(table, kind="overview", series_col="Reader"),
    ):
        assert list(fig.layout.yaxis.ticktext) == ids[:12]
        assert list(fig.data[0].error_x.array) == [2] * 12
        assert list(fig.data[0].error_x.arrayminus) == [1] * 12
        assert "12 of 14" in fig.layout.title.text


def test_chart_preserves_large_numeric_ids_in_hover_labels():
    ids = [2**60, 2**60 + 1]
    table = pd.DataFrame(
        {"series": ids, "value": [3.5, 2.5], "lo": [3, 2], "hi": [4, 3]}
    )
    fig = api.plot_corpus_figure(table, kind="overview")
    assert [p[0] for p in fig.data[0].customdata] == list(map(str, ids))


def test_inspecting_a_lower_rank_moves_the_chart_to_that_participant():
    at = AppTest.from_function(_overview_app)
    ids = [f"reader-{n:02d}" for n in range(15)]
    at.session_state["words"] = pd.DataFrame(
        {
            "participant_id": ids,
            "trial_id": ["one"] * len(ids),
            "total_fixation_duration_ms": list(range(15, 0, -1)),
        }
    )
    at.run()
    at.selectbox(key="corpus_inspect_participant").select(ids[-2]).run()
    assert not at.exception
    fig = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert fig["layout"]["yaxis"]["ticktext"] == ids[12:]
    assert fig["data"][0]["marker"]["symbol"] == ["circle", "diamond", "circle"]
    assert any("ranks 13–15 of 15" in c.value for c in at.caption)


def test_rate_chart_and_table_display_the_underlying_proportions_as_percentages(
    tmp_path, monkeypatch
):
    at = AppTest.from_function(_overview_app)
    at.session_state["words"] = pd.DataFrame(
        {
            "participant_id": ["a", "a", "b"],
            "trial_id": ["t"] * 3,
            "skip_flag": [True, False, False],
        }
    )
    at.session_state["corpus_summary_table"] = True
    at.run()
    assert not at.exception
    assert at.selectbox(key="corpus_inspect_participant").value is None
    at.selectbox(key="corpus_inspect_participant").select("a").run()
    assert any("**50.0%** mean" in m.value for m in at.markdown)
    assert at.dataframe[0].value["value"].tolist() == [0.5, 0.0]
    assert (
        json.loads(at.dataframe[0].proto.columns)["value"]["type_config"]["format"]
        == "percent"
    )
    fig = json.loads(at.get("plotly_chart")[0].proto.spec)
    csv = tmp_path / "skip.csv"
    at.dataframe[0].value.to_csv(csv, index=False)
    figures = []
    monkeypatch.setattr(
        api, "save_figure", lambda fig, path: figures.append(fig) or path
    )
    cli.main(
        [
            "corpus",
            "--input",
            str(csv),
            "--kind",
            "overview",
            "--series-col",
            "participant_id",
            "--percent",
            "-o",
            str(tmp_path / "skip.html"),
        ]
    )
    for output in (fig, figures[0].to_plotly_json()):
        assert output["layout"]["xaxis"]["tickformat"].endswith("%")
        assert "%{x:.1%}" in output["data"][0]["hovertemplate"]


def _participant_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.tabs import render_per_reader_tab

    render_per_reader_tab(
        st.session_state["words"],
        pd.DataFrame(),
        viz_settings={},
        canvas_width=700,
        canvas_height=500,
        base_font_size=14,
        font_family="Arial",
    )


def test_participant_profile_explains_missing_comparisons_and_counts_binary_words():
    at = AppTest.from_function(_participant_app)
    at.session_state["words"] = pd.DataFrame(
        {
            "participant_id": ["a", "a", "b"],
            "trial_id": ["t"] * 3,
            "skip_flag": [True, False, pd.NA],
            "first_fixation_ms": [np.nan, np.nan, 200],
        }
    )
    at.run()
    assert not at.exception
    assert any("Participant a has no recorded values" in s.value for s in at.info)
    fig = json.loads(at.get("plotly_chart")[0].proto.spec)
    assert [trace["name"] for trace in fig["data"]] == ["Other participants"]
    assert fig["data"][0]["spanmode"] == "hard"
    at.selectbox(key="prdr_measure").select(agg.MEASURES["skip"].label).run()
    assert not at.exception
    assert any("No other participant has a value" in s.value for s in at.info)
    assert [(m.label, m.value) for m in at.metric] == [("Participant a", "50.0%")]
    assert any("1 of 2 word observations" in c.value for c in at.caption)
    assert not at.get("plotly_chart")


def test_excluding_trial_fallbacks_preserves_distinct_large_numeric_text_ids():
    measure = agg.MEASURES["tfd"]
    ids = [2**60, 2**60 + 1, 2**60 + 2]
    words = pd.DataFrame(
        {
            "text_id": ids,
            "participant_id": ["a", "b", "c"],
            "trial_id": [1, 1, 1],
            data.TEXT_ID_MAPPED: [True, True, False],
            measure.column: [100, 200, 300],
        }
    )
    table = agg.corpus_overview(words, measure, "text")
    assert table["text_id"].tolist() == [ids[1], ids[0]]
    assert table["value"].tolist() == [200, 100]


@pytest.mark.parametrize(
    ("value", "lo", "hi"),
    [(2.0, np.nan, 4.0), (2, 3, 4), (np.inf, 0, 3), (1, 0, "bad")],
)
def test_overview_rejects_invalid_ranges(value, lo, hi):
    table = pd.DataFrame({"series": ["p1"], "value": [value], "lo": [lo], "hi": [hi]})
    with pytest.raises(ValueError):
        api.plot_corpus_figure(table, kind="overview")


def test_percent_overview_requires_proportions():
    counts = pd.DataFrame({"series": ["p1"], "value": [40], "lo": [15], "hi": [60]})
    with pytest.raises(ValueError, match="proportions from 0 to 1"):
        api.plot_corpus_figure(counts, kind="overview", as_percent=True)


def test_compare_groups_shows_rate_changes_in_percentage_points():
    at = AppTest.from_file(APP_SCRIPT, default_timeout=60)
    pin_view(at, "Corpus Analysis")
    at.session_state["corpus_measure"] = "skip"
    at.run()
    at.segmented_control(key="corpus_destination").set_value("Groups").run()
    assert not at.exception
    means = [m.value for m in at.metric if m.label.endswith(" mean")]
    assert len(means) == 2 and all(v.endswith("%") for v in means)
    a, b = (float(v.removesuffix("%")) for v in means)
    diff = next(m for m in at.metric if "percentage points" in m.label)
    assert float(diff.value) == pytest.approx(a - b, abs=0.15)


def test_deselection_after_leaving_the_chart_keeps_the_inspected_text(monkeypatch):
    from scanpath_studio import corpus_overview

    state = {"corpus_inspect_text": "passage"}
    monkeypatch.setattr(corpus_overview.st, "session_state", state)
    corpus_overview._inspect_point("unmounted_chart", "text", ["another-passage"])
    assert state["corpus_inspect_text"] == "passage"
