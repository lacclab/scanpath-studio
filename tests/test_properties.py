"""Property tests: invariants checked against thousands of generated inputs.

Each test states something that must hold for *every* input — a value read
back the way it was written, a step that changes nothing the second time, a
point that falls in exactly one box — and lets Hypothesis hunt for the input
that breaks it. The examples a hand-written test picks share the author's
blind spots; these do not.
"""

from __future__ import annotations

import copy
import io
import json
import zipfile
from urllib.parse import parse_qsl

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scanpath_studio import data, measures, plots, url_state
from scanpath_studio.column_names import encode_field_list
from scanpath_studio.constants import (
    LEGEND_ARRANGEMENTS,
    LEGEND_POSITIONS,
)
from scanpath_studio.utils import extract_trial

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


@given(
    st.sampled_from(["RGB", "opaque RGBA", "RGBA"]),
    st.binary(min_size=4, max_size=128),
    st.text(alphabet="aב猫 ·é", min_size=1, max_size=20),
)
def test_smaller_pngs_preserve_every_channel_and_embedded_metadata(mode, pixels, text):
    from PIL import Image, PngImagePlugin

    from scanpath_studio.export_png import compact_png

    channels = 3 if mode == "RGB" else 4
    values = np.resize(np.frombuffer(pixels, dtype=np.uint8), (24, 48, channels))
    if mode == "opaque RGBA":
        values[:, :, 3] = 255
    metadata = PngImagePlugin.PngInfo()
    metadata.add_itxt("Comment", text)
    with io.BytesIO() as original:
        Image.fromarray(values).save(
            original, "PNG", compress_level=0, pnginfo=metadata, dpi=(300, 300)
        )
        compact = compact_png(original.getvalue())
        assert len(compact) < original.tell()
        with Image.open(original) as before, Image.open(io.BytesIO(compact)) as after:
            assert before.size == after.size
            assert before.info == after.info
            assert before.convert("RGBA").tobytes() == after.convert("RGBA").tobytes()


@given(
    st.lists(st.binary(max_size=160), min_size=1, max_size=7),
    st.integers(min_value=4, max_value=96),
)
def test_disk_bundle_reads_members_across_part_boundaries(members, part_size):
    from scanpath_studio import export_archive

    def write(*, _archive):
        for i, value in enumerate(members):
            _archive.writestr(str(i), value)
        return None, None

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(export_archive, "_PART_BYTES", part_size)
        patch.setattr(export_archive, "_SMALL_ZIP", 0)
        bundle, _ = export_archive.build_download(write)
        try:
            assert all(
                bundle.part(i).stat().st_size == part_size
                for i in range(bundle.parts - 1)
            )
            with bundle.open() as stream, zipfile.ZipFile(stream) as archive:
                for i in reversed(range(len(members))):
                    assert archive.read(str(i)) == members[i]
        finally:
            bundle.close()


@given(st.lists(st.text(max_size=30), max_size=8))
def test_shared_hover_fields_preserve_exact_names_and_order(fields):
    value, as_json = encode_field_list(fields)
    for table in ("word", "fixation"):
        key = f"{table}_hover_fields" + ("_json" if as_json else "")
        assert url_state._URL_PRESETS[key][1](value) == fields


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


@given(st.lists(st.sampled_from([("p", "a"), ("p", "b"), ("q", "a")]), min_size=1))
def test_extract_trial_preserves_source_rows_and_slices_contiguous_readings(keys):
    frame = pd.DataFrame(keys, columns=["participant_id", "trial_id"])
    frame["position"] = np.arange(len(frame))
    frame.index = frame.index // 2  # Source index labels can repeat.
    reading = extract_trial(frame, "p", "a")
    expected = frame[(frame["participant_id"] == "p") & (frame["trial_id"] == "a")]
    pd.testing.assert_frame_equal(reading, expected)
    rows = expected["position"].to_numpy()
    if len(rows) and rows[-1] - rows[0] + 1 == len(rows):
        assert np.shares_memory(
            reading["position"].to_numpy(), frame["position"].to_numpy()
        )


@given(
    st.text(min_size=1, max_size=12),
    st.text(min_size=1, max_size=12),
)
def test_compare_link_value_round_trips(participant, trial):
    """``?compare=`` reads back the reading it named, whatever the ids hold —
    colons and backslashes included."""
    value = url_state.compare_value(participant, trial)
    assert url_state.parse_compare_value(value) == (participant, trial)


@given(*(st.text(min_size=1, max_size=20) for _ in range(3)))
def test_compare_upload_link_recovers_display_name_and_reading(
    name, participant, trial
):
    from scanpath_studio.constants import DATASET_ALIASES_KEY, DEMO_CHOICE
    from scanpath_studio.session_keys import PENDING_COMPARE_STATE_KEY

    sender = {
        "_datasets": {"sender key": {}},
        DATASET_ALIASES_KEY: {"sender key": name},
        "_share_selection": {
            "compare": {
                "source": "sender key",
                "participant_id": participant,
                "trial_id": trial,
            }
        },
    }
    recipient = {
        "_datasets": {"recipient key": {}},
        DATASET_ALIASES_KEY: {"recipient key": name},
    }
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(url_state.st, "session_state", sender)
        query, _ = url_state._build_share_query(DEMO_CHOICE)
        patch.setattr(url_state.st, "session_state", recipient)
        patch.setattr(url_state.st, "query_params", dict(parse_qsl(query)))
        assert url_state.resolve_link_compare_source(DEMO_CHOICE) is None
    assert recipient["cmp_dataset"] == "recipient key"
    assert recipient[PENDING_COMPARE_STATE_KEY] == {
        "participant_id": participant,
        "trial_id": trial,
    }


@given(st.from_regex(r"[A-Za-z][A-Za-z0-9_-]{0,25}", fullmatch=True))
def test_shared_public_b_survives_a_catalogue_label_change(short):
    from scanpath_studio import app, compare_source
    from scanpath_studio.constants import DEMO_CHOICE

    state = {
        "_share_selection": {
            "compare": {"source": "Old label", "participant_id": "p", "trial_id": "t"}
        }
    }
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(url_state.st, "session_state", state)
        patch.setattr(app, "public_datasets_enabled", lambda: True)
        patch.setattr(
            app, "public_dataset_registry", lambda: {"Old label": {"short": short}}
        )
        query, _ = url_state._build_share_query(DEMO_CHOICE)
        patch.setattr(url_state.st, "query_params", dict(parse_qsl(query)))
        patch.setattr(
            app, "public_dataset_registry", lambda: {"New label": {"short": short}}
        )
        patch.setattr(
            compare_source,
            "public_dataset_readiness",
            lambda label, *, refresh: (True, ""),
        )
        assert url_state.resolve_link_compare_source(DEMO_CHOICE) is None
    assert state["cmp_dataset"] == "New label"


@given(st.booleans(), st.booleans(), st.booleans(), st.booleans())
def test_a_shared_replay_reopens_with_its_layers(animate, fixations, saccades, auto):
    """A link reopens the mode and gaze layers it was shared with, and a
    replay that showed fixations for itself still returns to a static figure
    without them."""
    from scanpath_studio.constants import DEMO_CHOICE

    # Only a replay turns its fixations on for itself, and it shows them.
    auto = auto and animate and fixations
    keys = ("single_animate", "global_show_fix", "global_show_saccades")
    sender = {
        "_share_selection": {"participant_id": "p", "trial_id": "t"},
        **dict(zip(keys, (animate, fixations, saccades), strict=True)),
        **({"_auto_replay_fixations": True} if auto else {}),
    }
    recipient: dict = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(url_state.st, "session_state", sender)
        query, _ = url_state._build_share_query(DEMO_CHOICE)
        patch.setattr(url_state.st, "session_state", recipient)
        patch.setattr(url_state.st, "query_params", dict(parse_qsl(query)))
        url_state._apply_url_preset()
    assert {k: bool(recipient.get(k)) for k in keys} == {
        k: bool(sender[k]) for k in keys
    }
    assert bool(recipient.get("_auto_replay_fixations")) == auto


@given(
    st.tuples(
        st.integers(min_value=1, max_value=400), st.integers(min_value=1, max_value=400)
    ),
    st.tuples(
        st.integers(min_value=1, max_value=400), st.integers(min_value=1, max_value=400)
    ),
    st.booleans(),
    st.booleans(),
)
def test_a_shared_fixation_window_keeps_its_scope(window, full, chosen, all_trials):
    """A link carries a chosen window and whether it is kept across trials;
    a window kept across trials travels even when it spans this trial."""
    from scanpath_studio.constants import DEMO_CHOICE

    window, full = tuple(sorted(window)), tuple(sorted(full))
    sender = {
        "_share_selection": {
            "participant_id": "p",
            "trial_id": "t",
            "full_fix_range": full,
        },
        "single_fix_range": window,
        "single_fix_range_user_set": chosen,
        "single_fix_range_all_trials": all_trials,
    }
    recipient: dict = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(url_state.st, "session_state", sender)
        query, _ = url_state._build_share_query(DEMO_CHOICE)
        patch.setattr(url_state.st, "session_state", recipient)
        patch.setattr(url_state.st, "query_params", dict(parse_qsl(query)))
        url_state._apply_url_preset()
    assert bool(recipient.get("single_fix_range_all_trials")) == all_trials
    travels = chosen and (all_trials or window != full)
    assert recipient.get("single_fix_range") == (window if travels else None)


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
        "animate",
        "fixations",
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
def test_a_replay_saved_while_it_always_drew_fixations_draws_them(config):
    """A schema-9 file that saved a replay opens it with fixations, as that
    version drew it, and nothing else in the file changes."""
    config = {**config, "schema": 9}
    migrated, note = url_state._migrate_plot_config(config)
    assert note is None
    mode, layers = config.get("mode"), config.get("layers")
    replay = isinstance(mode, dict) and mode.get("animate") is True
    if replay and isinstance(layers, dict) and "fixations" in layers:
        assert migrated["layers"]["fixations"]
    if isinstance(layers, dict):
        if not replay or "fixations" not in layers or layers["fixations"]:
            assert migrated["layers"] == layers
        else:
            assert migrated["layers"] == {**layers, "fixations": True}
    assert {k: v for k, v in migrated.items() if k not in ("layers", "schema")} == {
        k: v for k, v in config.items() if k not in ("layers", "schema")
    }


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
    st.lists(
        st.tuples(
            st.sampled_from(["t1", "t2"]),
            st.sampled_from(["a", "b"]),
            st.sampled_from(["L", "R", None]),
            st.one_of(st.none(), st.integers(min_value=0, max_value=5)),
        ),
        min_size=1,
        max_size=30,
    )
)
def test_samples_are_numbered_in_recorded_order_within_their_group(rows):
    """Each reading, screen and eye numbers its samples 1 … n, in the order
    of their clock, every sample counted, whatever order the table holds."""
    from scanpath_studio.chart_axes import with_sample_index
    from scanpath_studio.constants import SAMPLE_INDEX

    samples = pd.DataFrame(
        rows, columns=["trial_id", "screen_id", "eye", "timestamp_ms"]
    ).assign(participant_id="p", x=np.nan)
    samples["timestamp_ms"] = samples["timestamp_ms"].astype(float)
    numbered = with_sample_index(samples)
    keys = ["participant_id", "trial_id", "screen_id", "eye"]
    for _, group in numbered.groupby(keys, dropna=False):
        assert sorted(group[SAMPLE_INDEX]) == list(range(1, len(group) + 1))
        clock = group["timestamp_ms"].fillna(np.inf).to_numpy()
        ranked = group[SAMPLE_INDEX].to_numpy()
        assert all(
            (clock[i] < clock[j]) <= (ranked[i] < ranked[j])
            for i in range(len(group))
            for j in range(len(group))
        )


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


@given(st.text(min_size=1), st.text(min_size=1))
def test_upload_reference_survives_a_new_label_and_name_reuse(old, new):
    from scanpath_studio.constants import DATASET_ALIASES_KEY
    from scanpath_studio.dataset_identity import (
        dataset_share_id,
        resolve_dataset_reference,
    )

    session = {"_datasets": {"first": {}}}
    identifier = dataset_share_id(session, "first")
    session[DATASET_ALIASES_KEY] = {"first": new, "second": old}
    session["_datasets"]["second"] = {}
    assert resolve_dataset_reference(session, old, identifier) == "first"
    assert dataset_share_id(session, "first") == identifier


@given(st.lists(st.tuples(_ID_TEXT, _ID_TEXT), max_size=8))
def test_publication_recipe_preserves_panel_order_and_wording(labels):
    from scanpath_studio import publication

    sources = [
        {"id": str(i), "title": title, "figure": {"data": [], "layout": {}}}
        for i, (title, _) in enumerate(labels)
    ]
    doc = publication.project(sources)
    for panel, (_, caption) in zip(doc["panels"], labels):
        panel["labels"] = [dict(x=0, y=2, dx=0, dy=1, text=caption)]
    restored = json.loads(publication.render(doc, "json"))
    publication.validate_project(restored)
    assert restored == doc


@given(
    st.lists(st.text(alphabet='ab,"\n', max_size=6), min_size=1, max_size=5),
)
def test_a_header_line_ends_where_the_csv_module_ends_its_record(cells):
    """The header line is cut at its first newline outside quotes, as the
    csv module writes and reads it, in one pass over the text."""
    import csv
    import io

    from scanpath_studio.data import _unquoted_line_end

    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerow(cells)
    record = buf.getvalue()
    text = record + "next\n"
    assert _unquoted_line_end(text, '"', "\n") == len(record) - 1
    assert _unquoted_line_end(text.encode(), b'"', b"\n") == len(record.encode()) - 1


@given(
    st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=45, unique=True),
    st.data(),
)
def test_a_category_keeps_its_colour_in_every_figure_of_its_dataset(vocabulary, data):
    """Assigned over the dataset's labels, a category wears the colour the whole
    vocabulary gives it whatever subset a figure shows and in whatever order; up
    to the palette's size every pair is palette-far apart, and a label the
    vocabulary lacks takes a colour none of the vocabulary's has."""
    from itertools import combinations

    shown = data.draw(st.lists(st.sampled_from(vocabulary), unique=True))
    stranger = data.draw(
        st.text(min_size=1, max_size=8).filter(lambda t: t not in vocabulary)
    )
    whole = plots._category_color_map(vocabulary)
    figure = plots._category_color_map(
        [*shown, stranger, None], vocabulary=vocabulary[::-1]
    )
    assert all(figure[label] == whole[label] for label in shown)
    colors = [whole[label] for label in vocabulary]
    assert len(set(colors)) == len(colors)
    assert figure[stranger] not in colors
    if len(vocabulary) <= len(plots._CATEGORY_PALETTE):
        labs = [plots._color_lab(color) for color in colors]
        assert all(plots._delta_e(a, b) >= 23 for a, b in combinations(labs, 2))


@given(
    requested=st.text(min_size=1, max_size=120).filter(str.strip),
    taken=st.lists(st.text(max_size=90), max_size=8),
    max_chars=st.integers(min_value=8, max_value=80),
)
def test_a_dataset_name_is_free_and_fits(requested, taken, max_chars):
    """One rule names an upload, a saved drawing and a renamed built-in: the
    name differs (ignoring case) from every name in use, and fits the field."""
    from scanpath_studio.dataset_identity import unique_name

    name = unique_name(requested, taken, max_chars=max_chars)
    assert name.strip()
    assert len(name) <= max_chars
    assert name.casefold() not in {t.casefold() for t in taken}
    if requested.strip()[:max_chars].rstrip().casefold() not in {
        t.casefold() for t in taken
    }:
        assert name == requested.strip()[:max_chars].rstrip()


_COLUMN = st.text(max_size=12)


@given(
    schema=st.dictionaries(
        st.text(min_size=1, max_size=12),
        st.one_of(st.none(), _COLUMN, st.lists(_COLUMN, min_size=1, max_size=3)),
        min_size=1,
        max_size=5,
    )
)
def test_a_mapping_written_into_a_command_reads_back(schema):
    """Share → Code writes each table's mapping as a flag (A's `--word-schema`,
    B's `--compare-word-schema` / `--compare-fix-schema`); `render` reads the
    same mapping back, whatever the field and column names hold."""
    import shlex

    from scanpath_studio import api, cli
    from scanpath_studio import code_snippet as cs

    state = cs.FigureState(
        kind="comparison",
        settings=api.figure_options("comparison"),
        participant="p1",
        trial="t1",
        compare=cs.CompareTarget(
            participant="p2",
            trial="t2",
            dataset="Pilot",
            schemas={"word_schema": schema, "fix_schema": schema},
        ),
    )
    source = cs.SnippetSource(
        kind=cs.SOURCE_FILES,
        label="files",
        options={"words": ["w.csv"], "fixations": ["f.csv"], "word_schema": schema},
    )
    command = cs.reproduction_code(source, state).cli
    args = cli._render_parser().parse_args(
        shlex.split(command.replace(" \\\n", " "))[2:]
    )
    for attr in ("word_schema", "compare_word_schema", "compare_fix_schema"):
        assert cli._parse_schema_arg(getattr(args, attr), attr) == schema
