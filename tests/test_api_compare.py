"""CMP-9 — compare mode's headless surface.

Compare mode existed only in the UI and the share link: there was no way to
build a two-scanpath figure from a script or a Makefile. `compare_scanpaths` is
that surface, and the cross-dataset half of it is where the sharp edges are —
the participant-namespacing rule that `tests/test_compare_cross_dataset.py`
guards for the app has to hold here too, from a completely different caller.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api
from scanpath_studio.experimental_setup import Provenance, SetupSnapshot


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


def _measured(width: int = 1920, height: int = 1080) -> SetupSnapshot:
    return SetupSnapshot(
        canvas_width=width,
        canvas_height=height,
        screen_provenance=Provenance.MEASURED,
    )


def _pair():
    words = pd.concat(
        [_words("p1", "t1"), _words("p2", "t2", x0=400.0)], ignore_index=True
    )
    fixations = pd.concat(
        [_fixations("p1", "t1", y=70.0), _fixations("p2", "t2", y=300.0)],
        ignore_index=True,
    )
    return words, fixations


class TestSameDataset:
    def test_overlay_builds(self):
        words, fixations = _pair()
        fig = api.compare_scanpaths(
            words, fixations, ("p1", "t1"), ("p2", "t2"), canvas_size=(1920, 1080)
        )
        assert fig.data

    @pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
    def test_every_layout_builds(self, layout):
        words, fixations = _pair()
        fig = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t2"),
            layout=layout,
            canvas_size=(1920, 1080),
        )
        assert fig.data

    def test_hyphenated_layout_is_accepted(self):
        """`--compare-layout side-by-side` and the API must agree on one name."""
        words, fixations = _pair()
        fig = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t2"),
            layout="side-by-side",
            canvas_size=(1920, 1080),
        )
        assert fig.data

    def test_an_unknown_layout_names_the_valid_ones(self):
        words, fixations = _pair()
        with pytest.raises(ValueError, match="overlay"):
            api.compare_scanpaths(
                words, fixations, ("p1", "t1"), ("p2", "t2"), layout="sideways"
            )

    def test_unknown_keyword_names_close_matches(self):
        words, fixations = _pair()
        with pytest.raises(TypeError, match="show_saccades"):
            api.compare_scanpaths(
                words, fixations, ("p1", "t1"), ("p2", "t2"), show_saccade=False
            )


class TestCrossDataset:
    """B arrives as its own pair of frames — the CMP-8 §3 rule, headless."""

    def test_colliding_ids_still_render_two_distinct_scanpaths(self):
        """Both corpora hold ``(p1, t1)``; un-namespaced, one reading draws twice."""
        fig = api.compare_scanpaths(
            _words("p1", "t1"),
            _fixations("p1", "t1", y=70.0),
            ("p1", "t1"),
            ("p1", "t1"),
            words_b=_words("p1", "t1"),
            fixations_b=_fixations("p1", "t1", y=300.0),
            dataset_b="PoTeC",
            layout="stacked",
            canvas_size=(1920, 1080),
        )
        per_trace = [
            {round(float(y)) for y in trace.y if y is not None}
            for trace in fig.data
            if getattr(trace, "y", None) is not None and len(trace.y)
        ]
        assert {70} in per_trace, per_trace
        assert {300} in per_trace, per_trace
        assert {70, 300} not in per_trace, "a panel drew both scanpaths"

    def test_overlay_on_one_screen_is_allowed(self):
        fig = api.compare_scanpaths(
            _words("p1", "t1"),
            _fixations("p1", "t1", y=70.0),
            ("p1", "t1"),
            ("p1", "t1"),
            words_b=_words("p1", "t1"),
            fixations_b=_fixations("p1", "t1", y=300.0),
            dataset_b="PoTeC",
            layout="overlay",
            setup=_measured(),
            setup_b=_measured(),
        )
        assert fig.data

    def test_overlay_on_two_screens_raises_rather_than_resolving(self):
        """Headless must NOT silently hand back a different layout.

        The app resolves an incomparable overlay to side-by-side, because a user
        can see what they got. A script cannot, so returning a differently-shaped
        figure than the one asked for is the wrong failure here.
        """
        with pytest.raises(ValueError) as excinfo:
            api.compare_scanpaths(
                _words("p1", "t1"),
                _fixations("p1", "t1"),
                ("p1", "t1"),
                ("p1", "t1"),
                words_b=_words("p1", "t1"),
                fixations_b=_fixations("p1", "t1", y=300.0),
                dataset_b="PoTeC",
                layout="overlay",
                setup=_measured(1920, 1080),
                setup_b=_measured(1680, 1050),
            )
        message = str(excinfo.value)
        assert "1680" in message
        # BUG-85: it says what this surface does — nothing was drawn — and how
        # to ask for the split here, not the app's "shown side by side instead".
        assert "side by side instead" not in message
        assert "layout='side_by_side'" in message
        # The surface-neutral reason rides along, so `render` can word the same
        # refusal in its own flags rather than echo Python syntax.
        reason = excinfo.value.reason
        assert "1680" in reason and reason in message
        assert "layout=" not in reason

    def test_a_split_layout_is_allowed_on_two_screens(self):
        fig = api.compare_scanpaths(
            _words("p1", "t1"),
            _fixations("p1", "t1"),
            ("p1", "t1"),
            ("p1", "t1"),
            words_b=_words("p1", "t1"),
            fixations_b=_fixations("p1", "t1", y=300.0),
            dataset_b="PoTeC",
            layout="side_by_side",
            setup=_measured(1920, 1080),
            setup_b=_measured(1680, 1050),
        )
        assert fig.data

    def test_disjoint_columns_do_not_break_the_merge(self):
        """Two corpora rarely ship the same measure set (CMP-8 §5.4)."""
        fig = api.compare_scanpaths(
            _words("p1", "t1"),
            _fixations("p1", "t1").assign(gpt2_surprisal=[1.0, 2.0, 3.0]),
            ("p1", "t1"),
            ("p1", "t1"),
            words_b=_words("p1", "t1"),
            fixations_b=_fixations("p1", "t1", y=300.0).assign(word_length=[3, 5, 3]),
            dataset_b="PoTeC",
            layout="stacked",
            canvas_size=(1920, 1080),
        )
        assert fig.data


class TestCompareStimulus:
    def test_b_only_drops_as_stimulus_layer(self):
        words, fixations = _pair()
        both = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t2"),
            canvas_size=(1920, 1080),
            show_words=True,
        )
        only_b = api.compare_scanpaths(
            words,
            fixations,
            ("p1", "t1"),
            ("p2", "t2"),
            canvas_size=(1920, 1080),
            compare_stimulus="b",
            show_words=True,
        )

        def lefts(fig):
            return {
                round(float(shape.x0))
                for shape in fig.layout.shapes
                if (shape.name or "").startswith("__sps_layer:word_boxes")
            }

        assert {100, 400} <= lefts(both)
        assert 100 not in lefts(only_b)
        assert 400 in lefts(only_b)


class TestExportedFromThePackageRoot:
    def test_lazy_re_export(self):
        import scanpath_studio as sps

        assert callable(sps.compare_scanpaths)


class TestFigureOptions:
    def test_comparison_kind_is_answerable(self):
        """`_reject_unknown_options` points callers at `figure_options()`.

        It said "api.figure_options() lists them with their defaults" while
        `figure_options("comparison")` raised — so the error message sent you
        somewhere that did not exist.
        """
        options = api.figure_options("comparison")
        assert "compare_stimulus" not in options  # a named parameter, not a kwarg
        assert "show_words" in options
        assert "layout" not in options  # ditto
        # Animation-only settings are not comparison options.
        assert "playback_speed" not in options

    def test_unknown_kind_names_all_three(self):
        with pytest.raises(ValueError, match="comparison"):
            api.figure_options("nonsense")


class TestDualCoAnimationAcceptsCompareStimulus:
    def test_animate_scanpath_takes_compare_stimulus(self):
        """`_render_scanpath_animation` reads it, so the option set must allow it.

        It was excluded alongside `layout`/`style_a`/`canvas_b`, which the
        animation builder genuinely never reads — but this one it does, so the
        exclusion made a reachable dual co-animation setting unreachable.
        """
        words, fixations = _pair()
        fig = api.animate_scanpath(
            words,
            fixations,
            "p1",
            "t1",
            canvas_size=(1920, 1080),
            words_b=_words("p2", "t2", x0=400.0),
            fixations_b=_fixations("p2", "t2", y=300.0),
            compare_stimulus="b",
        )
        assert fig.frames


class TestCoAnimationDrawsOneSecondReading:
    """BUG-85: `animate_scanpath` drew whatever B frames it was handed.

    `compare_scanpaths` takes B's *corpus* plus a `trial_b` pair, so frames
    passed the same way to the co-animation drew every fixation in them — 3,209
    on the demo, where B's trial has 89. `trial_b` now picks the reading, as it
    does there, and B frames holding several trials refuse rather than guess.
    """

    _A = ("l37_1129", "l37_1129_2_1_1_Ele_r0")
    _B = ("l37_1129", "l37_1129_2_1_2_Ele_r0")

    @staticmethod
    def _trace_b(fig):
        (trace,) = [trace for trace in fig.data if trace.name == "Scanpath B"]
        return trace

    def test_trial_b_picks_one_reading_out_of_the_corpus(self):
        from scanpath_studio.utils import extract_trial

        words, fixations = api.load_sample_data()
        expected = len(extract_trial(fixations, *self._B))
        fig = api.animate_scanpath(words, fixations, *self._A, trial_b=self._B)
        assert len(self._trace_b(fig).x) == expected

    def test_trial_b_is_looked_up_in_bs_own_frames(self):
        """A second dataset's reader is found in *its* frames, never in A's."""
        words, fixations = _pair()
        fig = api.animate_scanpath(
            words,
            fixations,
            "p1",
            "t1",
            canvas_size=(1920, 1080),
            words_b=pd.concat(
                [_words("p9", "t9"), _words("p8", "t8")], ignore_index=True
            ),
            fixations_b=pd.concat(
                [_fixations("p9", "t9", y=300.0), _fixations("p8", "t8", y=500.0)],
                ignore_index=True,
            ),
            trial_b=("p9", "t9"),
        )
        trace = self._trace_b(fig)
        assert len(trace.y) == 3
        # The replay's first frame holds each not-yet-reached fixation as None.
        assert {round(float(y)) for y in trace.y if y is not None} == {300}

    def test_b_frames_holding_several_trials_ask_for_trial_b(self):
        words, fixations = api.load_sample_data()
        with pytest.raises(ValueError, match=r"trial_b="):
            api.animate_scanpath(
                words, fixations, *self._A, words_b=words, fixations_b=fixations
            )

    def test_a_trial_b_with_no_fixations_raises(self):
        words, fixations = api.load_sample_data()
        with pytest.raises(ValueError, match="No fixations for the second scanpath"):
            api.animate_scanpath(
                words, fixations, *self._A, trial_b=("nobody", "nothing")
            )

    def test_one_trials_frames_still_need_no_trial_b(self):
        """The shape every existing caller passes — `render` slices B first."""
        words, fixations = _pair()
        fig = api.animate_scanpath(
            words,
            fixations,
            "p1",
            "t1",
            canvas_size=(1920, 1080),
            words_b=_words("p2", "t2", x0=400.0),
            fixations_b=_fixations("p2", "t2", y=300.0),
        )
        assert len(self._trace_b(fig).x) == 3


@pytest.mark.parametrize("layout", ["overlay", "side_by_side", "stacked"])
def test_the_default_comparison_draws_the_apps_marker_opacity(monkeypatch, layout):
    """CMP-20: the app seeds each scanpath's `cmp{idx}_opacity` at 0.7, while
    the builder's own fallback — all a headless caller ever got — was 1.0. Both
    now read one constant, so the default figures agree."""
    from scanpath_studio import controls

    seeded: dict = {}
    monkeypatch.setattr(
        controls, "_pin", lambda key, default: seeded.setdefault(key, default)
    )
    controls._seed_compare_styles()

    words = pd.concat([_words("p1", "t1"), _words("p2", "t1")], ignore_index=True)
    fixations = pd.concat(
        [_fixations("p1", "t1"), _fixations("p2", "t1")], ignore_index=True
    )
    fig = api.compare_scanpaths(
        words, fixations, ("p1", "t1"), ("p2", "t1"), layout=layout
    )
    opacities = [t.marker.opacity for t in fig.data if t.mode and "markers" in t.mode]
    assert opacities == [seeded["cmp0_opacity"], seeded["cmp1_opacity"]]
