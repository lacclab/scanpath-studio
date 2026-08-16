"""Pin the session-state / URL **wire format** (ENG-6).

A ``st.session_state`` key that a deep link seeds, the Share button emits, or a
saved 💾 config restores is not a variable name — it is a contract with links
and files that already exist in the world. Renaming one is silent: the link
still opens and the config still restores, they just quietly lose the setting.

So the contract is frozen twice — as named constants + frozen groupings in
:mod:`scanpath_studio.session_keys`, and here, where the frozen literals are
compared against what ``url_state`` **actually** does today. Both directions
fail loudly:

* a key that *disappeared* from the code → an old link/config just broke;
* a key that is *new* in the code and unpinned → it becomes wire format the
  moment it ships, so it has to be added to ``session_keys`` deliberately.

The three behavioural tests drive the real entry points (``_apply_url_preset``,
``_build_share_query``, ``_restore_plot_config``) rather than re-reading the
tables, so a change in how a table is *consumed* is caught too.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from scanpath_studio import session_keys as sk

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


# A fixations frame with numeric x/y/duration/pass_index (so the colour-by and
# axis fields in the saved config validate) and a trial_id that doubles as
# unique_trial_id (so the config's `selection` block resolves). Built inline in
# the AppTest functions below — they exec as standalone scripts.
_FIX_COLUMNS = {
    "participant_id": ["p1", "p1", "p2"],
    "trial_id": ["t1", "t2", "t1"],
    "unique_trial_id": ["t1", "t2", "t1"],
    "paragraph_id": ["pA", "pB", "pA"],
    "x": [1.0, 2.0, 3.0],
    "y": [4.0, 5.0, 6.0],
    "duration_ms": [100, 200, 300],
    "pass_index": [1, 1, 2],
}

_BROKE_LINKS = (
    "This is a wire-format break: every share link and saved config already out "
    "there carries the old name, and neither fails loudly — the setting is just "
    "silently dropped. If the removal is deliberate, remove it from "
    "scanpath_studio/session_keys.py in the same commit (and consider keeping a "
    "legacy alias, the way `hide_fixation_numbers` is kept)."
)
_UNPINNED = (
    "It becomes part of the wire format the moment it ships, so pin it "
    "consciously: add the constant + put it in the matching frozen grouping in "
    "scanpath_studio/session_keys.py."
)


def _assert_frozen(actual: set, frozen: frozenset, *, what: str, where: str) -> None:
    """Compare a live key set against the frozen one, failing on either drift."""
    problems = []
    missing = sorted(frozen - set(actual))
    if missing:
        problems.append(
            f"{what} pinned in session_keys but gone from {where}: {missing}\n{_BROKE_LINKS}"
        )
    added = sorted(set(actual) - frozen)
    if added:
        problems.append(
            f"{what} present in {where} but not pinned: {added}\n{_UNPINNED}"
        )
    assert not problems, "\n\n".join(problems)


# ---------------------------------------------------------------------------
# Static pins — the tables themselves
# ---------------------------------------------------------------------------
def test_url_preset_params_match_frozen_list():
    """Every ``?param=`` a deep link can carry is pinned (and only those)."""
    from scanpath_studio.url_state import _URL_PRESETS

    _assert_frozen(
        set(_URL_PRESETS),
        sk.URL_PRESET_PARAMS,
        what="URL deep-link params",
        where="url_state._URL_PRESETS",
    )


def test_url_preset_state_keys_match_frozen_list():
    """And every session key those params write is pinned."""
    _assert_frozen(
        {state for state, _coerce in _url_preset_targets()},
        frozenset(sk.SHARE_PARAMS.values()),
        what="session keys seeded by a deep link",
        where="url_state._URL_PRESETS",
    )


def _url_preset_targets():
    from scanpath_studio.url_state import _URL_PRESETS

    return list(_URL_PRESETS.values())


@pytest.mark.parametrize(
    "group",
    [
        "SHARE_TOGGLE_PARAMS",
        "SHARE_VALUE_PARAMS",
        "SHARE_INT_PARAMS",
        "SHARE_FLOAT_PARAMS",
        "SHARE_INT_RANGE_PARAMS",
        "SHARE_FLOAT_RANGE_PARAMS",
    ],
)
def test_share_param_groups_match_frozen_mappings(group):
    """Each share group is pinned param-by-param, including its wiring.

    The group a param lives in *is* wire format — it decides the encoding
    ("1"/"0" vs str vs "lo,hi") — so the groups are pinned separately, and the
    param → session-key mapping is compared as a whole (a rewiring that keeps
    both names alive would round-trip the wrong value).
    """
    from scanpath_studio import url_state

    live = dict(getattr(url_state, f"_{group}"))
    frozen = dict(getattr(sk, group))
    _assert_frozen(
        set(live),
        frozenset(frozen),
        what=f"share params in {group}",
        where=f"url_state._{group}",
    )
    rewired = {k: (frozen[k], live[k]) for k in frozen if live.get(k) != frozen[k]}
    assert not rewired, (
        f"share param → session key rewired in url_state._{group}: "
        f"{ {k: f'{was} -> {now}' for k, (was, now) in rewired.items()} }\n"
        "A link written by an older build carries the old value under this "
        "param name; pointing it at a different widget silently applies the "
        "wrong setting."
    )


def test_url_bounded_state_keys_frozen():
    """The clamped (slider/number_input-backed) deep-link targets are pinned.

    A key that drops out of ``_URL_BOUNDED`` stops being clamped, and a
    hand-crafted out-of-range link then crashes the widget on render.
    """
    from scanpath_studio.url_state import _URL_BOUNDED

    _assert_frozen(
        set(_URL_BOUNDED),
        sk.URL_BOUNDED_STATE_KEYS,
        what="URL-clamped session keys",
        where="url_state._URL_BOUNDED",
    )


def test_plot_config_layer_keys_frozen():
    """The saved config's ``layers`` block uses its own names — pin both sides."""
    from scanpath_studio.url_state import _PLOT_CONFIG_LAYER_KEYS

    live = dict(_PLOT_CONFIG_LAYER_KEYS)
    frozen = dict(sk.PLOT_CONFIG_LAYER_KEYS)
    _assert_frozen(
        set(live),
        frozenset(frozen),
        what="saved-config `layers` keys",
        where="url_state._PLOT_CONFIG_LAYER_KEYS",
    )
    assert live == frozen, (
        "a saved-config layer name now points at a different session key: "
        f"{ {k: (frozen[k], live[k]) for k in frozen if live.get(k) != frozen[k]} }"
    )


def test_plot_config_schema_version_pinned():
    """The config schema version is pinned, and the migration chain is complete."""
    from scanpath_studio.url_state import _PLOT_CONFIG_MIGRATIONS, PLOT_CONFIG_SCHEMA

    assert PLOT_CONFIG_SCHEMA == sk.PLOT_CONFIG_SCHEMA_VERSION, (
        f"PLOT_CONFIG_SCHEMA moved to {PLOT_CONFIG_SCHEMA} but session_keys still "
        f"pins {sk.PLOT_CONFIG_SCHEMA_VERSION}. Bumping the schema means the "
        "saved-config layout changed: register the migration in "
        "_PLOT_CONFIG_MIGRATIONS, update PLOT_CONFIG_SCHEMA_VERSION here, and "
        "re-check the frozen key sets below."
    )
    gaps = [v for v in range(1, PLOT_CONFIG_SCHEMA) if v not in _PLOT_CONFIG_MIGRATIONS]
    assert not gaps, (
        f"no migration registered from config schema {gaps} — a config saved by "
        "an older build can't be walked forward and loses its settings."
    )


def test_annotation_store_key_matches_annotations_module():
    """The annotations store key travels inside every schema-2 config."""
    from scanpath_studio.annotations import ANNOTATIONS_STATE_KEY

    assert sk.TRIAL_ANNOTATIONS == ANNOTATIONS_STATE_KEY


def test_selection_prefix_pinned():
    """The trial-picker key prefix a link seeds is itself wire format."""
    from scanpath_studio.url_state import _SELECTION_PREFIXES

    assert _SELECTION_PREFIXES == ("single",), (
        "the trial-picker key prefix changed — every `?participant=`/`?trial=` "
        "link seeds `<prefix>_*` keys before the widget exists, so a renamed "
        "prefix silently stops landing on the linked trial."
    )
    for key in (
        sk.SINGLE_SELECT_TRIAL_MODE,
        sk.SINGLE_TRIAL_ID,
        sk.SINGLE_PARTICIPANT,
        sk.SINGLE_SLIDER,
        sk.SINGLE_ANIMATE,
    ):
        assert key.startswith(_SELECTION_PREFIXES[0] + "_")


# ---------------------------------------------------------------------------
# Behavioural pins — the real read/write paths
# ---------------------------------------------------------------------------
def _deep_link_app():
    """Apply a deep link carrying *every* pinned param; record what it seeded."""
    import streamlit as st

    from scanpath_studio.url_state import _apply_url_preset

    before = set(st.session_state.keys())
    st.session_state["_source"] = _apply_url_preset()
    st.session_state["_seeded"] = sorted(
        set(st.session_state.keys()) - before - {"_source", "_seeded"}
    )


def test_deep_link_seeds_frozen_state_keys():
    """Opening a maximal deep link seeds exactly the pinned session keys."""
    from scanpath_studio.constants import (
        ONESTOP_PART_LABELS,
        ONESTOP_REGIME_LABELS,
        ONESTOP_VARIANT_LABELS,
    )

    query = {
        sk.PARAM_SOURCE: "onestop_public",
        sk.PARAM_PARTICIPANT: "p1",
        sk.PARAM_TRIAL: "3",
        sk.PARAM_TRIAL_ID: "t1",
        sk.PARAM_TAB: "animation",
        sk.PARAM_HIDE_FIXATION_NUMBERS: "1",
        sk.PARAM_ONESTOP_VARIANT: next(iter(ONESTOP_VARIANT_LABELS)),
        sk.PARAM_ONESTOP_REGIME: next(iter(ONESTOP_REGIME_LABELS)),
        sk.PARAM_ONESTOP_PARTS: ",".join(list(ONESTOP_PART_LABELS)[:2]),
        # CMP-8 §7. Both halves are needed: the reader requires `<pid>:<trial>`,
        # and without them the two keys they seed (`single_compare_toggle`,
        # `cmp_dataset`) would never appear here — leaving the frozen-key
        # assertion below vacuous for exactly the newest additions.
        sk.COMPARE_PARAM: "p2:t2",
        sk.COMPARE_SOURCE_PARAM: "synthetic",
    }
    # Plausible values per encoding — a bad one would be dropped with a warning
    # (asserted empty below), which would hide a missing key. A param whose
    # reader validates against a closed domain needs its own real value here.
    validated = {
        "align_algorithm": "Warp",
        # VIZ-31: the reading-class filter parses against a closed set of class
        # names, so a placeholder would be rejected with a warning.
        "saccade_classes": "forward,regression",
        # CMP-11: both are `st.segmented_control` options, so both readers
        # validate against the control's exact spellings. The layout is given in
        # its hyphenated CLI form on purpose — the parser accepts both, and a
        # link built from a `--compare-layout` value must survive the round trip.
        sk.COMPARE_LAYOUT_PARAM: "side-by-side",
        sk.COMPARE_STIMULUS_PARAM: "B",
    }
    for param in sk.SHARE_TOGGLE_PARAMS:
        query[param] = "1"
    for param in sk.SHARE_VALUE_PARAMS:
        query[param] = validated.get(
            param, "Blues" if "colorscale" in param else "Default"
        )
    for param in sk.SHARE_INT_PARAMS:
        query[param] = "50"
    for param in sk.SHARE_FLOAT_PARAMS:
        query[param] = "1.0"
    for param in (*sk.SHARE_INT_RANGE_PARAMS, *sk.SHARE_FLOAT_RANGE_PARAMS):
        query[param] = "5,10"

    at = AppTest.from_function(_deep_link_app)
    for param, value in query.items():
        at.query_params[param] = value
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert [w.value for w in at.warning] == [], (
        "a pinned URL param no longer parses — see the warning text above"
    )
    assert at.session_state["_source"] == "onestop_public"

    _assert_frozen(
        set(at.session_state["_seeded"]),
        frozenset(sk.SHARE_PARAMS.values()) | sk.URL_SEEDED_STATE_KEYS,
        what="session keys a deep link seeds",
        where="url_state._apply_url_preset()",
    )


def _share_query_app():
    """Populate every shared setting, then build the Share link."""
    import streamlit as st

    from scanpath_studio.constants import (
        ONESTOP_PART_LABELS,
        ONESTOP_PUBLIC_CHOICE,
        ONESTOP_REGIME_LABELS,
        ONESTOP_VARIANT_LABELS,
    )
    from scanpath_studio.session_keys import (
        ONESTOP_PARTS,
        ONESTOP_REGIME,
        ONESTOP_VARIANT,
        SHARE_FLOAT_PARAMS,
        SHARE_FLOAT_RANGE_PARAMS,
        SHARE_INT_PARAMS,
        SHARE_INT_RANGE_PARAMS,
        SHARE_TOGGLE_PARAMS,
        SHARE_VALUE_PARAMS,
        SINGLE_ANIMATE,
    )
    from scanpath_studio.url_state import _build_share_query

    for key in SHARE_TOGGLE_PARAMS.values():
        st.session_state[key] = True
    for key in SHARE_VALUE_PARAMS.values():
        st.session_state[key] = "zz"
    for key in SHARE_INT_PARAMS.values():
        st.session_state[key] = 50
    for key in SHARE_FLOAT_PARAMS.values():
        st.session_state[key] = 1.0
    for key in (*SHARE_INT_RANGE_PARAMS.values(), *SHARE_FLOAT_RANGE_PARAMS.values()):
        st.session_state[key] = (5, 10)
    # CMP-11: `cmp_layout` / `cmp_stimulus` describe a comparison, so they are
    # emitted only when one is being shared. Without a `compare` entry here the
    # frozen-param assertion below would report them as "gone from
    # `_build_share_query`" — and, worse, a future genuine removal would be
    # indistinguishable from this harness simply not comparing anything.
    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": {"participant_id": "p2", "trial_id": "t2"},
    }
    st.session_state[SINGLE_ANIMATE] = True
    st.session_state[ONESTOP_VARIANT] = next(iter(ONESTOP_VARIANT_LABELS))
    st.session_state[ONESTOP_REGIME] = next(iter(ONESTOP_REGIME_LABELS))
    st.session_state[ONESTOP_PARTS] = list(ONESTOP_PART_LABELS)[:2]

    query, caveats = _build_share_query(ONESTOP_PUBLIC_CHOICE)
    st.session_state["_query"] = query
    st.session_state["_caveats"] = caveats


def test_share_link_emits_frozen_params():
    """The Share button emits exactly the pinned params — the write side.

    Read (``_apply_url_preset``) and write (``_build_share_query``) are separate
    code paths over the same tables, so both are driven: a param emitted but no
    longer parsed (or vice versa) is a one-way link.
    """
    at = AppTest.from_function(_share_query_app)
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_caveats"] == []

    emitted = set(parse_qs(at.session_state["_query"]))
    # `URL_OPTIONAL_PARAMS` are emitted only when there is something to say —
    # `setup_prov` is absent for a shareable source that declares no monitor
    # (Authoring, Synthetic) — so they are compared separately from the set every
    # fully-populated session emits.
    _assert_frozen(
        emitted - sk.URL_OPTIONAL_PARAMS,
        sk.SHARE_QUERY_PARAMS,
        what="params the Share link emits",
        where="url_state._build_share_query()",
    )
    accepted = sk.URL_PRESET_PARAMS | sk.URL_SELECTION_PARAMS | sk.URL_OPTIONAL_PARAMS
    assert emitted <= accepted, (
        "the Share link emits a param the deep-link reader doesn't parse: "
        f"{sorted(emitted - accepted)}"
    )


def _restore_config_app():
    """Restore a complete, fully-valid saved config; record what it wrote."""
    import pandas as pd
    import streamlit as st

    from scanpath_studio.constants import SACCADE_CLASS_EDITABLE
    from scanpath_studio.controls import color_field_options, numeric_field_options
    from scanpath_studio.url_state import _PLOT_CONFIG_LAYER_KEYS, _restore_plot_config
    from scanpath_studio.utils import build_combo_options

    fixations = pd.DataFrame(st.session_state["_fix"])
    combos, _, _ = build_combo_options(fixations)
    color_by = color_field_options(fixations)[0]
    numeric = numeric_field_options(fixations)
    flag = {"mode": "Highlight", "threshold_ms": 80, "symbol": "x", "color": "#ff0000"}
    compare_entry = {
        "fix_color": "#111111",
        "saccade_color": "#222222",
        "saccade_style": "Solid",
        "saccade_width": 2.0,
        "marker_size_range": [4, 10],
        "hollow": True,
        "opacity": 0.5,
        "label_pattern": "{participant_id} · {trial_id}",
    }
    config = {
        "schema": st.session_state["_schema"],
        "column_mapping": {"col_map_fix_participant": "participant_id"},
        "layers": {key: True for key in _PLOT_CONFIG_LAYER_KEYS},
        "coloring": {
            "palette": "Default (colourblind-safe)",
            "color_by": color_by,
            "heatmap_style": "Word boxes",
            "heatmap_norm": "Linear",
            "heatmap_metric": "duration_ms",
            "show_colorbars": True,
            "fixation_colorscale": "Blues",
            "heatmap_colorscale": "Greens",
            "fixation_range": [0, 1],
            "heatmap_range": [0, 1],
            "saccade_color": "#112233",
            "saccade_style": "Solid",
            "saccade_width": 2.0,
            "saccade_render_mode": "Arc",
            "saccade_color_mode": "Uniform",
            "saccade_type_legend": True,
            "saccade_class_colors": {c: "#445566" for c in SACCADE_CLASS_EDITABLE},
            # VIZ-31 reading-class filter — a real subset, since the reader
            # validates the names against the classes this build knows.
            "saccade_classes": ["forward", "regression"],
            "fixation_snap_to_word": True,
            "drift_correction": "Warp",
            "drift_connectors": True,
            "fixation_symbol": "circle",
            "fixation_color": "#778899",
            "hollow_fixations": True,
            "fixation_opacity": 0.8,
            "stimulus_image_opacity": 0.5,
            "stimulus_image_offset_x": 1.0,
            "stimulus_image_offset_y": 2.0,
            "stimulus_image_scale": 1.5,
            "colorbar_orientation": "Vertical",
            "colorbar_tickangle": 10,
            "colorbar_tickfont_size": 12,
        },
        "sizing": {
            "marker_size_range": [4, 10],
            "order_font_size": 12,
            "order_font_color": "#000000",
            "base_font_size": 14,
        },
        "animation": {"grid_step_ms": 100, "max_frames": 360},
        "canvas_px": {"width": 1000, "height": 800},
        "axes": {
            "x_field": numeric[0],
            "y_field": numeric[1],
            "coordinate_grid": True,
            "coordinate_grid_auto": False,
            "coordinate_grid_spacing": 250.0,
        },
        "text": {
            "scale_text_to_boxes": True,
            "line_spacing": 3.0,
            "font_family": "Arial",
            "text_color": "#010203",
        },
        "highlighting": {
            "critical_span_style": "Mark text",
            "highlight_column": "is_in_aspan",
            "fixation_flags": {"short": flag, "long": flag, "oob": flag},
            "highlight_text_color": "#123456",
            # Deliberately NOT a BACKGROUND_PRESETS value, so the custom-colour
            # branch runs and both background keys are exercised.
            "background_color": "#abcdef",
            "span_border_color": "#000000",
        },
        "labels": {
            "show_title_caption": True,
            "title_pattern": "{participant_id} · {trial_id}",
            "caption_pattern": "{text_id} · {n_fixations} fixations",
        },
        "compare": [compare_entry, dict(compare_entry)],
        # CMP-11 — the compare *view*, distinct from the per-scanpath styling
        # list above. Both fields are validated against the segmented controls'
        # options, so placeholders would be skipped rather than written.
        "compare_view": {"layout": "Stacked", "stimulus": "A"},
        "selection": {"participant_id": "p1", "trial_id": "t1"},
        "annotations": [],
    }
    before = set(st.session_state.keys())
    applied, skipped = _restore_plot_config(config, combos, fixations)
    st.session_state["_written"] = sorted(
        set(st.session_state.keys()) - before - {"_written", "_applied", "_skipped"}
    )
    st.session_state["_applied"] = applied
    st.session_state["_skipped"] = skipped


def test_saved_config_restore_writes_frozen_state_keys():
    """A complete saved config restores exactly the pinned session keys.

    Drives the reader with every field the writer emits, all valid, so nothing
    is skipped: what lands in ``session_state`` is the saved-config contract.
    """
    at = AppTest.from_function(_restore_config_app)
    at.session_state["_fix"] = _FIX_COLUMNS
    at.session_state["_schema"] = sk.PLOT_CONFIG_SCHEMA_VERSION
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_skipped"] == [], (
        "a field of the current saved-config format was rejected by its own "
        "reader — the writer and reader disagree about the format"
    )

    written = set(at.session_state["_written"])
    mapping_keys = {k for k in written if k.startswith(sk.COLUMN_MAPPING_PREFIX)}
    assert mapping_keys == {"col_map_fix_participant"}, (
        "the saved column mapping is seeded under a different prefix — a "
        f"restored config would stop pre-filling the mapping: {sorted(mapping_keys)}"
    )

    expected = (
        sk.PLOT_CONFIG_STATE_KEYS
        | sk.PLOT_CONFIG_OTHER_STATE_KEYS
        | sk.compare_state_keys(0)
        | sk.compare_state_keys(1)
    )
    _assert_frozen(
        written - mapping_keys,
        expected,
        what="session keys a saved config restores",
        where="url_state._restore_plot_config()",
    )


def test_saved_config_from_older_schema_still_restores():
    """A schema-1 config (no ``schema`` key) still lands the same settings.

    The migration chain is the reason an old file keeps working; if it stops
    walking forward, the settings are silently dropped rather than erroring.
    """
    at = AppTest.from_function(_restore_config_app)
    at.session_state["_fix"] = _FIX_COLUMNS
    at.session_state["_schema"] = 1
    at.run(timeout=30)
    assert not at.exception, at.exception
    assert at.session_state["_skipped"] == []
    assert sk.PLOT_CONFIG_STATE_KEYS <= set(at.session_state["_written"])


def _setup_prov_round_trip_app():
    """Emit `setup_prov` for a corpus that declares a monitor, then read it back."""
    from urllib.parse import parse_qs as _parse_qs

    import streamlit as st

    from scanpath_studio.constants import ONESTOP_PUBLIC_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    query, _ = _build_share_query(ONESTOP_PUBLIC_CHOICE)
    st.session_state["_query"] = query

    # Feed the emitted params straight back through the reader.
    st.query_params.clear()
    for key, values in _parse_qs(query).items():
        st.query_params[key] = values[0]
    _apply_url_preset()


def test_setup_provenance_round_trips_through_the_share_link():
    """DATA-22 §7 surface 2: a link carries the recording setup's *values*
    already; without the badge the recipient cannot tell a monitor the sender
    measured from one the app assumed on their behalf."""
    at = AppTest.from_function(_setup_prov_round_trip_app)
    at.run(timeout=30)
    assert not at.exception, at.exception

    emitted = parse_qs(at.session_state["_query"])
    assert emitted[sk.SETUP_PROVENANCE_PARAM] == [
        "screen:measured,geom:assumed,text:measured"
    ]
    # The reader parks the parsed badge for the UI.
    assert at.session_state[sk.SETUP_PROVENANCE_STATE_KEY] == {
        "screen": "measured",
        "geometry": "assumed",
        "text": "measured",
    }


def _compare_share_round_trip_app():
    """CMP-8 §7: emit the comparison selection, then read it back."""
    from urllib.parse import parse_qs as _parse_qs

    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE, SYNTHETIC_CHOICE
    from scanpath_studio.url_state import _apply_url_preset, _build_share_query

    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": {
            "participant_id": "p2",
            "trial_id": "t2",
            "source": SYNTHETIC_CHOICE,
        },
    }
    query, caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_query"] = query
    st.session_state["_caveats"] = caveats

    st.query_params.clear()
    for key, values in _parse_qs(query).items():
        st.query_params[key] = values[0]
    _apply_url_preset()


def test_compare_selection_round_trips_through_the_share_link():
    """Compare mode had no link representation at all before CMP-8 — a
    `cmp_source` naming B's corpus without naming B's trial would restore
    nothing, so the pair travels together."""
    at = AppTest.from_function(_compare_share_round_trip_app)
    at.run(timeout=30)
    assert not at.exception, at.exception

    emitted = parse_qs(at.session_state["_query"])
    assert emitted[sk.COMPARE_PARAM] == ["p2:t2"]
    assert emitted[sk.COMPARE_SOURCE_PARAM] == ["synthetic"]
    # The reader turns Compare on and parks B for the picker, which is the only
    # place the candidate *labels* exist.
    assert at.session_state["single_compare_toggle"] is True
    assert at.session_state[sk.PENDING_COMPARE_STATE_KEY] == {
        "participant_id": "p2",
        "trial_id": "t2",
    }
    assert at.session_state[sk.COMPARE_SOURCE_STATE_KEY] == "Synthetic test trial"


def _compare_share_unshareable_app():
    """A stored upload as B can't travel — the link must say so, not drop it."""
    import streamlit as st

    from scanpath_studio.constants import DEMO_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["_share_selection"] = {
        "participant_id": "p1",
        "trial_id": "t1",
        "compare": {
            "participant_id": "p2",
            "trial_id": "t2",
            "source": "My upload",
        },
    }
    query, caveats = _build_share_query(DEMO_CHOICE)
    st.session_state["_query"] = query
    st.session_state["_caveats"] = caveats


def test_an_unshareable_compare_source_is_declared_not_dropped():
    at = AppTest.from_function(_compare_share_unshareable_app)
    at.run(timeout=30)
    assert not at.exception, at.exception

    emitted = parse_qs(at.session_state["_query"])
    # Neither half is emitted — a `compare=` without its `cmp_source` would land
    # the recipient on a trial id looked up in the *wrong* corpus.
    assert sk.COMPARE_PARAM not in emitted
    assert sk.COMPARE_SOURCE_PARAM not in emitted
    assert any("My upload" in caveat for caveat in at.session_state["_caveats"])
