"""AN-34 — a JSON recipe beside every Corpus Analysis table download.

The builder is pure and tested as units; one ``AppTest`` flow pins that the
recipe is offered beside the CSV and records the page's trial filters.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scanpath_studio.aggregation import MEASURES
from scanpath_studio.analysis_recipe import (
    EXCLUDES,
    RECIPE_KIND,
    analysis_choices,
    build_analysis_recipe,
    group_definition,
    jsonable,
    recipe_file_name,
    result_counts,
)
from tests.conftest import APP_SCRIPT, pin_view


class TestAnalysisChoices:
    def test_records_what_applies_and_drops_the_rest(self):
        out = analysis_choices(
            section="Per text",
            view="Cohort profile",
            text=("unique_paragraph_id", "3_1"),
            measure=MEASURES["tfd"],
            aggregation="mean",
            normalize=True,
            spread="SEM",
            min_readers=2,
        )
        assert out == {
            "section": "Per text",
            "view": "Cohort profile",
            "text": {"field": "unique_paragraph_id", "id": "3_1"},
            "measure": {"key": "tfd", "label": MEASURES["tfd"].label},
            "aggregation": "mean",
            "normalization": "z-score within reader",
            "spread": "SEM",
            "min_readers": 2,
        }

    def test_a_rate_is_never_recorded_as_normalized(self):
        """The aggregation helpers skip z-scoring a 0–1 rate whatever the toggle
        says, so the recipe records what was applied."""
        out = analysis_choices(measure=MEASURES["skip"], normalize=True)
        assert out["normalization"] == "none"

    def test_screen_zero_is_kept(self):
        assert analysis_choices(screen=0)["screen"] == 0


class TestGroupDefinition:
    def test_spec_values_and_composite_keys(self):
        out = group_definition(
            "Adv",
            {
                "difficulty_level": ["Adv"],
                ("participant_id", "trial_id"): {("p2", "t1"), ("p1", "t1")},
            },
        )
        assert out == {
            "label": "Adv",
            "constraints": [
                {"field": "difficulty_level", "values": ["Adv"]},
                {
                    "field": ["participant_id", "trial_id"],
                    "values": [["p1", "t1"], ["p2", "t1"]],
                },
            ],
        }

    def test_an_empty_spec_is_the_whole_pool(self):
        assert group_definition("All", None) == {"label": "All", "constraints": []}


def test_jsonable_handles_numpy_and_nan():
    assert jsonable(
        {"a": np.int64(3), "b": np.float64("nan"), "c": np.bool_(True)}
    ) == {
        "a": 3,
        "b": None,
        "c": True,
    }


def test_result_counts_reads_the_table_and_keeps_view_counts():
    table = pd.DataFrame({"participant_id": ["p1", "p1", "p2"], "value": [1, 2, 3]})
    assert result_counts(table, {"group_readers": np.int64(2)}) == {
        "rows": 3,
        "readers": 2,
        "group_readers": 2,
    }
    assert result_counts(pd.DataFrame({"word_id": [1]})) == {"rows": 1}


def test_recipe_separates_filters_from_figure_settings_and_embeds_no_data():
    recipe = build_analysis_recipe(
        app_version="9.9.9",
        dataset={"name": "Bundled Demo", "source": "Bundled Demo"},
        trial_filters=[
            {"field": "Participant", "values": ["p1"], "keys": ("filter_x",)},
            {"field": "Trial index", "range": [3.0, 10.0]},
        ],
        pool={"trials": 12, "trials_in_dataset": 24},
        analysis={"view": "Cohort profile"},
        table_file="cohort.csv",
        counts={"rows": 40},
        exported_at="2026-10-03T00:00:00",
    )
    assert recipe["kind"] == RECIPE_KIND
    assert recipe["app"]["version"] == "9.9.9"
    assert recipe["dataset"] == {"name": "Bundled Demo", "source": "Bundled Demo"}
    # Only the filter's meaning travels — never the widget keys behind it.
    assert recipe["trial_filters"] == [
        {"field": "Participant", "values": ["p1"]},
        {"field": "Trial index", "range": [3.0, 10.0]},
    ]
    assert recipe["result"] == {"file": "cohort.csv", "rows": 40}
    assert recipe["excludes"] == EXCLUDES
    assert "figure_settings" in recipe["excludes"]
    assert not {"figure_settings", "viz_settings", "rows", "annotations"} & set(recipe)
    json.dumps(recipe)  # plain JSON throughout


def test_recipe_file_name():
    assert recipe_file_name("cohort_profile_tfd_3.csv") == (
        "cohort_profile_tfd_3.recipe.json"
    )


streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.mark.timeout(180)
def test_corpus_tables_offer_a_recipe_that_records_the_filters(monkeypatch):
    import functools

    from scanpath_studio import tabs

    # The recipe is built when its button is clicked, which AppTest cannot do.
    # Record what the button's callable is bound to, then build it from that.
    bound: list = []

    def recording_partial(func, *args, **kwargs):
        if func is tabs._recipe_json:
            bound.append(args)
        return functools.partial(func, *args, **kwargs)

    monkeypatch.setattr(tabs, "partial", recording_partial)

    at = streamlit_testing.AppTest.from_file(APP_SCRIPT)
    at.run(timeout=90)
    at.session_state["filter_participants"] = ["l7_1090"]
    at.run(timeout=90)
    bound.clear()
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    assert not at.exception, at.exception

    # Per text → Per-reader profiles is the page's default view.
    buttons = {b.key: b for b in at.get("download_button")}
    assert "dl_ptext1" in buttons
    assert buttons["dl_ptext1_recipe"].proto.label == "⬇ Download the recipe (JSON)"
    assert bound, "the recipe button was never handed its inputs"

    recipe = json.loads(tabs._recipe_json(*bound[-1]))
    assert recipe["dataset"]["source"] == "Bundled Demo"
    assert recipe["trial_filters"] == [{"field": "Participant", "values": ["l7_1090"]}]
    assert recipe["pool"] == {
        "trials": 12,
        "trials_in_dataset": 24,
        "readers": 1,
        "readers_in_dataset": 2,
    }
    assert recipe["analysis"]["section"] == "Per text"
    assert recipe["analysis"]["view"] == "Per-reader profiles"
    assert recipe["analysis"]["measure"]["key"] == "tfd"
    assert recipe["result"]["file"].startswith("per_reader_tfd_")
    assert recipe["result"]["readers"] == 1
