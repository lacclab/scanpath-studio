"""A JSON recipe beside every Corpus Analysis table download.

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
            "normalization": "z-score per participant",
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
        dataset={"name": "Bundled demo", "source": "Bundled demo"},
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
    assert recipe["dataset"] == {"name": "Bundled demo", "source": "Bundled demo"}
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

    # Per text → Per-participant profiles is the page's default view.
    buttons = {b.key: b for b in at.download_button}
    assert "dl_ptext1" in buttons
    assert buttons["dl_ptext1_recipe"].proto.label == "⬇ Download the recipe (JSON)"
    assert bound, "the recipe button was never handed its inputs"

    recipe = json.loads(tabs._recipe_json(*bound[-1]))
    assert recipe["dataset"]["source"] == "Bundled demo"
    assert recipe["trial_filters"] == [{"field": "Participant", "values": ["l7_1090"]}]
    assert recipe["pool"] == {
        "trials": 12,
        "trials_in_dataset": 24,
        "readers": 1,
        "readers_in_dataset": 2,
    }
    assert recipe["analysis"]["section"] == "Per text"
    assert recipe["analysis"]["view"] == "Per-participant profiles"
    assert recipe["analysis"]["measure"]["key"] == "tfd"
    assert recipe["result"]["file"].startswith("per_reader_tfd_")
    assert recipe["result"]["readers"] == 1


def test_downloaded_filtered_profile_replays_through_cli_and_api(monkeypatch, tmp_path):
    """The app's two download payloads are the independent scientific oracle."""
    import functools

    from scanpath_studio import api, cli, tabs

    captured = {}

    def capture(func, *args, **kwargs):
        callback = functools.partial(func, *args, **kwargs)
        if func is tabs._recipe_json and args[2].startswith("cohort_profile_"):
            captured["recipe"] = callback
        elif func is tabs._tidy_csv and {"lo", "hi", "word_id", "enough"} <= set(
            args[0]
        ):
            captured["csv"] = callback
        return callback

    monkeypatch.setattr(tabs, "partial", capture)
    at = streamlit_testing.AppTest.from_file(APP_SCRIPT).run(timeout=90)
    at.session_state["filter_participants"] = ["l7_1090"]
    at.run(timeout=90)
    pin_view(at, "Corpus Analysis")
    at.run(timeout=90)
    at.selectbox(key="ptext_view").select("Cohort profile").run(timeout=90)
    at.selectbox(key="ptext_agg").select("median").run(timeout=90)
    assert not at.exception, at.exception
    expected = captured["csv"]()
    saved = tmp_path / "profile.recipe.json"
    saved.write_text(captured["recipe"](), encoding="utf-8-sig")
    spec = json.loads(saved.read_bytes())
    assert spec["selection"]["participants"] == ["l7_1090"]
    assert (
        api.run_analysis_recipe(saved, *api.load_sample_data())
        .to_csv(index=False)
        .encode()
        == expected
    )
    out = tmp_path / "profile.csv"
    cli.main(["recipe", str(saved), "--sample", "-o", str(out)])
    assert out.read_bytes() == expected


def _cohort_recipe(**overrides):
    recipe = build_analysis_recipe(
        app_version="1",
        dataset={},
        trial_filters=[],
        pool={},
        analysis=analysis_choices(
            section="Per text",
            view="Cohort profile",
            text=("text_id", "story"),
            measure=MEASURES["tfd"],
            aggregation="mean",
            spread="SD",
            normalize=False,
            min_readers=1,
        ),
        table_file="profile.csv",
        counts={"rows": 1},
    )
    return dict(recipe, **overrides)


def _profile_words():
    return pd.DataFrame(
        {
            "participant_id": ["01", "02", "03"],
            "trial_id": ["t1", "t1", "t2"],
            "text_id": ["story"] * 3,
            "word_id": [1, 1, 1],
            "total_fixation_duration_ms": [100.0, 50.0, 15.0],
        }
    )


@pytest.mark.parametrize(
    ("grain", "id_field", "ids"),
    [
        ("participant", "subject", ["01", "02"]),
        ("trial", "trial", ["t1", "t2"]),
        ("text", "passage", ["story", "other"]),
    ],
)
def test_required_metadata_table_and_annotations_restrict_readings(
    tmp_path, grain, id_field, ids
):
    from scanpath_studio import run_analysis_recipe

    rule = {"id_column": id_field, "values": {"group": ["A"]}, "column": "text_id"}
    recipe = _cohort_recipe(
        selection={
            "metadata": {grain: rule},
            "annotations": {"required_tags": ["pilot"]},
        }
    )
    with pytest.raises(ValueError, match=f"requires the {grain} metadata"):
        run_analysis_recipe(recipe, _profile_words())
    table = pd.DataFrame({id_field: ids, "group": ["A", "B"]})
    opts = {f"{grain}_metadata": table}
    with pytest.raises(ValueError, match="requires the dataset's annotations"):
        run_analysis_recipe(recipe, _profile_words(), **opts)
    annotated = tmp_path / "annotations.json"
    annotated.write_text(
        json.dumps(
            {
                "annotations": [
                    {"participant_id": "01", "trial_id": "t1", "tags": ["pilot"]},
                    {
                        "participant_id": "03",
                        "trial_id": "t2",
                        "screen_id": "s1",
                        "tags": ["pilot"],
                    },
                ]
            }
        )
    )
    annotated.write_text(annotated.read_text(), encoding="utf-8-sig")
    actual = run_analysis_recipe(
        recipe, _profile_words(), annotations=annotated, **opts
    )
    assert actual.iloc[0][["value", "n"]].tolist() == [100.0, 1]


@pytest.mark.parametrize(
    ("mapping", "expected"),
    [(["A", "B"], 75.0), (["A + B"], 15.0)],
)
def test_trial_metadata_recipe_keeps_exact_id_columns_after_restore(
    monkeypatch, tmp_path, mapping, expected
):
    from scanpath_studio import controls, metadata, run_analysis_recipe

    words = _profile_words().assign(trial_id=["item_01", "item_01", "item_02"])
    source = pd.DataFrame(
        {
            "A": ["item", "item"],
            "B": ["01", "02"],
            "A + B": ["item_02", "item_01"],
            "group": ["keep", "drop"],
        }
    )
    csv = tmp_path / "trial.csv"
    source.to_csv(csv, index=False)
    keys = metadata.trial_keys(words)
    attached = metadata.build_trial_metadata(source, mapping, keys=keys)
    saved = metadata.trial_to_payload(attached)
    restored = metadata.trial_from_payload(saved)
    monkeypatch.setattr(metadata, "attached_for", lambda grain, prefix: restored)
    monkeypatch.setattr(
        controls.st,
        "session_state",
        {controls.trial_metadata_filter_key("group"): ["keep"]},
    )
    rules = {}
    controls._trial_metadata_narrowing("", lambda: keys, rules)
    assert rules["trial"]["id_column"] == mapping
    recipe = _cohort_recipe(selection={"metadata": rules})
    for table in (csv, restored.frame):
        assert (
            run_analysis_recipe(recipe, words, trial_metadata=table).iloc[0]["value"]
            == expected
        )

    del saved["id_columns"]  # Older attachments recorded only the displayed label.
    restored = metadata.trial_from_payload(saved)
    controls._trial_metadata_narrowing("", lambda: keys, rules)
    assert rules["trial"]["id_column"] == "A + B"
    for table in (csv, restored.frame):
        with pytest.raises(ValueError, match="ambiguous.*Reattach"):
            run_analysis_recipe(recipe, words, trial_metadata=table)


def test_old_cohort_recipe_supports_participants_and_refuses_ambiguous_fields():
    from scanpath_studio import run_analysis_recipe

    recipe = _cohort_recipe(trial_filters=[{"field": "Participant", "values": ["02"]}])
    assert run_analysis_recipe(recipe, _profile_words()).iloc[0]["value"] == 50
    recipe["trial_filters"] = [{"field": "Score", "range": [0, 2]}]
    with pytest.raises(ValueError, match="without its source field"):
        run_analysis_recipe(recipe, _profile_words())


def test_condition_needs_its_table_and_compares_both_tables_per_reading():
    from scanpath_studio import run_analysis_recipe

    recipe = _cohort_recipe(
        selection={
            "conditions": {"list": ["A"]},
            "fixation_fields": ["list"],
            "word_fields": ["list"],
        }
    )
    words = _profile_words().assign(list=["A", "A", "B"])
    fixations = words[["participant_id", "trial_id"]].assign(list=["B", "A", "A"])
    with pytest.raises(ValueError, match="--fixations"):
        run_analysis_recipe(recipe, words)
    assert run_analysis_recipe(recipe, words, fixations).iloc[0]["value"] == 50


def test_source_recipe_replays_mapping_filename_ids_and_merged_boxes(tmp_path):
    from scanpath_studio import cli

    words = tmp_path / "reader07_story.csv"
    pd.DataFrame(
        {
            "token": [1, 1],
            "glyph": ["hi", "hi"],
            "left": [0, 1],
            "top": [1, 1],
            "width": [1, 1],
            "height": [2, 2],
            "dwell": [120, 30],
        }
    ).to_csv(words, index=False)
    schema = {
        "participant": "source_file_1",
        "trial": "source_file",
        "text_id": "passage",
        "word_id": "token",
        "text": "glyph",
        "x": "left",
        "y": "top",
        "width": "width",
        "height": "height",
        "measure_tfd": "dwell",
    }
    recipe = _cohort_recipe(
        inputs={
            "schemas": {"words": schema},
            "steps": ["aggregate_char_boxes"],
            "derive": [
                {
                    "table": "Words table",
                    "mode": "Split on a delimiter",
                    "delimiter": "_",
                },
                {
                    "table": "Words table",
                    "column": "source_file_2",
                    "mode": "Extract with a regex",
                    "pattern": "(?P<passage>.+)",
                },
            ],
        }
    )
    # Joining the two characters uses the first IA value; treating the two
    # rows as repeated readings would instead yield 75 ms.
    saved = tmp_path / "cohort.recipe.json"
    saved.write_text(json.dumps(recipe))
    output = tmp_path / "cohort.csv"
    cli.main(["recipe", str(saved), "--words", str(words), "-o", str(output)])
    assert pd.read_csv(output)["value"].tolist() == [120]


def test_replay_refuses_different_values_with_the_same_row_count():
    import hashlib

    from scanpath_studio import run_analysis_recipe

    recipe = _cohort_recipe()
    words = _profile_words()
    table = run_analysis_recipe(recipe, words)
    recipe["result"]["sha256"] = hashlib.sha256(
        table.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ).hexdigest()
    words.loc[0, "total_fixation_duration_ms"] = 25
    with pytest.raises(ValueError, match="differs from the original"):
        run_analysis_recipe(recipe, words)


def test_replay_keeps_its_screen_and_minimum_per_word():
    from scanpath_studio import run_analysis_recipe

    words = _profile_words().assign(screen_id="second", screen_index=2)
    other_screen = words.assign(
        screen_id="first", screen_index=1, total_fixation_duration_ms=3000
    )
    rare_word = words.iloc[:1].assign(word_id=2)
    spec = _cohort_recipe()
    spec["analysis"].update(min_readers=2, screen="second")
    out = run_analysis_recipe(
        spec, pd.concat([other_screen, words, rare_word], ignore_index=True)
    )
    assert out["word_id"].tolist() == [1]
    assert out.iloc[0]["value"] == 55


def test_recipe_replays_text_ids_supplied_by_raw_gaze(tmp_path, monkeypatch):
    from scanpath_studio import api, cli, controls, data, metadata

    source = pd.DataFrame(
        {
            "participant_id": ["p1", "p2"],
            "trial_id": "story",
            "word_id": 1,
            "text": "A",
            "x": 0,
            "y": 0,
            "width": 10,
            "height": 10,
            "IA_DWELL_TIME": [100, 50],
        }
    )
    gaze = source[["participant_id", "trial_id", "x", "y"]].assign(book_code=["a", "b"])
    schema = dict(data.propose_raw_gaze_schema(gaze), text_id="book_code")
    samples = api.load_raw_gaze(gaze, raw_gaze_schema=schema, names="canonical")
    words, fixations = api.load_scanpath_data(source, names="canonical")
    texts = pd.DataFrame({"text_id": ["a", "b"], "genre": ["poem", "story"]})
    attached = metadata.build_text_metadata(texts, "text_id", keys={"a", "b"})
    monkeypatch.setattr(
        controls.st,
        "session_state",
        {
            metadata.TEXT_SESSION_KEY: attached,
            controls.text_metadata_filter_key("genre"): ["poem"],
        },
    )
    selection = controls._compute_trial_filters(words, fixations, samples)
    assert selection["trial_keys"] == {("p1", "story")}
    recipe = _cohort_recipe(
        selection=jsonable(selection["recipe_selection"]),
        inputs={"schemas": {"raw_gaze": schema}},
    )
    with pytest.raises(ValueError, match="Supply --raw-gaze"):
        api.run_analysis_recipe(recipe, words, fixations, text_metadata=texts)
    expected = api.run_analysis_recipe(
        recipe, words, fixations, raw_gaze=samples, text_metadata=texts
    )
    assert expected.iloc[0][["value", "n"]].tolist() == [100, 1]

    saved = tmp_path / "profile.json"
    saved.write_text(json.dumps(recipe))
    arguments = ["recipe", str(saved)]
    for flag, frame in (
        ("words", source),
        ("text-metadata", texts),
        ("raw-gaze", gaze),
    ):
        path = tmp_path / f"{flag}.csv"
        frame.to_csv(path, index=False)
        arguments.extend([f"--{flag}", str(path)])
    output = tmp_path / "profile.csv"
    cli.main([*arguments, "-o", str(output)])
    assert pd.read_csv(output).iloc[0][["value", "n"]].tolist() == [100, 1]


def test_two_group_recipe_reproduces_signed_difference_and_one_sided_word():
    from scanpath_studio import run_analysis_recipe
    from scanpath_studio.aggregation import group_word_difference

    words = _profile_words().assign(
        text=["ink", "ink", "end"],
        word_id=[1, 1, 2],
        screen_id="second",
        screen_index=5,
    )
    groups = [{"participant_id": ["01"]}, {"participant_id": ["02", "03"]}]
    recipe = _cohort_recipe()
    recipe["analysis"] = analysis_choices(
        section="Groups",
        view="Difference word profile",
        text=("text_id", "story"),
        screen="second",
        measure=MEASURES["tfd"],
        aggregation="mean",
        groups=[
            group_definition(label, spec) for label, spec in zip(("A", "B"), groups)
        ],
        min_readers=1,
    )
    recipe["result"]["rows"] = 2
    expected = group_word_difference(
        words, "text_id", "story", MEASURES["tfd"], *groups, screen_id="second"
    )
    pd.testing.assert_frame_equal(run_analysis_recipe(recipe, words), expected)
    assert expected.loc[0, "diff"] == 50 and expected.loc[1, "word_text"] == "end"


def _group_difference_app():
    import streamlit as st

    from scanpath_studio import tabs

    token = tabs._RECIPE_CONTEXT.set(
        {"dataset": {"source": "Lab"}, "section": "Groups"}
    )
    try:
        tabs.render_group_comparison_tab(
            st.session_state["words"],
            st.session_state["fix"],
            viz_settings={},
            canvas_width=700,
            canvas_height=400,
            base_font_size=14,
            font_family="Arial",
        )
    finally:
        tabs._RECIPE_CONTEXT.reset(token)


def test_paired_contrast_counts_a_reader_who_has_only_fixations(monkeypatch):
    from scanpath_studio import tabs

    words = (
        _profile_words()
        .iloc[:2]
        .assign(
            participant_id="r1",
            trial_id=["a", "b"],
            total_fixation_duration_ms=[100, 150],
        )
    )
    fix = pd.DataFrame(
        {"participant_id": ["r1", "r1", "r2", "r2"], "trial_id": ["a", "b", "a", "b"]}
    )
    monkeypatch.setattr(
        tabs,
        "_render_group_definition",
        lambda *args, **kwargs: ({"trial_id": ["a"]}, {"trial_id": ["b"]}, "A", "B"),
    )
    at = streamlit_testing.AppTest.from_function(_group_difference_app)
    at.session_state["words"], at.session_state["fix"] = words, fix
    at.session_state["cmp_view"] = "Within-participant contrast"
    at.run(timeout=60)
    assert not at.exception
    assert any("1 missing A and 1 missing B" in caption.value for caption in at.caption)
    result = at.dataframe[-1].value.set_index("participant_id")
    assert result.loc["r2"].isna().all()
    assert result.at["r1", "difference_a_minus_b"] == -50


def test_downloaded_group_difference_replays_from_source_files(tmp_path, monkeypatch):
    import functools
    import hashlib

    from scanpath_studio import api, cli, tabs

    source = _profile_words().assign(
        text=["ink", "ink", "end"],
        word_id=[1, 1, 2],
        x=[0, 0, 20],
        y=0,
        width=20,
        height=10,
        screen_id="second",
        screen_index=5,
    )
    path = tmp_path / "words.csv"
    source.to_csv(path, index=False)
    words, fix = api.load_scanpath_data(path, None, names="canonical")
    captures = {}

    def capture(func, *args, **kwargs):
        fn = functools.partial(func, *args, **kwargs)
        if func is tabs._recipe_json and args[2].startswith("difference_"):
            captures["recipe"] = fn
        if func is tabs._tidy_csv and "diff" in args[0]:
            captures["csv"] = fn
        return fn

    monkeypatch.setattr(tabs, "partial", capture)
    monkeypatch.setattr(
        tabs,
        "_render_group_definition",
        lambda *a, **k: (
            {"participant_id": ["01"]},
            {"participant_id": ["02", "03"]},
            "A",
            "B",
        ),
    )
    at = streamlit_testing.AppTest.from_function(_group_difference_app)
    at.session_state["words"], at.session_state["fix"] = words, fix
    at.session_state["cmp_view"] = "Difference word profile"
    at.run(timeout=90)
    assert not at.exception
    payload, expected = captures["recipe"](), captures["csv"]()
    recipe = json.loads(payload)
    assert recipe["result"]["sha256"] == hashlib.sha256(expected).hexdigest()
    saved, out = tmp_path / "groups.recipe.json", tmp_path / "difference.csv"
    saved.write_text(payload, encoding="utf-8")
    cli.main(["recipe", str(saved), "--words", str(path), "-o", str(out)])
    assert out.read_bytes() == expected
