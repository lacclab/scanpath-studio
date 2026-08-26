"""The Upload / Add-dataset wizard (the main-area guided data-setup flow).

Split out of ``app.py``: everything from the upload-table reading UI through the
ordered wizard steps (identity → trial/participant/text → keep-fields/filters →
name & finish) and the MultiplEYE upload branch. ``app.py`` drives this from
``resolve_data_source`` / ``main`` and re-exports a few helpers for tests.

A handful of data-IO / normalization helpers (``_read_uploaded_frame``,
``_normalize_pair``, ``_stash_active_mapping``, ``_render_unmapped_view``) stay in
``app.py`` and are reached via ``app.<name>`` at call time — that keeps the
``app._read_uploaded_frame`` upload seam (monkeypatched in AppTests) intact and
avoids an app⇄wizard import cycle.
"""

from __future__ import annotations

import html
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
    UPLOAD_MAX_SIZE_MB,
    WIZARD_LEAVE_KEY,
    multipleye_upload_enabled,
)
from .controls import (
    ADD_ATTEMPTED_KEY,
    FIX_FIELD_SPECS,
    NONE_OPTION,
    RAW_GAZE_FIELD_SPECS,
    TOUCHED_FIELDS_KEY,
    WORD_FIELD_SPECS,
    column_mapping_ui,
    inline_field_label,
    mark_missing_cells,
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
from .styles import mapping_menu_css
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
        # UX-114: the per-table keep pickers (`wizard_keep_col_map_words` etc.,
        # plus their Select-all/None button keys) share the "col_map_" table
        # names as a *suffix*, not a prefix — sweep "wizard_keep_" too, or a
        # new dataset would inherit the previous one's keep choices.
        if isinstance(k, str) and k.startswith(("col_map_", "wizard_keep_"))
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
        # UX-53: a new dataset starts unattempted, so its required fields are
        # blank rather than red until this one is asked to be added — and
        # unconfirmed, so nothing is green until somebody picks it here.
        ADD_ATTEMPTED_KEY,
        TOUCHED_FIELDS_KEY,
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


def _wizard_finalize_metadata_pools(payload: dict) -> tuple:
    """The just-finalized dataset's own participant/trial/text pools.

    UX-116: unlike ``_wizard_reader_ids``/``_wizard_trial_combos``/
    ``_wizard_text_ids`` (which read the *raw*, pre-normalization frames,
    because those run live while mapping is still being worked out), this
    reads the *normalized* ``words``/``fixations`` already in ``payload`` —
    the canonical ``participant_id``/``trial_id``/``text_id`` columns are
    exactly what the real dataset will carry, so there is no re-deriving to
    do. Called once, from ``_finalize_wizard_dataset``.
    """
    words = payload.get("words")
    fixations = payload.get("fixations")
    combo_frames = [
        frame[["participant_id", "trial_id"]]
        for frame in (fixations, words)
        if frame is not None and not frame.empty and "participant_id" in frame.columns
    ]
    combos = (
        pd.concat(combo_frames, ignore_index=True).drop_duplicates()
        if combo_frames
        else pd.DataFrame(columns=["participant_id", "trial_id"])
    )
    participants = sorted(combos["participant_id"].dropna().astype(str).unique())
    text_series = [
        frame["text_id"]
        for frame in (fixations, words)
        if frame is not None and not frame.empty and "text_id" in frame.columns
    ]
    texts = (
        sorted(pd.concat(text_series).dropna().astype(str).unique())
        if text_series
        else []
    )
    return participants, combos, texts


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
    # UX-116: the metadata tables' own join was deferred (`live_join=False`)
    # while this dataset was still being assembled — do it now, against the
    # pools this dataset actually ends up with. No UI here: a callback runs
    # before the widgets that would host it exist for this run.
    from scanpath_studio.tabs import commit_deferred_metadata

    participants, combos, texts = _wizard_finalize_metadata_pools(payload)
    commit_deferred_metadata(participants, combos, texts)
    ds_name = _safe_dataset_name(st.session_state.get("wizard_dataset_name"))
    store = st.session_state.setdefault("_datasets", {})
    store[ds_name] = payload
    # Apply the source switch through the plain pending key that
    # resolve_data_source consumes before the radio instantiates, and
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
    before the radio re-instantiates, like the wizard finalize/cancel switch).

    **UX-87: deleting a dataset drops the computations derived from it.** Every
    figure, table and normalization the app cached for this dataset is dead the
    moment its frames leave the session — keeping them only holds memory and
    leaves stale results one undo-less click away from being attributed to
    whatever takes the name next. ``@st.cache_data`` has no per-key eviction, so
    this is ``clear_computation_cache``'s blunt instrument: the survivors are
    recomputed on the next rerun from frames that are still loaded, which is the
    same lossless trade the 🧹 button makes.
    """
    store = st.session_state.get("_datasets", {})
    store.pop(name, None)
    if st.session_state.get("data_source_choice") == name:
        st.session_state["_pending_source_choice"] = DEMO_CHOICE
    app.clear_computation_cache()


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


def _render_leave_prompt(host) -> None:
    """Ask before abandoning a half-built dataset (BUG-31).

    Raised by ``app.main`` when the user navigates away while the wizard is open:
    rather than switching the app onto the unfinished upload — which reported
    *"this dataset isn't set up yet"* over a session full of finished datasets —
    the view is held here and the question is asked.

    It says the files will be lost because they will. Streamlit drops a widget's
    key at the end of any run in which it did not render, and ``st.file_uploader``
    is the one widget ``persist_state="session"`` cannot cover (ENG-36), so
    "park it and come back" is not available to promise. The mapping answers
    would survive; the uploads would not, which is the half that matters.

    **UX-79** made it a modal. ``host`` is kept in the signature — the caller
    reserves a place in the wizard's sticky bar and nothing else needs to know
    that the question now opens over the page rather than inside it.
    """
    destination = st.session_state.get(WIZARD_LEAVE_KEY)
    if not destination:
        return
    _leave_prompt_dialog(destination)


@st.dialog("Leave setup?")
def _leave_prompt_dialog(destination: str) -> None:
    """The modal body — UX-79. Opened by :func:`_render_leave_prompt`.

    A dialog rather than a bar inside the wizard: the question is raised by a
    click on the **nav**, at the top of the window, while the answer used to
    appear inside a screen the user is already scrolled down in. It also has to
    interrupt — the run that asks it is the run that would otherwise have
    navigated away.

    The keys are unchanged (`WIZARD_LEAVE_KEY` arms it; the two callbacks clear
    it), so `app.main`'s hold-the-view logic is untouched: a dialog is opened by
    *calling* it, so all that moved is where the flag is read.

    **BUG-36:** handled by the button's *return value*, not `on_click` — an
    `st.dialog` body is a fragment, so an `on_click` callback here reran only
    the dialog: it wrote the session state fine, but `main()` never
    re-executed, so the modal sat there looking inert. `st.rerun(scope="app")`
    both closes the modal and renders the page underneath (see `tour.py`'s
    `_tutorial_library_dialog`, which hit the same trap first).
    """
    st.warning(
        f"**Leave setup and go to {destination}?** This dataset isn't added yet "
        "— the files you uploaded won't be kept.",
        icon="⚠️",
    )
    stay_col, leave_col = st.columns(2)
    if stay_col.button(
        "↩️ Keep setting up",
        key="wizard_leave_stay",
        width="stretch",
        type="primary",
    ):
        app.stay_in_wizard()
        st.rerun(scope="app")
    if leave_col.button(
        "🗑️ Discard and leave",
        key="wizard_leave_discard",
        width="stretch",
    ):
        app.discard_and_leave_wizard()
        st.rerun(scope="app")


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


def _map_section(
    raw, specs, proposed, prefix, host, keys, *, per_row: int = 1, stacked: bool = True
) -> dict:
    """Render a subset of a table's mapping fields. Returns that partial mapping.

    ``per_row`` (UX-53 r7) is how many fields share a line — four fixation
    fields fit where one used to, which is what gets the whole mapping onto one
    screen. ``stacked`` keeps every wizard field's title *above* its control,
    including a lone field dropped into a row the caller laid out (r17); the
    🗂️ Data page keeps `label | field` by not going through here.

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
        columns_per_row=per_row,
        stack_labels=stacked,
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


def _render_identity_field(
    field_key: str,
    label: str,
    help_text: str,
    cells,
    raw_words,
    raw_fix,
    word_schema,
    fix_schema,
    has_words,
    has_fix,
    default_cols: list,
    required: bool = False,
) -> None:
    """One identifier (trial / participant / text), **one picker per table**.

    UX-53 r13 removed the *Different … per table* toggle. It was a mode switch
    guarding a case that costs nothing to show: the tables are listed anyway, so
    naming the column in each is one pick either way, and the toggle made the
    common case ("same column, obviously") look like a decision while hiding the
    uncommon one behind a control nobody finds. Each present table now gets its
    own multiselect, seeded from the same proposal, so identical columns are
    still identical — just visible.

    Several columns compose an id (joined with ``_``, like the trial id). Writes
    ``schema[field_key]`` (str / list / None) into ``word_schema`` /
    ``fix_schema`` in place; the per-table ``col_map_<tbl>_<field>`` keys are the
    stored values, which is what save/restore and deep links already carry.

    ``cells`` is one container per present table, in (fixations, words) order —
    the caller lays the row out, because a theme's fields share one row.
    """

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
            st.session_state[key] = [c for c in fallback if c in options]
            return
        valid = [c for c in stored if c in options]
        if len(valid) != len(stored):
            st.session_state[key] = valid or [c for c in fallback if c in options]

    tables = []
    if has_fix:
        tables.append(("fix", "Fixations", raw_fix, fix_schema))
    if has_words:
        tables.append(("words", "AOI", raw_words, word_schema))

    missing_cells: list[str] = []
    for cell, (slug, table_label, raw, schema) in zip(cells, tables):
        key = f"col_map_{slug}_{field_key}"
        # UX-108 — the file's real header, not `raw.columns`: PERF-6 parses
        # only the columns an auto-detect + the optional-field registry +
        # whatever a `col_map_*` key already names decided to keep, and Trial
        # ID / Participant ID / Text ID are exactly the fields a composite
        # mapping is built from — the ones a narrow parse is most likely to
        # have left out. Same fallback as `controls.column_mapping_ui`: empty
        # outside a real upload (this function also renders for a *stored*
        # dataset's already-normalized frames, which have no header to ask).
        full_header = st.session_state.get(f"col_map_{slug}_header")
        options = list(full_header) if full_header else list(raw.columns)
        _seed(key, options, default_cols)
        # Title on the cell's first line, control on its second (UX-53 r14), so
        # the row reads as a line of names over a line of pickers. The title
        # carries no table name (r15): the rows are now grouped *by* table and
        # each is labelled once at its head, so repeating it on all three fields
        # would say the same thing three times.
        inline_field_label(cell, label, f"{help_text} ({table_label} table)")
        # UX-91: a keyed wrapper so an empty *required* picker can be tinted the
        # red every other required field turns after a failed add. These
        # multiselects are the wizard's own — they never went through
        # `column_mapping_ui`, which is why Trial ID stayed grey while the
        # selects beside it went red.
        cell_key = f"{key}_cell"
        chosen = cell.container(key=cell_key).multiselect(
            f"{label} — {table_label}",
            options=options,
            key=key,
            help=help_text,
            label_visibility="collapsed",
        )
        schema[field_key] = _mapping(chosen)
        if required and not chosen and st.session_state.get(ADD_ATTEMPTED_KEY):
            missing_cells.append(cell_key)
    if missing_cells:
        mark_missing_cells(missing_cells)


#: UX-113 — session key holding the *committed* filename-derive settings
#: (mode/delimiter/pattern/lower). Kept separate from the live widget keys
#: below so editing the delimiter or regex doesn't silently change what is
#: actually derived — only clicking Apply does.
_FILENAME_DERIVE_APPLIED_KEY = "wizard_filename_applied"

#: A worked example rather than a blank box — shown as the regex field's own
#: starting value (edit or replace it) and repeated in its help text so the
#: two stay in sync.
_FILENAME_REGEX_EXAMPLE = r"(?P<session>\d+_\w+_ET\d)_.*_(?P<stimulus>.+)_scanpath"


def _wizard_filename_derive(body, raw_words, raw_fix, raw_gaze):
    """Optional step: derive columns from an uploaded column's own text — the
    captured ``source_file`` by default, or any other column — so identity
    that lives only inside a string (a filename, or a structured value like
    ``question_04111_target``) can be mapped.

    Two modes: split into positional ``file_part_N`` columns on a delimiter, or
    extract *named groups* with a regex (robust to variable-length parts, e.g. a
    stimulus name whose length varies). Nothing is derived, and nothing becomes
    mappable below, until **Apply** — the settings here are a draft until then,
    so retyping a regex mid-thought never silently changes the committed
    columns. Returns the (possibly augmented) frames so the identifier pickers
    below see the new columns; a no-op while the toggle is off.
    """
    toggle_col, controls_col = body.columns(
        [0.26, 0.74], gap="small", vertical_alignment="center"
    )
    enabled = toggle_col.toggle(
        "Derive columns from the filename",
        key="wizard_filename_split",
        help=(
            "When identity lives only inside a text value — no column carries "
            "it on its own — derive real columns from it (e.g. session, "
            "stimulus) that you can then map as an id below: split it on a "
            "delimiter into positional columns, or pull out named regex "
            "groups for parts of variable length (e.g. a stimulus name). "
            "Defaults to the uploaded filename (captured as `source_file`), "
            "but any other uploaded column works the same way."
        ),
    )
    if not enabled:
        return raw_words, raw_fix, raw_gaze

    # UX-113: which column to read — `source_file` (the filename) by default,
    # but any column the upload carries. The same trick that pulls a trial id
    # out of a filename also pulls e.g. a question id + block name out of a
    # `page`-style column's own text.
    available_columns = list(
        dict.fromkeys(
            c
            for fr in (raw_words, raw_fix, raw_gaze)
            if not fr.empty
            for c in fr.columns
        )
    ) or [SOURCE_FILE_COLUMN]
    default_column = (
        SOURCE_FILE_COLUMN
        if SOURCE_FILE_COLUMN in available_columns
        else available_columns[0]
    )
    column_key = "wizard_filename_column"
    if st.session_state.get(column_key) not in available_columns:
        st.session_state[column_key] = default_column

    col_col, mode_col, input_col, lower_col, apply_col = controls_col.columns(
        [0.2, 0.16, 0.32, 0.16, 0.16], gap="small", vertical_alignment="bottom"
    )
    source_column = col_col.selectbox(
        "Column",
        available_columns,
        key=column_key,
        label_visibility="collapsed",
        help="Which uploaded column to derive from — defaults to the "
        "filename (`source_file`); pick any other column that encodes "
        "identity as text.",
    )
    mode = mode_col.selectbox(
        "How",
        ["Split on a delimiter", "Regex named groups"],
        key="wizard_filename_mode",
        label_visibility="collapsed",
        help="How to pull columns out of the chosen column's text.",
    )
    pattern = ""
    lower = False
    if mode == "Split on a delimiter":
        delimiter = (
            input_col.text_input(
                "Delimiter",
                value="_",
                key="wizard_filename_delim",
                max_chars=8,
                label_visibility="collapsed",
                help="Character(s) to split the filename on — e.g. "
                "`reader0_b0_scanpath` → reader0 / b0 / scanpath.",
            )
            or "_"
        )
    else:
        pattern = input_col.text_input(
            "Regex (named groups)",
            value=_FILENAME_REGEX_EXAMPLE,
            key="wizard_filename_regex",
            label_visibility="collapsed",
            help=f"e.g. `{_FILENAME_REGEX_EXAMPLE}` — each named group becomes "
            "a column. Edit this to match your own filenames.",
        )
        lower = lower_col.toggle(
            "Lowercase",
            key="wizard_filename_regex_lower",
            help="Fold case so a value matches across tables (e.g. CamelCase "
            "scanpath names vs lowercase AOI names).",
        )
        if pattern:
            try:
                re.compile(pattern)
            except re.error as exc:
                controls_col.error(f"Invalid regex: {exc}")
                pattern = ""

    apply_clicked = apply_col.button(
        "Apply",
        key="wizard_filename_apply",
        width="stretch",
        disabled=mode == "Regex named groups" and not pattern,
        help="Derive the columns above and make them available to map below.",
    )
    if apply_clicked:
        st.session_state[_FILENAME_DERIVE_APPLIED_KEY] = {
            "mode": mode,
            "column": source_column,
            "delimiter": delimiter if mode == "Split on a delimiter" else None,
            "pattern": pattern if mode != "Split on a delimiter" else None,
            "lower": lower,
        }

    applied = st.session_state.get(_FILENAME_DERIVE_APPLIED_KEY)
    if not applied:
        return raw_words, raw_fix, raw_gaze
    # Older sessions' applied state predates the column picker (UX-113) —
    # `source_file` was the only option then, so that's the correct fallback.
    applied_column = applied.get("column", SOURCE_FILE_COLUMN)

    if applied["mode"] == "Split on a delimiter":
        out = [
            split_source_file(fr, delimiter=applied["delimiter"], column=applied_column)
            if not fr.empty
            else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]
    else:
        applied_pattern = applied["pattern"]
        # A group named after an existing column would be skipped (real data
        # wins) — flag it so the user renames the group instead of silently
        # getting the original column.
        collisions = sorted(
            {
                c
                for fr in (raw_words, raw_fix, raw_gaze)
                if not fr.empty
                for c in source_file_regex_collisions(
                    fr, applied_pattern, column=applied_column
                )
            }
        )
        if collisions:
            body.warning(
                "These group names already exist as columns and were left "
                f"untouched: {', '.join(collisions)}. Rename the group(s) and "
                "Apply again to extract them."
            )
        out = [
            extract_columns_from_source_file(
                fr, applied_pattern, column=applied_column, lowercase=applied["lower"]
            )
            if not fr.empty
            else fr
            for fr in (raw_words, raw_fix, raw_gaze)
        ]

    raw_words, raw_fix, raw_gaze = out
    # UX-113: prefer whichever table actually carries the derived-from column
    # — it no longer has to be `source_file`, universally stamped on every
    # table, so a table that never had `applied_column` (e.g. an AOI-only
    # `page` value) must not become the preview.
    preview_candidates = [
        fr
        for fr in (raw_fix, raw_words)
        if not fr.empty and applied_column in fr.columns
    ]
    preview = (
        preview_candidates[0]
        if preview_candidates
        else (raw_fix if not raw_fix.empty else raw_words)
    )
    if applied["mode"] == "Split on a delimiter":
        new_cols = [c for c in preview.columns if c.startswith(FILE_PART_PREFIX)]
    else:
        new_cols = [
            c for c in re.compile(applied["pattern"]).groupindex if c in preview.columns
        ]
    if new_cols:
        # UX-113: publish the derived columns into each table's own header
        # stash. `column_mapping_ui` offers `col_map_<slug>_header` over the
        # live frame's own columns (PERF-6's narrow-parse plan), which is the
        # *file's* header stashed at upload time — so a column synthesized in
        # memory afterwards, like these, never showed up in the picker below
        # even though the frame itself already carried it.
        for prefix, fr in (
            ("col_map_words", raw_words),
            ("col_map_fix", raw_fix),
            ("col_map_raw_gaze", raw_gaze),
        ):
            if fr.empty:
                continue
            header_key = f"{prefix}_header"
            header = list(st.session_state.get(header_key) or fr.columns)
            missing = [c for c in new_cols if c not in header]
            if missing:
                st.session_state[header_key] = [*header, *missing]
        body.caption("Derived columns (first rows) — map them as ids below:")
        body.dataframe(
            preview[[applied_column, *new_cols]].drop_duplicates().head(),
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
    *,
    cells=None,
    extras_host=None,
) -> None:
    """Trial-identifier wizard step: one picker per table (UX-53 r13), plus the
    per-table trial-count check that flags mismatches. Mutates ``word_schema`` /
    ``fix_schema`` in place. ``cells`` are the row containers the caller built —
    each table's count is a caption inside its own cell (UX-67 r2), and
    ``extras_host`` is left with the one thing that is not a count: the warning
    that the two tables' trial ids do not line up at all."""
    # Core tables present (raw-gaze keeps its own mapping in its own step).
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default_trial = _default_trial_columns(prop_primary, common_cols)
    _render_identity_field(
        "trial",
        "Trial ID *",
        "The column holding your unique trial ID — or several to build one on "
        "the fly (values joined with '_'), e.g. participant + text.",
        cells if cells is not None else [body] * 2,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        default_trial,
        required=True,
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
    # UX-67 r2: the count is a caption under the picker it counts, not a banner.
    # One `st.success` per identifier stacked three coloured boxes onto a screen
    # whose whole point is that the mapping fits on it — and put the number far
    # from the menu that produces it. Per *table*, too: each cell counts its own
    # column, so a mismatch is read by comparing two numbers side by side rather
    # than by parsing a sentence about it.
    cell_by_table = dict(zip(sets, cells if cells is not None else []))
    for table, values in sets.items():
        cell = cell_by_table.get(table)
        if values is None or cell is None:
            continue
        cell.caption(f"✓ {len(values):,} trials")
    # Only a real problem still gets a box, and it renders where UX-67 put the
    # blockers: directly above **Add dataset**.
    counts_host = extras_host if extras_host is not None else body
    present = {k: v for k, v in sets.items() if v is not None}
    if len(present) > 1:
        values = list(present.values())
        counts_str = ", ".join(f"{k}: **{len(v):,}**" for k, v in present.items())
        if not set.intersection(*values):
            counts_host.warning(
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
    *,
    cells=None,
    extras_host=None,
) -> None:
    """Optional participant- or text-identifier step: one picker per table
    (UX-53 r13), then a distinct-value count captioned under **each** table's
    own picker (UX-67 r2) — every present table gets one, the same per-table
    shape `_wizard_trial_step` uses (BUG-35: previously only Fixations' count
    was ever shown, so the AOI row's pickers had nothing under them). Mutates
    the schemas in place."""
    core = [f for f, present in ((raw_fix, has_fix), (raw_words, has_words)) if present]
    common_cols = [c for c in core[0].columns if all(c in f.columns for f in core)]
    prop_primary = prop_f if has_fix else prop_w
    default = prop_primary.get(field_key)
    default_cols = [default] if default in common_cols else []
    _render_identity_field(
        field_key,
        label,
        help_text,
        cells if cells is not None else [body] * 2,
        raw_words,
        raw_fix,
        word_schema,
        fix_schema,
        has_words,
        has_fix,
        default_cols,
    )
    tables = []
    if has_fix:
        tables.append(("fix", raw_fix, fix_schema))
    if has_words:
        tables.append(("words", raw_words, word_schema))
    cell_by_table = dict(zip((slug for slug, *_ in tables), cells)) if cells else {}
    fallback_cell = extras_host if extras_host is not None else body
    for slug, frame, schema in tables:
        n = _distinct_id_count(frame, schema.get(field_key))
        if n is not None:
            # UX-67 r2: under the picker that produced it, as small text
            # rather than a banner.
            cell_by_table.get(slug, fallback_cell).caption(f"✓ {n:,} {noun}")


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


def _wizard_trial_combos(raw_words, word_schema, raw_fix, fix_schema):
    """The ``(participant_id, trial_id)`` pairs the finished dataset will have.

    DATA-29's table attaches in the wizard, which runs **before** the frames are
    normalized — so, exactly as :func:`_wizard_reader_ids` does one grain up,
    the keys are read off the raw tables through the mapping the user has just
    made. ``trial_id_series`` is what `normalize_*` itself uses to compose a
    trial id, including the multi-column case, so the pairs here are the pairs
    the join will really see.

    An unmapped participant column yields an empty reader half rather than no
    rows: the dataset has no reader identity, so a trial-keyed table still joins
    and a reader-keyed one correctly matches nothing.

    Gated on a table actually being attached, and cached per frame — this
    walks the whole raw frame, and the wizard reruns on every keystroke.
    """
    from scanpath_studio import metadata as metadata_mod

    empty = pd.DataFrame(columns=["participant_id", "trial_id"])
    if st.session_state.get(metadata_mod.TRIAL_RAW_SESSION_KEY) is None:
        return empty
    parts = []
    for frame, schema in ((raw_fix, fix_schema), (raw_words, word_schema)):
        trial_mapping = (schema or {}).get("trial")
        if not trial_mapping or frame is None or frame.empty:
            continue
        columns = trial_mapping_columns(trial_mapping)
        if any(column not in frame.columns for column in columns):
            continue
        participant = (schema or {}).get("participant")
        if participant and participant not in frame.columns:
            participant = None
        parts.append(
            _wizard_trial_combos_cached(
                frame,
                tuple(columns),
                participant,
                frame_fingerprint(frame),
            )
        )
    if not parts:
        return empty
    return pd.concat(parts, ignore_index=True).drop_duplicates()


@st.cache_data(show_spinner=False)
def _wizard_trial_combos_cached(_frame, columns: tuple, participant, fingerprint: str):
    """Distinct ``(participant_id, trial_id)`` pairs in one raw frame."""
    trial = trial_id_series(_frame, list(columns)).astype(str)
    reader = (
        _frame[participant].astype(str)
        if participant
        else pd.Series([""] * len(_frame), index=_frame.index)
    )
    out = pd.DataFrame({"participant_id": reader, "trial_id": trial})
    return out.drop_duplicates().reset_index(drop=True)


@st.cache_data(show_spinner=False)
def _wizard_reader_ids_cached(_frame, column: str, fingerprint: str) -> list:
    """Distinct reader ids in one raw frame's mapped participant column.

    Underscore-prefixed frame + an explicit `frame_fingerprint` key, the house
    convention — see `app._cached_participant_ids`.
    """
    return sorted({str(value) for value in _frame[column].dropna().unique()})


def _wizard_text_ids(raw_words, word_schema, raw_fix, fix_schema) -> list:
    """The text ids the finished dataset will have, read from the raw tables.

    The third-grain sibling of :func:`_wizard_reader_ids` — same reasoning:
    runs before normalization, so the join report is built off the raw
    frames through the mapping the user has just made, gated on a text table
    actually being attached, and cached per frame.
    """
    from scanpath_studio import metadata as metadata_mod

    if st.session_state.get(metadata_mod.TEXT_RAW_SESSION_KEY) is None:
        return []
    found: set = set()
    for frame, schema in ((raw_fix, fix_schema), (raw_words, word_schema)):
        column = (schema or {}).get("text_id")
        if not column or frame is None or frame.empty or column not in frame.columns:
            continue
        found |= set(_wizard_reader_ids_cached(frame, column, frame_fingerprint(frame)))
    return sorted(found)


def _row_body(host):
    """Indent to where the field-mapping pickers start (`_ID_ROW1_W`'s name
    column), for a row that has no name of its own — the "Extra fields to
    keep" picker and the "Aggregate character AOIs" toggle both describe the
    table above them rather than naming a new one, so they line up under the
    pickers rather than under the row-name label."""
    _, body = host.columns([_ID_ROW1_W[0], 1 - _ID_ROW1_W[0]], gap="small")
    return body


def _wizard_table_keep_picker(
    host, raw, schema, registry, prefix: str, *, noun: str
) -> tuple[set, list]:
    """One table's "fields to keep" decision (UX-114) — directly under that
    table's own mapping, replacing the old cross-table pair of pickers
    ("Filter trials by" / "Additional fields to keep") that used to be their
    own wizard stage. Everything not mapped above and not kept here is
    dropped at normalization; everything kept becomes available to filter
    trials by, sort by, color by, or show as an info chip later — one
    decision instead of two.

    Returns ``(kept_source_columns, meta_dest_fields)``: the first feeds
    ``compute_keep_columns(keep_columns=…)`` for this table; the second is
    this table's contribution to the cross-table trial-filter condition list
    (a source column detected as a trial-level "meta" condition, e.g.
    Hunting/Gathering or difficulty — kept by default, same as before).
    """
    if raw is None or raw.empty or schema is None:
        return set(), []
    # PERF-6: categorize against the file's HEADER, not the frame — the frame
    # holds only the columns the plan parsed, and the whole job of the picker
    # below is to offer the ones it didn't. Naming one here adds it to the
    # plan, and the file is read again under it.
    header = app._uploaded_header(prefix)
    source = pd.DataFrame(columns=header) if header else raw
    cats = _c_categorize_columns(
        source,
        schema,
        registry,
        tuple(header) or frame_fingerprint(raw),
        (prefix, _schema_key(schema)),
    )
    detected = cats["detected_optional"]
    unclaimed = cats["unclaimed"]
    if not detected and not unclaimed:
        return set(), []
    host = _row_body(host)

    opts: list = []
    labels: dict = {}
    default: list = []
    meta_dest_by_source: dict = {}
    for d in detected:
        src = d["source"]
        opts.append(src)
        # UX-121: no more "· meta"/"· extra" suffix — each table's picker is
        # already its own, so the category badge that used to help tell
        # cross-table entries apart is redundant now; the field name alone.
        labels[src] = d["dest"]
        # Trial-level conditions and detected measures/linguistic features
        # were both auto-kept before UX-114 split them into two pickers —
        # same net defaults, offered as one choice now.
        if d["category"] in ("meta", "measure", "linguistic"):
            default.append(src)
        if d["category"] == "meta":
            meta_dest_by_source[src] = d["dest"]
    for col in unclaimed:
        opts.append(col)
        labels.setdefault(col, col)

    key = f"wizard_keep_{prefix}"
    if key not in st.session_state:
        st.session_state[key] = list(default)
    _clean_multiselect_state(key, opts)

    inline_field_label(
        host,
        f"Extra fields to keep — {noun}",
        "Columns not used in the mapping above. Keep the ones you want "
        "available later — to filter trials by, sort by, color by, or show "
        "as an info chip. Anything left out here is dropped when the "
        "dataset is added.",
    )
    picker_col, all_col, none_col = host.columns(
        [0.72, 0.14, 0.14], gap="small", vertical_alignment="bottom"
    )
    if all_col.button("Select all", key=f"{key}_all", width="stretch"):
        st.session_state[key] = list(opts)
    if none_col.button("None", key=f"{key}_none", width="stretch"):
        st.session_state[key] = []
    chosen = set(
        picker_col.multiselect(
            f"Extra fields to keep — {noun}",
            options=opts,
            format_func=lambda s: labels.get(s, s),
            key=key,
            label_visibility="collapsed",
        )
    )
    warning = wide_frame_warning(len(chosen), len(raw))
    if warning:
        host.warning(warning)
    meta_fields = [meta_dest_by_source[s] for s in chosen if s in meta_dest_by_source]
    return chosen, meta_fields


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
        # UX-113 Phase 3: filename/column-derive settings + keep/filter-field
        # choices weren't captured before — a restored setup silently dropped
        # them, forcing a re-do even though the mapping itself round-tripped.
        # Both sections are optional (older files simply lack them), so no
        # PLOT_CONFIG_SCHEMA bump — same precedent as experimental_setup.
        if isinstance(config.get("filename_derive"), dict):
            fd = config["filename_derive"]
            if isinstance(fd.get("applied"), dict):
                st.session_state[_FILENAME_DERIVE_APPLIED_KEY] = fd["applied"]
            widgets = fd.get("widgets")
            if isinstance(widgets, dict):
                for key, value in widgets.items():
                    if value is not None:
                        st.session_state[key] = value
        if isinstance(config.get("keep_and_filter"), dict):
            kf = config["keep_and_filter"]
            # UX-114: the per-table picks are the real source of truth — each
            # `wizard_keep_<prefix>` widget re-derives `wizard_filter_fields`
            # itself once the mapping resolves, so seeding those (rather than
            # the flat legacy keys) is what actually reproduces the setup.
            by_table = kf.get("wizard_keep_by_table")
            if isinstance(by_table, dict):
                for prefix, cols in by_table.items():
                    if isinstance(cols, list):
                        st.session_state[f"wizard_keep_{prefix}"] = list(cols)
            elif kf.get("wizard_keep_extra") is not None:
                # A setup saved before UX-114 only has the flat cross-table
                # list — apply it to both tables; each one's picker prunes
                # away whatever it doesn't actually offer.
                cols = list(kf["wizard_keep_extra"])
                for prefix in ("col_map_words", "col_map_fix", "col_map_raw_gaze"):
                    st.session_state[f"wizard_keep_{prefix}"] = list(cols)
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


def _filename_derive_section() -> dict | None:
    """The ``filename_derive`` section for a saved config (UX-113 Phase 3): the
    committed derivation (``_FILENAME_DERIVE_APPLIED_KEY``) plus the live
    widget values needed to redisplay the control on restore. ``None`` when
    nothing has been applied — an absent section is the honest "not used"."""
    applied = st.session_state.get(_FILENAME_DERIVE_APPLIED_KEY)
    if not applied:
        return None
    return {
        "applied": applied,
        "widgets": {
            "wizard_filename_split": st.session_state.get("wizard_filename_split"),
            "wizard_filename_column": st.session_state.get("wizard_filename_column"),
            "wizard_filename_mode": st.session_state.get("wizard_filename_mode"),
            "wizard_filename_delim": st.session_state.get("wizard_filename_delim"),
            "wizard_filename_regex": st.session_state.get("wizard_filename_regex"),
            "wizard_filename_regex_lower": st.session_state.get(
                "wizard_filename_regex_lower"
            ),
        },
    }


def _keep_and_filter_section() -> dict | None:
    """The ``keep_and_filter`` section for a saved config (UX-113 Phase 3,
    reshaped per-table by UX-114). ``None`` when nothing was touched.

    UX-114 replaced the two cross-table pickers (``wizard_filter_by`` /
    ``wizard_keep_extra``) with one per-table multiselect each
    (``wizard_keep_<prefix>``) — a **new, additively-named** key,
    ``wizard_keep_by_table``, carries those; the old flat keys are still
    written too (kept in sync from the per-table picks) so a setup saved here
    still restores cleanly through any older reader of this section. No
    ``PLOT_CONFIG_SCHEMA`` bump — this whole section is already optional and
    read defensively.
    """
    by_table = {
        # UX-120: raw gaze joined the two tables with their own keep-picker.
        prefix: list(st.session_state[key])
        for prefix in ("col_map_words", "col_map_fix", "col_map_raw_gaze")
        if (key := f"wizard_keep_{prefix}") in st.session_state
        and st.session_state[key]
    }
    filter_fields = st.session_state.get("wizard_filter_fields")
    if not by_table and not filter_fields:
        return None
    return {
        "wizard_keep_by_table": by_table or None,
        "wizard_filter_by": filter_fields,
        "wizard_keep_extra": sorted({c for cols in by_table.values() for c in cols})
        or None,
    }


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
        "filename_derive": _filename_derive_section(),
        "keep_and_filter": _keep_and_filter_section(),
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
    re-applied later via the wizard's *Restore a saved setup* step. Rendered
    beside the **Add dataset** button (UX-53)."""
    host.download_button(
        # UX-93: short enough to sit on ONE line at the ✕ Cancel width the
        # footer now uses — "Download setup (JSON)" wrapped to two, making the
        # pair 55 px and 40 px tall side by side. What it saves and how to load
        # it back is on the tooltip, where the sentence was already.
        "⬇️ Save setup",
        data=json.dumps(_wizard_setup_config(), indent=2),
        file_name="scanpath_studio_setup.json",
        mime="application/json",
        key="wizard_setup_download",
        width="stretch",
        help="Save this column mapping to re-use on similar data — restore it "
        "from *Restore a saved setup* at the top of Column mapping.",
    )


#: UX-93 — the wizard's footer row. `1.4` is the ✕ Cancel width from the sticky
#: bar's `[7.2, 2.2, 1.4]`, so the two things you do with a finished setup are
#: the same size as the way out of it, side by side, with the rest of the line
#: left empty. They used to be either two full-width banners stacked (the
#: blocked path) or a 50/50 split of the whole section (the finished path) —
#: neither of which reads as "two buttons".
_FOOTER_ROW_W = (1.4, 1.4, 8.0)


def _wizard_footer(host, *, disabled: bool, help_text: str, on_click=None) -> None:
    """⬇️ Save setup · ✅ Add dataset, one line, matched widths (UX-93).

    One place for all three endings — blocked on required fields, blocked on a
    mapping the pipeline rejected, and finished — which is what keeps them the
    same size and the same colour. ✅ Add dataset is `primary` on every path:
    it is the page's one commit, and #UX-66 r2 already paired ✕ Cancel with it
    in the same filled blue, as the two ends of one decision.

    UX-113: the row is keyed so `styles.py` can widen the two button columns
    (and shrink the empty `_rest` one) on a narrow screen — `_FOOTER_ROW_W`'s
    compact desktop width leaves each button too few pixels there, and "Save
    setup" / "Add dataset" wrap to two lines.

    UX-113 also gave it a real `st.divider()` above — heavier and more spaced
    (its own keyed container, `styles.py` widens the margin on both sides)
    than the mapping blocks' own hairline (`.sps-wiz-blockgap`) on purpose:
    this is the one commit for the *whole* wizard, not the end of stage 5, and
    it should read as a clear break rather than one more row under Recording
    setup.
    """
    divider_host = host.container(key="wizard_footer_divider")
    divider_host.divider()
    row = host.container(key="wizard_footer_row")
    save_col, add_col, _rest = row.columns(
        _FOOTER_ROW_W, gap="small", vertical_alignment="center"
    )
    _render_setup_download(save_col)
    add_col.button(
        "✅ Add dataset",
        type="primary",
        key="wizard_finalize",
        disabled=disabled,
        on_click=on_click,
        width="stretch",
        help=help_text,
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


def _setup_mode(
    host,
    group: str,
    options: list,
    help_text: str,
    label=None,
    *,
    key_prefix: str = "wizard",
):
    """One setup group's radio, namespaced for add or edit.

    Returns the chosen label or ``None``. The mode keys are wizard-local UI state
    and deliberately **not** wire format (same reasoning as ``share_identity_mode``
    in ``url_state.py``): what travels is the resolved value plus its provenance,
    not which radio button produced it.

    ``label`` overrides the heading for display only (UX-58). Three groups
    side by side leave no room for *Physical size & viewing distance*, and a
    heading that wraps to two lines drops its column out of line with the other
    two — which is the whole point of the row. `SETUP_GROUP_LABELS` stays the
    name everything else reports by.
    """
    # UX-90: every setup group is mandatory — *Add dataset* stays disabled until
    # each says how it is known — so each carries the same trailing `*` the
    # required mapping fields do. One convention for "you must answer this",
    # rather than a starred column mapping above an unstarred set of questions.
    return host.radio(
        f"{label or SETUP_GROUP_LABELS[group]} *",
        options,
        index=None,
        key=f"{key_prefix}_setup_{group}_mode",
        help=help_text,
    )


def _wizard_setup_step(
    host,
    words_raw,
    fix_raw,
    has_boxes: bool,
    *,
    key_prefix: str = "wizard",
    initial: SetupSnapshot | None = None,
    publish: bool = True,
) -> SetupSnapshot:
    """Render the three Recording-setup groups and resolve them to a snapshot.

    Writes the resolved values into the existing ``global_*`` wire-format keys
    (unchanged — the *values* were always wire format; only the provenance is
    new). Safe to write here because the wizard owns the page: ``app.main``
    returns before the rail renders, so no widget on a ``global_*`` key exists
    this run.
    """
    # UX-58: three columns, one per group, so their headings sit at the same
    # line height. Each column starts with its own radio, which is what keeps
    # them level even though what follows differs per answer (two number inputs,
    # an info box, or a caption) and so the columns end at different heights.
    # The description that used to print here is now the section's hover text.
    screen_host, geom_host, text_host = host.columns(3, gap="medium")

    # The Data Management editor reuses this exact control layout. Seed its
    # three mode choices from the saved snapshot once; the add flow keeps its
    # deliberate unanswered state because ``initial`` is None.
    if initial is not None:
        screen_modes = {
            Provenance.MEASURED: _SCREEN_KNOW,
            Provenance.ESTIMATED: _SCREEN_ESTIMATE,
            Provenance.ASSUMED: _SCREEN_DEFAULT,
        }
        geometry_modes = {
            Provenance.MEASURED: _GEOM_KNOW,
            Provenance.ASSUMED: _GEOM_DEFAULT,
            Provenance.SKIPPED: _GEOM_SKIP,
        }
        text_mode = (
            _TEXT_BOXES
            if initial.scale_text_to_boxes and has_boxes
            else _TEXT_DEFAULT
            if initial.text_provenance is Provenance.ASSUMED
            else _TEXT_FONT
        )
        st.session_state.setdefault(
            f"{key_prefix}_setup_screen_mode",
            screen_modes.get(initial.screen_provenance, _SCREEN_KNOW),
        )
        st.session_state.setdefault(
            f"{key_prefix}_setup_geometry_mode",
            geometry_modes.get(initial.geometry_provenance, _GEOM_DEFAULT),
        )
        st.session_state.setdefault(f"{key_prefix}_setup_text_mode", text_mode)

    # --- Screen -------------------------------------------------------------
    screen_mode = _setup_mode(
        screen_host,
        "screen",
        [_SCREEN_KNOW, _SCREEN_ESTIMATE, _SCREEN_DEFAULT],
        "The presentation monitor's resolution in pixels. Everything is drawn in "
        "these coordinates.",
        label="Screen",
        key_prefix=key_prefix,
    )
    est_w, est_h = compute_canvas_size(words_raw, fix_raw)
    canvas_w = (
        initial.canvas_width if initial is not None else _recalled("canvas_width", 2560)
    )
    canvas_h = (
        initial.canvas_height
        if initial is not None
        else _recalled("canvas_height", 1440)
    )
    if screen_mode == _SCREEN_KNOW:
        w_col, h_col = screen_host.columns(2, gap="small")
        canvas_w = w_col.number_input(
            "Width (px)",
            100,
            10000,
            int(canvas_w),
            key=f"{key_prefix}_setup_screen_w",
        )
        canvas_h = h_col.number_input(
            "Height (px)",
            100,
            10000,
            int(canvas_h),
            key=f"{key_prefix}_setup_screen_h",
        )
    elif screen_mode == _SCREEN_ESTIMATE:
        canvas_w, canvas_h = est_w, est_h
        screen_host.info(
            f"Estimated **{est_w} × {est_h} px** from the extent of your word "
            "boxes and fixations. This is a **lower bound** — text rarely fills "
            "the whole screen, so the real monitor was probably larger."
        )
    elif screen_mode == _SCREEN_DEFAULT:
        canvas_w, canvas_h = 2560, 1440
        screen_host.caption("Recorded as **assumed** — a common 1440p monitor.")

    # --- Physical size & viewing distance -----------------------------------
    geom_mode = _setup_mode(
        geom_host,
        "geometry",
        [_GEOM_KNOW, _GEOM_DEFAULT, _GEOM_SKIP],
        "Needed only to express distances in degrees of visual angle. Skipping is "
        "a real answer — the app then hides the numbers it cannot honestly derive.",
        label="Physical size",
        key_prefix=key_prefix,
    )
    mon_mm = float(
        initial.monitor_width_mm
        if initial is not None
        else _recalled("monitor_width_mm", 597.0)
    )
    dist_mm = float(
        initial.viewing_distance_mm
        if initial is not None
        else _recalled("viewing_distance_mm", 800.0)
    )
    if geom_mode == _GEOM_KNOW:
        mon_mm = geom_host.number_input(
            "Monitor width (mm)",
            50.0,
            2000.0,
            mon_mm,
            key=f"{key_prefix}_setup_monitor_mm",
        )
        dist_mm = geom_host.number_input(
            "Viewing distance (mm)",
            50.0,
            5000.0,
            dist_mm,
            key=f"{key_prefix}_setup_distance_mm",
        )
        if canvas_w and mon_mm > 0 and dist_mm > 0:
            geom_host.caption(
                f"→ **{pixels_per_degree(dist_mm, canvas_w, mon_mm):.1f} px** per "
                "degree of visual angle."
            )
    elif geom_mode == _GEOM_DEFAULT:
        mon_mm, dist_mm = 597.0, 800.0
        geom_host.caption("Recorded as **assumed** — typical lab values.")
    elif geom_mode == _GEOM_SKIP:
        geom_host.caption(
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
        text_host,
        "text",
        text_options,
        "How big the reading text was drawn. Word labels are rendered at this size "
        "so the figure matches what the participant saw.",
        label="Text size",
        key_prefix=key_prefix,
    )
    scale_to_boxes = True
    base_font = int(
        initial.base_font_size
        if initial is not None
        else _recalled("base_font_size", 16)
    )
    font_family = str(
        initial.font_family
        if initial is not None
        else _recalled("font_family", FONT_FAMILY)
    )
    if text_mode == _TEXT_BOXES:
        scale_to_boxes = True
        text_host.caption(
            "Label size is derived from each word box — the usual choice."
        )
    elif text_mode == _TEXT_FONT:
        scale_to_boxes = False
        initial_font_pt = float(_recalled("stimulus_font_pt", 12.0))
        if initial is not None and mon_mm > 0 and geom_mode != _GEOM_SKIP:
            initial_dpi = float(canvas_w) / (float(mon_mm) / 25.4)
            initial_font_pt = float(initial.base_font_size) * 72.0 / initial_dpi
        font_pt = text_host.number_input(
            "Stimulus font (pt)",
            4.0,
            96.0,
            initial_font_pt,
            key=f"{key_prefix}_setup_font_pt",
        )
        font_family = text_host.text_input(
            "Font family", value=font_family, key=f"{key_prefix}_setup_font_family"
        )
        # pt→px needs a DPI, which needs the physical width. Under a skipped
        # geometry group there is no honest DPI, so the conversion is withheld
        # and the point size falls back to being read as pixels.
        if geom_mode == _GEOM_SKIP:
            text_host.warning(
                "Converting points to pixels needs the monitor's physical width, "
                "which was skipped above. The size is being read as **pixels**; "
                "answer *Physical size & viewing distance* for a true pt → px "
                "conversion."
            )
            base_font = int(min(max(round(font_pt), 6), 72))
        else:
            dpi = float(canvas_w) / (float(mon_mm) / 25.4) if mon_mm > 0 else 96.0
            base_font = int(min(max(round(font_pt_to_px(font_pt, dpi)), 6), 72))
            text_host.caption(f"→ **{base_font} px** at {dpi:.0f} DPI.")
    elif text_mode == _TEXT_DEFAULT:
        scale_to_boxes = False
        base_font = 16
        text_host.caption("Recorded as **assumed** — a 16 px reading font.")

    snapshot = SetupSnapshot(
        canvas_width=int(canvas_w),
        canvas_height=int(canvas_h),
        monitor_width_mm=float(mon_mm),
        viewing_distance_mm=float(dist_mm),
        base_font_size=int(base_font),
        font_family=font_family,
        line_spacing=float(
            initial.line_spacing
            if initial is not None
            else st.session_state.get("global_line_spacing", 3.0)
        ),
        scale_text_to_boxes=bool(scale_to_boxes),
        screen_provenance=_SETUP_PROVENANCE.get(screen_mode),
        geometry_provenance=_SETUP_PROVENANCE.get(geom_mode),
        text_provenance=_SETUP_PROVENANCE.get(text_mode),
    )

    # Publish the snapshot for the save/restore + export writers. A partial one
    # resolves to None, so `current_setup_section` writes nothing rather than an
    # all-defaults section that would read as a real answer.
    if publish:
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
    if publish and snapshot.screen_provenance is not None:
        st.session_state["global_canvas_width"] = snapshot.canvas_width
        st.session_state["global_canvas_height"] = snapshot.canvas_height
        recall["canvas_width"] = snapshot.canvas_width
        recall["canvas_height"] = snapshot.canvas_height
    if publish and snapshot.geometry_provenance not in (None, Provenance.SKIPPED):
        st.session_state["global_monitor_width_mm"] = snapshot.monitor_width_mm
        st.session_state["global_viewing_distance_mm"] = snapshot.viewing_distance_mm
        recall["monitor_width_mm"] = snapshot.monitor_width_mm
        recall["viewing_distance_mm"] = snapshot.viewing_distance_mm
    if publish and snapshot.text_provenance is not None:
        st.session_state["global_base_font_size"] = snapshot.base_font_size
        st.session_state["global_font_family"] = snapshot.font_family
        st.session_state["global_scale_text_to_boxes"] = snapshot.scale_text_to_boxes
        recall["base_font_size"] = snapshot.base_font_size
        recall["font_family"] = snapshot.font_family
    if publish and recall:
        _remember_setup(recall)

    # UX-90 — an error, not a warning, and only once the user has actually tried
    # to add. Before that an unanswered question is one they have not reached
    # yet, and saying so in yellow on arrival made the page open already
    # complaining. Same rule the mapping fields follow
    # (`controls.ADD_ATTEMPTED_KEY`), so one click now turns the whole page red
    # at once instead of it nagging in two different tenses.
    unanswered = [g for g, p in snapshot.provenance.items() if p is None]
    if publish and unanswered and st.session_state.get(ADD_ATTEMPTED_KEY):
        host.error(
            "Still to answer: "
            + ", ".join(f"**{SETUP_GROUP_LABELS[g]}**" for g in unanswered)
            + ". Each needs to say how you know it before the dataset can be "
            "added."
        )
        _mark_missing_setup_groups(unanswered)
    return snapshot


def _mark_missing_setup_groups(unanswered: list) -> None:
    """Ring the unanswered required setup radios in red (UX-90).

    One ``<style>`` block for all of them, targeting each radio's `.st-key-…`
    container — the same technique as `controls._emit_field_tints`, and for the
    same reason: a wrapper element per group would be more DOM on a page whose
    whole problem is length.

    A ring and a red label rather than a fill: the group is a list of radio
    options, and tinting three option rows reads as three separate problems
    instead of one unanswered question.
    """
    keys = [_SETUP_MODE_KEYS[group] for group in unanswered]
    box = ", ".join(f".st-key-{key} > div" for key in keys)
    label = ", ".join(f".st-key-{key} label p" for key in keys)
    st.markdown(
        "<style>"
        f"{box} {{ border: 1px solid rgba(239, 68, 68, 0.85);"
        " border-radius: 0.4rem; padding: 0.35rem 0.5rem;"
        " background: rgba(239, 68, 68, 0.06); }"
        f"{label} {{ color: rgb(239, 68, 68); }}"
        "</style>",
        unsafe_allow_html=True,
    )


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
        app.render_canvas_controls(
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
        "adds the questions to the Stimulus & Context panel.",
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


#: UX-55 r4 — `table name | Trial ID | Screen ID | Participant ID | Text ID |
#: Word/IA ID | Fixation ID-or-Word text` — row 1 of the per-table block, now
#: merged with what used to be a separate "geometry" section (r3/r4:
#: identity-vs-description stopped paying for itself once Screen name left the
#: view and Word/IA id joined the row it already read as identity). The name
#: column stays narrow for one short word; the six pickers split the rest
#: evenly — a column name is what has to stay readable, and six is the most
#: this row fits.
#: UX-127: the name column widened from 0.09 to 0.135 (and the CSS overlay's
#: `width` in `styles.py` alongside it) — the file uploader's own "Browse
#: files" button didn't fit inside the narrower column. The six picker cells
#: shrink slightly (evenly) to make room.
_ID_ROW1_W = (0.135, 0.1444, 0.1444, 0.1444, 0.1444, 0.1444, 0.1444)

#: Row 2 of the Fixations block: X · Y · Timestamp · Duration. Same grid as
#: row 1 (UX-55 r2) so the two halves of the mapping line up down the page —
#: four equal picker cells under the name column, since these selects hold
#: column names rather than short ids.
_FIX_ROW2_W = (0.135, 0.2163, 0.2163, 0.2163, 0.2163)

#: Row 2 of the AOI block: the word box (a format radio plus four coordinate
#: selects that lay themselves out) and, sharing the same line, Line index —
#: the box gets most of the row, Line index the rest (UX-55 r3).
_AOI_ROW2_W = (0.135, 0.694, 0.171)

#: Row 2 of the Raw gaze block (UX-113): X · Y · Timestamp — no Duration, raw
#: gaze has no such concept (unlike row 1, which reuses `_ID_ROW1_W` outright:
#: same six identity fields, same shape as Fixations/AOI above it).
_RAW_GAZE_ROW2_W = (0.135, 0.2883, 0.2883, 0.2884)

#: UX-127: the metadata rows' own two-cell grid — same name-column width as
#: every other table's row 1, one wide cell for the id-column + keep-fields
#: picker stack (there is nothing to split across several picker cells here).
_META_ROW_W = (0.135, 0.865)


def _hover_note(host, label: str, note: str, *, link: str = "") -> None:
    """A short label whose explanation is only on hover (UX-53 round 3).

    The wizard's prose was the bulk of its length, and most of it is read once
    and never again. This keeps a scannable anchor on the page and puts the
    sentences behind the same `.sps-fhelp` tooltip the rail's labels use — a CSS
    one (120 ms), not the browser's native `title=`, which waits about a second
    and so is unusable for text people actually need.
    """
    tail = (
        f' <a href="{html.escape(link, quote=True)}" target="_blank">↗</a>'
        if link
        else ""
    )
    host.markdown(
        f'<div class="sps-wiz-note"><span class="sps-fhelp" '
        f'data-tip="{html.escape(note, quote=True)}">{html.escape(label)}</span>'
        f"{tail}</div>",
        unsafe_allow_html=True,
    )


def _mark_add_attempted() -> None:
    """Record that **✅ Add dataset** was pressed on a still-incomplete wizard.

    UX-53's red state is deliberately not shown on arrival: a required field the
    user has not reached yet is *unfilled*, not wrong. It turns red only once
    they have asked for the dataset to be added.
    """
    st.session_state[ADD_ATTEMPTED_KEY] = True


def _wizard_name_header(host, active: bool) -> None:
    """The dataset's name, its own numbered stage (UX-53 r8, UX-113).

    It used to sit in step 7 beside *Add dataset*, i.e. below every mapping
    field. The name is what the whole dataset is *called*, so it belongs to
    neither the upload nor the mapping — it leads the wizard, in its own keyed
    box that `styles.py` sizes up.
    """
    if not active:
        return
    st.session_state.setdefault("wizard_dataset_name", _default_dataset_name())
    box = host.container(key="wiz_name_box")
    box.text_input(
        "Dataset name",
        key="wizard_dataset_name",
        help="Shown in the Data source list so you can switch back to it.",
        placeholder="Name this dataset",
        # UX-113: the numbered stage heading above ("1 Dataset name") already
        # says this — the widget's own label just repeated it verbatim.
        label_visibility="collapsed",
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
    # UX-114: "fields" no longer has widgets of its own — it reads whichever
    # per-table keep picker(s) exist (`wizard_keep_<prefix>`, one per mapped
    # table).
    fields_touched = any(
        ss.get(f"wizard_keep_{prefix}")
        for prefix in ("col_map_words", "col_map_fix", "col_map_raw_gaze")
    )

    def required(done: bool) -> wizard_shell.StepStatus:
        if done:
            return S.DONE
        # ACTION ("blocked on something specific") only once there is data to act
        # on; before that the step is simply not started.
        return S.ACTION if uploaded_any else S.TODO

    statuses = {
        "name": S.DONE if (ss.get("wizard_dataset_name") or "").strip() else S.TODO,
        "data": S.DONE if uploaded_any else S.TODO,
        "identity": required(trial_mapped),
        "geometry": required(uploaded_any and not problems),
        "setup": required(setup_answered),
        # DATA-20: optional until a table is actually attached. Reads the parsed
        # frame, not the uploader widget — the frame is what survives a rerun.
        "readers": (
            S.DONE if ss.get(metadata_mod.RAW_SESSION_KEY) is not None else S.OPTIONAL
        ),
        # UX-114: "fields" is not a numbered part any more (its pickers moved
        # into "mapping", one per table) — the key stays for any bookkeeping
        # that still badges it by name, and it's OPTIONAL so it never blocks
        # "mapping" from reaching DONE below.
        "fields": S.DONE if fields_touched else S.OPTIONAL,
    }
    # UX-53/UX-113/UX-114: "identity"/"geometry" are still *sections* nested
    # inside the "mapping" step, so it aggregates them — a part is only DONE
    # when every required section under it is. "setup" is a step of its own
    # and does not roll up into this one. The section keys stay in the dict
    # because the section headings, the blocker list and
    # `_wizard_problems_last` all still badge per topic.
    statuses["mapping"] = (
        S.DONE
        if all(statuses[k] is S.DONE for k in ("identity", "geometry"))
        else required(False)
    )
    return statuses


def _mapping_label(mapping) -> str | None:
    """A human-readable column name for a mapping value (str | list | None)."""
    if not mapping or mapping == NONE_OPTION:
        return None
    if isinstance(mapping, (list, tuple)):
        return " + ".join(str(c) for c in mapping) or None
    return str(mapping)


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
        # UX-66 — ONE row, and it stays put while the page scrolls: the title,
        # the guide button, the docs link, and the way out. Everything else that
        # used to stack above the wizard is gone (the page header and its summary
        # in `app.main`, the "Adding a dataset…" caption in
        # `resolve_data_source`, and the second copy of this very title
        # that lived here) — four headings for one screen, from three modules.
        #
        # Keyed so `styles.py` can pin it; the CSS is scoped to this key alone,
        # so only the add-dataset screen gets a sticky bar.
        bar = st.container(key="wiz_sticky_bar")
        title_col, help_col, cancel_col = bar.columns(
            [7.2, 2.2, 1.4], vertical_alignment="center"
        )
        title_col.markdown(
            '<div class="sps-wiz-title">Set up your dataset</div>',
            unsafe_allow_html=True,
        )
        # Step-by-step guide: a bottom-right card that auto-opens once per session
        # and is replayable via the popover below. Arm it (auto/first-visit) then
        # render the card early so it streams before the heavy upload/normalize
        # work.
        maybe_show_wizard_guide()
        render_spotlight_wizard_guide()
        # UX-84: one ❓ Help popover replaces the two buttons that used to sit
        # here (🧭 guide · 📖 docs) — a popover, not a dialog, since it is a
        # two-item chooser with no modal weight to it (matches #UX-65's nav
        # Help, minus the "arm-then-bounce" dance that menu entries need).
        with help_col.popover("❓ Help", width="stretch"):
            render_wizard_guide_button(st)
            # A real `link_button`, not an in-app navigation: it opens in a new
            # tab and so cannot lose an in-progress upload the way switching
            # views would — the same reason #BUG-31's leave prompt exists.
            st.link_button(
                # UX-66 r2: named for what it *is* rather than for the page it
                # opens — "Data guide" reads like one more wizard step on a row
                # of wizard controls, which is the one thing it is not.
                "📖 More documentation ↗",
                "https://lacclab.github.io/scanpath-studio/bring-your-own-data/",
                help="What your export needs, worked EyeLink and plain-CSV "
                "examples, and what each failure symptom means.",
                width="stretch",
            )
        # The way out, on the row that stays on screen.
        #
        # BUG-36: checked by return value, not `on_click` — arms the same
        # leave-prompt the nav-triggered leave uses (`_render_leave_prompt`
        # below reads it later in this same run), rather than calling
        # `app.leave_add_data_wizard` straight away, which discarded an
        # in-progress upload with no confirmation at all. It has to be the
        # return-value form here too: `app.main`'s hold-the-view prologue pops
        # `WIZARD_LEAVE_KEY` at the top of every run whenever the nav is
        # already on 🗂️ Data — true for the whole time the wizard is open — so
        # an `on_click` callback (which runs *before* that prologue) would have
        # its flag wiped before `_render_leave_prompt` ever saw it. Setting it
        # here, after the prologue has already run this pass, is what makes it
        # stick for the `_render_leave_prompt(bar)` call three lines down.
        if cancel_col.button(
            "✕ Cancel",
            key="cancel_add_data",
            # UX-66 r2: the same filled blue as ✅ Add dataset. The two are the
            # ends of the same decision — commit or leave — and a ghost button
            # beside a filled one reads as the disabled half of a pair rather
            # than as the other way out.
            type="primary",
            help="Leave the wizard and go back to the dataset you were on.",
            width="stretch",
        ):
            st.session_state[WIZARD_LEAVE_KEY] = _VIEW_DATA
        _render_leave_prompt(bar)
        # UX-53 r8 / UX-113: no progress chips. They were navigation for an
        # accordion that no longer exists — the five parts are linear, so there
        # is nothing to flip between and a chip row would be a menu with one
        # path through it.
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

    # Five linear parts. `part()` while the wizard is active — a one-line
    # numbered headline, no expander — and `step_panel`'s bold-heading
    # degradation in the collapsed *Data & mapping* review panel, which is
    # itself an expander and so can nest neither.
    def _part(step_id: str, *, trailing=None):
        step = wizard_shell.STEPS_BY_ID[step_id]
        status = statuses.get(step_id, wizard_shell.StepStatus.TODO)
        if active:
            # UX-88: no status badge. `step_panel` already refuses one (a keyed
            # expander that changes label remounts collapsed); the headline was
            # the last place a ⚠️ could nag about a field visible on the same
            # screen.
            return wizard_shell.part(body, step, trailing=trailing)
        return wizard_shell.step_panel(body, step, status, active=False)

    # UX-53 r8 / UX-113: the dataset's **name** is its own numbered stage — it
    # names the whole thing, so it belongs to neither the upload nor the
    # mapping — rendered first since nothing after it makes sense without one.
    s_name = _part("name")
    _wizard_name_header(s_name, active)

    def _render_restore_trigger(host) -> None:
        # UX-127: beside stage 2's title now, not stage 3's — UX-113's reason
        # (it never touches the uploads themselves) no longer separates the
        # two stages, since every table now uploads *inside* stage 3 too;
        # what actually matters is that a restored setup is visible before
        # the wizard is filled in, and stage 2 is the first thing on screen.
        restore_box = host.popover("↩️ Restore a saved setup (optional)")
        _wizard_restore_config(restore_box)
        _render_restored_config_caption(restore_box)

    # UX-114: the "Dataset format" choice + the MultiplEYE branch it dispatches
    # to are held back this release (mirrors PRE-21/PRE-22's gate) — the code
    # stays for a later revival, but with the flag off there is no format
    # *question* at all, on either Add or Edit dataset (this function backs
    # both). Force the key rather than relying on the `.get(..., "Generic")`
    # fallback below, so a stale "MultiplEYE" left over from an earlier,
    # flagged session can't sneak back in.
    _multipleye_enabled = multipleye_upload_enabled()
    if not _multipleye_enabled:
        st.session_state["wizard_dataset_format"] = "Generic"

    # Restoring a config seeds `col_map_*` keys, which mean nothing on the
    # MultiplEYE branch (no column mapping there) — read from state, same as
    # the format-dispatch check below, since the picker itself hasn't
    # (re-)rendered yet at this point in the script.
    _generic_format = (
        st.session_state.get("wizard_dataset_format", "Generic") != "MultiplEYE"
    )
    s1 = _part(
        "data",
        trailing=_render_restore_trigger if active and _generic_format else None,
    )
    s_map = _part("mapping")

    # === 1 · Upload data tables ==============================================
    if active and _multipleye_enabled:
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
    if (
        _multipleye_enabled
        and st.session_state.get("wizard_dataset_format", "Generic") == "MultiplEYE"
    ):
        return _render_multipleye_upload(body, active)

    # The run-locally tip keeps its always-created container: a *conditional*
    # child here shifts the element tree mid-parse and Streamlit leaves a
    # greyed-out ghost of the whole upload group on screen (BUG-2).
    intro = s1.container()
    core_uploaded = bool(
        st.session_state.get("col_map_fix_upload")
        or st.session_state.get("col_map_words_upload")
    )
    already_uploaded = core_uploaded or bool(
        st.session_state.get("col_map_raw_gaze_upload")
    )
    if active and not already_uploaded:
        # UX-113: a small caption near the stage title, not a boxed alert — the
        # three tables below say the same thing at their own titles' hover, this
        # is just the nudge to open with.
        intro.caption(
            "⬆️ Upload at least one of **Fixations**, **Words / IA**, or "
            "**Raw gaze** in **Map data fields** below to get started."
        )
        app_url = str(getattr(st.context, "url", "") or "")
        if not is_loopback_url(app_url):
            intro.markdown(
                "💡 **Working with a large dataset?** It's faster — and keeps your "
                "data on your own machine — to run Scanpath Studio locally:\n\n"
                "```bash\npip install scanpath-studio\nscanpath-studio\n```"
            )

    # UX-124: the size/type line `st.file_uploader` prints under its own
    # dropzone ("5GB per file • CSV, TSV, …") doesn't fit this narrow column
    # either — `styles.py` hides it there, so it needs to survive somewhere:
    # appended to `help_text`, which already reaches both the title's hover
    # tooltip and the uploader's own accessible help.
    _upload_types_note = (
        ", ".join(t.upper() for t in app._UPLOAD_TYPES)
        + f" — up to {UPLOAD_MAX_SIZE_MB // 1000}GB per file."
    )

    def upload_box(
        host, *, label, help_text, prefix, multi, noun, kind=None, short_label=None
    ):
        # UX-113: the title reads like every mapping field's — dotted underline,
        # the description on hover (`.sps-fhelp`) — instead of Streamlit's own
        # label + native (~1s) help tooltip. UX-123: `short_label` is what
        # actually shows — the narrow row-name column this now renders into
        # (UX-122) is too tight for "Fixations table(s)"/"Words / IA
        # table(s)", which just ellipsised. The accessible name and the
        # uploader's own tooltip still carry the full `label`/`help_text`.
        inline_field_label(host, short_label or label, help_text, emphasis=True)
        frame = app._read_uploaded_frame(
            uploader_label=label,
            upload_help=help_text,
            state_prefix=prefix,
            multi=multi,
            container=host,
            kind=kind,
            label_visibility="collapsed",
        )
        if not frame.empty:
            # PERF-6 parses only the columns the mapping needs, so the frame's
            # own width is the *plan*, not the file's. Count the header, which
            # is what the user is being asked to check against their export.
            n_columns = len(app._uploaded_header(prefix)) or len(frame.columns)
            # UX-117/118/119: a small caption, like the metadata tables' own
            # "✓ N identified" — the row/column count was a full-width green
            # banner, disproportionate next to a one-line join caption. The
            # preview trigger and the count sit in one `stats` container
            # (`styles.py` turns it into a packed flex row, the same trick
            # `railbtn_*` uses) rather than `st.columns` — a ratio-based
            # column always reserves its ratio's share of the row even once
            # its content is `width="content"`-sized, which is what left a gap
            # between an icon-sized button and the text that used to follow
            # it two columns later.
            stats = host.container(key=f"wiz_upload_stats_{prefix}")
            if active:
                # UX-117: the preview used to sit permanently on the page —
                # several rows tall per table, three tables wide. A hover-only
                # reveal was tried first, but `st.dataframe`'s canvas grid
                # (glide-data-grid) sizes itself once at mount via
                # ResizeObserver and never recovers from mounting inside a
                # zero-size/hidden box, so it stayed blank even once "shown".
                # A popover sidesteps that: Streamlit doesn't render its body
                # at all until opened, so the grid always mounts visible.
                # UX-119: icon-only trigger (no "Preview" label) — way smaller,
                # matching the rail's other icon-only popovers (⇅, ✏️).
                preview = stats.popover(
                    "👁️", width="content", help="Preview — first rows"
                )
                preview.caption("First rows:")
                preview.dataframe(frame.head(), width="stretch", hide_index=True)
            # UX-124: two short lines, not one that has to wrap mid-count in
            # this narrow column — and no leading "✓", which read as a stray
            # mark once split from a sentence it no longer shares a line with.
            counts = stats.container(key=f"wiz_upload_counts_{prefix}")
            counts.caption(f"{len(frame):,} {noun}")
            counts.caption(f"{n_columns} columns")
        return frame

    # UX-122/UX-127: none of the six tables upload here any more — each has
    # its own uploader in "3 Map data fields", replacing that table's
    # row-name label (see `row_fix`/`row_words`/`rg_row1`/`_render_metadata_
    # uploads` below). `raw_fix`/`raw_words`/`raw_gaze` are placeholders
    # until those rows render; this stage now holds only the intro note.
    raw_fix, raw_words, raw_gaze = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def _render_metadata_uploads(word_schema, fix_schema) -> None:
        """DATA-20/DATA-29's participant + trial tables, plus the text table —
        UX-127: three more rows of the same "left = upload, right = mapping"
        format Fixations/AOI/Raw gaze use above, under a small **Metadata**
        heading, rather than the three-wide block of their own this used to
        be in stage 2. `word_schema`/`fix_schema` are `{}` pre-upload — there
        is nothing to derive a join report from yet, which is also the
        correct answer — and the real mapping once identity (stage 3) has
        resolved it. Still only while `active`: the collapsed *Data &
        mapping* review panel would otherwise build the same widget keys as
        the 🗂️ Data page's section.
        """
        if not active:
            return
        from scanpath_studio.tabs import (
            render_participant_metadata_section,
            render_text_metadata_section,
            render_trial_metadata_section,
        )

        meta_host.markdown(
            '<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True
        )
        inline_field_label(
            meta_host,
            "Metadata",
            "Optional per-reader, per-trial and per-text tables. Once "
            "attached, their columns behave like fields in the data: "
            "filters, chips, trial sorting, inspection and export.",
            emphasis=True,
        )

        def _meta_row(slug, renderer, ids):
            block = meta_host.container(key=f"wiz_map_block_meta_{slug}")
            row = block.columns(_META_ROW_W, gap="small")
            # UX-116: `live_join=False` — there is no finished dataset to join
            # against yet (the pools below are provisional, still shifting as
            # identity mapping is worked out), so the wizard only collects the
            # upload + id-column + keep-fields choices here. The real join
            # runs once, in `_finalize_wizard_dataset`, against the dataset's
            # own settled pools — see `tabs.commit_deferred_metadata`.
            renderer(
                ids,
                host=row[1],
                live_join=False,
                upload_host=row[0].container(key=f"wiz_map_upload_meta_{slug}"),
            )

        _meta_row(
            "participant",
            render_participant_metadata_section,
            _wizard_reader_ids(raw_words, word_schema, raw_fix, fix_schema),
        )
        meta_host.markdown(
            '<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True
        )
        _meta_row(
            "trial",
            render_trial_metadata_section,
            _wizard_trial_combos(raw_words, word_schema, raw_fix, fix_schema),
        )
        meta_host.markdown(
            '<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True
        )
        _meta_row(
            "text",
            render_text_metadata_section,
            _wizard_text_ids(raw_words, word_schema, raw_fix, fix_schema),
        )

    # === 2 · Map data fields =================================================

    # UX-71: this screen's dropdowns hold column names, so their option lists
    # get to be wider than the selects they drop from (see the docstring — it is
    # per-screen because the menu is portalled out of our DOM and cannot be
    # scoped any other way).
    s_map.markdown(mapping_menu_css(), unsafe_allow_html=True)

    # Reserve-then-fill, in reading order: the mapping sections, then the counts,
    # then the footer. UX-67 moved the trial/reader/text counts down here from
    # under the identity rows -- they are a check you run *before committing*,
    # so they belong beside "Add dataset", not three sections above it.
    sections_host = s_map.container()
    counts_host = s_map.container()

    # UX-113: no heading — it is the first, usually only thing under "3 Map
    # data fields" now that `setup`/`fields` are their own stages (only a
    # raw-gaze upload adds a second, titled "Raw gaze" section below), so a
    # sub-heading here just repeated the stage title above it.
    s2 = sections_host.container()

    # UX-122: each table's own uploader replaces its plain row-name label —
    # there is no separate "Upload data files" step for these three tables
    # any more (only the metadata tables still upload in stage 2), so the row
    # — and its uploader — has to exist before we know whether that table has
    # data. Fixations then AOI always render, in that fixed order, each
    # resolving `has_fix`/`has_words` and reserving its own feature/keep rows
    # immediately (UX-89: a table's rows stay adjacent, not batched by kind)
    # before the next table's row begins.
    id_rows = {}
    feature_rows = {}
    extra_rows = {}
    keep_rows = {}

    # UX-123: "Derive columns from the filename" stays the first thing in
    # this stage, as it was before UX-122 — reserved here (screen order is
    # creation order) and filled in further down, once the uploads below it
    # have actually run and there is something to derive from.
    derive_host = s2.container()
    derive_gap = s2.container()

    # UX-125: each table's own block (row 1 + row 2 + keep-picker) is wrapped
    # in its own container so the uploader — `position: absolute` inside it,
    # see `styles.py` — can center against the *whole* block's height, not
    # just row 1's (which the uploader itself was already taller than,
    # defeating `vertical_alignment="center"` on row 1 alone).
    fix_block = s2.container(key="wiz_map_block_col_map_fix")
    row_fix = fix_block.columns(_ID_ROW1_W, gap="small", vertical_alignment="center")
    raw_fix = upload_box(
        row_fix[0].container(key="wiz_map_upload_col_map_fix"),
        label="Fixations table(s)",
        short_label="Fixations",
        help_text="One or more files (e.g. one per participant); concatenated. "
        + _upload_types_note,
        prefix="col_map_fix",
        multi=True,
        noun="fixations",
        kind="fixations",
    )
    has_fix = not raw_fix.empty
    if has_fix:
        id_rows["fix"] = row_fix[1:]
        feature_rows["fix"] = fix_block.columns(
            _FIX_ROW2_W, gap="small", vertical_alignment="bottom"
        )
        keep_rows["fix"] = fix_block.container()

    s2.markdown('<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True)
    words_block = s2.container(key="wiz_map_block_col_map_words")
    row_words = words_block.columns(
        _ID_ROW1_W, gap="small", vertical_alignment="center"
    )
    raw_words = upload_box(
        row_words[0].container(key="wiz_map_upload_col_map_words"),
        label="Words / IA table(s)",
        short_label="AOIs",
        help_text="One or more files (e.g. one per text); concatenated. "
        + _upload_types_note,
        prefix="col_map_words",
        kind="words",
        multi=True,
        noun="words",
    )
    has_words = not raw_words.empty
    if has_words:
        id_rows["words"] = row_words[1:]
        feature_rows["words"] = words_block.columns(
            _AOI_ROW2_W, gap="small", vertical_alignment="bottom"
        )
        extra_rows["words"] = words_block.container()
        keep_rows["words"] = words_block.container()

    # UX-113: stages 3-5 render unconditionally now, rather than exiting here
    # before any of them exist — every `has_words`/`has_fix`/`raw_gaze.empty`
    # guard below already tolerates all three being empty (the same guards the
    # raw-gaze-only path needed), so there is nothing left to special-case.
    # `raw_gaze` itself uploads a little further down (its own row), so
    # `nothing_uploaded` is finalized there.
    prop_w = (
        _c_propose_word_schema(raw_words, frame_fingerprint(raw_words))
        if has_words
        else {}
    )
    prop_f = (
        _c_propose_fix_schema(raw_fix, frame_fingerprint(raw_fix)) if has_fix else {}
    )
    word_schema: dict = {}
    fix_schema: dict = {}

    # Column derivation must run *before* the identifier pickers so the
    # derived columns are mappable below. UX-53 took it out of its popover —
    # "advanced" is a reason to place a control last, not to hide it behind a
    # click — so it renders inline, below the pickers it feeds. UX-113: no
    # longer gated on `source_file` specifically — the tool derives from any
    # uploaded column now, so any non-empty table is reason enough to offer
    # it. UX-122/123: it needs the Fixations/AOI uploads above to already
    # exist, which by this point in the script they do — but it still
    # *renders* above them, into `derive_host`/`derive_gap`, reserved before
    # either row so screen order puts it first regardless of fill order.
    if has_words or has_fix:
        raw_words, raw_fix, raw_gaze = _wizard_filename_derive(
            derive_host,
            raw_words,
            raw_fix,
            raw_gaze,
        )
        derive_gap.markdown(
            '<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True
        )

        # `_render_identity_field` takes its cells in (fixations, AOI) order.
        def _cells_for(index: int) -> list:
            return [id_rows[s][index] for s in ("fix", "words") if s in id_rows]

        id_extras = counts_host
        # Row 1, in the order the request pins: Trial ID · Screen ID ·
        # Participant ID · Text ID · Word/IA ID · Fixation ID-or-Word text.
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
            cells=_cells_for(0),
            extras_host=id_extras,
        )
        # Screen ID (DATA-21 multipart) — a simple per-table field, not a
        # composite like Trial/Participant/Text, so it goes straight through
        # `_map_section` rather than `_render_identity_field`. Screen *name*
        # (`screen_index`) is dropped from the view entirely (UX-55 r4): order
        # within a multipart trial still comes from it when it is mapped and
        # from first appearance when it is not (multipart.normalize_screen_
        # identity), so the column stays auto-detected — see Background for
        # why the field itself is gone rather than merely unlabelled.
        screen_specs = (
            ("fix", raw_fix, FIX_FIELD_SPECS, prop_f, fix_schema, has_fix),
            ("words", raw_words, WORD_FIELD_SPECS, prop_w, word_schema, has_words),
        )
        for slug, raw, specs, proposal, schema, present in screen_specs:
            if not present or slug not in id_rows:
                continue
            schema.update(
                _map_section(
                    raw,
                    specs,
                    proposal,
                    f"col_map_{slug}",
                    id_rows[slug][1],
                    ["screen_id"],
                )
            )
        _wizard_participant_text_step(
            "participant",
            "Participant ID",
            "readers",
            "The reader column — or several to compose an id. Leave empty for a "
            "single anonymous reader.",
            s2,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
            cells=_cells_for(2),
            extras_host=id_extras,
        )
        _wizard_participant_text_step(
            "text_id",
            "Text ID",
            "texts",
            "The text column — or several to compose an id. Leave empty to fall "
            "back to the trial id.",
            s2,
            raw_words,
            raw_fix,
            prop_w,
            prop_f,
            word_schema,
            fix_schema,
            has_words,
            has_fix,
            cells=_cells_for(3),
            extras_host=id_extras,
        )
        # Word/IA ID — the fixations table's own `word_id` says which AOI a
        # fixation hit; the AOI table's is which AOI a row *is*. Different
        # columns, same slot: both tables read it as identity now.
        for slug, raw, specs, proposal, schema, present in screen_specs:
            if not present or slug not in id_rows:
                continue
            schema.update(
                _map_section(
                    raw,
                    specs,
                    proposal,
                    f"col_map_{slug}",
                    id_rows[slug][4],
                    ["word_id"],
                )
            )
        # Row 1's last slot differs per table: Fixation ID for Fixations,
        # Word text/label for AOI.
        if has_fix:
            fix_schema.update(
                _map_section(
                    raw_fix,
                    FIX_FIELD_SPECS,
                    prop_f,
                    "col_map_fix",
                    id_rows["fix"][5],
                    ["fixation_id"],
                )
            )
        if has_words:
            word_schema.update(
                _map_section(
                    raw_words,
                    WORD_FIELD_SPECS,
                    prop_w,
                    "col_map_words",
                    id_rows["words"][5],
                    ["text"],
                )
            )

        # Row 2 of each block: the table's own features, filled into the cells
        # reserved above so they sit directly under that table's identity row.
        # UX-89 also removed the per-block validation warnings that used to
        # print here ("Words/IA — missing Word/IA ID", …): a required field that
        # is empty turns red in place the moment ✅ Add dataset is pressed, and
        # a sentence repeating it below the row was the third copy of the same
        # complaint on a page whose problem is length.
        if has_fix:
            for cell, key in zip(
                feature_rows["fix"][1:], ["x", "y", "timestamp", "duration"]
            ):
                fix_schema.update(
                    _map_section(
                        raw_fix, FIX_FIELD_SPECS, prop_f, "col_map_fix", cell, [key]
                    )
                )
        if has_words:
            # The box (a format radio plus four coordinate selects that lay
            # themselves out) and Line index share the row (UX-55 r3).
            words_row2 = feature_rows["words"]
            word_schema.update(
                _map_section(
                    raw_words,
                    WORD_FIELD_SPECS,
                    prop_w,
                    "col_map_words",
                    words_row2[1],
                    ["box"],
                )
            )
            word_schema.update(
                _map_section(
                    raw_words,
                    WORD_FIELD_SPECS,
                    prop_w,
                    "col_map_words",
                    words_row2[2],
                    ["line"],
                )
            )
            # UX-104 — line 3 of the AOI block. One row per *character* is a
            # fact about this table, so the question sits with the fields that
            # describe it, not in a later section the user reads after they
            # have stopped thinking about the AOI file. UX-118: indented to
            # where the pickers above start (`_row_body`), not the row-name
            # label — this line has no name of its own, it describes the AOI
            # table above it.
            aoi_extra = _row_body(extra_rows["words"])
            aggregate_char_boxes_on = aoi_extra.toggle(
                "Aggregate character AOIs into word boxes",
                key="wizard_aggregate_char_boxes",
                help="For interest-area tables with one row per *character* "
                "(e.g. CJK corpora): collapse the characters of each word "
                "(grouped by the Trial + Word/IA id above) into one bounding "
                "box.",
            )
            # UX-113: only relevant once aggregating — a table whose rows are
            # grouped into sub-screen blocks that each restart their own word
            # numbering (e.g. a comprehension question's answer blocks) needs
            # to say so, or two blocks' word 0 would silently merge into one
            # box (see data.aggregate_char_boxes).
            if aggregate_char_boxes_on:
                word_schema.update(
                    _map_section(
                        raw_words,
                        WORD_FIELD_SPECS,
                        prop_w,
                        "col_map_words",
                        aoi_extra,
                        ["block"],
                    )
                )

    # UX-104 — the raw-gaze block. UX-113: same "name column + evenly split
    # pickers" grid as the Fixations/AOI blocks above (a single generic
    # `column_mapping_ui` grid read as a cramped, differently-shaped block
    # beside them). UX-122: its own uploader replaces the "Raw gaze" label
    # in row 1's name column, so — like Fixations/AOI above — row 1 always
    # renders (there is nowhere else to upload); row 2 and everything below
    # only once there is something to map.
    # UX-125: keyed like `fix_block`/`words_block` above — the raw-gaze
    # uploader centers against this whole block's height too.
    s3 = sections_host.container(key="wiz_map_block_col_map_raw_gaze")
    # UX-127: reserved here, right after `s3` (raw gaze) — a sibling of `s2`/
    # `s3` in `sections_host`, so whatever `_render_metadata_uploads` fills
    # into it later lands after all three main tables' rows in the DOM,
    # regardless of how late in the script it actually runs.
    meta_host = sections_host.container()
    if has_words or has_fix:
        # A hairline under the identity block above, same as the gap
        # between the Fixations and AOI blocks — nothing to separate from
        # on a raw-gaze-only upload, where this is the first block.
        s3.markdown('<div class="sps-wiz-blockgap"></div>', unsafe_allow_html=True)
    # Row 1: Trial ID · Screen ID · Participant ID · Text ID · Word/IA ID ·
    # Word text/label — same six-cell grid, same field order, as the
    # Fixations/AOI row above.
    rg_row1 = s3.columns(_ID_ROW1_W, gap="small", vertical_alignment="center")
    raw_gaze = upload_box(
        rg_row1[0].container(key="wiz_map_upload_col_map_raw_gaze"),
        label="Raw gaze table (optional)",
        short_label="Raw gaze",
        help_text="Millisecond-level gaze overlay (one file). " + _upload_types_note,
        prefix="col_map_raw_gaze",
        multi=False,
        noun="gaze points",
    )
    # UX-113: stages 3-5 render unconditionally now, rather than exiting here
    # before any of them exist — every `has_words`/`has_fix`/`raw_gaze.empty`
    # guard below already tolerates all three being empty (the same guards the
    # raw-gaze-only path needed), so there is nothing left to special-case.
    nothing_uploaded = raw_words.empty and raw_fix.empty and raw_gaze.empty
    prop_g = (
        _c_propose_raw_gaze_schema(raw_gaze, frame_fingerprint(raw_gaze))
        if not raw_gaze.empty
        else {}
    )
    if not raw_gaze.empty:
        # Row 2: X · Y · Timestamp — no Duration, raw gaze has no such concept.
        rg_row2 = s3.columns(_RAW_GAZE_ROW2_W, gap="small", vertical_alignment="bottom")
        raw_gaze_schema: dict = {}
        row1_keys = ["trial", "screen_id", "participant", "text_id", "word_id", "text"]
        for cell, key in zip(rg_row1[1:], row1_keys):
            raw_gaze_schema.update(
                _map_section(
                    raw_gaze,
                    RAW_GAZE_FIELD_SPECS,
                    prop_g,
                    "col_map_raw_gaze",
                    cell,
                    [key],
                )
            )
        for cell, key in zip(rg_row2[1:], ["x", "y", "timestamp"]):
            raw_gaze_schema.update(
                _map_section(
                    raw_gaze,
                    RAW_GAZE_FIELD_SPECS,
                    prop_g,
                    "col_map_raw_gaze",
                    cell,
                    [key],
                )
            )
        # UX-120: the same per-table "extra fields to keep" picker
        # Fixations/AOI have — raw gaze had none, because
        # `normalize_raw_gaze` had no mechanism to carry an extra column
        # through at all (it built an entirely fresh frame from only the
        # schema-mapped columns). It does now (`_carry_extra_columns`), so
        # this table gets the same choice, no registry of known-optional
        # fields to offer (there is no raw-gaze equivalent of
        # `saccade_amplitude` common enough to earn a canonical name) —
        # every unmapped column is offered as a plain extra to keep.
        rg_kept, rg_meta = _wizard_table_keep_picker(
            s3.container(),
            raw_gaze,
            raw_gaze_schema,
            [],
            "col_map_raw_gaze",
            noun="Raw gaze",
        )
    else:
        raw_gaze_schema = {}
        rg_kept, rg_meta = set(), []

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

    # UX-53 r5 removed the auto-detect summary card ("✓ Trial id — Trial_Id",
    # "⚠️ Word box — not detected", …). It restated, in a block of its own, what
    # every field now shows in place: the ✨ flag and the select's tint say
    # detected-or-not per row, and a genuinely missing required field turns red
    # and is listed above ✅ Add dataset. Since the fields all live on one screen
    # now, the summary was a second copy of what was directly below it.

    # UX-114: "Keep extra fields" is no longer a stage of its own — each
    # table's own decision now sits directly under that table's own mapping
    # (the `keep_rows[slug]` containers reserved above), so there is nothing
    # left to render at this point except collect the two tables' results.
    keep_by_prefix: dict = {}
    filter_fields: list = []
    if has_words:
        kept, meta = _wizard_table_keep_picker(
            keep_rows["words"],
            raw_words,
            word_schema,
            WORD_OPTIONAL_FIELDS,
            "col_map_words",
            noun="AOI",
        )
        keep_by_prefix["col_map_words"] = kept
        filter_fields += meta
    if has_fix:
        kept, meta = _wizard_table_keep_picker(
            keep_rows["fix"],
            raw_fix,
            fix_schema,
            FIX_OPTIONAL_FIELDS,
            "col_map_fix",
            noun="Fixations",
        )
        keep_by_prefix["col_map_fix"] = kept
        filter_fields += meta
    keep_by_prefix["col_map_raw_gaze"] = rg_kept
    filter_fields += rg_meta
    # The same dest field (e.g. "difficulty") can legitimately come from both
    # tables — `_wizard_table_keep_picker` decides per table, so de-dup here,
    # order-preserving.
    st.session_state["wizard_filter_fields"] = list(dict.fromkeys(filter_fields))

    # DATA-20's participant table (and DATA-29's trial/text tables) render as
    # three more rows of this same stage (UX-127) — they are uploads, and
    # they belong with the others. Called down here, after identity (stage 3)
    # has resolved the real mapping, so the join report reads the up-to-date
    # schema rather than the `{}` an earlier call would have had to use.
    _render_metadata_uploads(word_schema, fix_schema)

    # UX-113: "Recording setup" is stage 5 — its own numbered part. Its old
    # caption ("These describe the screen the data was recorded on…") now lives
    # as the WizardStep's own hover caption.
    s_setup = _part("setup")
    restored_setup = _restored_setup_snapshot()
    if restored_setup is not None:
        _apply_restored_setup(restored_setup)
        s_setup.caption(
            "✓ Pre-answered from the restored setup file — review it below."
        )
    setup_snapshot = _wizard_setup_step(
        s_setup, raw_words, raw_fix, has_boxes=has_words
    )

    # The foot of the wizard: what is still missing, then the button. UX-53 put
    # the alerts *directly above* **Add dataset** — a blocker listed a screen
    # away from the control it blocks is a blocker the user reads after
    # clicking. UX-113: now trails all five stages, not just "Map data fields".
    s6 = body.container()

    setup_blockers = [
        SETUP_GROUP_LABELS[g] for g, p in setup_snapshot.provenance.items() if p is None
    ]
    # `nothing_uploaded` is its own term (not folded into `problems`/
    # `setup_blockers`): a restored setup config can answer every group with
    # nothing uploaded, which must still block — there is nothing to add.
    blocked = nothing_uploaded or bool(problems) or bool(setup_blockers)

    # UX-53 dropped the review table. Every figure in it is now stated where it
    # is decided — row counts beside each upload, the trial count under the trial
    # picker (`_wizard_trial_step`), the mapped column beside its own field, and
    # each setup value beside its provenance radio. Repeating them here made a
    # second screen out of things the user had just read.

    # UX-88: no "Still to do" list, and no status badges on the part headlines
    # or section headings above. The page said the same thing three times — a
    # badge on the part, a badge on its section, and a warning down here — for a
    # field the user can see is empty, on a page whose entire complaint has been
    # length. What is left is the one thing that actually points at the problem:
    # clicking ✅ Add dataset sets `ADD_ATTEMPTED_KEY`, which turns every unmapped
    # required row **red in place**. `blocked` still gates finalizing; it just
    # no longer narrates.

    if problems:
        if active:
            # UX-88 removed the *Still to do* list that used to print here on
            # arrival. What it must NOT remove is the answer to "I pressed Add
            # and nothing happened" — and for some blockers there is nothing
            # else to see: a raw-gaze-only upload whose trial id cannot be
            # mapped has no required field on screen to turn red, so with no
            # message at all the button is a dead end.
            #
            # So the problems still get stated, on exactly the terms UX-90 set
            # for the Recording-setup gate: red, and only once the user has
            # actually tried. Before that the page stays quiet.
            if st.session_state.get(ADD_ATTEMPTED_KEY):
                for line in problems:
                    s6.error(line)
            # Enabled, not disabled (UX-53). A disabled button cannot be *tried*,
            # and "red when you try to add with it empty" needs the attempt: the
            # click sets ADD_ATTEMPTED_KEY, which is what turns every unmapped
            # required row red on the rerun. It still cannot finalize — this
            # branch returns the problems either way.
            _wizard_footer(
                s6,
                disabled=False,
                on_click=_mark_add_attempted,
                help_text="Some required fields are still empty — they are "
                "marked in red above.",
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
                _wizard_footer(s6, disabled=True, help_text=problem)
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
            raw_gaze_norm = normalize_raw_gaze(
                raw_gaze,
                raw_gaze_schema,
                keep_columns=keep_by_prefix.get("col_map_raw_gaze", set()),
            )

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
        # UX-53: the two things you can do with a finished setup share one row —
        # save it for next time, or add it — instead of stacking two full-width
        # buttons. UX-93 made that row the same on all three endings.
        _wizard_footer(
            s6,
            disabled=blocked,
            on_click=_finalize_wizard_dataset,
            help_text=(
                "Upload a Fixations, Words/IA, or Raw gaze table above to get started."
                if nothing_uploaded
                else "Answer the Recording setup section first: "
                + ", ".join(setup_blockers)
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
