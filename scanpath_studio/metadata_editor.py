"""Participant, trial and text metadata controls for Data Management and the import wizard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import metadata as md
from .constants import ICONS, UPLOAD_FILE_TYPES, md_literal, plural, upload_limit_mb
from .data import (
    explain_read_error,
    header_only_error,
    read_table,
    read_table_columns,
    trial_id_series,
    trial_mapping_columns,
)
from .fields import row_label
from .upload_ui import say_read_error


def _clear_metadata(grain: str) -> None:
    """Forget the previous upload and the field choices made for its columns."""
    for key in (
        *md.grain_keys(grain),
        f"_{grain}_metadata_name",
        f"{grain}_metadata_id_column",
        f"{grain}_metadata_keep_fields",
    ):
        st.session_state.pop(key, None)


def _on_metadata_file_change(grain: str, widget: str) -> None:
    """Detach only when the user removes the last file from the uploader."""
    if not st.session_state.get(widget):
        _clear_metadata(grain)


def _attached_metadata_note(host, attached, *, grain: str) -> None:
    """Offer a detach action when the table outlives the file picker."""
    host.caption(
        f"**{md_literal(attached.source_name)}** · {plural(len(attached.fields), 'field')}. "
        "Upload the file again to change its ID column or fields."
    )
    host.button(
        "✕ Detach",
        key=f"{grain}_metadata_detach_restored",
        on_click=_clear_metadata,
        args=(grain,),
        help="Remove this table. Its fields leave the filters, the trial summary "
        "and trial sorting.",
    )


class _MetadataReadError(Exception):
    """One of a metadata table's files could not be read; names which, in the
    words every upload box uses (`say_read_error`)."""

    def __init__(self, name: str, cause: Exception) -> None:
        self.name = name
        self.cause = cause
        super().__init__(explain_read_error(name, cause).sentence())

    def say(self) -> None:
        """The message, where the metadata table's uploader is."""
        say_read_error(st, self.name, self.cause)


def _metadata_upload_signature(uploads) -> tuple:
    """What a metadata uploader holds, by each file's `file_id` — not its name
    and size: a corrected file of the same name and length must be read again
    (as in `controls._uploaded_image_data_uri`)."""
    return tuple(
        getattr(upload, "file_id", None) or (upload.name, getattr(upload, "size", None))
        for upload in uploads
    )


def _metadata_upload_name(uploads) -> str:
    """The files a metadata table was read from, for its "from **X**" captions."""
    first = uploads[0].name
    if len(uploads) == 1:
        return first
    return f"{first} + {plural(len(uploads) - 1, 'more file')}"


def _read_metadata_uploads(uploads, grain="participant", mapping=()) -> pd.DataFrame:
    """Every file uploaded for one metadata table, stacked into one table.

    A table split across files (one per session, one per lab) reads as one:
    columns line up by name, and a column a file lacks is empty for its rows.
    The same reader turning up in two files is what the builders already
    handle — combined when the rows agree, dropped and reported when not.
    """
    infer = {
        "participant": md.infer_participant_id_column,
        "trial": md.infer_trial_id_column,
        "text": md.infer_text_id_column,
    }[grain]
    frames = []
    for upload in uploads:
        try:
            header = read_table_columns(upload)
            plan = md.id_read_plan(mapping, infer)(header)
            if grain == "participant" and not mapping and not plan.identity and header:
                # The single-column picker selects the first column by default.
                plan = md.id_read_plan(header[0], infer)(header)
            frame = read_table(upload, plan=plan)
        except Exception as exc:  # unreadable file — the caller names it
            raise _MetadataReadError(upload.name, exc) from exc
        if frame.empty and len(frame.columns):
            # Attached, it would join nothing and say nothing.
            error = header_only_error(upload.name)
            raise _MetadataReadError(upload.name, error) from error
        frames.append(frame)
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, ignore_index=True, sort=False)


def _metadata_upload(grain: str, help_text: str, upload_host) -> pd.DataFrame | None:
    """Read a metadata upload once and show its preview beside the mapping controls."""
    host = st if upload_host is None else upload_host
    title = f"{grain.capitalize()} metadata table (optional)"
    row_label(
        host,
        title if upload_host is None else f"{grain.capitalize()}s",
        help_text,
        emphasis=True,
    )
    widget = md.upload_key(grain)
    uploads = host.file_uploader(
        title,
        type=list(UPLOAD_FILE_TYPES),
        key=widget,
        on_change=_on_metadata_file_change,
        args=(grain, widget),
        accept_multiple_files=True,
        help=help_text,
        label_visibility="collapsed",
        max_upload_size=upload_limit_mb(),
    )
    attached_key, raw_key, file_key = md.grain_keys(grain)
    if not uploads:
        attached = st.session_state.get(attached_key)
        if attached is not None:
            _attached_metadata_note(host, attached, grain=grain)
        return None

    signature = _metadata_upload_signature(uploads)
    previous = st.session_state.get(file_key)
    new_files = previous != signature
    mapping_key = f"{grain}_metadata_id_column"
    mapping = (
        tuple(trial_mapping_columns(st.session_state.get(mapping_key) or ()))
        if not new_files
        else ()
    )
    raw = st.session_state.get(raw_key)
    if new_files or raw is None or raw.attrs.get("metadata_id_mapping") != mapping:
        try:
            raw = _read_metadata_uploads(uploads, grain, mapping)
        except _MetadataReadError as exc:
            _clear_metadata(grain)
            exc.say()
            return None
        raw.attrs["metadata_id_mapping"] = mapping
        st.session_state[raw_key] = raw
    if new_files:
        # Mapping can stop until the user picks an ID in the new table.
        # No field from the preceding attachment should remain active then.
        st.session_state.pop(attached_key, None)
        if not isinstance(previous, tuple) or not set(previous).intersection(signature):
            st.session_state.pop(f"{grain}_metadata_keep_fields", None)
        st.session_state[file_key] = signature
        st.session_state[f"_{grain}_metadata_name"] = _metadata_upload_name(uploads)
        st.session_state.pop(f"{grain}_metadata_id_column", None)
        if grain == "trial":
            st.session_state.pop("trial_metadata_participant_column", None)

    raw = st.session_state.get(raw_key)
    if raw is None or raw.empty:
        return None
    stats = host.container(key=f"wiz_upload_stats_{grain}_metadata")
    preview = stats.popover(
        "Preview the first rows",
        icon=ICONS["preview"],
        width="content",
        wrap=True,
        help="Preview — first rows",
        key=f"iconpop_preview_{grain}_metadata",
    )
    preview.caption("First rows:")
    preview.dataframe(raw.head(), width="stretch", hide_index=True)
    counts = stats.container(key=f"wiz_upload_counts_{grain}_metadata")
    counts.caption(plural(len(raw), "row"))
    counts.caption(plural(len(raw.columns), "column"))
    return raw


def render_participant_metadata_section(
    participants, *, host=None, live_join: bool = True, upload_host=None
) -> None:
    """Edit participant metadata. The wizard defers matching until the dataset is saved.

    When supplied, ``upload_host`` holds the file picker and preview beside the mappings.
    """
    if host is not None:
        with host:
            _participant_metadata_body(
                participants, live_join=live_join, upload_host=upload_host
            )
        return
    _participant_metadata_body(
        participants, live_join=live_join, upload_host=upload_host
    )


def _participant_metadata_body(
    participants, *, live_join: bool = True, upload_host=None
) -> None:
    # The description rides the uploader's own title as a tooltip —
    # descriptive prose on this page is hover-only — in the same
    # dotted-underline format the mapping fields use (`row_label`),
    # rather than Streamlit's own label + native (~1s) help tooltip.
    _pm_help = (
        "One row per participant, with a participant-id column. Its columns "
        "work like fields in the data, in filters, the trial summary, "
        "trial sorting, inspection and export. CSV, TSV, Parquet or Excel; "
        "several files are stacked into one table."
    )
    raw = _metadata_upload("participant", _pm_help, upload_host)
    if raw is None:
        return

    columns = [str(column) for column in raw.columns]
    inferred = md.infer_participant_id_column(raw)
    key_host = st.container()
    status_host = st.container()
    id_column = key_host.selectbox(
        "Participant ID column *",
        columns,
        index=columns.index(inferred) if inferred in columns else 0,
        key="participant_metadata_id_column",
        persist_state="session",
        help="The column holding the participant id, used to join this table to "
        "your data. Required.",
    )
    # Which non-id columns actually become fields — right under the id
    # picker. How many are selected is in that picker's own label (see
    # `_metadata_keep_picker`).
    kept = _metadata_keep_picker(
        key_host, raw, id_column, prefix="participant_metadata", noun="participant"
    )
    if not live_join:
        # The wizard doesn't have a finished dataset to join against yet,
        # and a join report against a *provisional* reader pool (still
        # changing as identity mapping is worked out) would read as noise, or
        # worse — a wrong verdict. Nothing is matched or attached here;
        # `commit_deferred_metadata` does that once "✅ Add dataset" is clicked.
        return
    attached = md.build_participant_metadata(
        raw[[id_column, *kept]],
        id_column,
        source_name=str(
            st.session_state.get("_participant_metadata_name") or "participant table"
        ),
        participants=participants,
    )
    st.session_state[md.SESSION_KEY] = attached

    report = attached.report
    if not attached.fields:
        status_host.warning(
            "No fields kept. Pick at least one field above, or remove the "
            "uploaded file to detach this table.",
            icon=ICONS["warning"],
        )
        return
    id_count = _metadata_id_count(raw, id_column)
    matched = len(report.matched)
    if report.is_clean or matched:
        # One small combined line — the distinct-id count (independent of
        # the join) and the join result together.
        parts = _join_status_parts(id_count, report)
        parts.append(_combined_rows_note(report))
        status_host.caption(" · ".join(p for p in parts if p))
    else:
        # Zero matches is a silent trap (see `_render_key_mismatch`): the
        # fields attach, appear everywhere, and read as missing everywhere.
        # Loud on purpose — unlike the line above, this stays a real alert.
        with status_host:
            _render_key_mismatch(attached, report, "reader")


def render_trial_metadata_section(
    combos, *, host=None, live_join: bool = True, upload_host=None
) -> None:
    """Attach a trial-level table and report the join.

    The sibling of :func:`render_participant_metadata_section`, and deliberately
    the same shape: nothing is guessed, the key column is offered pre-filled
    but overridable, and the join result is reported before the fields go
    anywhere.

    **Trial id only, no reader column.** A table keyed by trial id
    alone describes a *text*, and every reading of that text inherits its
    row; a table keyed by reader *and* trial describes one *reading* — but
    this UI only attaches the first kind. The picker itself is a
    multiselect, exactly like the uploaded data's own Trial ID mapping: pick
    one column, or several to build a unique id on the fly (joined with "_"
    via :func:`data.trial_id_series`, through :func:`metadata.build_trial_metadata`).
    A row-per-reading table still reaches the app headlessly, via
    ``--trial-metadata-reader-column`` (:func:`api.load_trial_metadata`),
    which takes the ``participant_column`` parameter this screen does not
    expose.

    ``live_join=False`` — see :func:`render_participant_metadata_section`.
    ``upload_host`` — see :func:`render_participant_metadata_section`.
    """
    if host is not None:
        with host:
            _trial_metadata_body(combos, live_join=live_join, upload_host=upload_host)
        return
    _trial_metadata_body(combos, live_join=live_join, upload_host=upload_host)


def _trial_metadata_body(combos, *, live_join: bool = True, upload_host=None) -> None:
    # Same dotted-underline title format as the mapping fields.
    _tm_help = (
        "One row per trial, with a trial-id column. Its columns work like "
        "fields in the data, in filters, the trial summary, trial sorting, "
        "inspection and export. CSV, TSV, Parquet or Excel; several files are "
        "stacked into one table."
    )
    raw = _metadata_upload("trial", _tm_help, upload_host)
    if raw is None:
        return

    columns = [str(column) for column in raw.columns]
    inferred = md.infer_trial_id_column(raw)
    # Two slots, filled below, so the section reads as **one line**
    # once the table is in: the key pickers, then the verdict. Reserved in
    # this order because Streamlit's creation order is screen order and the
    # pickers have to run before the join they decide.
    key_host = st.container()
    status_host = st.container()
    # One key — the trial id — not a trial-id-plus-reader-id pair.
    # A row-per-reading table (one row per reader × trial) needs its own
    # reader column to disambiguate, which is not offered here; such a
    # table can be attached via the headless
    # `--trial-metadata-reader-column` (api.load_trial_metadata).
    trial_key = "trial_metadata_id_column"
    stored = st.session_state.get(trial_key)
    if not isinstance(stored, list):
        st.session_state[trial_key] = [inferred] if inferred in columns else []
    else:
        valid = [c for c in stored if c in columns]
        st.session_state[trial_key] = valid or (
            [inferred] if inferred in columns else []
        )
    row_label(
        key_host,
        "Trial ID column *",
        "The column holding this table's trial id, or several columns "
        "combined as in the data's Trial ID mapping. Each row applies to every "
        "participant's trial with that id. Required to join the table to the "
        "data.",
    )
    trial_columns = key_host.multiselect(
        "Trial ID column *",
        columns,
        key=trial_key,
        select_all=False,  # an id is a few columns, never all
        persist_state="session",
        label_visibility="collapsed",
    )
    if not trial_columns:
        status_host.warning(
            "Pick a Trial ID column above. It is required to join this table "
            "to the data.",
            icon=ICONS["warning"],
        )
        return
    # Which non-id columns actually become fields — right under the id
    # picker. How many are selected is in that picker's own label (see
    # `_metadata_keep_picker`).
    kept = _metadata_keep_picker(
        key_host, raw, trial_columns, prefix="trial_metadata", noun="trial"
    )
    if not live_join:
        # See the matching branch in `_participant_metadata_body`.
        return
    attached = md.build_trial_metadata(
        raw[[*trial_columns, *kept]],
        trial_columns,
        None,
        source_name=str(st.session_state.get("_trial_metadata_name") or "trial table"),
        keys=md.trial_keys(combos),
    )
    st.session_state[md.TRIAL_SESSION_KEY] = attached

    report = attached.report
    if not attached.fields:
        status_host.warning(
            "No fields kept. Pick at least one field above, or remove the "
            "uploaded file to detach this table.",
            icon=ICONS["warning"],
        )
        return
    grain = "trial"
    id_count = _metadata_id_count(raw, trial_columns)
    matched = len(report.matched)
    if report.is_clean or matched:
        # One small combined line — the distinct-id count (independent of
        # the join) and the join result together.
        parts = _join_status_parts(id_count, report)
        parts.append(_combined_rows_note(report))
        status_host.caption(" · ".join(p for p in parts if p))
    else:
        # Nothing matched. A quiet "Joined to 0 trials" would dress the *worst*
        # case as a status line: the table attaches, its fields appear in every
        # picker, and then every one of them renders as missing everywhere, with
        # nothing on screen connecting the two facts. It is an error, and it names
        # the two things that cause it, with both sides' ids side by side — nearly
        # always a spelling difference ("101" against "101.0", a float column
        # with one blank cell in it) or the wrong column picked above. Loud on
        # purpose — unlike the line above, this stays a real alert.
        with status_host:
            _render_key_mismatch(attached, report, grain)


def render_text_metadata_section(
    texts, *, host=None, live_join: bool = True, upload_host=None
) -> None:
    """Attach a text-level table and report the join — the third grain.

    Sibling of :func:`render_participant_metadata_section` and
    :func:`render_trial_metadata_section`, same shape: nothing is guessed, the
    key column is offered pre-filled but overridable, and the join result is
    reported before the fields go anywhere.

    Flat grain, like the participant table — one row per ``text_id``, never a
    reader-paired key, since a text is a stimulus rather than something one
    reader owns. The id picker is a multiselect like the trial table's,
    though: a text id can be composite (joined with "_" via
    :func:`data.trial_id_series`, through :func:`metadata.build_text_metadata`).

    ``live_join=False`` — see :func:`render_participant_metadata_section`.
    ``upload_host`` — see :func:`render_participant_metadata_section`.
    """
    if host is not None:
        with host:
            _text_metadata_body(texts, live_join=live_join, upload_host=upload_host)
        return
    _text_metadata_body(texts, live_join=live_join, upload_host=upload_host)


def _text_metadata_body(texts, *, live_join: bool = True, upload_host=None) -> None:
    _txm_help = (
        "One row per text, with a text-id column. Its columns work like "
        "fields in the data, in filters, the trial summary, trial sorting, "
        "inspection and export. CSV, TSV, Parquet or Excel; several files are "
        "stacked into one table."
    )
    raw = _metadata_upload("text", _txm_help, upload_host)
    if raw is None:
        return

    columns = [str(column) for column in raw.columns]
    inferred = md.infer_text_id_column(raw)
    key_host = st.container()
    status_host = st.container()
    text_key = "text_metadata_id_column"
    stored = st.session_state.get(text_key)
    if not isinstance(stored, list):
        st.session_state[text_key] = [inferred] if inferred in columns else []
    else:
        valid = [c for c in stored if c in columns]
        st.session_state[text_key] = valid or (
            [inferred] if inferred in columns else []
        )
    row_label(
        key_host,
        "Text ID column *",
        "The column holding this table's text id, or several columns combined "
        "as in the data's Text ID mapping. Required to join the table to the "
        "data.",
    )
    text_columns = key_host.multiselect(
        "Text ID column *",
        columns,
        key=text_key,
        select_all=False,  # an id is a few columns, never all
        persist_state="session",
        label_visibility="collapsed",
    )
    if not text_columns:
        status_host.warning(
            "Pick a Text ID column above. It is required to join this table "
            "to the data.",
            icon=ICONS["warning"],
        )
        return
    # Which non-id columns actually become fields — right under the id
    # picker. How many are selected is in that picker's own label (see
    # `_metadata_keep_picker`).
    kept = _metadata_keep_picker(
        key_host, raw, text_columns, prefix="text_metadata", noun="text"
    )
    if not live_join:
        # See the matching branch in `_participant_metadata_body`.
        return
    attached = md.build_text_metadata(
        raw[[*text_columns, *kept]],
        text_columns,
        source_name=str(st.session_state.get("_text_metadata_name") or "text table"),
        keys=texts,
    )
    st.session_state[md.TEXT_SESSION_KEY] = attached

    report = attached.report
    if not attached.fields:
        status_host.warning(
            "No fields kept. Pick at least one field above, or remove the "
            "uploaded file to detach this table.",
            icon=ICONS["warning"],
        )
        return
    id_count = _metadata_id_count(raw, text_columns)
    matched = len(report.matched)
    if report.is_clean or matched:
        # One small combined line — the distinct-id count (independent of
        # the join) and the join result together.
        parts = _join_status_parts(id_count, report)
        parts.append(_combined_rows_note(report))
        status_host.caption(" · ".join(p for p in parts if p))
    else:
        # Loud on purpose — unlike the line above, this stays a real alert:
        # a metadata table that joins to nothing says so.
        with status_host:
            _render_key_mismatch(attached, report, "text")


def _join_status_parts(id_count, report) -> list[str | None]:
    """A metadata table's join line: what is in it, what matched, and
    what did not — data rows without a table row, ids dropped as conflicting."""
    unmatched = len(report.only_in_data)
    conflicting = len(report.conflicting)
    return [
        f"{id_count:,} in the table" if id_count is not None else None,
        f"{len(report.matched):,} matched",
        f"{unmatched:,} in the data have no row" if unmatched else None,
        f"{conflicting:,} dropped (rows disagree)" if conflicting else None,
    ]


def _combined_rows_note(report) -> str | None:
    """``combined 2 compatible duplicate rows`` — or ``None`` when none were.

    Rows that repeat a key without disagreeing are folded into one, each field
    taking the one value they hold (`metadata._merge_duplicates`); the status
    line says so, so a table shorter than its file is not a surprise.
    """
    combined = int(getattr(report, "combined_rows", 0) or 0)
    if not combined:
        return None
    return (
        f"combined {combined:,} compatible duplicate row{'s' if combined != 1 else ''}"
    )


def _render_key_mismatch(attached, report, grain: str) -> None:
    """Nothing joined — say so, and show the two sides' ids.

    Shared by both metadata sections: zero matches is the one outcome that
    looks like success everywhere else in the app (the table attaches, its
    fields fill every picker) and is a total failure wherever a value is
    actually read. It names the columns the key was built from, because that is
    what the fix is.

    Quiet when the dataset has contributed **no** keys to match against. In the
    add-dataset wizard the table can be attached before the id column it joins
    on is mapped, and there is nothing wrong with that — shouting "nothing
    matched" at a user on their way to mapping it would be an error message for
    a step they have not reached.
    """
    if not report.only_in_data:
        st.caption(
            "Nothing to join to yet. Map this dataset's id column to see the "
            "report here."
        )
        return
    # Three grains, three attribute shapes — dispatch on which the attached
    # object actually carries rather than a passed-in type tag.
    if hasattr(attached, "id_column"):
        keyed = f", keyed by `{attached.id_column}`"
    elif hasattr(attached, "keyed_by_participant"):
        if attached.keyed_by_participant:
            keyed = (
                f", keyed by `{attached.participant_column}` + "
                f"`{attached.trial_column}`"
            )
        else:
            keyed = f", keyed by `{attached.trial_column}`"
    else:
        keyed = f", keyed by `{attached.text_column}`"
    st.error(
        f"**No {grain} in this dataset matched a row in that table**{keyed}. "
        "Its fields will read as missing until the ids match. Check the column "
        "picked above, or remove the uploaded file to detach the table.\n\n"
        f"In the table: {_id_list(list(report.only_in_table), limit=4)}  \n"
        f"In this dataset: {_id_list(list(report.only_in_data), limit=4)}\n\n"
        "A common cause is a trailing `.0` on one side. The id column was read "
        "as decimals in one file (one blank cell is enough) and as whole "
        "numbers in the other.",
        icon=ICONS["error"],
    )


def _id_list(ids, limit: int = 6) -> str:
    """``p1, p2, p3 …`` — enough to act on without flooding the page."""
    shown = ", ".join(f"`{value}`" for value in list(ids)[:limit])
    extra = len(ids) - limit
    return f"{shown} +{extra} more" if extra > 0 else shown


def _metadata_id_count(raw, mapping) -> int | None:
    """Distinct values of a metadata table's own id-column mapping.

    The same immediate "✓ N" feedback the wizard's own Trial ID field gives
    (`wizard._distinct_id_count`) — a sanity check on what the picked column(s)
    actually contain, independent of whether they go on to join anything.
    Reimplemented locally rather than imported: `wizard.py` imports from this
    module, so the reverse import would be a cycle."""
    if raw is None or getattr(raw, "empty", True) or not mapping:
        return None
    cols = trial_mapping_columns(mapping)
    if not cols or not all(c in raw.columns for c in cols):
        return None
    return int(trial_id_series(raw, mapping).nunique())


def _metadata_keep_picker(host, raw, id_columns, *, prefix: str, noun: str) -> list:
    """Which of a metadata table's non-id columns to register as fields —
    the metadata-table sibling of the wizard's own per-table "Extra fields to
    keep" picker. Everything not kept here never becomes a field: not
    filterable, not sortable, not a color-by option, not an info chip.
    Defaults to every non-id column, so ignoring this control keeps them all.
    """
    id_cols = (
        {str(c) for c in trial_mapping_columns(id_columns)} if id_columns else set()
    )
    options = [str(c) for c in raw.columns if str(c) not in id_cols]
    if not options:
        return []
    key = f"{prefix}_keep_fields"
    if key not in st.session_state:
        st.session_state[key] = list(options)
    else:
        stored = st.session_state[key]
        if isinstance(stored, list):
            opt_set = set(options)
            cleaned = [c for c in stored if c in opt_set]
            if len(cleaned) != len(stored):
                st.session_state[key] = cleaned

    # The selected-count is in this label, right where the count changes, so
    # it costs no vertical space of its own.
    n_selected = len(st.session_state.get(key, options))
    row_label(
        host,
        f"Extra fields to keep — {noun} · {n_selected} selected",
        "Columns besides the id. Keep the ones you want to filter, sort or "
        "color trials by, or show in the trial summary. Columns left out are not "
        "added.",
    )
    # No bulk-select buttons, as on the wizard's twin of this row: the
    # multiselect's select-all lives in its dropdown and its ✕ clears, so a
    # pair of buttons would only copy the widget's own controls.
    # `wrap=True`, as on the wizard's pickers — in a column the chips
    # otherwise stay on one row that scrolls sideways.
    return host.multiselect(
        f"Extra fields to keep — {noun}",
        options=options,
        key=key,
        label_visibility="collapsed",
        wrap=True,
    )


def commit_deferred_metadata(payload: dict) -> None:
    """Attach the wizard's pending uploads to the finalized dataset before its first run."""
    if all(
        st.session_state.get(key) is None
        for key in (
            md.RAW_SESSION_KEY,
            md.TRIAL_RAW_SESSION_KEY,
            md.TEXT_RAW_SESSION_KEY,
        )
    ):
        return
    readings = md.recording_keys(
        payload.get("fixations"), payload.get("words"), payload.get("raw_gaze")
    )
    raw = st.session_state.get(md.RAW_SESSION_KEY)
    id_column = st.session_state.get("participant_metadata_id_column")
    kept = st.session_state.get("participant_metadata_keep_fields") or []
    if raw is not None and not raw.empty and id_column and kept:
        st.session_state[md.SESSION_KEY] = md.build_participant_metadata(
            raw[[id_column, *kept]],
            id_column,
            source_name=str(
                st.session_state.get("_participant_metadata_name")
                or "participant table"
            ),
            participants=md.participant_ids(readings),
        )

    raw = st.session_state.get(md.TRIAL_RAW_SESSION_KEY)
    trial_columns = st.session_state.get("trial_metadata_id_column") or []
    kept = st.session_state.get("trial_metadata_keep_fields") or []
    if raw is not None and not raw.empty and trial_columns and kept:
        st.session_state[md.TRIAL_SESSION_KEY] = md.build_trial_metadata(
            raw[[*trial_columns, *kept]],
            trial_columns,
            None,
            source_name=str(
                st.session_state.get("_trial_metadata_name") or "trial table"
            ),
            keys=md.trial_keys(readings),
        )

    raw = st.session_state.get(md.TEXT_RAW_SESSION_KEY)
    text_columns = st.session_state.get("text_metadata_id_column") or []
    kept = st.session_state.get("text_metadata_keep_fields") or []
    if raw is not None and not raw.empty and text_columns and kept:
        st.session_state[md.TEXT_SESSION_KEY] = md.build_text_metadata(
            raw[[*text_columns, *kept]],
            text_columns,
            source_name=str(
                st.session_state.get("_text_metadata_name") or "text table"
            ),
            keys=md.text_keys(readings),
        )
