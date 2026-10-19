"""The gallery shows complete, reproducible examples rather than clipped demos."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gallery_examples as gallery  # noqa: E402

import scanpath_studio as sps  # noqa: E402


def test_only_the_highlight_example_marks_the_demo_answer_span():
    for example in gallery.EXAMPLES:
        figure = gallery._build(example.slug)["fig"]
        notes = [note.text for note in figure.layout.annotations or ()]
        has_span_key = any("Highlighted:" in note for note in notes)
        assert has_span_key == (example.slug == "highlighted-text"), example.slug


def test_comparison_contains_every_fixation_for_both_readers():
    figure = gallery._build("comparison")["fig"]
    _, fixations = sps.load_sample_data(names="canonical")
    for label, participant in (("Reader A", "l37_1129"), ("Reader B", "l7_1090")):
        expected = fixations[
            (fixations.participant_id == participant)
            & (fixations.trial_id == f"{participant}_2_2_4_Ele_r0")
        ]
        trace = next(t for t in figure.data if t.name == label and t.mode == "markers")
        assert len(trace.x) == len(expected)


def test_replay_thumbnail_has_frames_and_uses_the_real_player():
    figure = gallery._build("replay", preview=True)["fig"]
    assert len(figure.frames) > 1
    markup = gallery.gallery_cards()
    payloads = re.findall(r'data-figure="([^"]+)"', markup)
    replay = next(
        spec
        for payload in payloads
        if (spec := json.loads(html.unescape(payload))).get("player")
    )
    assert replay["layout"]["meta"]["scanpath_autoplay"] is True
    assert replay["layout"]["meta"]["sps_preview_loop"] is True

    # Rendering a thumbnail must leave the detail page interactive.
    detail = json.loads(
        html.unescape(
            re.search(r'data-figure="([^"]+)"', gallery.gallery_figure("replay")).group(
                1
            )
        )
    )
    assert detail["player"]
    buttons = detail["layout"]["updatemenus"][0]["buttons"]
    assert {button["name"] for button in buttons} >= {"play", "pause"}
    assert detail["layout"]["sliders"]
    assert not detail["config"].get("staticPlot")
    assert not detail["layout"]["meta"].get("sps_preview_loop")


def test_experiment_points_match_the_recorded_trial_means():
    example = gallery._build("across-experiment")
    expected = (
        example["reader"].groupby("trial_index").total_fixation_duration_ms.mean()
    )
    series = next(
        trace for trace in example["fig"].data if trace.mode == "lines+markers"
    )
    np.testing.assert_array_equal(series.x, expected.index)
    np.testing.assert_allclose(series.y, expected.values)


def test_schematic_is_two_lines_and_its_saccades_fit_the_canvas():
    example = gallery._build("illustration")
    assert example["words"].y.nunique() == 2
    figure = example["fig"]
    saccades = next(trace for trace in figure.data if trace.name == "saccades")
    x = np.array([value for value in saccades.x if value is not None], dtype=float)
    y = np.array([value for value in saccades.y if value is not None], dtype=float)
    assert x.min() >= min(figure.layout.xaxis.range)
    assert x.max() <= max(figure.layout.xaxis.range)
    assert y.min() >= min(figure.layout.yaxis.range)
    assert y.max() <= max(figure.layout.yaxis.range)


def test_customizable_example_visits_each_word_once_in_reading_order():
    example = gallery._build("hearts-arrows")
    words, fixations = example["words"], example["fixations"]
    sequence = words.set_index("word_id").loc[fixations.word_id, "text"].tolist()
    assert sequence == ["The", "cat", "sat", "on", "the", "mat"]
    np.testing.assert_array_equal(fixations.x, words.x + words.width / 2)
    np.testing.assert_array_equal(fixations.y, words.y + words.height / 2)
    schematic = gallery._build("illustration")["fixations"]
    assert schematic.equals(fixations)


def test_redacted_example_draws_blocks_and_no_words():
    example = gallery._build("redacted-text")
    figure = example["fig"]
    assert any(t.name == "words" and t.fill == "toself" for t in figure.data)
    words = example["words"]
    trial = words[words["unique_trial_id"] == example["tid"]]
    long_words = {w for w in trial["IA_LABEL"].astype(str) if len(w) >= 8}
    assert long_words
    payload = figure.to_json()
    assert not [word for word in long_words if word in payload]


def test_annotated_example_carries_title_caption_and_both_legends():
    figure = gallery._build("title-caption-legend")["fig"]
    notes = " ".join(str(note.text) for note in figure.layout.annotations or ())
    assert figure.layout.title.text == "One reader, one article"
    assert "Marker size: fixation duration" in notes
    assert "ms" in notes  # the fixation-size key
    assert any(t.showlegend and t.name == "Forward" for t in figure.data)
