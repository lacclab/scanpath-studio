"""CMP-8 — comparing scanpaths across two datasets.

The regression this file exists for is the one in §3: two corpora can hold the
same ``(participant_id, trial_id)``, and the comparison builder slices its frame
by exactly that pair — so an un-namespaced merge renders *the wrong scanpath*,
silently and plausibly. Everything else here (per-panel geometry, the column
union, the overlay gate) guards a correct-looking figure that would be lying
about its own geometry.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.compare_source import SecondaryDataset
from scanpath_studio.experimental_setup import Provenance, SetupSnapshot
from scanpath_studio.plots import FigureSettings, make_comparison_figure

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _words(participant: str, trial: str, *, x0: float = 100.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 3,
            "trial_id": [trial] * 3,
            "text_id": ["t1"] * 3,
            "word_id": [0, 1, 2],
            "text": ["the", "quick", "fox"],
            "x": [x0, x0 + 100, x0 + 200],
            "y": [50.0, 50.0, 50.0],
            "width": [90.0, 90.0, 90.0],
            "height": [40.0, 40.0, 40.0],
        }
    )


def _fixations(participant: str, trial: str, *, y: float = 70.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "participant_id": [participant] * 3,
            "trial_id": [trial] * 3,
            "text_id": ["t1"] * 3,
            "x": [120.0, 220.0, 320.0],
            "y": [y, y, y],
            "duration_ms": [200.0, 250.0, 180.0],
            "timestamp_ms": [0.0, 200.0, 450.0],
            "order_in_trial": [1, 2, 3],
            "word_id": [0, 1, 2],
        }
    )


class TestQualifyForCompare:
    def test_leaves_the_source_frame_untouched(self):
        frame = _fixations("p1", "t1")
        before = frame.copy()
        tabs._qualify_for_compare(frame, "PoTeC")
        pd.testing.assert_frame_equal(frame, before)

    def test_ids_collide_before_and_not_after(self):
        a = _fixations("p1", "t1")
        b = _fixations("p1", "t1")
        assert set(a["participant_id"]) == set(b["participant_id"])
        qualified = tabs._qualify_for_compare(b, "PoTeC")
        assert set(a["participant_id"]).isdisjoint(set(qualified["participant_id"]))
        assert set(qualified["dataset"]) == {"PoTeC"}
        assert qualified["participant_id"].iloc[0] == tabs._qualified_participant(
            "PoTeC", "p1"
        )

    def test_an_empty_frame_passes_through(self):
        empty = _fixations("p1", "t1").iloc[0:0]
        assert tabs._qualify_for_compare(empty, "PoTeC").empty

    def test_the_two_intended_trials_render_when_the_ids_collide(self):
        """The whole point of §3.

        Both datasets hold ``(p1, t1)``. Without namespacing the builder would
        slice the *same* rows twice and draw one scanpath as if it were two —
        wrong, and completely plausible on screen.
        """
        words_a, fix_a = _words("p1", "t1"), _fixations("p1", "t1", y=70.0)
        words_b = tabs._qualify_for_compare(_words("p1", "t1"), "PoTeC")
        fix_b = tabs._qualify_for_compare(_fixations("p1", "t1", y=300.0), "PoTeC")

        merged_words = pd.concat([words_a, words_b])
        merged_fix = pd.concat([fix_a, fix_b])
        fig = make_comparison_figure(
            merged_words,
            merged_fix,
            ("p1", "t1"),
            (tabs._qualified_participant("PoTeC", "p1"), "t1"),
            settings=FigureSettings(
                canvas_width=1000,
                canvas_height=800,
                base_font_size=16,
                layout="stacked",
            ),
        )
        # Panel A's fixations sit at y=70, panel B's at y=300. Asserting each
        # *panel* holds only its own is what makes this a real regression test:
        # without namespacing both slices match all six rows, so both panels draw
        # both scanpaths — and a "both values are somewhere in the figure" check
        # would pass on the bug (verified by removing the qualification).
        per_trace = [
            {round(float(y)) for y in trace.y if y is not None}
            for trace in fig.data
            if getattr(trace, "y", None) is not None and len(trace.y)
        ]
        assert {70} in per_trace, per_trace
        assert {300} in per_trace, per_trace
        assert {70, 300} not in per_trace, "a panel drew both scanpaths"


class TestAlignCompareColumns:
    def test_union_preserved_and_intersection_reported(self):
        a = _fixations("p1", "t1").assign(gpt2_surprisal=[1.0, 2.0, 3.0])
        b = _fixations("p2", "t2").assign(word_length=[3, 5, 3])
        a_out, b_out, shared = tabs._align_compare_columns(a, b)

        assert list(a_out.columns) == list(b_out.columns)
        assert {"gpt2_surprisal", "word_length"} <= set(a_out.columns)
        # Only columns numeric in BOTH frames may colour a cross-dataset figure.
        assert "duration_ms" in shared
        assert "gpt2_surprisal" not in shared and "word_length" not in shared

    def test_concat_of_disjoint_frames_does_not_warn(self):
        a = _fixations("p1", "t1").assign(only_a=[1, 2, 3])
        b = _fixations("p2", "t2").assign(only_b=[4, 5, 6])
        a_out, b_out, _ = tabs._align_compare_columns(a, b)
        with pd.option_context("mode.chained_assignment", "raise"):
            merged = pd.concat([a_out, b_out])
        assert len(merged) == 6
        assert merged["only_a"].isna().sum() == 3

    def test_identical_frames_are_returned_unchanged(self):
        a, b = _fixations("p1", "t1"), _fixations("p2", "t2")
        a_out, b_out, _ = tabs._align_compare_columns(a, b)
        # No reindex when the columns already match — same objects, no copy.
        assert a_out is a and b_out is b


class TestPerPanelGeometry:
    def _figure(self, *, canvas_b=None):
        words = pd.concat([_words("p1", "t1"), _words("p2", "t2")])
        fixations = pd.concat([_fixations("p1", "t1"), _fixations("p2", "t2")])
        return make_comparison_figure(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t2"),
            settings=FigureSettings(
                canvas_width=1000,
                canvas_height=800,
                base_font_size=16,
                layout="side_by_side",
                canvas_b=canvas_b,
                fit_to_monitor=True,
            ),
        )

    def test_canvas_b_gives_the_second_panel_its_own_axis_range(self):
        same = self._figure()
        differing = self._figure(canvas_b=(2560, 1440))
        # Panel A is untouched; only panel B's x-axis follows the second monitor.
        assert same.layout.xaxis.range == differing.layout.xaxis.range
        assert same.layout.xaxis2.range != differing.layout.xaxis2.range
        assert differing.layout.xaxis2.range[1] == pytest.approx(2560)

    def test_label_font_scales_differ_between_panels_on_different_screens(self):
        differing = self._figure(canvas_b=(2560, 1440))
        label_sizes = [
            float(trace.textfont.size)
            for trace in differing.data
            if getattr(trace, "name", "") == "words" and trace.textfont.size
        ]
        assert len(label_sizes) == 2
        # B's words are drawn on a wider screen fitted into the same panel, so
        # they must come out at a different on-screen size than A's.
        assert label_sizes[0] != label_sizes[1]

    def test_same_dataset_figure_is_unchanged_by_the_new_fields(self):
        """`canvas_b=None` must be a true no-op — every existing comparison."""
        before = self._figure()
        after = self._figure(canvas_b=None)
        assert before.to_json() == after.to_json()


class TestSecondaryDatasetShape:
    def test_snapshot_travels_with_the_dataset(self):
        source = SecondaryDataset(
            name="PoTeC",
            words=_words("r1", "b0"),
            fixations=_fixations("r1", "b0"),
            combos=pd.DataFrame(),
            setup=SetupSnapshot(
                canvas_width=1680,
                canvas_height=1050,
                screen_provenance=Provenance.MEASURED,
            ),
        )
        assert source.setup.canvas == (1680, 1050)
        assert source.setup.screen_provenance is Provenance.MEASURED


def _overlay_gate_app():
    """A cross-dataset pair must resolve to a split layout, key untouched."""
    import streamlit as st

    from scanpath_studio.compare_source import COMPARE_SOURCE_KEY
    from scanpath_studio.tabs import _compare_source_name

    st.session_state["single_compare_layout"] = "Overlay"
    st.session_state[COMPARE_SOURCE_KEY] = "PoTeC"
    layout = {
        "Overlay": "overlay",
        "Side by side": "side_by_side",
        "Stacked": "stacked",
    }.get(st.session_state.get("single_compare_layout"), "overlay")
    if layout == "overlay" and _compare_source_name() is not None:
        layout = "side_by_side"
    st.session_state["_resolved_layout"] = layout


class TestOverlayGate:
    def test_cross_dataset_resolves_to_split_without_rewriting_the_key(self):
        at = AppTest.from_function(_overlay_gate_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["_resolved_layout"] == "side_by_side"
        # Resolve, don't rewrite: switching back to a same-dataset pair has to
        # restore the user's Overlay choice.
        assert at.session_state["single_compare_layout"] == "Overlay"


class TestPairExportBundle:
    def test_bundle_names_both_sources_and_both_setups(self):
        import io
        import json
        import zipfile

        from scanpath_studio.export import ComparisonSide, ExportOptions, pair_export

        side_a = ComparisonSide(
            participant="p1",
            trial="t1",
            words=_words("p1", "t1"),
            fixations=_fixations("p1", "t1"),
            setup=SetupSnapshot().to_dict(),
        )
        qualified_words = tabs._qualify_for_compare(_words("p1", "t1"), "PoTeC")
        qualified_fix = tabs._qualify_for_compare(_fixations("p1", "t1"), "PoTeC")
        side_b = ComparisonSide(
            participant="p1",
            trial="t1",
            words=tabs._unqualify_for_export(qualified_words, "p1"),
            fixations=tabs._unqualify_for_export(qualified_fix, "p1"),
            dataset="PoTeC",
            setup=SetupSnapshot(canvas_width=1680, canvas_height=1050).to_dict(),
        )
        data = pair_export(
            None,  # no figure — Kaleido isn't available in CI
            side_a,
            side_b,
            canvas_width=1000,
            canvas_height=800,
            x_field="x",
            y_field="y",
            settings={},
            options=ExportOptions(
                include_fixations=True, include_measures=True, table_format="csv"
            ),
        )
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            folder = "p1__t1__vs__p1__t1"
            assert f"{folder}/plot_config.json" in names
            assert f"{folder}/fixations.csv" in names
            config = json.loads(zf.read(f"{folder}/plot_config.json"))
            fixations = pd.read_csv(io.BytesIO(zf.read(f"{folder}/fixations.csv")))

        assert config["datasets"]["a"]["source"] is None
        assert config["datasets"]["b"]["source"] == "PoTeC"
        assert config["datasets"]["b"]["setup"]["canvas_width"] == 1680
        # The `dataset` column is what tells two identically-named readers apart
        # in the exported table — the ids themselves are the corpus' own.
        assert set(fixations["dataset"]) == {"(this dataset)", "PoTeC"}
        assert set(fixations["participant_id"]) == {"p1"}


class TestRestoredSetupCannotInventAMonitor:
    """DATA-22's whole point, at the restore door.

    `tabs._build_studio_config` writes `experimental_setup` **without** a canvas
    (that lives in the sibling `canvas_px`). Feeding that section straight to
    `SetupSnapshot.from_dict(..., fallback=SetupSnapshot())` fills 2560x1440 from
    the class default — and if the file's provenance says `measured`, the wizard
    would pre-answer the screen step with a measured monitor nobody measured.
    """

    def test_a_section_without_a_canvas_does_not_pre_answer_the_screen(self):
        from scanpath_studio import wizard

        import streamlit as st

        st.session_state["_wizard_restored_setup"] = {
            "monitor_width_mm": 500.0,
            "viewing_distance_mm": 700.0,
            "screen_provenance": "measured",
            "geometry_provenance": "measured",
            "text_provenance": "assumed",
        }
        answerable = wizard._restored_setup_answerable_groups()
        assert "screen" not in answerable, (
            "a file that never stated a canvas must not pre-answer the screen"
        )
        # The groups it *did* state are still pre-answered — the point is not to
        # re-ask everything, only what the file cannot honestly answer.
        assert {"geometry", "text"} <= answerable

    def test_a_section_carrying_a_canvas_still_pre_answers(self):
        from scanpath_studio import wizard

        import streamlit as st

        st.session_state["_wizard_restored_setup"] = {
            "canvas_width": 1920,
            "canvas_height": 1080,
            "screen_provenance": "measured",
        }
        assert "screen" in wizard._restored_setup_answerable_groups()


def _arrived_provenance_app():
    """A link's `setup_prov` badge must be *shown*, not just parsed and parked."""
    import streamlit as st

    from scanpath_studio.experimental_setup import Provenance, SetupSnapshot
    from scanpath_studio.session_keys import SETUP_PROVENANCE_STATE_KEY
    from scanpath_studio.tabs import _render_arrived_provenance_note

    st.session_state[SETUP_PROVENANCE_STATE_KEY] = {
        "screen": "assumed",
        "geometry": "assumed",
        "text": "measured",
    }
    # This session resolved a *measured* screen — the sender's was assumed.
    _render_arrived_provenance_note(
        SetupSnapshot(
            screen_provenance=Provenance.MEASURED,
            geometry_provenance=Provenance.ASSUMED,
            text_provenance=Provenance.MEASURED,
        )
    )


def _matching_provenance_app():
    import streamlit as st

    from scanpath_studio.experimental_setup import Provenance, SetupSnapshot
    from scanpath_studio.session_keys import SETUP_PROVENANCE_STATE_KEY
    from scanpath_studio.tabs import _render_arrived_provenance_note

    st.session_state[SETUP_PROVENANCE_STATE_KEY] = {"screen": "measured"}
    _render_arrived_provenance_note(
        SetupSnapshot(screen_provenance=Provenance.MEASURED)
    )


class TestArrivedProvenanceIsShown:
    """The `setup_prov` badge exists so a recipient can tell a measured monitor
    from one the app assumed. Parsing it into session state achieves nothing on
    its own — the Data Inspection table is derived from the *recipient's* source,
    so the badge has to be rendered where it disagrees."""

    def test_a_differing_badge_is_surfaced(self):
        at = AppTest.from_function(_arrived_provenance_app)
        at.run()
        assert not at.exception, at.exception
        captions = " ".join(c.value for c in at.caption)
        assert "shared from a setup recorded differently" in captions
        assert "assumed" in captions
        # Only the groups that actually differ are named.
        assert "Screen" in captions or "screen" in captions

    def test_a_matching_badge_is_silent(self):
        at = AppTest.from_function(_matching_provenance_app)
        at.run()
        assert not at.exception, at.exception
        assert [c.value for c in at.caption] == []
