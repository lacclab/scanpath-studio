"""Executable specification for multipart logical trials (DATA-21)."""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from scanpath_studio import api
from scanpath_studio.annotations import deserialize, serialize
from scanpath_studio.export import ExportOptions, bulk_export
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
    normalized_words, normalized_fixations = api.load_scanpath_data(words, fixations)
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
    )
    second = api.plot_scanpath(
        normalized_words,
        normalized_fixations,
        "synthetic",
        "multipart_demo",
        screen="question",
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


def _single_screen_navigator_app():
    from scanpath_studio.multipart import part_catalog
    from scanpath_studio.synthetic import make_multipart_synthetic_data
    from scanpath_studio.tabs import _render_screen_navigator

    words, fixations = make_multipart_synthetic_data()
    # One row = one screen: the case the slider must NOT render for.
    _render_screen_navigator(part_catalog(words, fixations).head(1))


def test_ux47_screen_slider_and_selectbox_stay_in_sync_both_ways():
    """UX-47: the screen row gained the trial picker's scrubbing slider.

    The slider is a second view of ``single_screen_id``, never a second source of
    truth — stepping or picking must move the thumb, and scrubbing must move the
    canonical selection back.
    """
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_multipart_navigator_app).run()
    assert not at.exception, at.exception
    assert at.select_slider(key="single_screen_pos").value == "intro"

    # ◀ ▶ write the selectbox; the slider must follow on the next run.
    at.button(key="single_screen_next").click().run()
    assert at.select_slider(key="single_screen_pos").value == "question"

    # ...and a drag writes back, via the _on_screen_slider callback.
    at.select_slider(key="single_screen_pos").set_value("intro").run()
    assert at.selectbox(key="single_screen_id").value == "intro"
    assert at.button(key="single_screen_previous").disabled


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
    assert 'container(key="railbtn_single_screen_trail")' in source
    # The steps must be children of that container, not of the columns.
    assert 'trail.button(\n        "◀"' in source
    assert 'trail.button(\n        "▶"' in source
    # ...and the shared rule must actually match that key.
    assert '[class*="st-key-railbtn_"] {' in get_app_css()
