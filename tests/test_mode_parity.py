"""VIZ-23 — the rail's settings must reach *all three* render paths.

The scanpath rail is one control set feeding three builders (static figure,
animation, comparison). ``scanpath_studio/CLAUDE.md`` → *Which viz settings
apply in which render path (VIZ-21)* is the map; this file is the executable
half of it for the cells VIZ-23 turned from ❌ into ✅:

- **drift correction** (PRE-3) is applied once, above the render-mode split, so
  the two Drift-correction controls move fixations on the animation and the
  comparison figure too — not just the static plot;
- the animation now takes the word-label / arrow / flag / colorbar options;
- the comparison figure now takes the marker symbol, the critical-span text
  marking, the stimulus image and the colorbar styling.

Every assertion is paired with a "correction off / setting at its default"
counterpart, because backward compatibility is the hard constraint: an
untouched control must reproduce exactly what it produced before.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scanpath_studio import alignment, plots, tabs
from scanpath_studio.constants import DEFAULT_FIXATION_SYMBOL, WORD_LABEL_COLOR
from tests.conftest import APP_SCRIPT

# The two text lines of the toy stimulus below sit at these y centers
# (``y + height / 2``), so a corrected fixation must land on one of them.
LINE_CENTERS = (110.0, 210.0)
# Raw fixations are placed this far below their line — far enough that drift
# correction visibly moves them, close enough that the nearest line is obvious.
DRIFT_OFFSET = 9.0
# A 1×1 PNG as a ``data:`` URI — the same shape the stimulus-image *upload* takes,
# and ``plots._image_to_data_uri`` passes it straight through, so the layer draws
# without a fixture file on disk.
STIMULUS_URI = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1Pe"
    "AAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


# -----------------------------------------------------------------------------
# Toy two-reader corpus (two lines of three words, read by "A" and "B")
# -----------------------------------------------------------------------------


def _words() -> pd.DataFrame:
    rows = []
    for participant in ("A", "B"):
        for word_id in range(6):
            rows.append(
                {
                    "participant_id": participant,
                    "trial_id": "t1",
                    "text_id": "para",
                    "word_id": word_id,
                    "x": 100.0 + 100.0 * (word_id % 3),
                    "y": 100.0 if word_id < 3 else 200.0,
                    "width": 50.0,
                    "height": 20.0,
                    "text": f"w{word_id}",
                    "is_in_aspan": word_id in (1, 2),
                    "total_fixation_duration_ms": 100.0 * (word_id + 1),
                }
            )
    return pd.DataFrame(rows)


def _fixations() -> pd.DataFrame:
    rows = []
    for participant, bump in (("A", 0.0), ("B", 3.0)):
        for order, word_id in enumerate([0, 1, 2, 3, 4, 5], start=1):
            line_y = LINE_CENTERS[0] if word_id < 3 else LINE_CENTERS[1]
            rows.append(
                {
                    "participant_id": participant,
                    "trial_id": "t1",
                    "text_id": "para",
                    "x": 125.0 + 100.0 * (word_id % 3) + bump,
                    # Off the line on purpose — this is the vertical drift the
                    # PRE-3 algorithms exist to remove.
                    "y": line_y + DRIFT_OFFSET,
                    "duration_ms": 100.0 + 10.0 * order,
                    "timestamp_ms": 200.0 * (order - 1),
                    "word_id": word_id,
                    "order_in_trial": order,
                }
            )
    return pd.DataFrame(rows)


def _trial(frame: pd.DataFrame, participant: str) -> pd.DataFrame:
    return frame[frame["participant_id"] == participant]


def _viz(**overrides) -> dict:
    """A complete ``viz_settings`` dict at its defaults, plus ``overrides``.

    Mirrors what ``controls._collect_viz_settings`` produces for the keys the
    animation / comparison call sites read, so a wiring test exercises the real
    key names rather than a private shorthand."""
    settings = {
        "show_words": True,
        "show_labels": True,
        "show_fix": True,
        "show_saccades": True,
        "show_saccade_arrows": False,
        "show_order": False,
        "marker_size_range": (8, 24),
        "order_font_size": 10,
        "order_font_color": "#000000",
        "color_by": None,
        "color_by_line": False,
        "fixation_colorscale": "Viridis",
        "fixation_color_range": None,
        "fixation_flags": None,
        "show_colorbars": False,
        "colorbar_orientation": "Vertical",
        "colorbar_tickangle": 0,
        "colorbar_tickfont_size": 12,
        "fixation_symbol": DEFAULT_FIXATION_SYMBOL,
        "text_color": WORD_LABEL_COLOR,
        "critical_span_style": "Mark text",
        "highlight_column": "is_in_aspan",
        "highlight_text_color": "#C8097C",
        "word_hover_measure": None,
        "fit_to_monitor": True,
        "align_algorithm": "Off",
        "align_connectors": False,
    }
    settings.update(overrides)
    return settings


@pytest.fixture
def quiet_chart(monkeypatch):
    """Swallow the true-scale HTML embed, so the two render helpers can be called
    outside a running Streamlit script."""
    monkeypatch.setattr(tabs, "_render_true_scale_chart", lambda *a, **k: None)


# -----------------------------------------------------------------------------
# _drift_corrected — the no-op contract
# -----------------------------------------------------------------------------


class TestDriftCorrectedNoOp:
    """No algorithm selected must cost nothing and change nothing — the default."""

    def test_off_returns_the_same_object(self):
        fix = _trial(_fixations(), "A")
        assert tabs._drift_corrected(fix, _trial(_words(), "A"), "Off") is fix

    def test_none_algorithm_returns_the_same_object(self):
        fix = _trial(_fixations(), "A")
        assert tabs._drift_corrected(fix, _trial(_words(), "A"), None) is fix

    def test_empty_frames_return_the_same_object(self):
        fix = _trial(_fixations(), "A")
        empty = fix.iloc[0:0]
        assert tabs._drift_corrected(empty, _trial(_words(), "A"), "Cluster") is empty
        assert tabs._drift_corrected(fix, _words().iloc[0:0], "Cluster") is fix

    def test_correction_snaps_to_line_centers_without_mutating_the_input(self):
        fix = _trial(_fixations(), "A")
        before = fix["y"].to_numpy(dtype=float).copy()
        corrected = tabs._drift_corrected(fix, _trial(_words(), "A"), "Cluster")

        assert corrected is not fix
        assert set(np.round(corrected["y"].to_numpy(dtype=float), 6)) <= set(
            LINE_CENTERS
        )
        # The caller still needs the untouched frame for the connector layer.
        np.testing.assert_array_equal(fix["y"].to_numpy(dtype=float), before)


# -----------------------------------------------------------------------------
# _marked_text_column — the "Mark border" gate
# -----------------------------------------------------------------------------


class TestMarkedTextColumn:
    """Builders with no border-overlay layer must get ``None`` unless the style
    is "Mark text" — otherwise "Mark border" silently becomes text marking."""

    @pytest.mark.parametrize(
        ("style", "expected"),
        [
            ("Mark text", "is_in_aspan"),
            ("Mark border", None),
            ("None", None),
        ],
    )
    def test_style_gates_the_column(self, style, expected):
        viz = _viz(critical_span_style=style)
        assert tabs._marked_text_column(viz) == expected

    def test_no_span_column_selected_stays_none(self):
        assert tabs._marked_text_column(_viz(highlight_column=None)) is None


# -----------------------------------------------------------------------------
# Animation — the newly wired parameters reach make_scanpath_animation
# -----------------------------------------------------------------------------


def _animate(viz: dict, monkeypatch, *, drift_corrected: bool = False, dual=False):
    """Run ``_build_and_render_animation`` and return ``(figure, builder kwargs)``.

    ``dual=True`` co-animates the second reader, i.e. Animate + Compare."""
    seen: dict = {}
    # Reach for the module the builder lives in, not the (possibly already
    # patched) name in ``tabs`` — otherwise a second call inside one test spies
    # on the first spy and both dicts fill up.
    real = plots.make_scanpath_animation

    def spy(words, fixations, **kwargs):
        seen.update(kwargs)
        seen["_fixations"] = fixations
        return real(words, fixations, **kwargs)

    monkeypatch.setattr(tabs, "make_scanpath_animation", spy)
    fig, *_ = tabs._build_and_render_animation(
        _trial(_words(), "A"),
        _trial(_fixations(), "A"),
        _trial(_words(), "B") if dual else None,
        _trial(_fixations(), "B") if dual else None,
        "A",
        "t1",
        "B" if dual else None,
        "t1" if dual else None,
        canvas_width=800,
        canvas_height=600,
        base_font_size=14,
        font_family="Arial",
        viz_settings=viz,
        playback_speed=1.0,
        line_spacing=1.0,
        scale_text_to_boxes=True,
        drift_corrected=drift_corrected,
    )
    return fig, seen


@pytest.mark.usefixtures("quiet_chart")
class TestAnimationWiring:
    def test_defaults_reproduce_the_previous_replay(self, monkeypatch):
        """Every VIZ-23 parameter must default to the pre-VIZ-23 behaviour."""
        _, kwargs = _animate(
            _viz(critical_span_style="None", highlight_column=None), monkeypatch
        )
        assert kwargs["show_saccade_arrows"] is False
        assert kwargs["fixation_flags"] is None
        assert kwargs["text_color"] == WORD_LABEL_COLOR
        assert kwargs["highlight_column"] is None
        assert kwargs["word_hover_measure"] is None
        assert kwargs["colorbar_orientation"] == "Vertical"
        assert kwargs["colorbar_tickangle"] == 0
        assert kwargs["colorbar_tickfont_size"] == 12

    def test_every_new_setting_is_forwarded(self, monkeypatch):
        flags = {"long": {"mode": "Highlight", "threshold_ms": 120, "symbol": "x"}}
        viz = _viz(
            show_saccade_arrows=True,
            fixation_flags=flags,
            text_color="#123456",
            highlight_text_color="#abcdef",
            word_hover_measure="total_fixation_duration_ms",
            colorbar_orientation="Horizontal",
            colorbar_tickangle=45,
            colorbar_tickfont_size=9,
        )
        _, kwargs = _animate(viz, monkeypatch)

        assert kwargs["show_saccade_arrows"] is True
        assert kwargs["fixation_flags"] is flags
        assert kwargs["text_color"] == "#123456"
        assert kwargs["highlight_column"] == "is_in_aspan"
        assert kwargs["highlight_text_color"] == "#abcdef"
        assert kwargs["word_hover_measure"] == "total_fixation_duration_ms"
        assert kwargs["colorbar_orientation"] == "Horizontal"
        assert kwargs["colorbar_tickangle"] == 45
        assert kwargs["colorbar_tickfont_size"] == 9

    def test_mark_border_does_not_leak_into_the_replay(self, monkeypatch):
        _, kwargs = _animate(_viz(critical_span_style="Mark border"), monkeypatch)
        assert kwargs["highlight_column"] is None

    def test_the_span_actually_reaches_the_word_labels(self, monkeypatch):
        """Not just accepted — visible. The two answer-span words take the
        highlight colour, the rest the base text colour."""
        fig, _ = _animate(
            _viz(text_color="#123456", highlight_text_color="#abcdef"), monkeypatch
        )
        labels = [t for t in fig.data if t.mode == "text"]
        assert labels, "the replay draws no word-label trace"
        colors = list(labels[0].textfont.color)
        assert colors.count("#abcdef") == 2
        assert colors.count("#123456") == 4

    def test_word_hover_measure_reaches_the_hovertemplate(self, monkeypatch):
        fig, _ = _animate(
            _viz(word_hover_measure="total_fixation_duration_ms"), monkeypatch
        )
        labels = [t for t in fig.data if t.mode == "text"]
        assert "customdata[2]" in labels[0].hovertemplate

    def test_drift_corrected_forces_colour_by_line(self, monkeypatch):
        _, off = _animate(_viz(), monkeypatch, drift_corrected=False)
        _, on = _animate(_viz(), monkeypatch, drift_corrected=True)
        assert off["color_by_line"] is False
        assert on["color_by_line"] is True

    def test_the_dual_co_animation_survives_the_new_layers(self, monkeypatch):
        """Animate + Compare builds a second trail, its own arrow/flag traces and
        a second word set — the paths most likely to break on a new layer."""
        flags = {
            "long": {
                "mode": "Highlight",
                "threshold_ms": 120,
                "symbol": "square-open",
                "color": "#9467bd",
            }
        }
        viz = _viz(
            show_saccade_arrows=True,
            fixation_flags=flags,
            word_hover_measure="total_fixation_duration_ms",
            text_color="#123456",
        )
        fig, kwargs = _animate(viz, monkeypatch, dual=True)
        assert kwargs["fixations_b"] is not None
        assert fig.frames, "the co-animation produced no frames"
        # Trace 0 is the static word layer; every animated trace after it must be
        # re-specified by EVERY frame, or Plotly's redraw=False replay desyncs the
        # traces (an arrow layer paired with the wrong scanpath, say).
        animated = tuple(range(1, len(fig.data)))
        assert {tuple(f.traces) for f in fig.frames} == {animated}
        assert {len(f.data) for f in fig.frames} == {len(animated)}


# -----------------------------------------------------------------------------
# Comparison — the newly wired parameters reach make_comparison_figure
# -----------------------------------------------------------------------------


def _compare(viz: dict, monkeypatch, *, fixations=None, layout="overlay", **extra):
    """Run ``_render_comparison_figure`` and return ``(figure, builder kwargs)``."""
    seen: dict = {}
    real = plots.make_comparison_figure

    def spy(words, fix, trial_a, trial_b, **kwargs):
        seen.update(kwargs)
        seen["_fixations"] = fix
        return real(words, fix, trial_a, trial_b, **kwargs)

    monkeypatch.setattr(tabs, "make_comparison_figure", spy)
    combos = pd.DataFrame(
        {"participant_id": ["A", "B"], "trial_id": ["t1", "t1"], "text_id": ["p", "p"]}
    )
    fig = tabs._render_comparison_figure(
        combos,
        _words(),
        _fixations() if fixations is None else fixations,
        "A",
        "t1",
        "para",
        "B",
        "t1",
        800,
        600,
        "Arial",
        14,
        viz,
        layout=layout,
        **extra,
    )
    return fig, seen


@pytest.mark.usefixtures("quiet_chart")
class TestComparisonWiring:
    def test_defaults_reproduce_the_previous_figure(self, monkeypatch):
        _, kwargs = _compare(
            _viz(critical_span_style="None", highlight_column=None), monkeypatch
        )
        assert kwargs["fixation_symbol"] == DEFAULT_FIXATION_SYMBOL
        assert kwargs["highlight_column"] is None
        assert kwargs["colorbar_orientation"] == "Vertical"
        assert kwargs["colorbar_tickangle"] == 0
        assert kwargs["colorbar_tickfont_size"] == 12
        assert kwargs["background_image"] is None
        assert kwargs["background_image_size"] is None
        assert kwargs["background_image_origin"] is None
        assert kwargs["background_image_opacity"] == 1.0

    def test_every_new_setting_is_forwarded(self, monkeypatch):
        viz = _viz(
            fixation_symbol="diamond",
            highlight_text_color="#abcdef",
            colorbar_orientation="Horizontal",
            colorbar_tickangle=30,
            colorbar_tickfont_size=8,
        )
        fig, kwargs = _compare(
            viz,
            monkeypatch,
            background_image=STIMULUS_URI,
            background_image_size=(800.0, 600.0),
            background_image_origin=(0.0, 0.0),
            background_image_opacity=0.4,
        )
        assert kwargs["fixation_symbol"] == "diamond"
        assert kwargs["highlight_column"] == "is_in_aspan"
        assert kwargs["highlight_text_color"] == "#abcdef"
        assert kwargs["colorbar_orientation"] == "Horizontal"
        assert kwargs["colorbar_tickangle"] == 30
        assert kwargs["colorbar_tickfont_size"] == 8
        assert kwargs["background_image"] == STIMULUS_URI
        assert kwargs["background_image_size"] == (800.0, 600.0)
        assert kwargs["background_image_origin"] == (0.0, 0.0)
        assert kwargs["background_image_opacity"] == 0.4
        # …and it is drawn, under everything else.
        assert len(fig.layout.images) == 1
        assert fig.layout.images[0].opacity == 0.4
        assert fig.layout.images[0].layer == "below"

    def test_mark_border_does_not_leak_into_the_comparison(self, monkeypatch):
        _, kwargs = _compare(_viz(critical_span_style="Mark border"), monkeypatch)
        assert kwargs["highlight_column"] is None

    def test_the_symbol_actually_reaches_both_scanpaths(self, monkeypatch):
        fig, _ = _compare(_viz(fixation_symbol="diamond"), monkeypatch)
        symbols = {
            t.marker.symbol
            for t in fig.data
            if t.mode and "markers" in t.mode and t.marker is not None
        }
        assert symbols == {"diamond"}

    def test_the_span_actually_reaches_the_word_labels(self, monkeypatch):
        fig, _ = _compare(
            _viz(text_color="#123456", highlight_text_color="#abcdef"), monkeypatch
        )
        labels = [t for t in fig.data if t.mode == "text"]
        assert labels, "the comparison draws no word-label trace"
        assert "#abcdef" in list(labels[0].textfont.color)

    def test_per_scanpath_styles_still_beat_the_globals(self, monkeypatch):
        """CMP overrides own colour/size/opacity — VIZ-23 must not take them
        over by passing the global equivalents."""
        viz = _viz(
            compare_style_a={"fix_color": "#ff0000", "opacity": 0.5},
            compare_style_b={"fix_color": "#00ff00", "opacity": 0.5},
            fixation_symbol="diamond",
        )
        fig, _ = _compare(viz, monkeypatch)
        marker_colors = {
            t.marker.color
            for t in fig.data
            if t.mode and "markers" in t.mode and isinstance(t.marker.color, str)
        }
        assert {"#ff0000", "#00ff00"} <= marker_colors

    @pytest.mark.parametrize("layout", ["side_by_side", "stacked"])
    def test_split_layouts_get_the_same_treatment(self, monkeypatch, layout):
        fig, kwargs = _compare(
            _viz(fixation_symbol="diamond"),
            monkeypatch,
            layout=layout,
            background_image=STIMULUS_URI,
            background_image_size=(800.0, 600.0),
            background_image_origin=(0.0, 0.0),
        )
        assert kwargs["fixation_symbol"] == "diamond"
        # One stimulus image per panel — no split-layout gap left.
        assert len(fig.layout.images) == 2
        symbols = {
            t.marker.symbol
            for t in fig.data
            if t.mode and "markers" in t.mode and t.marker is not None
        }
        assert symbols == {"diamond"}


# -----------------------------------------------------------------------------
# Drift correction on all three paths, driven through the real app
# -----------------------------------------------------------------------------

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _fixation_ys(frame: pd.DataFrame, participant: str) -> np.ndarray:
    return (
        _trial(frame, participant)
        .sort_values("order_in_trial")["y"]
        .to_numpy(dtype=float)
    )


class TestDriftCorrectionReachesEveryPath:
    """The hoist: ``alignment.correct`` runs once, above the render-mode split.

    Driven through ``AppTest`` because the hoist lives inside
    ``render_single_trial_tab`` — that is the code under test. One boot, six
    reruns (three render modes × correction off/on), with the three builders
    spied on so the assertion is "the frame the builder received".
    """

    @staticmethod
    def _spy(monkeypatch) -> dict:
        seen: dict[str, list] = {"static": [], "anim": [], "compare": []}
        real_static = tabs._cached_scanpath_figure
        real_anim = plots.make_scanpath_animation
        real_compare = plots.make_comparison_figure

        def static(words, fixations, build_kwargs, fig_key):
            seen["static"].append((words, fixations))
            return real_static(words, fixations, build_kwargs, fig_key)

        def anim(words, fixations, **kwargs):
            seen["anim"].append((words, fixations, kwargs))
            return real_anim(words, fixations, **kwargs)

        def compare(words, fixations, trial_a, trial_b, **kwargs):
            seen["compare"].append((words, fixations, trial_a, trial_b))
            return real_compare(words, fixations, trial_a, trial_b, **kwargs)

        monkeypatch.setattr(tabs, "_cached_scanpath_figure", static)
        monkeypatch.setattr(tabs, "make_scanpath_animation", anim)
        monkeypatch.setattr(tabs, "make_comparison_figure", compare)
        return seen

    @staticmethod
    def _assert_snapped(words: pd.DataFrame, ys: np.ndarray) -> None:
        centers = set(np.round(alignment._line_centers(words), 6))
        assert centers, "the trial has no text lines to snap to"
        assert set(np.round(ys, 6)) <= centers

    def test_static_animation_and_comparison_all_move(self, monkeypatch):
        seen = self._spy(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception

        # --- static -------------------------------------------------------
        words, raw_static = seen["static"][-1]
        seen["static"].clear()
        at.session_state["global_align_algorithm"] = "Cluster"
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, corrected_static = seen["static"][-1]
        assert not np.array_equal(
            raw_static["y"].to_numpy(dtype=float),
            corrected_static["y"].to_numpy(dtype=float),
        )
        self._assert_snapped(words, corrected_static["y"].to_numpy(dtype=float))

        # --- animation ----------------------------------------------------
        at.session_state["global_align_algorithm"] = "Off"
        at.session_state["single_animate"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert seen["anim"], "Animate mode did not reach make_scanpath_animation"
        anim_words, raw_anim, raw_kwargs = seen["anim"][-1]
        seen["anim"].clear()

        at.session_state["global_align_algorithm"] = "Cluster"
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, corrected_anim, corrected_kwargs = seen["anim"][-1]
        assert not np.array_equal(
            raw_anim["y"].to_numpy(dtype=float),
            corrected_anim["y"].to_numpy(dtype=float),
        ), "the animation still receives the raw fixations"
        self._assert_snapped(anim_words, corrected_anim["y"].to_numpy(dtype=float))
        # …and the replay says so, exactly as the static figure does.
        assert raw_kwargs["color_by_line"] is False
        assert corrected_kwargs["color_by_line"] is True

        # --- comparison ---------------------------------------------------
        at.session_state["global_align_algorithm"] = "Off"
        at.session_state["single_animate"] = False
        at.session_state["single_compare_toggle"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        assert seen["compare"], "Compare mode did not reach make_comparison_figure"
        cmp_words, raw_cmp, trial_a, trial_b = seen["compare"][-1]
        seen["compare"].clear()

        at.session_state["global_align_algorithm"] = "Cluster"
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, corrected_cmp, trial_a2, trial_b2 = seen["compare"][-1]
        assert (trial_a, trial_b) == (trial_a2, trial_b2)

        # BOTH compared scanpaths move, each against its own words frame.
        for participant, trial_id in (trial_a2, trial_b2):
            raw_ys = _pair_ys(raw_cmp, participant, trial_id)
            new_ys = _pair_ys(corrected_cmp, participant, trial_id)
            assert len(new_ys), f"{participant}/{trial_id} missing from the frame"
            assert not np.array_equal(raw_ys, new_ys), (
                f"{participant}/{trial_id} still comes through uncorrected"
            )
            self._assert_snapped(_pair_words(cmp_words, participant, trial_id), new_ys)

    def test_no_algorithm_leaves_every_path_untouched(self, monkeypatch):
        """The default. Each builder must see the very frame it saw before —
        same values, in the same order."""
        seen = self._spy(monkeypatch)
        at = AppTest.from_file(APP_SCRIPT)
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, static_fix = seen["static"][-1]

        at.session_state["single_compare_toggle"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, compare_fix, trial_a, trial_b = seen["compare"][-1]

        at.session_state["single_compare_toggle"] = False
        at.session_state["single_animate"] = True
        at.run(timeout=90)
        assert not at.exception, at.exception
        _, anim_fix, _ = seen["anim"][-1]

        # The raw, uncorrected trial straight out of the loader.
        participant, trial_id = trial_a
        raw = _pair_ys(compare_fix, participant, trial_id)
        np.testing.assert_array_equal(static_fix["y"].to_numpy(dtype=float), raw)
        np.testing.assert_array_equal(anim_fix["y"].to_numpy(dtype=float), raw)
        # …and the second scanpath is equally untouched.
        assert len(_pair_ys(compare_fix, *trial_b))


def _pair_ys(frame: pd.DataFrame, participant, trial_id) -> np.ndarray:
    rows = frame[
        (frame["participant_id"] == participant) & (frame["trial_id"] == trial_id)
    ]
    return rows.sort_values("timestamp_ms")["y"].to_numpy(dtype=float)


def _pair_words(frame: pd.DataFrame, participant, trial_id) -> pd.DataFrame:
    return frame[
        (frame["participant_id"] == participant) & (frame["trial_id"] == trial_id)
    ]
