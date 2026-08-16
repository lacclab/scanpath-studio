"""The Upload / Add-dataset wizard (the main-area guided data-setup flow).

Split out of ``app.py``: everything from the upload-table reading UI through the
ordered wizard steps (identity → trial/participant/text → keep-fields/filters →
name & finish) and the MultiplEYE upload branch. ``app.py`` drives this from
``render_sidebar_data_source`` / ``main`` and re-exports a few helpers for tests.

A handful of data-IO / normalization helpers (``_read_uploaded_frame``,
``_normalize_pair``, ``_stash_active_mapping``, ``_render_unmapped_view``) stay in
``app.py`` and are reached via ``app.<name>`` at call time — that keeps the
``app._read_uploaded_frame`` upload seam (monkeypatched in AppTests) intact and
avoids an app⇄wizard import cycle.
"""

from __future__ import annotations

import json
import re
from typing import NamedTuple

import pandas as pd
import streamlit as st

from . import app, wizard_shell
from .constants import (
    _VIEW_DATA,
    DEMO_CHOICE,
    FONT_FAMILY,
    ONESTOP_CHOICE,
    PUBLIC_DATASETS_CHOICE,
    SYNTHETIC_CHOICE,
    UPLOAD_CHOICE,
)
from .controls import (
    FIX_FIELD_SPECS,
    NONE_OPTION,
    RAW_GAZE_FIELD_SPECS,
    WORD_FIELD_SPECS,
    column_mapping_ui,
)
from .data import (
    FILE_PART_PREFIX,
    FIX_OPTIONAL_FIELDS,
    PARTICIPANT_CANDIDATES,
    SOURCE_FILE_COLUMN,
    WORD_OPTIONAL_FIELDS,
    aggregate_char_boxes,
    categorize_columns,
    compute_canvas_size,
    compute_keep_columns,
    dropped_columns,
    empty_fixations_frame,
    empty_words_frame,
    extract_columns_from_source_file,
    frame_fingerprint,
    normalize_raw_gaze,
    pick_column,
    propose_fix_schema,
    propose_raw_gaze_schema,
    propose_word_schema,
    source_file_regex_collisions,
    split_source_file,
    trial_id_series,
    trial_mapping_columns,
    validate_fix_schema,
    validate_raw_gaze_schema,
    validate_word_schema,
)
from .experimental_setup import (
    SETUP_GROUP_LABELS,
    SETUP_GROUPS,
    Provenance,
    SetupSnapshot,
    font_pt_to_px,
    pixels_per_degree,
)
from .persistence import is_loopback_url, rename_cached_dataset
from .session_keys import COMPARE_SOURCE_STATE_KEY
from .tabs import _collect_column_mapping
from .tour import (
    maybe_show_wizard_guide,
    render_spotlight_wizard_guide,
    render_wizard_guide_button,
)
from .url_state import PLOT_CONFIG_SCHEMA, _seed_column_mapping


class _UploadResult(NamedTuple):
    """Result of the grouped-upload flow.

    ``words``/``fixations``/``raw_gaze`` are normalized (empty when absent or, for
    words/fixations, when the mapping is incomplete). ``raw_words``/``raw_fixations``
    are the pre-normalization frames shown by ``app._render_unmapped_view`` when
    ``problems`` is non-empty."""

    words: pd.DataFrame
    fixations: pd.DataFrame
    raw_gaze: pd.DataFrame
    raw_words: pd.DataFrame
    raw_fixations: pd.DataFrame
    problems: list


def _reset_wizard_widgets() -> None:
    """Clear the wizard's per-table mapping + keep-field widgets so 'Add data'
    starts a fresh dataset."""
    for key in [
        k
        for k in list(st.session_state.keys())
        if isinstance(k, str) and k.startswith("col_map_")
    ]:
        del st.session_state[key]
    for key in (
        "wizard_dataset_name",
        "wizard_dataset_format",
        "wizard_config_restore",
        "_wizard_config_last",
        "_wizard_restored_meta",
        "_composite_trial_columns",
        "wizard_filter_fields",
        "wizard_filter_by",
        "wizard_keep_extra",
        "wizard_trial_per_table",
        "wizard_participant_per_table",
        "wizard_text_id_per_table",
        # MultiplEYE preset uploads + generic filename-derivation / aggregation.
        "mpe_fix_upload",
        "mpe_aoi_upload",
        "mpe_questions_upload",
        "mpe_participant_upload",
        "wizard_filename_split",
        "wizard_filename_mode",
        "wizard_filename_regex",
        "wizard_filename_regex_lower",
        "wizard_aggregate_char_boxes",
        # DATA-22 Recording-setup step. The *mode* radios always reset — decision
        # (d): a second dataset from the same lab keeps the pre-filled values
        # (`_wizard_setup_recall`, deliberately NOT cleared here) but the user
        # still has to assert that the setup applies to this dataset too.
        *(_SETUP_MODE_KEYS[g] for g in SETUP_GROUPS),
        "wizard_setup_screen_w",
        "wizard_setup_screen_h",
        "wizard_setup_monitor_mm",
        "wizard_setup_distance_mm",
        "wizard_setup_font_pt",
        "wizard_setup_font_family",
        "_wizard_restored_setup",
        "_wizard_setup_restored_applied",
        "_wizard_problems_last",
    ):
        st.session_state.pop(key, None)
    # Re-seed the accordion on the next entry instead of opening wherever the
    # previous dataset was left.
    wizard_shell.reset_accordion()


def _default_dataset_name() -> str:
    """A unique 'Dataset N' name not already taken by a stored dataset."""
    existing = st.session_state.get("_datasets", {})
    n = len(existing) + 1
    while f"Dataset {n}" in existing:
        n += 1
    return f"Dataset {n}"


# Built-in data-source labels a user dataset must not shadow (else the radio gets
# a duplicate option and the stored entry hijacks the built-in source's branch).
_RESERVED_SOURCE_NAMES = frozenset(
    {
        DEMO_CHOICE,
        ONESTOP_CHOICE,
        PUBLIC_DATASETS_CHOICE,
        SYNTHETIC_CHOICE,
        UPLOAD_CHOICE,
    }
)


def _safe_dataset_name(name: str | None, *, exclude: str | None = None) -> str:
    """A non-empty dataset name that collides with neither a built-in source label
    nor an already-stored dataset (suffixed ``(2)``, ``(3)``… rather than silently
    overwriting an existing entry's frames).

    ``exclude`` drops one stored name from the collision check — a rename (DATA-23)
    must not read the dataset being renamed as a clash with itself and turn
    "My corpus" into "My corpus (2)" on a capitalisation fix."""
    name = (name or "").strip() or _default_dataset_name()
    if name in _RESERVED_SOURCE_NAMES:
        name = f"{name} (uploaded)"
    existing = {
        key: value
        for key, value in st.session_state.get("_datasets", {}).items()
        if key != exclude
    }
    if name in existing:
        base, n = name, 2
        while f"{base} ({n})" in existing:
            n += 1
        name = f"{base} ({n})"
    return name


def _finalize_wizard_dataset() -> None:
    """Store the wizard's normalized frames as a named dataset and switch to it.

    Runs as the "✅ Add dataset" button's ``on_click`` callback. A callback —
    not an inline ``if button:`` handler — is required because a real
    ``st.file_uploader`` in the wizard can swallow an inline button click (the
    click triggers a rerun in which the uploader re-renders and the handler is
    never reached), leaving the dataset unstored. The callback fires as part of
    the click event, before the rerun, so it always runs. The frames were stashed
    in ``_wizard_finalize_payload`` on the render that drew the button."""
    payload = st.session_state.pop("_wizard_finalize_payload", None)
    if payload is None:
        return
    ds_name = _safe_dataset_name(st.session_state.get("wizard_dataset_name"))
    store = st.session_state.setdefault("_datasets", {})
    store[ds_name] = payload
    # Apply the source switch through the plain pending key that
    # render_sidebar_data_source consumes before the radio instantiates, and
    # leave the wizard.
    st.session_state["_pending_source_choice"] = ds_name
    st.session_state["_show_upload_wizard"] = False
    st.session_state["setup_complete"] = True
    # Flag the transition so main() paints a "loading" bridge over the wizard
    # while the new dataset's first figure builds — otherwise the wizard lingers
    # on screen (stale DOM) for the seconds the heavy first render takes.
    st.session_state["_wizard_finalizing"] = True


def _remove_dataset(name: str) -> None:
    """Remove a previously added dataset (the ✕ button's ``on_click`` callback).

    Pops it from the ``_datasets`` store and, if it was the selected source,
    switches back to the bundled demo via ``_pending_source_choice`` (applied
    before the radio re-instantiates, like the wizard finalize/cancel switch)."""
    store = st.session_state.get("_datasets", {})
    store.pop(name, None)
    if st.session_state.get("data_source_choice") == name:
        st.session_state["_pending_source_choice"] = DEMO_CHOICE


def rename_dataset(old: str, new: str) -> str | None:
    """Rename a stored dataset (DATA-23). Returns the name it actually took.

    The name is the **key** into the ``_datasets`` store, so a rename is a re-key,
    and every other holder of that string has to move with it: the canonical
    ``data_source_choice`` (through the pre-widget ``_pending_source_choice`` seam,
    like `_remove_dataset`'s fallback — assigning the widget key inline is
    unreliable in a browser), the wizard's ``_prev_source`` return address, and
    CMP-8's ``cmp_dataset`` when the comparison draws scanpath B from it. The
    ENG-26 recovery cache follows in :func:`persistence.rename_cached_dataset`,
    which moves the Parquet files rather than re-encoding them.

    Returns ``None`` when there is nothing to rename (unknown dataset, or the new
    name resolves to the one it already has). The store is rebuilt in order rather
    than re-inserted, so the renamed dataset keeps its place in the source picker.
    """
    store = st.session_state.get("_datasets", {})
    if old not in store:
        return None
    name = _safe_dataset_name(new, exclude=old)
    if name == old:
        return None
    st.session_state["_datasets"] = {
        (name if key == old else key): value for key, value in store.items()
    }
    if st.session_state.get("data_source_choice") == old:
        st.session_state["_pending_source_choice"] = name
    if st.session_state.get("_prev_source") == old:
        st.session_state["_prev_source"] = name
    if st.session_state.get(COMPARE_SOURCE_STATE_KEY) == old:
        st.session_state[COMPARE_SOURCE_STATE_KEY] = name
    rename_cached_dataset(st.session_state, old, name)
    return name


def _enter_add_data_wizard() -> None:
    """Open the upload wizard (the "➕ Add data" button's ``on_click`` callback).

    Tracks the wizard in a *plain* ``_show_upload_wizard`` flag rather than
    stuffing ``UPLOAD_CHOICE`` into the ``data_source_choice`` radio key. The
    radio isn't rendered while the wizard is open, and Streamlit garbage-collects
    a not-rendered widget key after a couple of reruns — which used to silently
    drop ``data_source_choice`` mid-wizard (more so for a composite trial id,
    which needs more interactions/reruns) and bounce the user back to the main
    app. The flag is never GC'd, and the radio's value stays a real source."""
    st.session_state["_prev_source"] = st.session_state.get(
        "data_source_choice", DEMO_CHOICE
    )
    st.session_state["_show_upload_wizard"] = True
    st.session_state["setup_complete"] = False
    # DATA-26: the wizard is the 🗂️ Data page's add-a-dataset mode, so take the
    # user there. Written as a *request* (`menu.render_nav` reconciles it on the
    # next run) rather than a `switch_to_view` — this is an `on_click` callback,
    # where Streamlit forbids `st.switch_page`.
    st.session_state["main_nav"] = _VIEW_DATA
    _reset_wizard_widgets()


def _map_section(raw, specs, proposed, prefix, host, keys) -> dict:
    """Render a subset of a table's mapping fields (the wizard renders the core
    fields in grouped, ordered steps). Returns the partial mapping for ``keys``.

    No ``on_change`` any more: the accordion's open state is owned by the keyed
    expander and moved only by explicit navigation (``wizard_shell``), so a
    mapping widget no longer has to defend the step it lives in against being
    collapsed by its own edit (DATA-19's mechanism, deleted by DATA-22)."""
    if raw is None or getattr(raw, "empty", True):
        return {}
    return column_mapping_ui(
        raw,
        table_label="",
        state_key_prefix=prefix,
        field_specs=specs,
        proposed=proposed,
        container=host,
        use_expander=False,
        only_keys=keys,
        header=False,
    )


def _default_trial_columns(proposed: dict, present_cols) -> list:
    """Default trial-id mapping for the wizard, restricted to ``present_cols`` (the
    columns common to every table).

    A *trial* is one reading of one passage, so the default composes the
    participant with the finest passage identifier present (paragraph preferred
    over a coarser text id), plus a repeated-reading column when the data has one
    — otherwise the two readings of the same paragraph would collapse into one
    trial (OneStop's own ``unique_trial_id`` is participant + paragraph +
    repeated reading). When that composite can't be built, prefer a single
    precomputed unique trial id over a redundant composite (e.g. don't pair
    ``unique_trial_id`` with the paragraph id it already encodes)."""
    cols_frame = pd.DataFrame(columns=list(present_cols))
    # Use the canonical candidate lists so non-standard names (reader_id,
    # recording_session_label, …) are matched here too, not just by the schema
    # auto-detect.
    participant = pick_column(cols_frame, PARTICIPANT_CANDIDATES)
    paragraph = pick_column(cols_frame, ["unique_paragraph_id", "paragraph_id"])
    text = pick_column(cols_frame, ["unique_text_id", "text_id"])
    # Finest passage grain first: a paragraph is one trial; a text/article may
    # span several paragraphs.
    passage = paragraph or text
    repeated = pick_column(cols_frame, ["repeated_reading_trial", "reread"])
    trial = proposed.get("trial")
    trial_present = bool(trial) and trial in set(present_cols)
    # A precomputed unique trial id that isn't just the passage we'd otherwise
    # compose wins outright (no benefit composing).
    if trial_present and trial not in (paragraph, text):
        return [trial]
    if participant and passage:
        return [c for c in (participant, passage, repeated) if c]
    if paragraph and text:
        return [paragraph, text]
    if trial_present:
        return [trial]
    # No usable composite/trial — fall back to whatever passage component we
    # have (never a lone participant, which isn't a trial), else leave empty so
    # the user picks.
    return list(dict.fromkeys(c for c in (passage,) if c))


# -----------------------------------------------------------------------------
# Cached per-rerun work (DATA-22 §5)
#
# Every one of these used to recompute on *every keystroke* with no spinner — a
# `nunique` over the whole uploaded frame, a full column scan, a re-proposal of
# the schema — while the user typed in a text box. They are now keyed on
# `data.frame_fingerprint` plus the mapping, and each carries a labelled spinner
# so the work is visible rather than felt. Frames pass un-hashed (underscore
# args) per the house convention; the fingerprint is the real key.
# -----------------------------------------------------------------------------


def _mapping_key(mapping) -> tuple:
    """A hashable cache key for a column mapping (str | list | None)."""
    if mapping is None:
        return ()
    if isinstance(mapping, (list, tuple)):
        return tuple(mapping)
    return (mapping,)


@st.cache_data(show_spinner="Counting trials…")
def _trial_id_values_cached(
    _raw, _mapping, fingerprint: tuple, key: tuple
) -> frozenset:
    return frozenset(trial_id_series(_raw, _mapping).unique())


def _trial_id_values(raw, schema) -> set | None:
    """Set of distinct trial-id strings for a raw frame + its trial mapping
    (composite mappings are joined, mirroring ``data.trial_id_series``). ``None``
    when the trial isn't mapped or its columns are absent."""
    if raw is None or getattr(raw, "empty", True) or not schema.get("trial"):
        return None
    cols = trial_mapping_columns(schema["trial"])
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return set(
        _trial_id_values_cached(
            raw,
            schema["trial"],
            frame_fingerprint(raw),
            _mapping_key(schema["trial"]),
        )
    )


@st.cache_data(show_spinner="Detecting columns…")
def _c_propose_word_schema(_raw, fingerprint: tuple) -> dict:
    return propose_word_schema(_raw)


@st.cache_data(show_spinner="Detecting columns…")
def _c_propose_fix_schema(_raw, fingerprint: tuple) -> dict:
    return propose_fix_schema(_raw)


@st.cache_data(show_spinner="Detecting columns…")
def _c_propose_raw_gaze_schema(_raw, fingerprint: tuple) -> dict:
    return propose_raw_gaze_schema(_raw)


@st.cache_data(show_spinner="Scanning fields…")
def _c_categorize_columns(_raw, _schema, _registry, fingerprint: tuple, key: tuple):
    # Only ``fingerprint`` + ``key`` form the cache key; the frame, the mapping
    # dict and the module-level registry table all ride un-hashed.
    return categorize_columns(_raw, _schema, _registry)


@st.cache_data(show_spinner="Aggregating character boxes…")
def _c_aggregate_char_boxes(_raw, _schema, fingerprint: tuple, key: tuple):
    return aggregate_char_boxes(_raw, _schema)


def _schema_key(schema: dict | None) -> tuple:
    """A hashable, order-stable projection of a mapping dict for cache keys."""
    if not schema:
        return ()
    return tuple(
        sorted(
            (k, tuple(v) if isinstance(v, (list, tuple)) else v)
            for k, v in schema.items()
        )
    )


def _render_unified_identifier(
    field_key: str,
    label: str,
    help_text: str,
    toggle_label: str,
    body,
    raw_words,
    raw_fix,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
    common_cols: list,
    default_cols: list,
) -> None:
    """Shared identifier picker for trial / participant / text.

    One unified multiselect over the columns common to every present table by
    default, with an opt-in *Different … per table* toggle. The per-table
    override inherits the unified pick (so flipping it on never reverts to
    nothing — the old behaviour). Several columns compose an id (joined with
    ``_`` like the trial id). Writes ``schema[field_key]`` (str / list / None)
    into ``word_schema`` / ``fix_schema`` in place, mirroring into the per-table
    ``col_map_<tbl>_<field>`` keys for save/restore + a later per-table toggle.
    """
    fix_key, words_key = f"col_map_fix_{field_key}", f"col_map_words_{field_key}"
    unified_key = f"col_map_{field_key}_unified"

    def _mapping(chosen):
        if not chosen:
            return None
        return chosen[0] if len(chosen) == 1 else list(chosen)

    def _seed(key: str, options: list, fallback: list) -> None:
        """Seed a multiselect's session value, dropping columns absent from
        ``options`` (a new upload changes the column universe), like
        ``column_mapping_ui`` — so the stale-reset never fights a default arg."""
        stored = st.session_state.get(key)
        if stored is None:
            st.session_state[key] = list(fallback)
            return
        valid = [c for c in stored if c in options]
        if len(valid) != len(stored):
            st.session_state[key] = valid or list(fallback)

    per_table = False
    if has_words and has_fix:
        st.session_state.setdefault(f"wizard_{field_key}_per_table", False)
        per_table = body.toggle(
            toggle_label,
            key=f"wizard_{field_key}_per_table",
            help="Most datasets name it the same way in every table, so one "
            "shared mapping is used. Turn this on only if Words and Fixations "
            "name it differently.",
        )

    if per_table:
        # Inherit the unified pick so flipping per-table on doesn't start empty.
        inherited = list(st.session_state.get(unified_key) or [])
        if has_fix:
            if inherited and not st.session_state.get(fix_key):
                st.session_state[fix_key] = list(inherited)
            body.caption("Fixations")
            _seed(fix_key, list(raw_fix.columns), inherited)
            chosen_f = body.multiselect(
                label,
                options=list(raw_fix.columns),
                key=fix_key,
                help=help_text,
                label_visibility="collapsed",
            )
            fix_schema[field_key] = _mapping(chosen_f)
        if has_words:
            if inherited and not st.session_state.get(words_key):
                st.session_state[words_key] = list(inherited)
            body.caption("Words/IA")
            _seed(words_key, list(raw_words.columns), inherited)
            chosen_w = body.multiselect(
                label,
                options=list(raw_words.columns),
                key=words_key,
                help=help_text,
                label_visibility="collapsed",
            )
            word_schema[field_key] = _mapping(chosen_w)
    else:
        # One multiselect over the columns common to every present table; its
        # value is mirrored into each table's schema + the per-table widget keys
        # (so the save/restore round-trip and a later per-table toggle both start
        # from this choice). On first render, inherit a restored/seeded per-table
        # mapping when the tables agree, else fall back to ``default_cols``.
        stored = st.session_state.get(unified_key)
        if stored is None:
            inherited = None
            for k in (fix_key, words_key):
                v = st.session_state.get(k)
                if (
                    isinstance(v, (list, tuple))
                    and v
                    and all(c in common_cols for c in v)
                ):
                    inherited = list(v)
                    break
            st.session_state[unified_key] = (
                inherited if inherited else list(default_cols)
            )
        else:
            valid = [c for c in stored if c in common_cols]
            if len(valid) != len(stored):
                st.session_state[unified_key] = valid or list(default_cols)
        chosen = body.multiselect(
            label,
            options=common_cols,
            key=unified_key,
            help=help_text,
        )
        mapping = _mapping(chosen)
        if has_fix:
            fix_schema[field_key] = mapping
            st.session_state[fix_key] = list(chosen)
        if has_words:
            word_schema[field_key] = mapping
            st.session_state[words_key] = list(chosen)


def _wizard_filename_derive(body, raw_words, raw_fix, raw_gaze):
    """Optional step: derive columns from the captured ``source_file`` so a trial
    / participant id that lives only in the file name can be mapped.

    Two modes: split into positional ``file_part_N`` columns on a delimiter, or
    extract *named groups* with a regex (robust to variable-length parts, e.g. a
    stimulus name whose length varies). Returns the (possibly augmented) frames so
    the identifier pickers below see the new columns. No-op unless enabled."""
    body.caption(
        "When identity lives in the file name (no column carries it), the "
        "uploaded filename is captured as `source_file` — derive columns from it "
        "to map as the Trial or Participant id below."
    )
    if not body.toggle(
        "Derive columns from the filename",
        key="wizard_filename_split",
        help="Adds columns parsed from source_file (e.g. session, stimulus) you "
        "can then map as ids.",
    ):
        return raw_words, raw_fix, raw_gaze

    mode = body.radio(
        "How",
        ["Split on a delimiter", "Regex named groups"],
        key="wizard_filename_mode",
        horizontal=True,
    )
    pattern = ""
    if mode == "Split on a delimiter":
        delimiter = (
            body.text_input(
                "Delimiter",
                value="_",
                key="wizard_filename_delim",
                max_chars=8,
                help="Character(s) to split the filename on — e.g. "
                "`reader0_b0_scanpath` → reader0 / b0 / scanpath.",
            )
            or "_"
        )
        out = [
            split_source_file(fr, delimiter=delimiter) if not fr.empty else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]
    else:
        pattern = body.text_input(
            "Regex (named groups)",
            value="",
            key="wizard_filename_regex",
            help=r"e.g. `(?P<session>\d+_\w+_ET\d)_.*_(?P<stimulus>.+)_scanpath` — "
            "each named group becomes a column.",
        )
        lower = body.toggle(
            "Lowercase extracted values",
            key="wizard_filename_regex_lower",
            help="Fold case so a value matches across tables (e.g. CamelCase "
            "scanpath names vs lowercase AOI names).",
        )
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                body.error(f"Invalid regex: {exc}")
                return raw_words, raw_fix, raw_gaze
            # A group named after an existing column would be skipped (real data
            # wins) — flag it so the user renames the group instead of silently
            # getting the original column.
            collisions = sorted(
                {
                    c
                    for fr in (raw_words, raw_fix, raw_gaze)
                    if not fr.empty
                    for c in source_file_regex_collisions(fr, pattern)
                }
            )
            if collisions:
                body.warning(
                    "These group names already exist as columns and were left "
                    f"untouched: {', '.join(collisions)}. Rename the group(s) to "
                    "extract them."
                )
        out = [
            extract_columns_from_source_file(fr, pattern, lowercase=lower)
            if not fr.empty
            else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]

    raw_words, raw_fix, raw_gaze = out
    preview = raw_fix if not raw_fix.empty else raw_words
    if mode == "Split on a delimiter":
        new_cols = [c for c in preview.columns if c.startswith(FILE_PART_PREFIX)]
    elif pattern:
        new_cols = [c for c in re.compile(pattern).groupindex if c in preview.columns]
    else:
        new_cols = []
    if new_cols:
        body.caption("Derived columns (first rows) — map them as ids below:")
        body.dataframe(
            preview[[SOURCE_FILE_COLUMN, *new_cols]].drop_duplicates().head(),
            width="stretch",
            hide_index=True,
        )
    return raw_words, raw_fix, raw_gaze


def _wizard_trial_step(
    body,
    raw_words,
    raw_fix,
    prop_w,
    prop_f,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
) -> None:
    """Trial-identifier wizard step: a unified picker shared across tables by
    default (the participant+text default composite), an opt-in per-table
    override, and a per-table trial-count check that flags mismatches.
    Mutates ``word_schema`` / ``fix_schema`` in place."""
    body.caption(
        "Which column(s) identify a single trial (one reading of one text)? "
        "Pick several to compose an id — by default the participant and text ids."
    )

    # Core tables present (raw-gaze keeps its own mapping in its own step).
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default_trial = _default_trial_columns(prop_primary, common_cols)
    _render_unified_identifier(
        "trial",
        "Trial ID *",
        "Pick the column holding your unique trial ID — or several to build one "
        "on the fly (values joined with '_'), e.g. participant + text. The same "
        "mapping is applied to every table.",
        "Different trial-id columns per table",
        body,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        common_cols,
        default_trial,
    )

    # Per-table trial-id sets. Equal → one clean count. Differing but overlapping
    # is usually benign (one table simply covers extra trials, e.g. words for a
    # paragraph with no fixations) → emphasise the difference without implying a
    # mapping error. Differing AND disjoint means the ids don't line up at all.
    sets = {}
    if has_fix:
        sets["Fixations"] = _trial_id_values(raw_fix, fix_schema)
    if has_words:
        sets["Words/IA"] = _trial_id_values(raw_words, word_schema)
    present = {k: v for k, v in sets.items() if v is not None}
    if present:
        values = list(present.values())
        counts_str = ", ".join(f"{k}: **{len(v):,}**" for k, v in present.items())
        if all(v == values[0] for v in values):
            body.success(
                f"✓ **{len(values[0]):,}** trials detected — make sure this is the "
                "number of trials you expect to see."
            )
        elif set.intersection(*values):
            body.info(
                f"ℹ️ Trial coverage differs per table — {counts_str}. They share "
                f"**{len(set.intersection(*values)):,}** trials; some appear in "
                "only one table."
            )
        else:
            body.warning(
                f"⚠️ No trial ids are shared across tables — {counts_str}. Check "
                "the trial-id mapping lines up (try *Different trial-id columns "
                "per table*)."
            )


@st.cache_data(show_spinner="Counting…")
def _distinct_id_count_cached(_raw, _mapping, fingerprint: tuple, key: tuple) -> int:
    return int(trial_id_series(_raw, _mapping).nunique())


def _distinct_id_count(raw, mapping) -> int | None:
    """Distinct values of a single-column or composite identifier mapping."""
    if raw is None or getattr(raw, "empty", True) or not mapping:
        return None
    cols = trial_mapping_columns(mapping)
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return _distinct_id_count_cached(
        raw, mapping, frame_fingerprint(raw), _mapping_key(mapping)
    )


def _wizard_participant_text_step(
    field_key: str,
    label: str,
    noun: str,
    help_text: str,
    body,
    raw_words,
    raw_fix,
    prop_w,
    prop_f,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
) -> None:
    """Optional participant- or text-identifier step, in the same shape as the
    Trial identifier (unified picker + per-table toggle + composite support),
    followed by a distinct-value count. Mutates the schemas in place."""
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default = prop_primary.get(field_key)
    default_cols = [default] if default in common_cols else []
    _render_unified_identifier(
        field_key,
        label,
        help_text,
        f"Different {noun} columns per table",
        body,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        common_cols,
        default_cols,
    )
    pp, pp_schema = (raw_fix, fix_schema) if has_fix else (raw_words, word_schema)
    n = _distinct_id_count(pp, pp_schema.get(field_key))
    if n is not None:
        body.success(
            f"✓ **{n:,}** {noun} — make sure this is the number of {noun} you "
            "expect to see."
        )


def _clean_multiselect_state(key: str, valid) -> None:
    """Drop session values for a multiselect that aren't valid options (e.g. a
    restored config from different data), so Streamlit doesn't raise on render."""
    stored = st.session_state.get(key)
    if isinstance(stored, (list, tuple)):
        valid_set = set(valid)
        cleaned = [v for v in stored if v in valid_set]
        if len(cleaned) != len(stored):
            st.session_state[key] = cleaned


def wide_frame_warning(n_extra_fields: int, n_rows: int) -> str | None:
    """PERF-2 warning for selections large enough to affect rerun latency."""
    if n_extra_fields < 50 and n_extra_fields * max(n_rows, 0) < 5_000_000:
        return None
    return (
        f"Keeping {n_extra_fields} additional fields across up to {n_rows:,} rows "
        "can noticeably slow caching, grouping, and browser transfer. Keep only "
        "the measures and metadata you plan to use; you can revise this mapping later."
    )


def _wizard_reader_ids(raw_words, word_schema, raw_fix, fix_schema) -> list:
    """The reader ids the finished dataset will have, read from the raw tables.

    DATA-20's *About your readers* step runs **before** the frames are
    normalized (normalization needs the keep-columns the next step chooses), so
    the join report can't be built from `metadata.participant_ids`. The mapped
    participant column is only *renamed* by `normalize_*` — its values are
    untouched — so reading it off the raw frame gives the same id set the join
    will see, which is what makes "no row for reader p7" trustworthy here.

    Cached and **gated**, following `app._cached_participant_ids`: this is a
    `.unique()` over the *raw* (unfiltered, un-normalized) frames, the largest
    version there is, and the wizard reruns on every keystroke across all seven
    steps. Only the join report consumes the list, so nothing is scanned until a
    table is actually being attached.
    """
    from scanpath_studio import metadata as metadata_mod

    if st.session_state.get(metadata_mod.RAW_SESSION_KEY) is None:
        return []
    found: set = set()
    for frame, schema in ((raw_fix, fix_schema), (raw_words, word_schema)):
        column = (schema or {}).get("participant")
        if not column or frame is None or frame.empty or column not in frame.columns:
            continue
        found |= set(_wizard_reader_ids_cached(frame, column, frame_fingerprint(frame)))
    return sorted(found)


@st.cache_data(show_spinner=False)
def _wizard_reader_ids_cached(_frame, column: str, fingerprint: str) -> list:
    """Distinct reader ids in one raw frame's mapped participant column.

    Underscore-prefixed frame + an explicit `frame_fingerprint` key, the house
    convention — see `app._cached_participant_ids`.
    """
    return sorted({str(value) for value in _frame[column].dropna().unique()})


def _wizard_keep_and_filter(tables: list, filter_host, keep_host) -> tuple[dict, list]:
    """Render ONE cross-table *Filter trials by* picker (``filter_host``) and ONE
    *Additional fields to keep* picker (``keep_host``) — instead of duplicating
    both per table, which was confusing.

    ``tables`` is a list of ``(raw, schema, registry, prefix)``. Returns
    ``(keep_by_prefix, filter_dest_fields)``: the source columns to retain per
    table (fed to ``compute_keep_columns(keep_columns=…)``), and the trial-level
    condition fields the Filter panel should offer."""
    cat_by_prefix: dict = {}
    for raw, schema, registry, prefix in tables:
        if raw is None or raw.empty or schema is None:
            continue
        cat_by_prefix[prefix] = _c_categorize_columns(
            raw,
            schema,
            registry,
            frame_fingerprint(raw),
            # `prefix` is in the key because `_registry` rides un-hashed and
            # varies per table: two tables with the same fingerprint *and* the
            # same schema key would otherwise share one result.
            (prefix, _schema_key(schema)),
        )

    # --- Filter trials by: trial-level condition (meta) fields, cross-table ---
    # dest field -> [(prefix, source), …] so the chosen field's source column is
    # kept in the table(s) that carry it.
    filter_map: dict = {}
    for prefix, cats in cat_by_prefix.items():
        for d in cats["detected_optional"]:
            if d["category"] == "meta":
                filter_map.setdefault(d["dest"], []).append((prefix, d["source"]))
    filter_dest_fields: list = []
    if filter_map:
        opts = sorted(filter_map)
        _clean_multiselect_state("wizard_filter_by", opts)
        filter_dest_fields = filter_host.multiselect(
            "Filter trials by",
            options=opts,
            default=opts,
            key="wizard_filter_by",
            help="Trial-level conditions (Hunting/Gathering, difficulty, …). Each "
            "becomes a value picker in the sidebar Filter panel.",
        )

    # --- Additional fields to keep: non-meta detected + unclaimed, cross-table ---
    keep_map: dict = {}
    keep_labels: dict = {}
    keep_default: list = []
    for prefix, cats in cat_by_prefix.items():
        for d in cats["detected_optional"]:
            if d["category"] == "meta":
                continue  # handled by the Filter picker above
            keep_map.setdefault(d["source"], []).append((prefix, d["source"]))
            keep_labels[d["source"]] = f"{d['dest']}  ·  {d['category']}"
            if d["source"] not in keep_default:
                keep_default.append(d["source"])  # measures/linguistic kept by default
        for col in cats["unclaimed"]:
            keep_map.setdefault(col, []).append((prefix, col))
            keep_labels.setdefault(col, f"{col}  ·  extra")
    chosen_keep: set = set()
    if keep_map:
        opts = list(keep_map)
        _clean_multiselect_state("wizard_keep_extra", opts)
        chosen_keep = set(
            keep_host.multiselect(
                "Additional fields to keep",
                options=opts,
                # Detected reading measures / linguistic features kept by default;
                # unrecognised extras stay off until opted in.
                default=keep_default,
                format_func=lambda s: keep_labels.get(s, s),
                key="wizard_keep_extra",
                help="Reading measures, linguistic features and any other columns "
                "to retain (to colour or filter by). Fewer columns is faster.",
            )
        )
        warning = wide_frame_warning(
            len(chosen_keep),
            max(
                (len(raw) for raw, *_ in tables if raw is not None),
                default=0,
            ),
        )
        if warning:
            keep_host.warning(warning)

    # Map both pickers' choices back to the per-table source columns to keep.
    keep_by_prefix: dict = {prefix: set() for prefix in cat_by_prefix}
    for dest in filter_dest_fields:
        for prefix, source in filter_map.get(dest, []):
            keep_by_prefix[prefix].add(source)
    for key in chosen_keep:
        for prefix, source in keep_map.get(key, []):
            keep_by_prefix[prefix].add(source)
    return keep_by_prefix, list(filter_dest_fields)


def _wizard_restore_config(host) -> None:
    """Step 1 of the wizard: optionally restore a previously saved setup, seeding
    the column mapping + kept-field choices so the user skips re-mapping. Applied
    once per uploaded file; reruns so the mapping widgets pick up the values."""
    uploaded = host.file_uploader(
        "Restore a saved setup (optional)",
        type=["json"],
        key="wizard_config_restore",
        help="Re-apply a column mapping + field choices you exported earlier "
        "(from the 💾 Session panel).",
    )
    if uploaded is None:
        return
    signature = (uploaded.name, uploaded.size)
    if st.session_state.get("_wizard_config_last") == signature:
        return
    st.session_state["_wizard_config_last"] = signature
    try:
        config = json.loads(uploaded.getvalue().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        host.warning(f"Couldn't read config: {exc}")
        return
    if isinstance(config, dict):
        # Overwrite: the wizard's mapping widgets were already created on a prior
        # render, so their keys exist — setdefault would no-op and the restore
        # would silently fail. This step runs before the widgets re-instantiate
        # this pass, so writing the keys is safe, and it reruns afterwards.
        _seed_column_mapping(config.get("column_mapping"), overwrite=True)
        # Remember the restored config's provenance so the caller can show which
        # dataset (and when) it was exported from, below the upload box (9.1).
        st.session_state["_wizard_restored_meta"] = {
            "data_source": config.get("data_source"),
            "exported_at": config.get("exported_at"),
        }
        # DATA-22 decision (a): a restored setup file pre-answers the
        # Recording-setup step. The section is optional — a file written before
        # this existed simply leaves the step unanswered, which is the honest
        # outcome rather than a silent default. Additive, so per ENG-11 the
        # PLOT_CONFIG_SCHEMA stays where it is.
        if isinstance(config.get("experimental_setup"), dict):
            # The canvas is carried in a *sibling* section by the plot-config
            # writer (`tabs._build_studio_config` puts it under `canvas_px`), so
            # it has to be merged in here — see `_restored_setup_snapshot`, which
            # would otherwise fall back to the 2560x1440 class default and, if
            # the file's provenance said "measured", pre-answer the step with a
            # measured monitor nobody ever measured.
            restored = dict(config["experimental_setup"])
            canvas = config.get("canvas_px")
            if isinstance(canvas, dict):
                for key, source in (
                    ("canvas_width", "width"),
                    ("canvas_height", "height"),
                ):
                    if canvas.get(source) is not None:
                        restored.setdefault(key, canvas[source])
            st.session_state["_wizard_restored_setup"] = restored
            st.session_state.pop("_wizard_setup_restored_applied", None)
        st.toast("Restored the saved mapping — review it below.", icon="✅")
        st.rerun()


def _render_restored_config_caption(host) -> None:
    """Below the restore box: name the dataset the restored setup came from (and
    when it was exported), so the user can confirm they loaded the right one."""
    meta = st.session_state.get("_wizard_restored_meta")
    if not meta:
        return
    source = meta.get("data_source")
    exported = meta.get("exported_at")
    bits = []
    if source:
        bits.append(f"from **{source}**")
    if exported:
        try:
            from datetime import datetime

            bits.append(f"exported {datetime.fromisoformat(exported):%Y-%m-%d %H:%M}")
        except (ValueError, TypeError):
            bits.append(f"exported {exported}")
    detail = " · ".join(bits) if bits else "from a saved file"
    host.caption(f"✓ Restored setup {detail} — review the mapping below.")


def _wizard_setup_config() -> dict:
    """The current wizard setup as a JSON-able dict: the column mapping plus
    provenance, in the schema the restore step (``_wizard_restore_config``) reads
    back. Lets a user save their mapping and re-apply it to similar data later."""
    from datetime import datetime

    from scanpath_studio import __version__

    return {
        # The shared Save & restore format — this setup file can be loaded through
        # the main "💾 Save & restore" uploader too, so it stamps the same
        # single-source-of-truth schema version (ENG-11) rather than a literal.
        "schema": PLOT_CONFIG_SCHEMA,
        "app": {"name": "Scanpath Studio", "version": __version__},
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "data_source": (st.session_state.get("wizard_dataset_name") or "").strip()
        or None,
        "column_mapping": _collect_column_mapping(),
        # DATA-22 §7 surface 3: the recording setup + its provenance, so a
        # re-applied setup file carries "the monitor was assumed" rather than
        # quietly re-deriving a number the recipient would read as measured.
        "experimental_setup": current_setup_section(),
    }


def current_setup_section() -> dict | None:
    """The ``experimental_setup`` section for a saved config, or ``None``.

    Shared by ``_wizard_setup_config`` and ``tabs._build_studio_config`` so both
    writers emit the same shape. Returns ``None`` when the wizard has not
    resolved a snapshot yet — an absent section reads as "unknown", which is
    what it is; an all-defaults one would read as an answer.
    """
    payload = st.session_state.get("_wizard_setup_snapshot")
    return dict(payload) if isinstance(payload, dict) else None


def _render_setup_download(host) -> None:
    """Export the current column mapping as a JSON setup file, so it can be
    re-applied later via the wizard's *Restore a saved setup* step. Rendered just
    above the **Add dataset** button."""
    host.download_button(
        "⬇️ Download setup (JSON)",
        data=json.dumps(_wizard_setup_config(), indent=2),
        file_name="scanpath_studio_setup.json",
        mime="application/json",
        key="wizard_setup_download",
        help="Save this column mapping to re-use on similar data — restore it "
        "from *Restore a saved setup* at the top of Column mapping.",
    )


# -----------------------------------------------------------------------------
# Step 4 · Recording setup (DATA-22 §3)
#
# The old wizard rendered this panel as step *2* — before the upload — and
# silently seeded a 2560x1440 monitor, 597 mm, 800 mm and a 16 px font, with
# nothing telling the user those were guesses. Estimating from the data was not
# even possible there, because there was no data yet.
#
# Now it sits after the upload and asks, per group, *how do you know?* — with
# `index=None` so nothing is preselected. The user either knows the values,
# derives them from their own data, knowingly takes a named default, or (for
# visual-angle units only) skips. The answer is recorded as a `Provenance` that
# travels with the dataset, so a reader downstream can tell a measured screen
# from an assumed one.
#
# The gate is deliberately hard: **Add dataset** stays disabled until all three
# are answered. Nobody can be stranded by it — *Estimate from my data* always
# exists for the screen group and always succeeds — but nobody gets a silent
# default either.
# -----------------------------------------------------------------------------

_SETUP_MODE_KEYS = {g: f"wizard_setup_{g}_mode" for g in SETUP_GROUPS}

_SCREEN_KNOW = "I know the resolution"
_SCREEN_ESTIMATE = "Estimate from my data"
_SCREEN_DEFAULT = "Use a common default (2560×1440)"

_GEOM_KNOW = "I know them"
_GEOM_DEFAULT = "Use typical lab values (597 mm / 800 mm)"
_GEOM_SKIP = "Skip — I don't need visual-angle units"

_TEXT_BOXES = "Scale to the word boxes"
_TEXT_FONT = "I know the stimulus font"
_TEXT_DEFAULT = "Use a default (16 px)"

_SETUP_PROVENANCE = {
    _SCREEN_KNOW: Provenance.MEASURED,
    _SCREEN_ESTIMATE: Provenance.ESTIMATED,
    _SCREEN_DEFAULT: Provenance.ASSUMED,
    _GEOM_KNOW: Provenance.MEASURED,
    _GEOM_DEFAULT: Provenance.ASSUMED,
    _GEOM_SKIP: Provenance.SKIPPED,
    _TEXT_BOXES: Provenance.MEASURED,
    _TEXT_FONT: Provenance.MEASURED,
    _TEXT_DEFAULT: Provenance.ASSUMED,
}


def _recalled(field: str, fallback):
    """A value remembered from the previous dataset set up this session.

    Decision (d): answers are recalled across datasets as *pre-filled values with
    the radio reset* — fast for a second export from the same lab, but the user
    still has to assert that the setup applies to this dataset too.
    """
    return (st.session_state.get("_wizard_setup_recall") or {}).get(field, fallback)


def _remember_setup(values: dict) -> None:
    """Stash this dataset's answers as pre-fill for the next one (values only)."""
    recall = dict(st.session_state.get("_wizard_setup_recall") or {})
    recall.update(values)
    st.session_state["_wizard_setup_recall"] = recall


def _setup_mode(host, group: str, options: list, help_text: str):
    """One group's ``st.radio(index=None)`` — nothing preselected, ever.

    Returns the chosen label or ``None``. The mode keys are wizard-local UI state
    and deliberately **not** wire format (same reasoning as ``share_identity_mode``
    in ``url_state.py``): what travels is the resolved value plus its provenance,
    not which radio button produced it.
    """
    return host.radio(
        SETUP_GROUP_LABELS[group],
        options,
        index=None,
        key=_SETUP_MODE_KEYS[group],
        help=help_text,
    )


def _wizard_setup_step(host, words_raw, fix_raw, has_boxes: bool) -> SetupSnapshot:
    """Render the three Recording-setup groups and resolve them to a snapshot.

    Writes the resolved values into the existing ``global_*`` wire-format keys
    (unchanged — the *values* were always wire format; only the provenance is
    new). Safe to write here because the wizard owns the page: ``app.main``
    returns before the rail renders, so no widget on a ``global_*`` key exists
    this run.
    """
    host.caption(
        "These describe the screen the data was **recorded** on, not the screen "
        "you are looking at now. Pick how you know each one — there is no default, "
        "because a wrong guess here silently rescales every figure."
    )

    # --- Screen -------------------------------------------------------------
    screen_mode = _setup_mode(
        host,
        "screen",
        [_SCREEN_KNOW, _SCREEN_ESTIMATE, _SCREEN_DEFAULT],
        "The presentation monitor's resolution in pixels. Everything is drawn in "
        "these coordinates.",
    )
    est_w, est_h = compute_canvas_size(words_raw, fix_raw)
    canvas_w, canvas_h = (
        _recalled("canvas_width", 2560),
        _recalled("canvas_height", 1440),
    )
    if screen_mode == _SCREEN_KNOW:
        cols = host.columns(2)
        canvas_w = cols[0].number_input(
            "Width (px)", 100, 10000, int(canvas_w), key="wizard_setup_screen_w"
        )
        canvas_h = cols[1].number_input(
            "Height (px)", 100, 10000, int(canvas_h), key="wizard_setup_screen_h"
        )
    elif screen_mode == _SCREEN_ESTIMATE:
        canvas_w, canvas_h = est_w, est_h
        host.info(
            f"Estimated **{est_w} × {est_h} px** from the extent of your word "
            "boxes and fixations. This is a **lower bound** — text rarely fills "
            "the whole screen, so the real monitor was probably larger."
        )
    elif screen_mode == _SCREEN_DEFAULT:
        canvas_w, canvas_h = 2560, 1440
        host.caption("Recorded as **assumed** — a common 1440p monitor.")

    # --- Physical size & viewing distance -----------------------------------
    geom_mode = _setup_mode(
        host,
        "geometry",
        [_GEOM_KNOW, _GEOM_DEFAULT, _GEOM_SKIP],
        "Needed only to express distances in degrees of visual angle. Skipping is "
        "a real answer — the app then hides the numbers it cannot honestly derive.",
    )
    mon_mm = float(_recalled("monitor_width_mm", 597.0))
    dist_mm = float(_recalled("viewing_distance_mm", 800.0))
    if geom_mode == _GEOM_KNOW:
        cols = host.columns(2)
        mon_mm = cols[0].number_input(
            "Monitor width (mm)", 50.0, 2000.0, mon_mm, key="wizard_setup_monitor_mm"
        )
        dist_mm = cols[1].number_input(
            "Viewing distance (mm)",
            50.0,
            5000.0,
            dist_mm,
            key="wizard_setup_distance_mm",
        )
        if canvas_w and mon_mm > 0 and dist_mm > 0:
            host.caption(
                f"→ **{pixels_per_degree(dist_mm, canvas_w, mon_mm):.1f} px** per "
                "degree of visual angle."
            )
    elif geom_mode == _GEOM_DEFAULT:
        mon_mm, dist_mm = 597.0, 800.0
        host.caption("Recorded as **assumed** — typical lab values.")
    elif geom_mode == _GEOM_SKIP:
        host.caption(
            "Visual-angle units stay **hidden** for this dataset rather than being "
            "computed from a default."
        )

    # --- Reading text size ---------------------------------------------------
    text_options = [_TEXT_FONT, _TEXT_DEFAULT]
    if has_boxes:
        # Only offered when there are boxes to scale to — otherwise it is an
        # option that silently does nothing.
        text_options.insert(0, _TEXT_BOXES)
    text_mode = _setup_mode(
        host,
        "text",
        text_options,
        "How big the reading text was drawn. Word labels are rendered at this size "
        "so the figure matches what the participant saw.",
    )
    scale_to_boxes = True
    base_font = int(_recalled("base_font_size", 16))
    font_family = str(_recalled("font_family", FONT_FAMILY))
    if text_mode == _TEXT_BOXES:
        scale_to_boxes = True
        host.caption("Label size is derived from each word box — the usual choice.")
    elif text_mode == _TEXT_FONT:
        scale_to_boxes = False
        cols = host.columns(2)
        font_pt = cols[0].number_input(
            "Stimulus font (pt)",
            4.0,
            96.0,
            float(_recalled("stimulus_font_pt", 12.0)),
            key="wizard_setup_font_pt",
        )
        font_family = cols[1].text_input(
            "Font family", value=font_family, key="wizard_setup_font_family"
        )
        # pt→px needs a DPI, which needs the physical width. Under a skipped
        # geometry group there is no honest DPI, so the conversion is withheld
        # and the point size falls back to being read as pixels.
        if geom_mode == _GEOM_SKIP:
            host.warning(
                "Converting points to pixels needs the monitor's physical width, "
                "which was skipped above. The size is being read as **pixels**; "
                "answer *Physical size & viewing distance* for a true pt → px "
                "conversion."
            )
            base_font = int(min(max(round(font_pt), 6), 72))
        else:
            dpi = float(canvas_w) / (float(mon_mm) / 25.4) if mon_mm > 0 else 96.0
            base_font = int(min(max(round(font_pt_to_px(font_pt, dpi)), 6), 72))
            host.caption(f"→ **{base_font} px** at {dpi:.0f} DPI.")
    elif text_mode == _TEXT_DEFAULT:
        scale_to_boxes = False
        base_font = 16
        host.caption("Recorded as **assumed** — a 16 px reading font.")

    snapshot = SetupSnapshot(
        canvas_width=int(canvas_w),
        canvas_height=int(canvas_h),
        monitor_width_mm=float(mon_mm),
        viewing_distance_mm=float(dist_mm),
        base_font_size=int(base_font),
        font_family=font_family,
        line_spacing=float(st.session_state.get("global_line_spacing", 3.0)),
        scale_text_to_boxes=bool(scale_to_boxes),
        screen_provenance=_SETUP_PROVENANCE.get(screen_mode),
        geometry_provenance=_SETUP_PROVENANCE.get(geom_mode),
        text_provenance=_SETUP_PROVENANCE.get(text_mode),
    )

    # Publish the snapshot for the save/restore + export writers. A partial one
    # resolves to None, so `current_setup_section` writes nothing rather than an
    # all-defaults section that would read as a real answer.
    st.session_state["_wizard_setup_snapshot"] = (
        snapshot.to_dict() if snapshot.is_answered() else None
    )

    # Publish each group's values as soon as *that* group is answered, into the
    # wire-format `global_*` keys the rest of the app reads. The hard gate is on
    # **Add dataset**, not on a setting taking effect — a user who has just told
    # us the resolution should see the canvas change now, not after answering two
    # unrelated questions. Only the values were ever wire format; the provenance
    # beside them is what is new.
    recall: dict = {}
    if snapshot.screen_provenance is not None:
        st.session_state["global_canvas_width"] = snapshot.canvas_width
        st.session_state["global_canvas_height"] = snapshot.canvas_height
        recall["canvas_width"] = snapshot.canvas_width
        recall["canvas_height"] = snapshot.canvas_height
    if snapshot.geometry_provenance not in (None, Provenance.SKIPPED):
        st.session_state["global_monitor_width_mm"] = snapshot.monitor_width_mm
        st.session_state["global_viewing_distance_mm"] = snapshot.viewing_distance_mm
        recall["monitor_width_mm"] = snapshot.monitor_width_mm
        recall["viewing_distance_mm"] = snapshot.viewing_distance_mm
    if snapshot.text_provenance is not None:
        st.session_state["global_base_font_size"] = snapshot.base_font_size
        st.session_state["global_font_family"] = snapshot.font_family
        st.session_state["global_scale_text_to_boxes"] = snapshot.scale_text_to_boxes
        recall["base_font_size"] = snapshot.base_font_size
        recall["font_family"] = snapshot.font_family
    if recall:
        _remember_setup(recall)

    unanswered = [g for g, p in snapshot.provenance.items() if p is None]
    if unanswered:
        host.warning(
            "Still to answer: "
            + ", ".join(f"**{SETUP_GROUP_LABELS[g]}**" for g in unanswered)
            + ". *Add dataset* stays disabled until each says how you know it."
        )
    return snapshot


def _restored_setup_snapshot() -> SetupSnapshot | None:
    """The ``experimental_setup`` section of a restored setup JSON, if any.

    Decision (a): a restored setup file **does** pre-answer step 4 — it recorded
    a real choice once, and re-asking would be pedantry rather than rigour.

    But only for what it actually recorded. A file that carries a *screen*
    provenance without a canvas cannot pre-answer the screen: `from_dict` would
    fill 2560x1440 from the class default, and a `measured` badge on top of it
    would be the exact silent inheritance this whole step exists to prevent. In
    that case the screen group is reset to unanswered and the user is asked.
    """
    payload = st.session_state.get("_wizard_restored_setup")
    if not payload:
        return None
    return SetupSnapshot.from_dict(payload, fallback=SetupSnapshot())


def _restored_setup_answerable_groups() -> set:
    """Which groups a restored file may pre-answer — those it actually recorded.

    A plot config written by `tabs._build_studio_config` carries the physical
    geometry and typography but keeps the canvas in a sibling `canvas_px`
    section; when that is absent too, the screen size in the snapshot is the
    class default rather than anything the file stated, so the screen group is
    left for the user to answer.
    """
    payload = st.session_state.get("_wizard_restored_setup") or {}
    groups = set(SETUP_GROUPS)
    if payload.get("canvas_width") is None or payload.get("canvas_height") is None:
        groups.discard("screen")
    return groups


def _apply_restored_setup(snapshot: SetupSnapshot) -> None:
    """Pre-answer the Recording-setup radios from a restored file (once)."""
    if st.session_state.get("_wizard_setup_restored_applied"):
        return
    st.session_state["_wizard_setup_restored_applied"] = True
    answerable = _restored_setup_answerable_groups()
    by_prov = {
        "screen": {
            Provenance.MEASURED: _SCREEN_KNOW,
            Provenance.ESTIMATED: _SCREEN_ESTIMATE,
            Provenance.ASSUMED: _SCREEN_DEFAULT,
        },
        "geometry": {
            Provenance.MEASURED: _GEOM_KNOW,
            Provenance.ASSUMED: _GEOM_DEFAULT,
            Provenance.SKIPPED: _GEOM_SKIP,
        },
        "text": {
            Provenance.MEASURED: _TEXT_FONT,
            Provenance.ASSUMED: _TEXT_DEFAULT,
        },
    }
    for group, provenance in snapshot.provenance.items():
        if group not in answerable:
            continue
        label = by_prov.get(group, {}).get(provenance)
        if label is not None:
            st.session_state[_SETUP_MODE_KEYS[group]] = label
    remembered = {
        "monitor_width_mm": snapshot.monitor_width_mm,
        "viewing_distance_mm": snapshot.viewing_distance_mm,
        "base_font_size": snapshot.base_font_size,
        "font_family": snapshot.font_family,
    }
    # Only remember a canvas the file actually carried; otherwise this would
    # write the class default into the live geometry as if it were the user's.
    if "screen" in answerable:
        remembered["canvas_width"] = snapshot.canvas_width
        remembered["canvas_height"] = snapshot.canvas_height
    _remember_setup(remembered)


def _render_multipleye_upload(body, active: bool) -> _UploadResult:
    """MultiplEYE preset for the Add-dataset wizard (the "MultiplEYE" format).

    Skips the generic column-mapping steps: the user uploads the corpus's
    scanpath/fixation CSVs (+ optional word-AOI CSVs) and the recipe
    (``datasets.multipleye_frames_from_uploads``) parses participant / session /
    trial / stimulus from the file names, makes each *stimulus* a trial with its
    pages (and, when the question AOI + answer-layout version files are uploaded
    too, its comprehension-question screens) as ordered screens inside it,
    aggregates character AOIs into word boxes, and case-matches the (lowercase)
    AOI file names to the (CamelCase) stimuli. Produces the same normalized frames
    + ``_wizard_finalize_payload`` as a finished generic upload, so finalize /
    reload behave identically."""
    from scanpath_studio.datasets import (
        MULTIPLEYE_FIX_SCHEMA,
        MULTIPLEYE_MONITOR,
        multipleye_frames_from_uploads,
        multipleye_word_schema,
    )

    if active:
        body.caption(
            "Upload the MultiplEYE **scanpath** (or fixation) CSVs and, for word "
            "boxes, the **AOI** CSVs — identity is read from the file names, each "
            "stimulus becomes a trial whose pages are screens you can step "
            "through, and character AOIs are aggregated into word boxes "
            "automatically."
        )
        # Seed the MultiplEYE presentation monitor (true-to-scale default).
        st.session_state.setdefault("global_canvas_width", MULTIPLEYE_MONITOR[0])
        st.session_state.setdefault("global_canvas_height", MULTIPLEYE_MONITOR[1])
        app.render_sidebar_canvas_controls(
            empty_words_frame(),
            empty_fixations_frame(),
            data_choice=None,
            slot=body,
            expanded=False,
            title="Monitor, font & text scaling",
        )

    fix_df = app._read_uploaded_frame(
        uploader_label="Scanpath / fixation CSVs",
        upload_help="The per-trial *_scanpath.csv (preferred — they carry the word "
        "index) or *_fixation.csv files. Drop in as many as you like.",
        state_prefix="mpe_fix",
        multi=True,
        container=body,
    )
    aoi_df = app._read_uploaded_frame(
        uploader_label="Word AOI CSVs (optional)",
        upload_help="The per-stimulus *_aoi.csv files (character interest areas). "
        "Optional — without them you get fixations and no word boxes. To get the "
        "comprehension-question screens too, add the *_aoi_questions.csv files "
        "AND stimulus_order_versions_*.csv here (the version table says which "
        "answer layout each reader saw; without it the question screens are "
        "skipped), and upload the *_fixation.csv files — the scanpath export "
        "does not contain those screens.",
        state_prefix="mpe_aoi",
        multi=True,
        container=body,
    )
    questions_df = app._read_uploaded_frame(
        uploader_label="Comprehension questions (optional)",
        upload_help="The multipleye_comprehension_questions_*.xlsx workbook — "
        "adds the questions to the Stimulus & questions panel.",
        state_prefix="mpe_questions",
        multi=False,
        container=body,
    )
    participant_df = app._read_uploaded_frame(
        uploader_label="participant_data.csv (optional)",
        upload_help="Reader metadata (age / gender / languages…) → Trial Info chips.",
        state_prefix="mpe_participant",
        multi=False,
        container=body,
    )

    if fix_df.empty:
        if active:
            body.info("⬆️ Upload MultiplEYE scanpath / fixation CSVs to begin.")
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            ["Upload MultiplEYE scanpath / fixation CSVs to begin."],
        )

    words_raw, fix_raw = multipleye_frames_from_uploads(
        fix_df,
        aoi_df if not aoi_df.empty else None,
        questions_df=questions_df if not questions_df.empty else None,
        participant_meta_df=participant_df if not participant_df.empty else None,
    )
    if fix_raw.empty:
        problem = (
            "No MultiplEYE-shaped file names recognized — expected "
            "`<session>_…_trial_N_<stimulus>_<scanpath|fixation>.csv` (e.g. "
            "`001_ZH_CH_1_ET1_trial_1_Lit_Alchemist_4_scanpath.csv`). "
            "Browser uploads keep the file name but drop the folder, so the "
            "name must carry the session + stimulus."
        )
        if active:
            body.error(problem)
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            words_raw,
            fix_raw,
            [problem],
        )

    has_words = not words_raw.empty
    # Stimulus-level unless the recipe emitted per-reader boxes (question screens).
    word_schema = multipleye_word_schema(words_raw) if has_words else None
    fix_schema = dict(
        MULTIPLEYE_FIX_SCHEMA,
        word_id="word_idx" if "word_idx" in fix_raw.columns else None,
    )
    # Carry MultiplEYE's trial-level facets + side-data through normalization
    # (the upload path passes a keep-set, so registered meta fields must be named
    # here to survive — the directory path uses keep=None and keeps them all).
    keep_fix = compute_keep_columns(
        fix_schema,
        keep_columns={
            "genre",
            "session",
            "participant",
            "is_practice",
            "trial_num",
            "comprehension_questions",
            "pp_age",
            "pp_gender",
            "pp_native_language",
            "pp_years_education",
            "pp_education_level",
            # DATA-24: a trial mixes reading pages (from the scanpath export) and
            # question screens (from the fixation one), so the marker that tells
            # them apart must survive the keep-set too.
            "screen_kind",
        },
    )
    keep_words = (
        compute_keep_columns(
            word_schema,
            keep_columns={
                "genre",
                "comprehension_questions",
                "screen_kind",
                "aoi_block",
            },
        )
        if has_words
        else None
    )
    # app._normalize_pair sets _composite_trial_columns from the (single-column)
    # trial mapping → None, exactly what the reload branch expects.
    try:
        words_norm, fixations_norm = app._normalize_pair(
            words_raw if has_words else empty_words_frame(),
            word_schema,
            fix_raw,
            fix_schema,
            keep_words=keep_words,
            keep_fix=keep_fix,
        )
    except Exception as exc:
        # A rejected upload is a blocked wizard step, not a dead app — the
        # uploaders above have to stay on screen for the user to fix the set of
        # files they dropped in. See app.mapping_failure_problem.
        problem = app.mapping_failure_problem(exc)
        if active:
            body.error(problem)
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            words_raw,
            fix_raw,
            [problem],
        )
    filter_fields = ["genre", "session", "is_practice"]
    st.session_state["wizard_filter_fields"] = filter_fields
    schemas = {"words": word_schema, "fixations": fix_schema, "raw_gaze": None}
    app._stash_active_mapping("words", word_schema)
    app._stash_active_mapping("fixations", fix_schema)

    if active:
        boxes_msg = (
            f" · **{len(words_norm):,}** word boxes"
            if has_words
            else " · no AOI boxes (upload *_aoi.csv for word boxes)"
        )
        body.success(
            f"✓ **{fixations_norm['participant_id'].nunique()}** readers · "
            f"**{fixations_norm['trial_id'].nunique()}** page-trials" + boxes_msg
        )
        st.session_state["_wizard_finalize_payload"] = {
            "words": words_norm,
            "fixations": fixations_norm,
            "raw_gaze": pd.DataFrame(),
            "filter_fields": filter_fields,
            "composite_trial_columns": [],
            "schemas": schemas,
            "dropped_columns": {
                "words": dropped_columns(words_raw, keep=keep_words)
                if has_words
                else [],
                "fixations": dropped_columns(fix_raw, keep=keep_fix),
                "raw_gaze": [],
            },
            # CMP-8 §1: MultiplEYE needs no Recording-setup step — it *declares*
            # its geometry. The corpus records a real 1920x1080 presentation
            # monitor and stamps the stimulus font size + family from its own
            # config onto the words, so both are `measured`. Only the physical
            # size / viewing distance are unrecorded, and those stay honestly
            # `assumed` rather than being invented as measured.
            "setup": app.capture_setup_snapshot(
                {
                    "screen": Provenance.MEASURED,
                    "geometry": Provenance.ASSUMED,
                    "text": Provenance.MEASURED,
                }
            ).to_dict(),
        }
        body.button(
            "✅ Add dataset",
            type="primary",
            key="wizard_finalize",
            on_click=_finalize_wizard_dataset,
        )

    return _UploadResult(
        words_norm, fixations_norm, pd.DataFrame(), words_raw, fix_raw, []
    )


def _wizard_statuses() -> dict[str, wizard_shell.StepStatus]:
    """Each step's badge, derived from session state alone.

    Deliberately cheap and frame-free: it runs at the *top* of the wizard, before
    any step body renders, because the accordion seeding and every step's badge
    need it up front. The one thing not in session state is this run's validation
    result, so `_wizard_problems_last` carries the previous run's — the same
    one-run-behind contract the old progress bar had. Any widget interaction
    reruns the script, so a badge is never stale for longer than that, and the
    **gate** on *Add dataset* is computed from live values at the end, never from
    this.
    """
    from scanpath_studio import metadata as metadata_mod

    S = wizard_shell.StepStatus
    ss = st.session_state
    uploaded_core = bool(ss.get("col_map_fix_upload") or ss.get("col_map_words_upload"))
    uploaded_any = uploaded_core or bool(ss.get("col_map_raw_gaze_upload"))
    # Default to "pending" so the mapping step doesn't claim to be done before a
    # single validation pass has run.
    problems = ss.get("_wizard_problems_last", ["pending"])
    trial_mapped = bool(
        ss.get("col_map_trial_unified")
        or ss.get("col_map_fix_trial")
        or ss.get("col_map_words_trial")
    )
    setup_answered = all(ss.get(_SETUP_MODE_KEYS[g]) for g in SETUP_GROUPS)
    fields_touched = bool(ss.get("wizard_keep_extra") or ss.get("wizard_filter_by"))

    def required(done: bool) -> wizard_shell.StepStatus:
        if done:
            return S.DONE
        # ACTION ("blocked on something specific") only once there is data to act
        # on; before that the step is simply not started.
        return S.ACTION if uploaded_any else S.TODO

    statuses = {
        "data": S.DONE if uploaded_any else S.TODO,
        "identity": required(trial_mapped),
        "geometry": required(uploaded_any and not problems),
        "setup": required(setup_answered),
        # DATA-20: optional until a table is actually attached. Reads the parsed
        # frame, not the uploader widget — the frame is what survives a rerun.
        "readers": (
            S.DONE if ss.get(metadata_mod.RAW_SESSION_KEY) is not None else S.OPTIONAL
        ),
        "fields": S.DONE if fields_touched else S.OPTIONAL,
    }
    statuses["review"] = (
        S.DONE
        if all(statuses[k] is S.DONE for k in ("data", "identity", "geometry", "setup"))
        else S.TODO
    )
    return statuses


def _render_autodetect_card(host, word_schema, fix_schema, has_words, has_fix) -> None:
    """After the upload: what was detected, what is still missing, by name.

    A *report*, deliberately not a shortcut. Detection matches column names, so a
    complete-looking result can still be wrong in ways only the mapping steps
    reveal — and a wrong mapping renders a perfectly plausible figure of the
    wrong thing. The card tells the user what to confirm; steps 2-3 are where
    they confirm it.
    """
    checks: list[tuple[str, str | None]] = []
    if has_fix:
        checks += [
            ("Trial id", _mapping_label(fix_schema.get("trial"))),
            ("Fixation duration", _mapping_label(fix_schema.get("duration"))),
            (
                "Fixation position",
                _mapping_label(fix_schema.get("x"))
                or _mapping_label(fix_schema.get("word_id")),
            ),
        ]
    if has_words:
        checks += [
            ("Word id", _mapping_label(word_schema.get("word_id"))),
            (
                "Word box",
                _mapping_label(word_schema.get("left"))
                or _mapping_label(word_schema.get("x")),
            ),
            ("Word text", _mapping_label(word_schema.get("text"))),
        ]
    if not checks:
        return
    found = [f"✓ **{name}** — `{col}`" for name, col in checks if col]
    missing = [f"⚠️ **{name}** — not detected" for name, col in checks if not col]
    host.markdown("\n\n".join(found + missing))
    host.caption(
        "Detected by column name — confirm each one in the next two steps."
        if not missing
        else "Map whatever is missing in the next two steps."
    )


def _mapping_label(mapping) -> str | None:
    """A human-readable column name for a mapping value (str | list | None)."""
    if not mapping or mapping == NONE_OPTION:
        return None
    if isinstance(mapping, (list, tuple)):
        return " + ".join(str(c) for c in mapping) or None
    return str(mapping)


def _render_review_table(host, snapshot: SetupSnapshot, readouts: list) -> None:
    """Step 6's review table: every decision, its value, and its provenance.

    The provenance column is the reason this table exists — it is where an
    assumed monitor stops being invisible.
    """
    rows = [
        {"Decision": label, "Value": value, "How we know": how}
        for label, value, how in readouts
    ]
    for group in SETUP_GROUPS:
        provenance = snapshot.provenance[group]
        rows.append(
            {
                "Decision": SETUP_GROUP_LABELS[group],
                "Value": _setup_group_value(snapshot, group),
                "How we know": str(provenance) if provenance else "not answered",
            }
        )
    host.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    if snapshot.geometry_provenance is Provenance.SKIPPED:
        host.caption(
            "Visual-angle units (px per degree) are hidden for this dataset — the "
            "physical size was skipped, so there is nothing honest to derive them "
            "from."
        )
    elif snapshot.px_per_degree is not None:
        host.caption(
            f"≈ **{snapshot.px_per_degree:.1f} px** per degree of visual angle."
        )


def _setup_group_value(snapshot: SetupSnapshot, group: str) -> str:
    """The value column for one setup group in the review table."""
    if group == "screen":
        return f"{snapshot.canvas_width} × {snapshot.canvas_height} px"
    if group == "geometry":
        if snapshot.geometry_provenance is Provenance.SKIPPED:
            return "—"
        return (
            f"{snapshot.monitor_width_mm:.0f} mm wide, "
            f"{snapshot.viewing_distance_mm:.0f} mm away"
        )
    if snapshot.scale_text_to_boxes:
        return "scaled to word boxes"
    return f"{snapshot.base_font_size} px · {snapshot.font_family}"


def _render_data_setup(active: bool) -> _UploadResult:
    """The Add-dataset wizard: seven steps in an accordion (DATA-22).

    Replaces a single 620-line function that rendered 16 expanders across five
    numbered subsections under a three-step progress bar matching neither. The
    steps are now the unit of everything — the badge, the progress chip, the
    guide's target, and the "go here to fix it" button on a blocker.

    ``active`` is the guided wizard; ``active=False`` is the compact collapsed
    *Data & mapping* review panel, where `wizard_shell.step_panel` degrades each
    step to a plain heading (that panel is itself an expander, and Streamlit
    forbids nesting one inside another).

    **Every step body renders on every run, open or closed.** Streamlit drops a
    widget's key at the end of any run in which the widget did not render, and
    `controls.column_mapping_ui` builds its `col_map_*` widgets without
    `persist_state` — so gating a body on its expander being open would silently
    discard that step's mapping. Collapsed-but-rendered is the contract.
    """
    statuses = _wizard_statuses()
    if active:
        st.header("📂 Set up your dataset")
        st.caption(
            "Work down the seven steps in order, or jump straight to one with the "
            "chips below. Your answers are kept as you move around."
        )
        st.caption(
            "First time? [Bring your own data ↗]"
            "(https://lacclab.github.io/scanpath-studio/bring-your-own-data/) "
            "covers the minimum your export needs, worked EyeLink and plain-CSV "
            "examples, and what each failure symptom means."
        )
        # Step-by-step guide: a bottom-right card that auto-opens once per session
        # and is replayable via the button. Arm it (auto/first-visit) then render
        # the card early so it streams before the heavy upload/normalize work.
        maybe_show_wizard_guide()
        render_spotlight_wizard_guide()
        render_wizard_guide_button(st)
        # Must run before any expander instantiates — it writes the `wiz_open_*`
        # widget keys.
        wizard_shell.seed_open_step(statuses)
        wizard_shell.render_progress(st.container(), statuses)
        body = st.container()
    else:
        panel = st.expander("📋 Data & mapping", expanded=False)
        body = panel
        if panel.button(
            "⚙️ Change dataset / mapping",
            key="wizard_reconfigure",
            help="Re-open the setup wizard.",
        ):
            st.session_state["setup_complete"] = False
            st.rerun()

    def step_of(step_id: str):
        step = wizard_shell.STEPS_BY_ID[step_id]
        return step, wizard_shell.step_panel(
            body,
            step,
            statuses.get(step_id, wizard_shell.StepStatus.TODO),
            active=active,
        )

    # === 1 · Your data =======================================================
    _data_step, s1 = step_of("data")
    if active:
        s1.segmented_control(
            "Dataset format",
            ["Generic", "MultiplEYE"],
            key="wizard_dataset_format",
            default="Generic",
            help="**Generic**: map your own columns. **MultiplEYE**: upload the "
            "corpus's scanpath/fixation + AOI CSVs and the app parses identity "
            "from the file names (no column mapping needed).",
        )

    # A dedicated dataset format runs its own tailored flow and bypasses the
    # generic mapping steps. It renders into `body`, NOT into a step panel:
    # `_render_multipleye_upload` opens its own canvas expander, and
    # expander-in-expander is forbidden. Read from state so the collapsed review
    # panel branches the same way.
    if st.session_state.get("wizard_dataset_format", "Generic") == "MultiplEYE":
        return _render_multipleye_upload(body, active)

    # Privacy caption + run-locally tip keep their always-created container:
    # a *conditional* child here shifts the element tree mid-parse and Streamlit
    # leaves a greyed-out ghost of the whole upload group on screen (BUG-2).
    intro = s1.container()
    intro.caption(
        "🔒 Your file is parsed on the machine running this app and never sent "
        "elsewhere. Local/desktop installs keep a private recovery cache after "
        "you add the dataset; the hosted demo remains memory-only. "
        "[Where your data goes ↗](https://lacclab.github.io/scanpath-studio/privacy/)"
    )
    core_uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
    )
    already_uploaded = core_uploaded or bool(
        st.session_state.get("col_map_raw_gaze_upload")
    )
    if active and not already_uploaded:
        intro.info("⬆️ Upload a **Fixations** and/or **Words/IA** table to begin.")
        app_url = str(getattr(st.context, "url", "") or "")
        if not is_loopback_url(app_url):
            intro.markdown(
                "💡 **Working with a large dataset?** It's faster — and keeps your "
                "data on your own machine — to run Scanpath Studio locally:\n\n"
                "```bash\npip install scanpath-studio\nscanpath-studio\n```"
            )

    def upload_box(host, *, label, help_text, prefix, multi, noun):
        frame = app._read_uploaded_frame(
            uploader_label=label,
            upload_help=help_text,
            state_prefix=prefix,
            multi=multi,
            container=host,
        )
        if not frame.empty:
            host.success(
                f"✓ **{len(frame):,}** {noun} · **{len(frame.columns)}** columns "
                "— make sure this is the number you expect to see."
            )
            if active:
                host.caption("Preview — first rows:")
                host.dataframe(frame.head(), width="stretch", hide_index=True)
        return frame

    raw_fix = upload_box(
        s1,
        label="Fixations table(s)",
        help_text="One or more files (e.g. one per participant); concatenated.",
        prefix="col_map_fix",
        multi=True,
        noun="fixations",
    )
    raw_words = upload_box(
        s1,
        label="Words / IA table(s)",
        help_text="One or more files (e.g. one per text); concatenated.",
        prefix="col_map_words",
        multi=True,
        noun="words",
    )
    # Sub-blocks are popovers, not expanders: Streamlit forbids
    # expander-in-expander but allows popover-in-expander — the same constraint
    # that shapes `controls.py`.
    raw_gaze = upload_box(
        s1.popover("➕ Raw gaze overlay (optional)"),
        label="Raw gaze table",
        help_text="Optional millisecond-level gaze overlay (one file).",
        prefix="col_map_raw_gaze",
        multi=False,
        noun="gaze points",
    )
    restore_box = s1.popover("↩️ Restore a saved setup (optional)")
    _wizard_restore_config(restore_box)
    _render_restored_config_caption(restore_box)

    if raw_words.empty and raw_fix.empty and raw_gaze.empty:
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            raw_words,
            raw_fix,
            [],
        )

    prop_w = (
        _c_propose_word_schema(raw_words, frame_fingerprint(raw_words))
        if not raw_words.empty
        else {}
    )
    prop_f = (
        _c_propose_fix_schema(raw_fix, frame_fingerprint(raw_fix))
        if not raw_fix.empty
        else {}
    )
    prop_g = (
        _c_propose_raw_gaze_schema(raw_gaze, frame_fingerprint(raw_gaze))
        if not raw_gaze.empty
        else {}
    )
    word_schema: dict = {}
    fix_schema: dict = {}
    has_words, has_fix = not raw_words.empty, not raw_fix.empty

    # === 2 · Trials & readers ================================================
    _identity_step, s2 = step_of("identity")
    # Filename derivation must run *before* the identifier pickers so the
    # derived columns are mappable below.
    if (has_words or has_fix) and any(
        SOURCE_FILE_COLUMN in fr.columns for fr in (raw_fix, raw_words) if not fr.empty
    ):
        raw_words, raw_fix, raw_gaze = _wizard_filename_derive(
            s2.popover("⚙️ Advanced — derive ids from the filename"),
            raw_words,
            raw_fix,
            raw_gaze,
        )

    if has_words or has_fix:
        _wizard_trial_step(
            s2,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )
        _wizard_participant_text_step(
            "participant",
            "Participant ID",
            "readers",
            "Pick the reader column — or several to compose an id. Leave empty "
            "for a single anonymous reader.",
            s2,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )
        _wizard_participant_text_step(
            "text_id",
            "Text ID",
            "texts",
            "Pick the text column — or several to compose an id. Leave empty to "
            "fall back to the trial id.",
            s2,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )
        # DATA-21 multipart screens: beside, not inside, the logical trial id.
        screens = s2.popover("⚙️ Advanced — multipart screens")
        screens.caption(
            "Map these only when one logical trial contains ordered screens. "
            "Screen ID must be mapped in both reports; screen order is 1-based."
        )
        if has_words:
            screens.markdown("**Words / Interest Areas**")
            word_schema.update(
                _map_section(
                    raw_words,
                    WORD_FIELD_SPECS,
                    prop_w,
                    "col_map_words",
                    screens,
                    ["screen_id", "screen_index", "canvas_width", "canvas_height"],
                )
            )
        if has_fix:
            screens.markdown("**Fixations**")
            fix_schema.update(
                _map_section(
                    raw_fix,
                    FIX_FIELD_SPECS,
                    prop_f,
                    "col_map_fix",
                    screens,
                    [
                        "screen_id",
                        "screen_index",
                        "screen_timestamp",
                        "screen_fixation_id",
                        "canvas_width",
                        "canvas_height",
                    ],
                )
            )

    # === 3 · Fixations & text ================================================
    _geometry_step, s3 = step_of("geometry")
    if has_fix:
        s3.markdown("**Fixations** — where the eyes landed")
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                s3,
                ["x", "y", "duration", "fixation_id"],
            )
        )
        s3.caption(
            "Leave X/Y blank for AOI-only data and map the Word/IA ID under "
            "*Advanced* instead."
        )
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                s3.popover("⚙️ Advanced — more fixation mappings"),
                ["word_id", "timestamp"],
            )
        )
        # Validation problems render against their own sub-block rather than as
        # one lumped warning above the Add button.
        for problem in validate_fix_schema(fix_schema):
            s3.warning(f"Fixations — {problem}")

    if has_words:
        s3.markdown("**Words / Interest Areas** — where the words are")
        word_schema.update(
            _map_section(
                raw_words,
                WORD_FIELD_SPECS,
                prop_w,
                "col_map_words",
                s3,
                ["word_id", "text", "box"],
            )
        )
        words_advanced = s3.popover("⚙️ Advanced — more text mappings")
        word_schema.update(
            _map_section(
                raw_words,
                WORD_FIELD_SPECS,
                prop_w,
                "col_map_words",
                words_advanced,
                ["line"],
            )
        )
        words_advanced.caption(
            "Line index enables colouring fixations/words by reading line."
        )
        words_advanced.toggle(
            "Aggregate character AOIs into word boxes",
            key="wizard_aggregate_char_boxes",
            help="For interest-area tables with one row per *character* (e.g. CJK "
            "corpora): collapse the characters of each word (grouped by the Trial "
            "+ Word/IA id above) into one bounding box.",
        )
        for problem in validate_word_schema(word_schema):
            s3.warning(f"Words/IA — {problem}")

    if not raw_gaze.empty:
        rg_required = not has_words and not has_fix
        rg_host = (
            s3 if rg_required else s3.popover("⚙️ Advanced — raw gaze overlay mapping")
        )
        rg_host.markdown("**Raw gaze overlay**")
        raw_gaze_schema = _map_section(
            raw_gaze,
            RAW_GAZE_FIELD_SPECS,
            prop_g,
            "col_map_raw_gaze",
            rg_host,
            [
                "participant",
                "trial",
                "screen_id",
                "screen_index",
                "x",
                "y",
                "timestamp",
                "text",
            ],
        )
    else:
        raw_gaze_schema = {}

    words_problems = validate_word_schema(word_schema) if has_words else []
    fix_problems = validate_fix_schema(fix_schema) if has_fix else []
    raw_gaze_problems = (
        validate_raw_gaze_schema(raw_gaze_schema) if not raw_gaze.empty else []
    )
    problems: list = []
    if words_problems:
        problems.append("Words/IA: " + "; ".join(words_problems))
    if fix_problems:
        problems.append("Fixations: " + "; ".join(fix_problems))
    # A raw-gaze-ONLY upload: an incomplete raw-gaze mapping is the only thing
    # blocking a usable dataset — fold it into `problems` so finalize is gated.
    if not has_words and not has_fix and raw_gaze_problems:
        problems.append("Raw gaze: " + "; ".join(raw_gaze_problems))
    st.session_state["_wizard_problems_last"] = list(problems)

    # The auto-detect summary sits in step 1, but it needs the resolved schemas,
    # so it renders into a container reserved there. Streamlit lays containers
    # out in creation order, so it appears where it was reserved.
    # DATA-22 review: the card reports what was detected; it does **not** offer to
    # skip steps 2-3 on the strength of it. Auto-detection matches column *names*,
    # so it is confident and occasionally wrong — a `trial_id` that is really a
    # per-participant counter, an `x` that is the word's centre rather than its
    # left edge. Those produce a plausible figure of the wrong thing, and the only
    # place they are catchable is the mapping steps. Confirming a correct guess
    # costs two clicks; skipping a wrong one costs the whole dataset.
    _render_autodetect_card(s1.container(), word_schema, fix_schema, has_words, has_fix)

    # === 4 · Recording setup =================================================
    _setup_step, s4 = step_of("setup")
    restored_setup = _restored_setup_snapshot()
    if restored_setup is not None:
        _apply_restored_setup(restored_setup)
        s4.caption("✓ Pre-answered from the restored setup file — review it below.")
    setup_snapshot = _wizard_setup_step(s4, raw_words, raw_fix, has_boxes=has_words)

    # === 5 · About your readers ==============================================
    # DATA-20: the participant table's main home. Rendered only while the wizard
    # is `active` — the collapsed *Data & mapping* review panel would otherwise
    # build the same widget keys as the 🗂️ Data page's section, which renders
    # once the wizard is finished.
    readers_step, s_readers = step_of("readers")
    if active:
        from scanpath_studio.tabs import render_participant_metadata_section

        s_readers.caption(
            "Optional, and separate from the tables above: one row per **reader**, "
            "not per trial. Attach it here and its columns behave like fields in "
            "your data — filters, chips, trial sorting, corpus grouping, export."
        )
        render_participant_metadata_section(
            _wizard_reader_ids(raw_words, word_schema, raw_fix, fix_schema),
            host=s_readers.container(),
        )
        wizard_shell.continue_button(s_readers, readers_step, label="Continue →")

    # === 6 · Extra fields ====================================================
    _fields_step, s5 = step_of("fields")
    s5.caption(
        "*Filter trials by* becomes a value picker in the Narrow-by panel; "
        "*Additional fields to keep* are the columns you can colour, sort and "
        "analyse by later. Fewer columns is faster."
    )
    keep_tables: list = []
    if has_words:
        keep_tables.append(
            (raw_words, word_schema, WORD_OPTIONAL_FIELDS, "col_map_words")
        )
    if has_fix:
        keep_tables.append((raw_fix, fix_schema, FIX_OPTIONAL_FIELDS, "col_map_fix"))
    keep_by_prefix, filter_fields = _wizard_keep_and_filter(keep_tables, s5, s5)
    st.session_state["wizard_filter_fields"] = list(filter_fields)

    # === 6 · Name & add ======================================================
    _review_step, s6 = step_of("review")
    if active:
        st.session_state.setdefault("wizard_dataset_name", _default_dataset_name())
        s6.text_input(
            "Dataset name",
            key="wizard_dataset_name",
            help="Shown in the Data source list so you can switch back to it.",
        )

    setup_blockers = [
        SETUP_GROUP_LABELS[g] for g, p in setup_snapshot.provenance.items() if p is None
    ]
    blocked = bool(problems) or bool(setup_blockers)

    if active:
        readouts: list = []
        if has_fix:
            readouts.append(("Fixations", f"{len(raw_fix):,} rows", "uploaded"))
        if has_words:
            readouts.append(("Words / IA", f"{len(raw_words):,} rows", "uploaded"))
        trial_label = _mapping_label(
            (fix_schema if has_fix else word_schema).get("trial")
        )
        if trial_label:
            readouts.append(("Trial id", trial_label, "mapped"))
        _render_review_table(s6, setup_snapshot, readouts)

        if blocked:
            s6.markdown("**Still to do**")
            reasons: dict[str, list] = {}
            if problems:
                reasons["geometry"] = list(problems)
            if setup_blockers:
                reasons["setup"] = [
                    f"{name} — say how you know it" for name in setup_blockers
                ]
            for step, why in wizard_shell.blockers(_wizard_statuses(), reasons):
                if step.id not in reasons:
                    continue
                for line in reasons[step.id]:
                    s6.warning(line)
                s6.button(
                    f"Go to {step.number}. {step.title} →",
                    key=f"wiz_goto_{step.id}",
                    on_click=wizard_shell.go_to_step,
                    args=(step.id,),
                )

    if problems:
        if active:
            _render_setup_download(s6)
            s6.button("✅ Add dataset", disabled=True, key="wizard_finalize")
        st.session_state["_composite_trial_columns"] = None
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            raw_words,
            raw_fix,
            problems,
        )

    # Record the mapping so the Data Inspection tab shows it once the wizard is
    # collapsed (active=False) and the tabs render with this upload.
    wizard_schemas = {
        "words": dict(word_schema) if has_words else None,
        "fixations": dict(fix_schema) if has_fix else None,
        "raw_gaze": dict(raw_gaze_schema) if not raw_gaze.empty else None,
    }
    for table, schema in wizard_schemas.items():
        app._stash_active_mapping(table, schema)

    # Char→word aggregation: collapse character-level AOIs to one box per word
    # using the final word mapping, before normalization (which expects one row
    # per word box).
    if has_words and st.session_state.get("wizard_aggregate_char_boxes"):
        raw_words = _c_aggregate_char_boxes(
            raw_words,
            word_schema,
            frame_fingerprint(raw_words),
            _schema_key(word_schema),
        )

    keep_words = (
        compute_keep_columns(
            word_schema, keep_columns=keep_by_prefix.get("col_map_words", set())
        )
        if has_words
        else None
    )
    keep_fix = (
        compute_keep_columns(
            fix_schema, keep_columns=keep_by_prefix.get("col_map_fix", set())
        )
        if has_fix
        else None
    )
    if has_words or has_fix:
        try:
            words_norm, fixations_norm = app._normalize_pair(
                raw_words,
                word_schema if has_words else None,
                raw_fix,
                fix_schema if has_fix else None,
                keep_words=keep_words,
                keep_fix=keep_fix,
            )
        except Exception as exc:
            # The mapping is complete but the pipeline rejects the combination
            # (see app.mapping_failure_problem). Blocked exactly like an
            # incomplete one: the wizard stays up, ✅ Add dataset stays off, and
            # the review step's badge reads from `_wizard_problems_last`.
            problem = app.mapping_failure_problem(exc)
            st.session_state["_wizard_problems_last"] = [problem]
            st.session_state["_composite_trial_columns"] = None
            if active:
                s6.error(problem)
                s6.button("✅ Add dataset", disabled=True, key="wizard_finalize")
            return _UploadResult(
                empty_words_frame(),
                empty_fixations_frame(),
                pd.DataFrame(),
                raw_words,
                raw_fix,
                [problem],
            )
    else:
        # Raw-gaze-only dataset — record composite-trial columns from the raw-gaze
        # mapping so the trial picker still offers one selector per component.
        words_norm, fixations_norm = empty_words_frame(), empty_fixations_frame()
        rg_trial_cols = (
            trial_mapping_columns(raw_gaze_schema["trial"])
            if raw_gaze_schema and raw_gaze_schema.get("trial")
            else []
        )
        st.session_state["_composite_trial_columns"] = (
            rg_trial_cols if len(rg_trial_cols) > 1 else None
        )

    raw_gaze_norm = pd.DataFrame()
    if not raw_gaze.empty:
        if raw_gaze_problems:
            s3.warning("Raw gaze ignored — " + "; ".join(raw_gaze_problems))
        else:
            raw_gaze_norm = normalize_raw_gaze(raw_gaze, raw_gaze_schema)

    if active:
        # Stash the assembled, already-normalized dataset so the finalize callback
        # can store it. The callback (not an inline `if button:` handler) is what
        # makes "Add dataset" reliable: a real st.file_uploader in the wizard can
        # swallow an inline button click (the click reruns, the uploader
        # re-renders, and the handler is never reached), so the dataset would
        # never get stored. on_click runs as part of the click event, before the
        # rerun — exactly like the "➕ Add data" button.
        st.session_state["_wizard_finalize_payload"] = {
            "words": words_norm,
            "fixations": fixations_norm,
            "raw_gaze": raw_gaze_norm,
            "filter_fields": list(st.session_state.get("wizard_filter_fields", [])),
            # Persist the composite trial-id components (session-only state, not in
            # the frames) so switching back restores the cascading picker.
            "composite_trial_columns": list(
                st.session_state.get("_composite_trial_columns") or []
            ),
            # Persist the column mapping so reselecting this stored dataset can
            # repopulate the Data Inspection tab's mapping table.
            "schemas": wizard_schemas,
            # Source columns discarded at normalization — surfaced as a note in
            # the Data Inspection remap editor (they can't be remapped without a
            # re-upload). set(raw.columns) - keep is exactly the dropped set.
            "dropped_columns": {
                "words": dropped_columns(raw_words, keep=keep_words)
                if has_words
                else [],
                "fixations": dropped_columns(raw_fix, keep=keep_fix) if has_fix else [],
                "raw_gaze": dropped_columns(raw_gaze, schema=raw_gaze_schema)
                if not raw_gaze.empty
                else [],
            },
            # CMP-8 §1 / DATA-22 §7: the geometry this dataset was set up with,
            # plus how each group came to be known. A stored upload recorded no
            # geometry at all before this, which is why switching to one left the
            # canvas on the previous source's monitor.
            "setup": setup_snapshot.to_dict(),
        }
        _render_setup_download(s6)
        s6.button(
            "✅ Add dataset",
            type="primary",
            key="wizard_finalize",
            disabled=blocked,
            on_click=_finalize_wizard_dataset,
            help=(
                "Answer the Recording setup step first: " + ", ".join(setup_blockers)
                if setup_blockers
                else "Store this dataset and switch to it."
            ),
        )

    return _UploadResult(
        words_norm, fixations_norm, raw_gaze_norm, raw_words, raw_fix, []
    )


# -----------------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------------
