"""Where the fixation index number sits: above, inside or below its fixation.

One option, ``order_label_position``, read by every builder — the static
figure (plain and glyph markers), the replay and its frames, and Compare — and
carried by the CLI flag, the share link and the settings file.
"""

from __future__ import annotations

import pytest

import scanpath_studio as sps
from scanpath_studio.constants import ORDER_LABEL_POSITIONS
from tests.conftest import APP_SCRIPT


@pytest.fixture(scope="module")
def sample():
    words, fixations = sps.load_sample_data()
    (p1, t1), (p2, t2) = sps.list_trials(words, fixations).iloc[:2].values.tolist()
    return words, fixations, (p1, t1), (p2, t2)


def _index_positions(fig) -> set[str]:
    """The ``textposition`` of every trace that draws the fixation numbers —
    every text trace but the word labels."""
    return {
        trace.textposition
        for trace in fig.data
        if trace.mode and "text" in trace.mode and trace.name != "words"
    }


class TestEveryBuilder:
    @pytest.mark.parametrize("position", list(ORDER_LABEL_POSITIONS))
    def test_static(self, sample, position):
        words, fixations, (p, t), _ = sample
        fig = sps.plot_scanpath(
            words, fixations, p, t, show_order=True, order_label_position=position
        )
        assert _index_positions(fig) == {ORDER_LABEL_POSITIONS[position]}

    def test_static_glyph_markers(self, sample):
        # A glyph marker is drawn as text, so its numbers are a trace of their own.
        words, fixations, (p, t), _ = sample
        fig = sps.plot_scanpath(
            words,
            fixations,
            p,
            t,
            show_order=True,
            fixation_symbol="heart",
            order_label_position="below",
        )
        index = [tr for tr in fig.data if tr.name == "Fixation index"]
        assert index and index[0].textposition == "bottom center"

    def test_replay_and_its_frames(self, sample):
        words, fixations, (p, t), _ = sample
        fig = sps.animate_scanpath(
            words, fixations, p, t, show_order=True, order_label_position="inside"
        )
        assert _index_positions(fig) == {"middle center"}
        # Each frame re-sends the trace; a frame left on the default would snap
        # the numbers back above the markers once the replay plays.
        framed = {
            d.textposition
            for frame in fig.frames
            for d in frame.data
            if getattr(d, "mode", None) == "text"
        }
        assert framed == {"middle center"}

    def test_compare(self, sample):
        words, fixations, a, b = sample
        fig = sps.compare_scanpaths(
            words, fixations, a, b, show_order=True, order_label_position="below"
        )
        assert _index_positions(fig) == {"bottom center"}

    def test_above_is_the_default(self, sample):
        words, fixations, (p, t), _ = sample
        fig = sps.plot_scanpath(words, fixations, p, t, show_order=True)
        assert _index_positions(fig) == {"top center"}


class TestSpellings:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("Inside", "middle center"),
            ("bottom", "bottom center"),
            ("top", "top center"),
        ],
    )
    def test_any_spelling_or_alias(self, sample, given, expected):
        words, fixations, (p, t), _ = sample
        fig = sps.plot_scanpath(
            words, fixations, p, t, show_order=True, order_label_position=given
        )
        assert _index_positions(fig) == {expected}

    def test_an_unknown_position_is_refused(self, sample):
        words, fixations, (p, t), _ = sample
        with pytest.raises(ValueError, match="order_label_position"):
            sps.plot_scanpath(words, fixations, p, t, order_label_position="left")


class _FakeSt:
    def __init__(self):
        self.session_state = {}
        self.query_params = {}

    def warning(self, *args, **kwargs):
        pass


@pytest.fixture
def fake_st(monkeypatch):
    from scanpath_studio import url_state

    fake = _FakeSt()
    monkeypatch.setattr(url_state, "st", fake)
    return fake


class TestShareLink:
    def test_a_bad_link_value_is_ignored(self, fake_st):
        from scanpath_studio.url_state import _apply_url_preset

        fake_st.query_params = {"order_label_position": "sideways"}
        _apply_url_preset()
        assert "global_order_label_position" not in fake_st.session_state

    def test_a_link_value_is_read(self, fake_st):
        from scanpath_studio.url_state import _apply_url_preset

        fake_st.query_params = {"order_label_position": "below"}
        _apply_url_preset()
        assert fake_st.session_state["global_order_label_position"] == "below"


class TestTheRail:
    def test_the_position_control_reaches_the_figure_settings(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
        at.query_params["ui"] = "full"
        at.run()
        control = at.segmented_control(key="global_order_label_position")
        assert control.value == "above"
        assert control.disabled  # the numbers are off by default
        at.checkbox(key="global_show_order").check().run()
        control = at.segmented_control(key="global_order_label_position")
        assert not control.disabled
        control.set_value("inside").run()
        assert not at.exception
        assert at.session_state["global_order_label_position"] == "inside"
