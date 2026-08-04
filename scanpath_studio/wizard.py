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
from typing import Dict, NamedTuple, Optional, Tuple

import pandas as pd
import streamlit as st

from . import app
from .constants import (
    DEMO_CHOICE,
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
    compute_keep_columns,
    dropped_columns,
    empty_fixations_frame,
    empty_words_frame,
    extract_columns_from_source_file,
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
    ):
        st.session_state.pop(key, None)


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


def _safe_dataset_name(name: Optional[str]) -> str:
    """A non-empty dataset name that collides with neither a built-in source label
    nor an already-stored dataset (suffixed ``(2)``, ``(3)``… rather than silently
    overwriting an existing entry's frames)."""
    name = (name or "").strip() or _default_dataset_name()
    if name in _RESERVED_SOURCE_NAMES:
        name = f"{name} (uploaded)"
    existing = st.session_state.get("_datasets", {})
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
    _reset_wizard_widgets()


def _keep_wizard_step_open(title: str) -> None:
    """Widget callback: keep its mapping expander open across this rerun."""
    st.session_state["_wizard_keep_open"] = title


def _wizard_step_expanded(title: str, done: bool, flow: dict, state) -> bool:
    """Resolve wizard auto-advance while preserving the step being edited.

    A widget callback stamps ``_wizard_keep_open`` before Streamlit reruns. The
    matching completed step consumes that one-shot marker and reopens, so picking
    a second field does not make the expander disappear (DATA-19). Otherwise the
    first unfinished step retains the historical auto-advance behaviour.
    """
    if state.get("_wizard_keep_open") == title:
        state.pop("_wizard_keep_open", None)
        return True
    if done:
        return False
    expanded = not flow["claimed"]
    if expanded:
        flow["claimed"] = True
    return expanded


def _map_section(raw, specs, proposed, prefix, host, keys, *, step_title) -> Dict:
    """Render a subset of a table's mapping fields (the wizard renders the core
    fields in grouped, ordered steps). Returns the partial mapping for ``keys``."""
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
        on_change=_keep_wizard_step_open,
        on_change_args=(step_title,),
    )


def _default_trial_columns(proposed: Dict, present_cols) -> list:
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


def _trial_id_values(raw, schema) -> Optional[set]:
    """Set of distinct trial-id strings for a raw frame + its trial mapping
    (composite mappings are joined, mirroring ``data.trial_id_series``). ``None``
    when the trial isn't mapped or its columns are absent."""
    if raw is None or getattr(raw, "empty", True) or not schema.get("trial"):
        return None
    cols = trial_mapping_columns(schema["trial"])
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return set(trial_id_series(raw, schema["trial"]).unique())


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
    step_title: str,
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
            on_change=_keep_wizard_step_open,
            args=(step_title,),
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
                on_change=_keep_wizard_step_open,
                args=(step_title,),
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
                on_change=_keep_wizard_step_open,
                args=(step_title,),
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
            on_change=_keep_wizard_step_open,
            args=(step_title,),
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
        "Trial identifier",
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


def _distinct_id_count(raw, mapping) -> Optional[int]:
    """Distinct values of a single-column or composite identifier mapping."""
    if raw is None or getattr(raw, "empty", True) or not mapping:
        return None
    cols = trial_mapping_columns(mapping)
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return int(trial_id_series(raw, mapping).nunique())


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
    step_title: str,
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
        step_title,
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


def wide_frame_warning(n_extra_fields: int, n_rows: int) -> Optional[str]:
    """PERF-2 warning for selections large enough to affect rerun latency."""
    if n_extra_fields < 50 and n_extra_fields * max(n_rows, 0) < 5_000_000:
        return None
    return (
        f"Keeping {n_extra_fields} additional fields across up to {n_rows:,} rows "
        "can noticeably slow caching, grouping, and browser transfer. Keep only "
        "the measures and metadata you plan to use; you can revise this mapping later."
    )


def _wizard_keep_and_filter(tables: list, filter_host, keep_host) -> Tuple[dict, list]:
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
        cat_by_prefix[prefix] = categorize_columns(raw, schema, registry)

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
        "(from the 💾 Save & restore panel).",
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
    }


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


def _render_wizard_progress(body) -> None:
    """A native step indicator at the top of the active setup wizard.

    Read-only, driven by the *actual* wizard state (uploads present + whether
    last run's column mapping validated) rather than an independent counter — so
    the bar tracks real progression. ``_wizard_problems_last`` is written near the
    end of ``_render_data_setup`` once this run's validation `problems` are known.
    """
    name_done = bool(st.session_state.get("wizard_dataset_name"))
    uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
        or st.session_state.get("col_map_raw_gaze_upload")
    )
    # No problems last run (and something uploaded) ⇒ the mapping validates.
    # Default to "not yet" until a run has actually computed problems.
    mapped = uploaded and not st.session_state.get("_wizard_problems_last", ["pending"])
    steps = [("Name", name_done), ("Upload", uploaded), ("Map columns", mapped)]
    done_n = sum(1 for _, ok in steps if ok)
    body.progress(done_n / len(steps), text=f"Setup progress — {done_n} / {len(steps)}")
    body.caption(
        " · ".join(f"{'✅' if ok else '⬜'} {lbl}" for lbl, ok in steps)
        + " · 🏁 Add dataset"
    )


def _render_multipleye_upload(body, active: bool) -> _UploadResult:
    """MultiplEYE preset for the Add-dataset wizard (the "MultiplEYE" format).

    Skips the generic column-mapping steps: the user uploads the corpus's
    scanpath/fixation CSVs (+ optional word-AOI CSVs) and the recipe
    (``datasets.multipleye_frames_from_uploads``) parses participant / session /
    trial / stimulus from the file names, makes each stimulus *page* a trial,
    aggregates character AOIs into word boxes, and case-matches the (lowercase)
    AOI file names to the (CamelCase) stimuli. Produces the same normalized frames
    + ``_wizard_finalize_payload`` as a finished generic upload, so finalize /
    reload behave identically."""
    from scanpath_studio.datasets import (
        MULTIPLEYE_FIX_SCHEMA,
        MULTIPLEYE_MONITOR,
        MULTIPLEYE_WORD_SCHEMA,
        multipleye_frames_from_uploads,
    )

    if active:
        body.caption(
            "Upload the MultiplEYE **scanpath** (or fixation) CSVs and, for word "
            "boxes, the **AOI** CSVs — identity is read from the file names, each "
            "stimulus page becomes a trial, and character AOIs are aggregated into "
            "word boxes automatically."
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
        "Optional — without them you get fixations and no word boxes.",
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
    word_schema = dict(MULTIPLEYE_WORD_SCHEMA) if has_words else None
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
        },
    )
    keep_words = (
        compute_keep_columns(
            word_schema, keep_columns={"genre", "comprehension_questions"}
        )
        if has_words
        else None
    )
    # app._normalize_pair sets _composite_trial_columns from the (single-column)
    # trial mapping → None, exactly what the reload branch expects.
    words_norm, fixations_norm = app._normalize_pair(
        words_raw if has_words else empty_words_frame(),
        word_schema,
        fix_raw,
        fix_schema,
        keep_words=keep_words,
        keep_fix=keep_fix,
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


def _render_data_setup(active: bool) -> _UploadResult:
    """Hybrid data-setup surface for the Upload source.

    On first load (``active``) it's a guided wizard: dataset name + display setup
    at the top, a collapsible **Upload your data** subsection (one toggle per
    table, each showing its row count), a **Column mapping** subsection (one
    toggle per part — restore, trial id, participants, texts, fixations, text &
    interest areas, more mappings), then filter/keep pickers and the **Add
    dataset** button. Only the step you still need to fill stays open; finished /
    auto-detected steps collapse (auto-advance). After finishing it becomes a
    compact collapsed **Data & mapping** panel. Returns the normalized frames (or
    empties + ``problems``)."""
    if active:
        st.header("📂 Set up your dataset")
        st.caption(
            "Name your dataset, upload your tables, then map a few columns — only "
            "the step you still need to fill stays open."
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
        body = st.container()
        _render_wizard_progress(body)
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

    # Auto-advance: the first not-done step opens; finished + optional steps
    # collapse. In the collapsed panel everything renders inline (Streamlit
    # forbids nesting an expander inside the panel's own expander).
    flow = {"claimed": False}

    def toggle(title: str, *, done: bool = True, expanded: Optional[bool] = None):
        if not active:
            body.markdown(f"**{title}**")
            return body
        if expanded is None:
            expanded = _wizard_step_expanded(title, done, flow, st.session_state)
        return body.expander(title, expanded=expanded)

    def subsection(title: str, number: Optional[int] = None) -> None:
        # Numbered headings (1., 2., …) only in the active wizard, where they make
        # the order to work through explicit. The collapsed review panel drops the
        # numbers (its first two steps aren't re-rendered, so 3.,4.,5. would orphan).
        if not active:
            body.markdown(f"**{title}**")
        elif number is not None:
            body.markdown(f"#### {number}. {title}")
        else:
            body.markdown(f"#### {title}")

    def mapped(prefix: str, field: str) -> bool:
        """Best-effort 'this field is mapped' from last run's session state."""
        v = st.session_state.get(f"{prefix}_{field}")
        if isinstance(v, (list, tuple)):
            return bool(v)
        return bool(v) and v != NONE_OPTION

    # === 1. Dataset name + format ===
    if active:
        subsection("Dataset name", number=1)
        st.session_state.setdefault("wizard_dataset_name", _default_dataset_name())
        body.text_input(
            "Dataset name",
            key="wizard_dataset_name",
            label_visibility="collapsed",
            help="Shown in the Data source list so you can switch back to it.",
        )
        body.segmented_control(
            "Dataset format",
            ["Generic", "MultiplEYE"],
            key="wizard_dataset_format",
            default="Generic",
            help="**Generic**: map your own columns. **MultiplEYE**: upload the "
            "corpus's scanpath/fixation + AOI CSVs and the app parses identity "
            "from the file names (no column mapping needed).",
        )

    # A dedicated dataset format (e.g. MultiplEYE) runs its own tailored flow and
    # bypasses the generic mapping steps below. Read from state so the collapsed
    # review panel (active=False) branches the same way.
    if st.session_state.get("wizard_dataset_format", "Generic") == "MultiplEYE":
        return _render_multipleye_upload(body, active)

    # === 2. Experimental setup ===
    if active:
        subsection("Experimental setup", number=2)
        body.caption(
            "Match the screen the data was recorded on so word boxes and "
            "fixations stay true to scale — open the panel to set monitor size, "
            "font, and text scaling."
        )
        # app.render_sidebar_canvas_controls renders its own collapsible panel — that
        # IS the display-setup toggle. Seed it on empty frames up front (uploads
        # default to a 2560x1440 monitor; tweak it any time).
        app.render_sidebar_canvas_controls(
            empty_words_frame(),
            empty_fixations_frame(),
            data_choice=None,
            slot=body,
            expanded=False,
            title="Monitor, font & text scaling",
        )

    # === 3. Upload your data — one toggle per table, with row counts ===
    subsection("Upload your data", number=3)
    core_uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
    )
    # Getting-started guidance at the top of the step, shown only before anything
    # is uploaded (and only in the active wizard): the call to action plus a tip
    # to run locally for large datasets, which is faster and keeps data private.
    already_uploaded = core_uploaded or bool(
        st.session_state.get("col_map_raw_gaze_upload")
    )
    # Render the guidance into a container that is ALWAYS created (even when it
    # ends up empty) so the upload boxes below keep a fixed position in the
    # element tree. Otherwise the guidance vanishing the moment a file is added
    # shifts every following element up by two delta-paths — and because reading
    # a large upload blocks the rerun (the "Reading uploaded data…" cache spinner),
    # Streamlit freezes the half-reconciled DOM and leaves the pre-shift copy of
    # the whole upload group on screen as a greyed-out ghost (BUG-2).
    intro = body.container()
    # Say where an upload goes *before* the uploader, not after — a researcher
    # with participant data needs it stated, not inferred. Rendered
    # unconditionally: `intro` is always created, and adding a *conditional*
    # child here is exactly the element-tree shift the comment above describes.
    intro.caption(
        "🔒 Your file is parsed on the machine running this app and never sent "
        "elsewhere. Local/desktop installs keep a private recovery cache after "
        "you add the dataset; the hosted demo remains memory-only. "
        "[Where your data goes ↗](https://lacclab.github.io/scanpath-studio/privacy/)"
    )
    if active and not already_uploaded:
        intro.info("⬆️ Upload a **Fixations** and/or **Words/IA** table to begin.")
        intro.markdown(
            "💡 **Working with a large dataset?** It's faster — and keeps your "
            "data on your own machine — to run Scanpath Studio locally:\n\n"
            "```bash\npip install scanpath-studio\nscanpath-studio\n```"
        )

    def upload_box(title, *, label, help_text, prefix, multi, noun, expanded):
        # Keep a table's box open once it has an upload, so its row count and
        # head preview stay visible instead of collapsing out of sight.
        has_upload = bool(st.session_state.get(f"{prefix}_upload"))
        box = toggle(title, expanded=expanded or has_upload)
        col = box.columns([0.7, 0.3])[0] if active else box
        frame = app._read_uploaded_frame(
            uploader_label=label,
            upload_help=help_text,
            state_prefix=prefix,
            multi=multi,
            container=col,
        )
        if not frame.empty:
            box.success(
                f"✓ **{len(frame):,}** {noun} detected — make sure this is the "
                "number you expect to see."
            )
            if active:
                # Show the first rows so the user can eyeball the columns before
                # mapping them (a quick is-this-the-right-table sanity check).
                box.caption("Preview — first rows:")
                box.dataframe(frame.head(), width="stretch", hide_index=True)
        return frame

    # Order: raw gaze, then fixations, then words. Raw gaze is optional → starts
    # collapsed (auto-opens once it has a file); the core tables stay open so
    # their counts + previews remain visible after uploading.
    raw_gaze = upload_box(
        "Raw gaze (optional)",
        label="Raw gaze table",
        help_text="Optional millisecond-level gaze overlay (one file).",
        prefix="col_map_raw_gaze",
        multi=False,
        noun="gaze points",
        expanded=False,
    )
    raw_fix = upload_box(
        "Fixations",
        label="Fixations table(s)",
        help_text="One or more files (e.g. one per participant); concatenated.",
        prefix="col_map_fix",
        multi=True,
        noun="fixations",
        expanded=True,
    )
    raw_words = upload_box(
        "Words / Interest Areas",
        label="Words / IA table(s)",
        help_text="One or more files (e.g. one per text); concatenated.",
        prefix="col_map_words",
        multi=True,
        noun="words",
        expanded=True,
    )
    if raw_words.empty and raw_fix.empty and raw_gaze.empty:
        # The "upload to begin" prompt now lives at the top of this subsection.
        return _UploadResult(
            empty_words_frame(),
            empty_fixations_frame(),
            pd.DataFrame(),
            raw_words,
            raw_fix,
            [],
        )

    prop_w = propose_word_schema(raw_words) if not raw_words.empty else {}
    prop_f = propose_fix_schema(raw_fix) if not raw_fix.empty else {}
    prop_g = propose_raw_gaze_schema(raw_gaze) if not raw_gaze.empty else {}
    word_schema: Dict = {}
    fix_schema: Dict = {}
    has_words, has_fix = not raw_words.empty, not raw_fix.empty

    # === 4. Column mapping ===
    subsection("Column mapping", number=4)

    # Restore a saved setup (optional, collapsed).
    restore_box = toggle("Restore a saved setup (optional)", done=True)
    _wizard_restore_config(restore_box)
    _render_restored_config_caption(restore_box)

    # Derive ids from the filename (optional) — must run *before* the trial /
    # participant pickers so the split-out file_part_N columns are mappable.
    if (has_words or has_fix) and any(
        SOURCE_FILE_COLUMN in fr.columns for fr in (raw_fix, raw_words) if not fr.empty
    ):
        derive_box = toggle("Derive ids from filename (optional)", done=True)
        raw_words, raw_fix, raw_gaze = _wizard_filename_derive(
            derive_box, raw_words, raw_fix, raw_gaze
        )

    # Trial identifier (required → opens first if not yet mapped).
    if has_words or has_fix:
        trial_done = bool(
            st.session_state.get("col_map_trial_unified")
            or st.session_state.get("col_map_fix_trial")
            or st.session_state.get("col_map_words_trial")
        )
        tbox = toggle("Trial identifier", done=trial_done)
        _wizard_trial_step(
            tbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
        )

    # Participants (optional, same shape as the trial id).
    if has_words or has_fix:
        pbox = toggle("Participants (optional)", done=True)
        pbox.caption(
            "Which column(s) identify the reader? Leave blank for a single "
            "anonymous reader."
        )
        _wizard_participant_text_step(
            "participant",
            "Participant ID",
            "participants",
            "Pick the reader column — or several to compose an id. Leave empty "
            "for a single anonymous reader.",
            pbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
            "Participants (optional)",
        )

    # Texts (optional).
    if has_words or has_fix:
        txbox = toggle("Texts (optional)", done=True)
        txbox.caption(
            "Which column(s) identify the text/passage? Leave blank for a single text."
        )
        _wizard_participant_text_step(
            "text_id",
            "Text ID",
            "texts",
            "Pick the text column — or several to compose an id. Leave empty to "
            "fall back to the trial id.",
            txbox,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
            "Texts (optional)",
        )

    # Column mapping: Fixations — required fields (coordinates + duration) plus
    # the fixation id.
    if has_fix:
        fix_done = mapped("col_map_fix", "duration") and (
            mapped("col_map_fix", "x") or mapped("col_map_fix", "word_id")
        )
        fbox = toggle("Fixations", done=fix_done)
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                fbox,
                ["x", "y", "duration", "fixation_id"],
                step_title="Fixations",
            )
        )
        fbox.caption(
            "Leave X/Y blank for AOI-only data and map the Word/IA ID under "
            "*More fixation mappings* instead."
        )

    # Column mapping: Text & Interest Areas — required word fields.
    if has_words:
        words_done = mapped("col_map_words", "word_id") and (
            mapped("col_map_words", "left") or mapped("col_map_words", "x")
        )
        wbox = toggle("Text & Interest Areas", done=words_done)
        word_schema.update(
            _map_section(
                raw_words,
                WORD_FIELD_SPECS,
                prop_w,
                "col_map_words",
                wbox,
                ["word_id", "text", "box"],
                step_title="Text & Interest Areas",
            )
        )
        wbox.toggle(
            "Aggregate character AOIs into word boxes",
            key="wizard_aggregate_char_boxes",
            help="For interest-area tables with one row per *character* (e.g. CJK "
            "corpora): collapse the characters of each word (grouped by the Trial "
            "+ Word/IA id above) into one bounding box.",
        )

    # More text mappings (line index) — optional.
    if has_words:
        mtbox = toggle("More text mappings (optional)", done=True)
        word_schema.update(
            _map_section(
                raw_words,
                WORD_FIELD_SPECS,
                prop_w,
                "col_map_words",
                mtbox,
                ["line"],
                step_title="More text mappings (optional)",
            )
        )
        mtbox.caption("Line index enables colouring fixations/words by reading line.")

    # More fixation mappings (word id, timestamp) — optional.
    if has_fix:
        mfbox = toggle("More fixation mappings (optional)", done=True)
        fix_schema.update(
            _map_section(
                raw_fix,
                FIX_FIELD_SPECS,
                prop_f,
                "col_map_fix",
                mfbox,
                ["word_id", "timestamp"],
                step_title="More fixation mappings (optional)",
            )
        )

    # Raw gaze overlay mapping (its own table); required only for a raw-gaze-only
    # upload, else an optional overlay.
    if not raw_gaze.empty:
        rg_required = not has_words and not has_fix
        rg_done = not rg_required or (
            mapped("col_map_raw_gaze", "trial")
            and mapped("col_map_raw_gaze", "x")
            and mapped("col_map_raw_gaze", "y")
        )
        rgbox = toggle(
            "Raw gaze overlay" if rg_required else "Raw gaze overlay (optional)",
            done=rg_done,
        )
        raw_gaze_schema = _map_section(
            raw_gaze,
            RAW_GAZE_FIELD_SPECS,
            prop_g,
            "col_map_raw_gaze",
            rgbox,
            ["participant", "trial", "x", "y", "timestamp", "text"],
            step_title=(
                "Raw gaze overlay" if rg_required else "Raw gaze overlay (optional)"
            ),
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
    # Feed the wizard step indicator (read at the top of the next run).
    st.session_state["_wizard_problems_last"] = list(problems)

    # === 5. Filter & keep — one cross-table picker each (not per table) ===
    subsection("Filter & keep (optional)", number=5)
    keep_tables: list = []
    if has_words:
        keep_tables.append(
            (raw_words, word_schema, WORD_OPTIONAL_FIELDS, "col_map_words")
        )
    if has_fix:
        keep_tables.append((raw_fix, fix_schema, FIX_OPTIONAL_FIELDS, "col_map_fix"))
    filter_box = toggle("Filter trials by (optional)", done=True)
    keep_box = toggle("Additional fields to keep (optional)", done=True)
    keep_by_prefix, filter_fields = _wizard_keep_and_filter(
        keep_tables, filter_box, keep_box
    )
    st.session_state["wizard_filter_fields"] = list(filter_fields)

    if problems:
        if active:
            _render_setup_download(body)
            body.button("✅ Add dataset", disabled=True, key="wizard_finalize")
            body.warning(
                "Map the required field(s) above (marked \\*) to continue:\n\n"
                + "\n".join(f"- {p}" for p in problems)
            )
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

    # Char→word aggregation (optional generic power): collapse character-level
    # AOIs to one box per word using the final word mapping, before normalization
    # (which expects one row per word box). Only fires when the user toggled it on
    # in the Text & Interest Areas step and the words mapping is complete.
    if has_words and st.session_state.get("wizard_aggregate_char_boxes"):
        raw_words = aggregate_char_boxes(raw_words, word_schema)

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
        words_norm, fixations_norm = app._normalize_pair(
            raw_words,
            word_schema if has_words else None,
            raw_fix,
            fix_schema if has_fix else None,
            keep_words=keep_words,
            keep_fix=keep_fix,
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
            body.warning("Raw gaze ignored — " + "; ".join(raw_gaze_problems))
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
        }
        _render_setup_download(body)
        body.button(
            "✅ Add dataset",
            type="primary",
            key="wizard_finalize",
            on_click=_finalize_wizard_dataset,
        )

    return _UploadResult(
        words_norm, fixations_norm, raw_gaze_norm, raw_words, raw_fix, []
    )


# -----------------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------------
