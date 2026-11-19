"""Property tests: invariants checked against thousands of generated inputs.

Each test states something that must hold for *every* input — a value read
back the way it was written, a step that changes nothing the second time, a
point that falls in exactly one box — and lets Hypothesis hunt for the input
that breaks it. The examples a hand-written test picks share the author's
blind spots; these do not.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scanpath_studio import data, measures, plots, url_state
from scanpath_studio.constants import (
    LEGEND_ARRANGEMENTS,
    LEGEND_POSITIONS,
)

# No per-example deadline: under ``pytest -n auto`` on a busy CI runner a
# pandas call can take longer than Hypothesis' 200 ms default, and a test that
# fails on timing alone would teach a rerun, not a fix.
settings.register_profile("scanpath", deadline=None)
settings.load_profile("scanpath")

# Ids as they arrive from a user's file: any text, with the two characters the
# composite-id escaping cares about made common rather than rare.
_ID_TEXT = st.text(
    alphabet=st.one_of(st.sampled_from("_\\:,"), st.characters()),
    max_size=12,
)


# --- Round-trips -----------------------------------------------------------


@given(st.lists(st.integers(), min_size=1, max_size=50, unique=True))
def test_plot_history_round_trips_the_last_thirty_edits(values):
    from scanpath_studio.viz_history import Design, PlotHistory

    history = PlotHistory("demo")
    states = [{}] + [{"value": v} for v in values]
    for state in states:
        history.observe(state, Design(), ())
    states = states[-31:]
    for redo, targets in ((False, reversed(states[:-1])), (True, states[1:])):
        for expected in targets:
            keys, restored, _ = history.step(redo=redo)
            assert keys == {"value"} and restored == expected
            history.observe(restored, Design(), ())
        assert history.step(redo=redo) is None


@given(st.lists(_ID_TEXT, min_size=1, max_size=5))
def test_composite_id_round_trips(parts):
    """``split_composite_id`` reads back exactly the parts ``compose_id``
    joined — the property that makes two different readings never share an
    id."""
    assert data.split_composite_id(data.compose_id(parts)) == parts


@given(st.lists(_ID_TEXT, max_size=3), _ID_TEXT, _ID_TEXT)
def test_composite_id_is_injective(parts, head, tail):
    """Parts that a plain ``_`` join would merge stay apart: re-cutting the
    same characters at different ``_`` boundaries gives a different id."""
    parts = [*parts, f"{head}_{tail}"]
    recut = "_".join(parts).split("_")
    assert recut != parts
    assert data.compose_id(recut) != data.compose_id(parts)


@settings(suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.tuples(
            st.text(alphabet="ab_\\1", min_size=1, max_size=6),
            st.text(alphabet="ab_\\1", min_size=1, max_size=6),
        ),
        min_size=1,
        max_size=6,
    )
)
def test_trial_id_series_matches_compose_id(rows):
    """The vectorised composite id equals the scalar one, row by row."""
    frame = pd.DataFrame(rows, columns=["block", "item"], dtype=object)
    vectorised = data.trial_id_series(frame, ["block", "item"]).tolist()
    expected = [
        data.compose_id(
            [data.stable_id(pd.Series([part], dtype=object))[0] for part in row]
        )
        for row in rows
    ]
    assert vectorised == expected


@given(
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
)
def test_compare_link_value_round_trips(participant, trial):
    """``?compare=`` reads back the reading it named, whatever the ids hold —
    colons and backslashes included."""
    value = url_state.compare_value(participant, trial)
    assert url_state.parse_compare_value(value) == (participant, trial)


@given(
    st.sampled_from([p for p in LEGEND_POSITIONS if p != "auto"]),
    st.sampled_from(LEGEND_ARRANGEMENTS),
    st.one_of(st.none(), st.integers(min_value=1, max_value=500)),
)
def test_legend_spec_round_trips(position, arrangement, size):
    """``legend_<kind>=`` / ``render --legend`` text reads back the legend it
    was written from."""
    spec = {"position": position, "arrangement": arrangement, "size": size}
    parsed = plots.parse_legend_spec(plots.legend_spec_text(spec))
    assert parsed["position"] == position
    assert parsed.get("arrangement", "auto") == arrangement
    assert parsed.get("size") == size


@given(
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
)
def test_float_range_param_is_ordered_and_exact(a, b):
    """A ``lo,hi`` link range reads back its two numbers, low first, in
    either written order."""
    lo, hi = url_state._parse_float_range(f"{a!r},{b!r}")
    assert (lo, hi) == (min(a, b), max(a, b))


# --- Idempotency -----------------------------------------------------------


@given(st.text(alphabet=st.sampled_from("<>/ab= \"'"), max_size=40))
def test_strip_markup_leaves_no_tag_and_is_idempotent(text):
    """Figure text from a link can carry no markup tag, however the tags are
    nested or split around each other."""
    stripped = url_state._strip_markup(text)
    assert url_state._MARKUP_TAG.search(stripped) is None
    assert url_state._strip_markup(stripped) == stripped


_JSON_LEAF = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-10, max_value=10),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=6),
)
# Keys the migrations translate, so generated configs actually exercise them.
_CONFIG_KEYS = st.sampled_from(
    [
        "show_colorbars",
        "colorbar_orientation",
        "colorbar_tickangle",
        "show_title_caption",
        "fixation_snap_to_word",
        "marker_size_scale",
        "coordinate_grid",
        "compare",
        "x",
    ]
)
_SECTION = st.dictionaries(_CONFIG_KEYS, _JSON_LEAF, max_size=4)
_CONFIG = st.fixed_dictionaries(
    {},
    optional={
        "schema": st.one_of(
            st.integers(min_value=0, max_value=url_state.PLOT_CONFIG_SCHEMA + 2),
            st.text(max_size=3),
            st.none(),
        ),
        "coloring": st.one_of(_SECTION, _JSON_LEAF),
        "labels": _SECTION,
        "sizing": st.one_of(_SECTION, _JSON_LEAF),
        "axes": st.one_of(_SECTION, _JSON_LEAF),
        "layers": _SECTION,
        "selection": _SECTION,
        "mode": _SECTION,
        "annotations": st.lists(_JSON_LEAF, max_size=2),
    },
)


@given(_CONFIG)
def test_settings_migration_is_pure_and_idempotent(config):
    """Migrating a settings file never edits the caller's dict, lands on the
    current schema, and a second pass changes nothing — so a file saved
    after it was opened restores the same figure."""
    before = copy.deepcopy(config)
    migrated, note = url_state._migrate_plot_config(config)
    assert config == before
    if note is None:
        assert migrated["schema"] == url_state.PLOT_CONFIG_SCHEMA
        again, again_note = url_state._migrate_plot_config(migrated)
        assert again_note is None
        assert again == migrated
    # Whatever came in as JSON goes back out as JSON.
    json.dumps(migrated)


@given(_CONFIG)
def test_annotations_only_file_gains_no_plot_section(config):
    """A file with no plot section is not turned into a plot config by the
    migrations — restoring notes must not reset the figure to defaults."""
    for name in url_state._PLOT_SECTIONS:
        config.pop(name, None)
    migrated, _ = url_state._migrate_plot_config(config)
    assert not url_state._has_plot_section(migrated)


# --- Invariants ------------------------------------------------------------


@given(
    st.lists(st.integers(min_value=1, max_value=200), min_size=1, max_size=12),
    st.integers(min_value=0, max_value=400),
    st.integers(min_value=10, max_value=60),
    st.data(),
)
def test_tiling_boxes_hold_each_point_exactly_once(widths, left, height, draw):
    """On a line of boxes that share their edges, every point on the line is
    in exactly one box — a fixation is counted towards one word, never two
    and never none — and a point off the line is in none."""
    x0 = left + np.concatenate([[0], np.cumsum(widths)[:-1]]).astype(float)
    x1 = x0 + np.asarray(widths, dtype=float)
    y0 = np.full(len(widths), 100.0)
    y1 = y0 + height
    # Mostly whole pixels and box edges — EyeLink reports integer positions,
    # and the shared edges are where an off-by-one in the rule would show.
    lo, hi = left - 50, int(x1[-1]) + 50
    px = draw.draw(
        st.one_of(
            st.sampled_from([*x0, x1[-1]]),
            st.integers(min_value=lo, max_value=hi),
            st.floats(min_value=lo, max_value=hi),
        )
    )
    py = draw.draw(
        st.one_of(
            st.sampled_from([100.0, 100.0 + height]),
            st.floats(min_value=50, max_value=200),
        )
    )
    hits = measures.word_box_contains(
        np.array([[px]]), np.array([[py]]), x0, y0, x1, y1
    ).sum()
    on_line = (x0[0] <= px < x1[-1]) and (100.0 <= py < 100.0 + height)
    assert hits == (1 if on_line else 0)


@pytest.mark.parametrize("value", ["1e309", "nan", "-inf"])
def test_non_finite_range_is_refused(value):
    with pytest.raises(ValueError):
        url_state._parse_float_range(f"0,{value}")
