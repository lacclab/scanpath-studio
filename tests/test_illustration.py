import plotly.graph_objects as go

from scanpath_studio.illustration import illustration_reasons, resolve_label_reasons
from scanpath_studio.plots import add_illustration_label


def test_substantive_transformations_trigger_label_but_cosmetics_do_not():
    assert illustration_reasons({"fixation_color": "#ff00ff"}) == []
    assert illustration_reasons({"fixation_snap_to_line": True}) == [
        "fixations snapped to lines"
    ]
    assert "schematic saccade arcs" in illustration_reasons(
        {"saccade_render_mode": "Arc"}
    )
    assert "flagged fixations hidden" in illustration_reasons(
        {"fixation_flags": {"short": {"mode": "Discard"}}}
    )


def test_the_snap_and_the_arcs_count_only_on_a_layer_that_is_drawn():
    """#422: with the Fixations layer off the snap moves nothing, and with the
    Saccades layer off the arcs bend nothing — so neither labels the figure."""
    snap_and_arc = {"fixation_snap_to_line": True, "saccade_render_mode": "Arc"}
    assert illustration_reasons({**snap_and_arc, "show_fixations": False}) == [
        "schematic saccade arcs"
    ]
    assert illustration_reasons({**snap_and_arc, "show_saccades": False}) == [
        "fixations snapped to lines"
    ]
    assert (
        illustration_reasons(
            {**snap_and_arc, "show_fixations": False, "show_saccades": False}
        )
        == []
    )


def test_the_replay_and_the_comparison_draw_neither():
    """Only the static figure draws the snap or the arcs (VIZ-9)."""
    snap_and_arc = {"fixation_snap_to_line": True, "saccade_render_mode": "Arc"}
    assert illustration_reasons(snap_and_arc, static=False) == []
    # Other reasons still count there.
    assert illustration_reasons(
        {**snap_and_arc, "playback_speed": 2.0}, static=False
    ) == ["playback speed ×2"]


def test_the_api_does_not_label_a_snap_with_the_fixations_off():
    from scanpath_studio import api

    words, fixations = api.load_sample_data(names="canonical")
    pid, tid = api.list_trials(words, fixations).iloc[0]
    hidden = api.plot_scanpath(
        words, fixations, pid, tid, show_fixations=False, fixation_snap_to_line=True
    )
    shown = api.plot_scanpath(words, fixations, pid, tid, fixation_snap_to_line=True)
    assert "illustration_reasons" not in (hidden.layout.meta or {})
    assert shown.layout.meta["illustration_reasons"] == ["fixations snapped to lines"]
    # The saccades run between the recorded positions, as without the snap.
    plain = api.plot_scanpath(words, fixations, pid, tid, show_fixations=False)
    saccades = [
        next(t for t in fig.data if t.name == "saccades") for fig in (hidden, plain)
    ]
    assert list(saccades[0].y) == list(saccades[1].y)


def test_manual_label_override():
    assert resolve_label_reasons("Hide", ["fixation subset"]) == []
    assert resolve_label_reasons("Show", []) == ["manual label"]


def test_illustration_label_is_exported_as_annotation_and_metadata():
    fig = add_illustration_label(go.Figure(), ["schematic saccade arcs"])
    assert fig.layout.annotations[0].text.startswith("Illustration ·")
    assert fig.layout.meta["illustration"] is True
    assert fig.layout.meta["illustration_reasons"] == ["schematic saccade arcs"]


def test_custom_text_replaces_the_wording_but_keeps_the_reasons():
    fig = add_illustration_label(go.Figure(), ["snapped fixations"], text="Schematic")
    assert [a.text for a in fig.layout.annotations] == ["Schematic"]
    assert fig.layout.meta["illustration_reasons"] == ["snapped fixations"]


def test_blank_text_keeps_the_automatic_wording():
    fig = add_illustration_label(go.Figure(), ["snapped fixations"], text="  ")
    assert fig.layout.annotations[0].text == "Illustration · snapped fixations"


def test_the_api_draws_the_custom_text():
    from scanpath_studio import api

    words, fixations = api.load_sample_data(names="canonical")
    pid, tid = api.list_trials(words, fixations).iloc[0]
    fig = api.plot_scanpath(
        words,
        fixations,
        pid,
        tid,
        illustration_label="show",
        illustration_text="Schematic",
    )
    assert "Schematic" in [a.text for a in fig.layout.annotations]
