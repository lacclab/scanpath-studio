import plotly.graph_objects as go

from scanpath_studio.illustration import illustration_reasons, resolve_label_reasons
from scanpath_studio.plots import add_illustration_label


def test_substantive_transformations_trigger_label_but_cosmetics_do_not():
    assert illustration_reasons({"fixation_color": "#ff00ff"}) == []
    assert illustration_reasons({"fixation_snap_to_word": True}) == [
        "fixations snapped to words"
    ]
    assert "schematic saccade arcs" in illustration_reasons(
        {"saccade_render_mode": "Arc"}
    )
    assert "flagged fixations hidden" in illustration_reasons(
        {"fixation_flags": {"short": {"mode": "Discard"}}}
    )


def test_manual_label_override():
    assert resolve_label_reasons("Hide", ["fixation subset"]) == []
    assert resolve_label_reasons("Show", []) == ["manual label"]


def test_illustration_label_is_exported_as_annotation_and_metadata():
    fig = add_illustration_label(go.Figure(), ["schematic saccade arcs"])
    assert fig.layout.annotations[0].text.startswith("Illustration ·")
    assert fig.layout.meta["illustration"] is True
    assert fig.layout.meta["illustration_reasons"] == ["schematic saccade arcs"]
