"""VIZ-31: the saccade reading-class filter — which classes are drawn at all.

The Saccades section of the rail grew a 🧹 *filter* sub-section to match the
fixation one, and what it filters on is ``measures.classify_saccades`` — the
same split the VIZ-8 "By type" *colouring* uses, applied as visibility instead
of hue. "Show me only the regressions" is the figure a reading paper asks for;
before this the closest thing was colouring the other four classes to match the
background.

Three properties are worth pinning:

* the filter really removes segments — **and their direction arrows**, which come
  from a separate trace and would otherwise float over nothing;
* selecting every class is a *no-op*, byte-for-byte, because the builder
  short-circuits it back onto the unclassified fast path (the common case must
  not start paying for a classification pass); and
* it composes with both class colour modes, filtering on the *unfolded* classes
  so "regressions only" means the same thing under "By type" and under VIZ-19's
  two-way fold.

The wire-format round-trips (share link, saved config) live here too — a
"regressions only" view is exactly the kind of figure a link exists to
reproduce, so it has to survive one.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.constants import SACCADE_CLASS_ORDER
from scanpath_studio.data import (
    infer_fix_schema,
    infer_word_schema,
    load_sample_data,
    normalize_fixations,
    normalize_words,
)
from scanpath_studio.measures import classify_saccades
from scanpath_studio.plots import make_scanpath_figure

_LINE_NAMES = {
    "saccades",
    "Forward",
    "Skip",
    "Refixation",
    "Return sweep",
    "Regression",
    "Other",
}


@pytest.fixture(scope="module")
def trial():
    """One real trial from the bundled demo — every reading class is present.

    The tiny ``conftest`` frames read strictly forward, so they can't exercise a
    filter: the classes that matter here (regression, return sweep) only occur in
    a real multi-line scanpath.
    """
    words_raw, fixations_raw = load_sample_data()
    word_schema = infer_word_schema(words_raw)
    fix_schema = infer_fix_schema(fixations_raw)
    assert word_schema is not None and fix_schema is not None
    words = normalize_words(words_raw, word_schema)
    fix = normalize_fixations(fixations_raw, fix_schema)
    pid = fix["participant_id"].iloc[0]
    tid = fix.loc[fix["participant_id"] == pid, "trial_id"].iloc[0]
    trial_words = words[(words["participant_id"] == pid) & (words["trial_id"] == tid)]
    trial_fix = fix[(fix["participant_id"] == pid) & (fix["trial_id"] == tid)]
    classes = set(classify_saccades(trial_fix, trial_words).dropna())
    assert {"regression", "return_sweep"} <= classes, (
        f"the demo trial lost the classes this module filters on: {sorted(classes)}"
    )
    return trial_words, trial_fix


def _figure(words: pd.DataFrame, fixations: pd.DataFrame, **overrides):
    return make_scanpath_figure(
        words,
        fixations,
        canvas_width=1024,
        canvas_height=600,
        base_font_size=14,
        font_family="monospace",
        x_field="x",
        y_field="y",
        show_words=False,
        show_word_labels=False,
        show_fixations=True,
        show_order=False,
        show_saccades=True,
        show_saccade_arrows=True,
        show_heatmap=False,
        color_by="duration_ms",
        heatmap_metric=None,
        marker_size_range=(8, 24),
        order_font_size=10,
        order_font_color="#111111",
        show_colorbars=False,
        fixation_color_range=None,
        heatmap_range=None,
        **overrides,
    )


def _counts(fig) -> tuple[int, int]:
    """(saccade line points, arrowheads) — the two traces the filter must thin."""
    lines = sum(len(t.x) for t in fig.data if (t.name or "") in _LINE_NAMES)
    arrows = sum(len(t.x) for t in fig.data if t.name == "saccade direction")
    return lines, arrows


class TestFilterRemovesSegments:
    def test_single_class_keeps_only_that_class(self, trial):
        words, fixations = trial
        classes = classify_saccades(fixations, words)
        n_regressions = int((classes == "regression").sum())
        assert n_regressions > 0, "sample trial has no regressions to filter down to"

        _, arrows_all = _counts(_figure(words, fixations))
        lines, arrows = _counts(
            _figure(words, fixations, saccade_classes=["regression"])
        )
        # Each straight segment contributes (x0, x1, None).
        assert lines == n_regressions * 3
        assert arrows == n_regressions
        assert arrows < arrows_all, "the filter did not thin the arrowhead trace"

    def test_arrows_follow_the_filter_in_arc_mode(self, trial):
        """BUG-9's arch points are per-segment too, so the mask must hold there."""
        words, fixations = trial
        classes = classify_saccades(fixations, words)
        n_regressions = int((classes == "regression").sum())
        _, arrows = _counts(
            _figure(
                words,
                fixations,
                saccade_render_mode="Arc",
                saccade_classes=["regression"],
            )
        )
        assert arrows == n_regressions

    def test_two_classes_is_the_sum_of_each(self, trial):
        words, fixations = trial
        one = _counts(_figure(words, fixations, saccade_classes=["regression"]))
        two = _counts(_figure(words, fixations, saccade_classes=["return_sweep"]))
        both = _counts(
            _figure(words, fixations, saccade_classes=["regression", "return_sweep"])
        )
        assert both == (one[0] + two[0], one[1] + two[1])


class TestFullSelectionIsANoOp:
    def test_every_class_matches_no_filter_at_all(self, trial):
        """The default selects all six — it must cost nothing and change nothing."""
        words, fixations = trial
        assert _counts(
            _figure(words, fixations, saccade_classes=list(SACCADE_CLASS_ORDER))
        ) == _counts(_figure(words, fixations))

    def test_none_and_full_produce_the_same_trace_names(self, trial):
        words, fixations = trial
        unfiltered = _figure(words, fixations)
        full = _figure(words, fixations, saccade_classes=list(SACCADE_CLASS_ORDER))
        assert [t.name for t in full.data] == [t.name for t in unfiltered.data]


class TestComposesWithColourModes:
    @pytest.mark.parametrize("mode", ["By type", "Forward / regression"])
    def test_filter_applies_under_every_colour_mode(self, trial, mode):
        words, fixations = trial
        classes = classify_saccades(fixations, words)
        n_regressions = int((classes == "regression").sum())
        lines, arrows = _counts(
            _figure(
                words,
                fixations,
                saccade_color_mode=mode,
                saccade_classes=["regression"],
            )
        )
        assert (lines, arrows) == (n_regressions * 3, n_regressions)

    def test_two_way_fold_happens_after_the_filter(self, trial):
        """VIZ-19 folds skip/refixation/return-sweep into "Forward".

        The filter names *unfolded* classes, so asking for return sweeps alone
        must leave one Forward-coloured trace holding only return sweeps — not
        every forward-ish saccade.
        """
        words, fixations = trial
        classes = classify_saccades(fixations, words)
        n_sweeps = int((classes == "return_sweep").sum())
        fig = _figure(
            words,
            fixations,
            saccade_color_mode="Forward / regression",
            saccade_classes=["return_sweep"],
        )
        drawn = [t for t in fig.data if (t.name or "") in _LINE_NAMES]
        assert [t.name for t in drawn] == ["Forward"]
        assert len(drawn[0].x) == n_sweeps * 3


class TestWireFormat:
    def test_share_link_round_trips_a_subset(self):
        """A "regressions only" figure has to survive being linked to."""
        from scanpath_studio.url_state import _parse_saccade_classes

        assert _parse_saccade_classes("regression") == ["regression"]
        # Ordered by SACCADE_CLASS_ORDER, not by how the link spelled it, so the
        # same selection always produces the same figure-cache key.
        assert _parse_saccade_classes("regression,forward") == [
            "forward",
            "regression",
        ]

    def test_unknown_class_in_a_link_is_rejected(self):
        """The multiselect raises on a value outside its options, so the reader
        must reject the param (→ "Ignored bad URL param") rather than seed it."""
        from scanpath_studio.url_state import _parse_saccade_classes

        with pytest.raises(ValueError):
            _parse_saccade_classes("regression,microsaccade")

    def test_cli_flag_rejects_an_unknown_class(self):
        from scanpath_studio.cli import main

        with pytest.raises(SystemExit):
            main(
                [
                    "render",
                    "--sample",
                    "--saccade-classes",
                    "microsaccade",
                    "-o",
                    "unused.html",
                ]
            )
