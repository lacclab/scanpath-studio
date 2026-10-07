"""Executable specification for multipart logical trials (DATA-21)."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.annotations import deserialize, serialize
from scanpath_studio.export import (
    ExportOptions,
    bulk_export,
    plan_export,
    screen_choices,
)
from scanpath_studio.measures import compute_per_word_measures, enrich_fixations
from scanpath_studio.multipart import (
    SCREEN_ID,
    apply_trial_parts_manifest,
    extract_part,
    part_catalog,
)
from scanpath_studio.synthetic import (
    MULTIPART_EXPECTED,
    make_multipart_synthetic_data,
)
from scanpath_studio.tabs import _build_compare_meta, _part_catalog_for_display


def _multipart_navigator_app():
    import streamlit as st

    from scanpath_studio.multipart import part_catalog
    from scanpath_studio.synthetic import make_multipart_synthetic_data
    from scanpath_studio.tabs import _render_screen_navigator

    words, fixations = make_multipart_synthetic_data()
    selected = _render_screen_navigator(part_catalog(words, fixations))
    st.write(f"Selected screen: {selected}")


def test_catalog_and_part_selection_preserve_order_geometry_and_clocks():
    words, fixations = make_multipart_synthetic_data()
    catalog = part_catalog(words, fixations)
    assert catalog[SCREEN_ID].tolist() == MULTIPART_EXPECTED["screens"]
    assert catalog["screen_index"].tolist() == MULTIPART_EXPECTED["screen_indexes"]
    assert (
        list(zip(catalog["canvas_width"], catalog["canvas_height"]))
        == (MULTIPART_EXPECTED["canvas_sizes"])
    )
    assert [
        len(extract_part(fixations, "synthetic", "multipart_demo", screen))
        for screen in MULTIPART_EXPECTED["screens"]
    ] == MULTIPART_EXPECTED["fixations_per_screen"]
    assert (
        int(fixations["timestamp_ms"].min()),
        int(fixations["timestamp_ms"].max()),
    ) == MULTIPART_EXPECTED["parent_timestamp_span"]
    assert fixations.groupby(SCREEN_ID)["screen_fixation_id"].min().eq(1).all()


def test_multipleye_display_prefers_fixation_order_over_stale_word_order():
    words, fixations = make_multipart_synthetic_data()
    words = words.copy()
    fixations = fixations.assign(screen_kind="reading")
    words["screen_index"] = words["screen_index"].map({1: 2, 2: 1})

    catalog = _part_catalog_for_display(words, fixations)

    assert catalog[SCREEN_ID].tolist() == MULTIPART_EXPECTED["screens"]
    assert catalog["screen_index"].tolist() == MULTIPART_EXPECTED["screen_indexes"]


def test_scientific_enrichment_and_measures_never_cross_screen_boundary():
    words, fixations = make_multipart_synthetic_data()
    enriched = enrich_fixations(fixations, words)
    # The first fixation of screen 2 has no incoming cross-screen saccade.
    first_second = enriched[enriched[SCREEN_ID] == "question"].iloc[0]
    assert pd.isna(first_second["saccade_amplitude"])
    assert not bool(first_second["is_regression"])

    measured = compute_per_word_measures(fixations, words)
    word_zero = measured[measured["word_id"] == 0].set_index(SCREEN_ID)
    assert word_zero.loc["intro", "total_fixation_duration_ms"] == 100
    assert word_zero.loc["question", "total_fixation_duration_ms"] == 120


def test_explicit_columns_auto_normalize_and_headless_api_selects_one_screen():
    words, fixations = make_multipart_synthetic_data()
    normalized_words, normalized_fixations = api.load_scanpath_data(
        words, fixations, names="canonical"
    )
    assert SCREEN_ID in normalized_words
    assert SCREEN_ID in normalized_fixations
    assert api.list_trials(normalized_words, normalized_fixations).shape == (1, 2)
    assert api.list_parts(normalized_words, normalized_fixations)[
        SCREEN_ID
    ].tolist() == [
        "intro",
        "question",
    ]

    first = api.plot_scanpath(
        normalized_words,
        normalized_fixations,
        "synthetic",
        "multipart_demo",
        # The canvas alone: a colour bar would widen the figure by its margin.
        show_fixation_colorbar=False,
        show_heatmap_colorbar=False,
    )
    second = api.plot_scanpath(
        normalized_words,
        normalized_fixations,
        "synthetic",
        "multipart_demo",
        screen="question",
        show_fixation_colorbar=False,
        show_heatmap_colorbar=False,
    )
    assert first.layout.width == 640
    assert second.layout.width == 800


def test_nested_manifest_maps_arbitrary_source_selectors():
    raw = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "page_code": ["A", "B"],
        }
    )
    normalized = raw[["participant_id", "trial_id"]].copy()
    manifest = {
        "trials": [
            {
                "participant_id": "p1",
                "trial_id": "t1",
                "parts": [
                    {
                        "screen_id": "intro",
                        "screen_index": 1,
                        "canvas_width": 640,
                        "canvas_height": 480,
                        "words": {"page_code": "A"},
                    },
                    {
                        "screen_id": "question",
                        "screen_index": 2,
                        "canvas_width": 800,
                        "canvas_height": 600,
                        "words": {"page_code": "B"},
                    },
                ],
            }
        ]
    }
    attached = apply_trial_parts_manifest(normalized, raw, manifest, kind="words")
    assert attached[SCREEN_ID].tolist() == ["intro", "question"]
    assert attached["screen_index"].tolist() == [1, 2]


def test_parent_render_records_user_selected_transition_timing():
    words, fixations = make_multipart_synthetic_data()
    figures = api.render_parent_trial(
        words,
        fixations,
        "synthetic",
        "multipart_demo",
        animate=True,
        transition_mode="recorded",
    )
    assert list(figures) == ["intro", "question"]
    assert figures["intro"].layout.meta["transition_after_ms"] == 620
    assert figures["question"].layout.meta["transition_after_ms"] == 0


def test_screen_scoped_annotations_round_trip_without_changing_parent_keys():
    store = {
        ("p1", "t1"): {"star": True, "tags": [], "note": "parent"},
        ("p1", "t1", "intro"): {
            "star": False,
            "tags": ["Check alignment"],
            "note": "screen",
        },
    }
    assert deserialize(serialize(store)) == store


def test_bulk_export_writes_deterministic_per_screen_folders():
    words, fixations = make_multipart_synthetic_data()
    combos = api.list_trials(words, fixations)
    payload, progress = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=1200,
        canvas_height=800,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings={},
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_plot_config=False,
            include_fixations=True,
        ),
    )
    assert progress.total_trials == 2
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        paths = archive.namelist()
    assert any("screens/screen-001-intro/fixations.csv" in path for path in paths)
    assert any("screens/screen-002-question/fixations.csv" in path for path in paths)


def test_bulk_export_keeps_only_the_chosen_screens():
    words, fixations = make_multipart_synthetic_data()
    combos = api.list_trials(words, fixations)
    assert screen_choices(words, fixations) == ["intro", "question"]
    options = ExportOptions(
        include_png=False,
        include_svg=False,
        include_plot_config=False,
        include_fixations=True,
        screens=("question",),
    )
    plan = plan_export(combos, words, fixations, options)
    assert (plan.trials, plan.units) == (1, 1)
    payload, progress = bulk_export(
        combos,
        words,
        fixations,
        canvas_width=1200,
        canvas_height=800,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings={},
        options=options,
    )
    assert progress.total_trials == 1
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        paths = archive.namelist()
        readme = archive.read("README.md").decode()
    assert any("screens/screen-002-question/" in path for path in paths)
    assert not any("intro" in path for path in paths)
    assert "Screens: only question" in readme
    # A screen no trial shows leaves nothing to export.
    none = plan_export(combos, words, fixations, ExportOptions(screens=("missing",)))
    assert (none.trials, none.units) == (0, 0)


def test_parent_render_draws_only_the_chosen_screens():
    words, fixations = make_multipart_synthetic_data()
    figures = api.render_parent_trial(
        words, fixations, "synthetic", "multipart_demo", screens=["question"]
    )
    assert list(figures) == ["question"]
    assert figures["question"].layout.meta["screen_index"] == 2
    # One id as a string; a recorded transition never points past the last
    # screen drawn.
    only_intro = api.render_parent_trial(
        words,
        fixations,
        "synthetic",
        "multipart_demo",
        animate=True,
        transition_mode="recorded",
        screens="intro",
    )
    assert list(only_intro) == ["intro"]
    assert only_intro["intro"].layout.meta["transition_after_ms"] == 0
    with pytest.raises(ValueError, match="no screen 'nope'"):
        api.render_parent_trial(
            words, fixations, "synthetic", "multipart_demo", screens=["nope"]
        )


@pytest.mark.parametrize("with_figure", [True, False])
def test_each_screens_plot_config_records_its_own_canvas(with_figure):
    """The config beside a screen's figure records that screen's canvas, not the
    dataset's — with or without the figure (BUG-104)."""
    words, fixations = make_multipart_synthetic_data()
    payload, _ = bulk_export(
        api.list_trials(words, fixations),
        words,
        fixations,
        canvas_width=2560,
        canvas_height=1440,
        base_font_size=16,
        font_family="Arial",
        x_field="x",
        y_field="y",
        settings={},
        options=ExportOptions(
            include_png=False,
            include_svg=False,
            include_html=with_figure,
            include_plot_config=True,
        ),
    )
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        canvases = {
            name.split("/screens/")[1].split("/")[0]: json.loads(archive.read(name))[
                "canvas_px"
            ]
            for name in archive.namelist()
            if name.endswith("plot_config.json") and "/screens/" in name
        }
    assert canvases == {
        "screen-001-intro": {"width": 640, "height": 480},
        "screen-002-question": {"width": 800, "height": 600},
    }


def test_direct_comparison_selects_the_matching_screen_only():
    words, fixations = make_multipart_synthetic_data()
    other_words = words.assign(participant_id="other", trial_id="other_trial")
    other_fixations = fixations.assign(participant_id="other", trial_id="other_trial")
    meta = _build_compare_meta(
        pd.concat([words, other_words]),
        pd.concat([fixations, other_fixations]),
        "synthetic",
        "multipart_demo",
        "other",
        "other_trial",
        "question",
    )
    assert meta is not None
    assert meta["words"][SCREEN_ID].unique().tolist() == ["question"]
    assert meta["fixations"][SCREEN_ID].unique().tolist() == ["question"]


def test_comparison_lets_b_choose_its_own_screen_independent_of_a():
    """UX-112: B's screen is its own choice, not A's forced onto it.

    Passing a `compare_screen` is now unconditionally B's own selection —
    there is no "A's screen" concept left in `_build_compare_meta` at all —
    so a value that would be meaningless as *A's* screen id (the fixture only
    has "intro"/"question") still works correctly as long as it identifies a
    real screen of B's own trial.
    """
    words, fixations = make_multipart_synthetic_data()
    other_words = words.assign(participant_id="other", trial_id="other_trial")
    other_fixations = fixations.assign(participant_id="other", trial_id="other_trial")
    meta = _build_compare_meta(
        pd.concat([words, other_words]),
        pd.concat([fixations, other_fixations]),
        "synthetic",
        "multipart_demo",
        "other",
        "other_trial",
        "intro",
    )
    assert meta is not None
    assert meta["words"][SCREEN_ID].unique().tolist() == ["intro"]
    assert meta["fixations"][SCREEN_ID].unique().tolist() == ["intro"]


def test_cross_dataset_comparison_scopes_b_to_its_own_chosen_screen():
    """The regression this fix exists for: a cross-dataset multipart B used to
    come back as *every* screen concatenated (`compare_screen` was force-set
    to `None` whenever `source is not None`) — each screen its own coordinate
    space, silently mixed into one frame. B choosing its own screen applies
    regardless of `source`, so a cross-dataset B is scoped exactly like a
    same-dataset one."""
    from scanpath_studio.compare_source import SecondaryDataset
    from scanpath_studio.experimental_setup import SetupSnapshot

    words, fixations = make_multipart_synthetic_data()
    source = SecondaryDataset(
        name="OtherCorpus",
        words=words,
        fixations=fixations,
        combos=pd.DataFrame(),
        setup=SetupSnapshot(),
    )
    meta = _build_compare_meta(
        pd.DataFrame(),  # unused: `source is not None` reads from `source` instead
        pd.DataFrame(),
        "synthetic",
        "multipart_demo",
        "synthetic",
        "multipart_demo",
        "question",
        source=source,
    )
    assert meta is not None
    assert meta["words"][SCREEN_ID].unique().tolist() == ["question"]
    assert meta["fixations"][SCREEN_ID].unique().tolist() == ["question"]


def test_in_app_screen_navigator_keeps_parent_and_steps_in_recorded_order():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_multipart_navigator_app).run()
    assert not at.exception, at.exception
    assert at.selectbox(key="single_screen_id").value == "intro"
    assert at.button(key="single_screen_previous").disabled
    assert not at.button(key="single_screen_next").disabled

    at.button(key="single_screen_next").click().run()
    assert at.selectbox(key="single_screen_id").value == "question"
    assert at.button(key="single_screen_next").disabled


def _two_screen_navigators_app():
    """Stand-ins for A's own navigator and B's (`key_prefix="single_compare"`)
    — the two real surfaces in Compare mode, each over its own multipart
    trial (UX-112)."""
    from scanpath_studio.multipart import part_catalog
    from scanpath_studio.synthetic import make_multipart_synthetic_data
    from scanpath_studio.tabs import _render_screen_navigator

    words, fixations = make_multipart_synthetic_data()
    catalog = part_catalog(words, fixations)
    _render_screen_navigator(catalog)
    _render_screen_navigator(catalog, key_prefix="single_compare")


def test_as_and_bs_screen_navigators_stay_independent():
    """UX-112: distinct keys, so stepping one never touches the other — the
    same guarantee the trial pickers already have for A vs B."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_two_screen_navigators_app).run()
    assert not at.exception, at.exception
    assert at.selectbox(key="single_screen_id").value == "intro"
    assert at.selectbox(key="single_compare_screen_id").value == "intro"

    at.button(key="single_compare_screen_next").click().run()
    assert not at.exception, at.exception
    assert at.selectbox(key="single_compare_screen_id").value == "question"
    # A's own navigator is untouched by stepping B's.
    assert at.selectbox(key="single_screen_id").value == "intro"


def _single_screen_navigator_app():
    from scanpath_studio.multipart import part_catalog
    from scanpath_studio.synthetic import make_multipart_synthetic_data
    from scanpath_studio.tabs import _render_screen_navigator

    words, fixations = make_multipart_synthetic_data()
    # One row = one screen: the case the slider must NOT render for.
    _render_screen_navigator(part_catalog(words, fixations).head(1))


def test_the_screen_navigator_steps_with_no_slider():
    """The screen navigator is a compact cell at the end of the trial row
    (2026-10-07): a dropdown + ◀ ▶, with no scrubbing slider — a trial has few
    screens. ◀ ▶ move ``single_screen_id``, and each end disables its step."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_multipart_navigator_app).run()
    assert not at.exception, at.exception
    assert len(at.select_slider) == 0
    assert at.selectbox(key="single_screen_id").value == "intro"
    assert at.button(key="single_screen_previous").disabled

    at.button(key="single_screen_next").click().run()
    assert at.selectbox(key="single_screen_id").value == "question"
    assert not at.button(key="single_screen_previous").disabled


def test_ux47_single_screen_trial_renders_no_slider():
    """A one-option ``st.select_slider`` throws ``RangeError`` in the browser and
    blanks the tab. AppTest runs no frontend, so it cannot catch that directly —
    what it *can* pin is the guard: at one screen, no slider is built at all."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_single_screen_navigator_app).run()
    assert not at.exception, at.exception
    assert at.selectbox(key="single_screen_id").value == "intro"
    assert len(at.select_slider) == 0


def test_ux47_screen_steps_live_in_a_railbtn_cluster():
    """The ◀ ▶ pair must sit in a ``railbtn_*`` container.

    That key is the whole mechanism behind the alignment: styles.py lays every
    ``[class*="st-key-railbtn_"]`` out as a right-packed flex row with a shared
    pill shape, so the screen row lands on the same edge as the trial picker's
    ◀ ▶ ⇅ and the Filter-by **More**. No DOM exists under AppTest, so this is
    pinned structurally — the same approach test_tour.py takes for its CSS hooks.
    """
    import inspect

    from scanpath_studio.styles import get_app_css
    from scanpath_studio.tabs import _render_screen_navigator

    source = inspect.getsource(_render_screen_navigator)
    # UX-112: the key is prefix-parameterized (A's own "single" default, B's
    # own "single_compare") rather than the literal "single_screen_trail" —
    # still a `railbtn_*` name, which is the part the shared CSS rule below
    # actually matches on.
    assert 'key=f"railbtn_{key_prefix}_screen_trail"' in source
    # The steps must be children of that container, not of the columns.
    assert 'trail.button(\n        f"◀ {spoken(' in source
    assert 'trail.button(\n        f"▶ {spoken(' in source
    # ...and the shared rule must actually match that key.
    assert '[class*="st-key-railbtn_"] {' in get_app_css()


def test_a_stamped_screen_order_survives_a_mapping_that_does_not_name_it():
    """BUG-79: UX-88 took `screen_index` out of the mapping, trusting the corpora
    that stamp it onto their frames — but normalization rebuilt the frame from
    the mapping, so the stamp was dropped and order re-derived from row order.
    MultiplEYE's per-reader question order then disagreed between the tables and
    the 🗂️ Data page crashed. A schema without `screen_index` must keep it."""
    from scanpath_studio.data import normalize_words, propose_word_schema

    words, _ = make_multipart_synthetic_data()
    # Rows in the *reverse* of the recorded screen order: row order is what
    # the stamp has to beat.
    stamped = words.assign(
        screen_index=words[SCREEN_ID].map({"intro": 1, "question": 2})
    ).iloc[::-1]
    schema = propose_word_schema(stamped)
    schema.pop("screen_index", None)
    out = normalize_words(stamped, schema)
    order = out.drop_duplicates(SCREEN_ID).set_index(SCREEN_ID)["screen_index"]
    assert order.to_dict() == {"intro": 1, "question": 2}


def test_an_unmapped_screen_index_column_does_not_make_a_table_multipart():
    """DATA-59: with no screen field mapped, a raw `screen_index` column must not
    ride through BUG-79's stamp path — it derived a `screen_id` from it, so an
    AOI table stayed multipart after its screen fields were cleared, and the
    pair was refused ("Multipart identity is present in only one report")."""
    from scanpath_studio.data import normalize_fixations, normalize_words
    from scanpath_studio.multipart import has_screen_identity, validate_matching_parts

    words = pd.DataFrame(
        {
            "participant_id": ["p1", "p1"],
            "trial_id": ["t1", "t1"],
            "word_id": [0, 1],
            "text": ["a", "b"],
            "x": [0, 10],
            "y": [0, 0],
            "width": [10, 10],
            "height": [10, 10],
            "screen_index": [1, 1],
        }
    )
    fixations = pd.DataFrame(
        {
            "participant_id": ["p1"],
            "trial_id": ["t1"],
            "x": [5.0],
            "y": [5.0],
            "duration_ms": [100],
        }
    )
    word_schema = {
        "participant": "participant_id",
        "trial": "trial_id",
        "word_id": "word_id",
        "text": "text",
        "x": "x",
        "y": "y",
        "width": "width",
        "height": "height",
    }
    fix_schema = {
        "participant": "participant_id",
        "trial": "trial_id",
        "x": "x",
        "y": "y",
        "duration": "duration_ms",
    }
    out_words = normalize_words(words, word_schema)
    assert not has_screen_identity(out_words)
    validate_matching_parts(out_words, normalize_fixations(fixations, fix_schema))


def test_a_co_animation_draws_one_screen_of_a_multipart_second_reading():
    """BUG-85: `trial_b=` cut B to one trial but kept every screen of it, so a
    multipart B drew all its screens as one trail in A's coordinates — each
    screen is its own coordinate space. B keeps its first recorded screen, as A
    does without `screen=` and as the app's B navigator starts; B frames cut to
    another screen with `extract_part` pick that one instead."""
    words, fixations = make_multipart_synthetic_data()
    pid, tid = "synthetic", "multipart_demo"

    def trace_b(fig):
        (trace,) = [trace for trace in fig.data if trace.name == "Scanpath B"]
        return trace

    first = api.animate_scanpath(words, fixations, pid, tid, trial_b=(pid, tid))
    assert len(trace_b(first).x) == MULTIPART_EXPECTED["fixations_per_screen"][0]
    # The two screens differ in size, so A's question screen cannot co-animate
    # with B's first page in one coordinate space.
    from scanpath_studio.experimental_setup import IncomparableScreensError

    with pytest.raises(IncomparableScreensError):
        api.animate_scanpath(
            words, fixations, pid, tid, screen="question", trial_b=(pid, tid)
        )
    picked = api.animate_scanpath(
        words,
        fixations,
        pid,
        tid,
        screen="question",
        trial_b=(pid, tid),
        screen_b="question",
    )
    assert len(trace_b(picked).x) == MULTIPART_EXPECTED["fixations_per_screen"][1]

    chosen = api.animate_scanpath(
        words,
        fixations,
        pid,
        tid,
        screen="question",
        words_b=extract_part(words, pid, tid, "question"),
        fixations_b=extract_part(fixations, pid, tid, "question"),
    )
    assert len(trace_b(chosen).x) == MULTIPART_EXPECTED["fixations_per_screen"][1]


def _per_sentence_app():
    from scanpath_studio import tabs
    from scanpath_studio.synthetic import make_multipart_synthetic_data

    words, fixations = make_multipart_synthetic_data()
    # One text over both screens, so only the screen tells their sentence 1s apart.
    tabs._render_per_sentence_tab(
        words.assign(text_id="same"), fixations.assign(text_id="same")
    )


def test_per_sentence_keeps_each_screens_sentences_apart():
    """BUG-109: sentence ids restart per screen, so a sentence is keyed by its
    screen too — screen 1's sentence 1 is never averaged with screen 2's."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_per_sentence_app).run()
    assert not at.exception, at.exception
    at.selectbox(key="sentence_measure").set_value("total_dur").run()
    summary = at.dataframe[0].value
    assert list(summary[SCREEN_ID]) == ["intro", "question"]
    assert list(summary["sentence_id"]) == [1, 1]
    assert summary["Mean total fixation duration (ms)"].nunique() == 2


def _export_options_app():
    import pandas as pd
    import streamlit as st

    from scanpath_studio.export import render_export_options

    combos = pd.DataFrame({"participant_id": ["p"], "trial_id": ["t"]})
    options = render_export_options(st, combos, screen_options=["intro", "question"])
    st.write(f"screens={options.screens}")


def test_export_panel_offers_a_screens_picker():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_export_options_app).run()
    picker = at.multiselect(key="export_screens")
    assert picker.options == ["intro", "question"]
    assert any("screens=None" in md.value for md in at.markdown)
    picker.set_value(["question"]).run()
    assert any("screens=('question',)" in md.value for md in at.markdown)
