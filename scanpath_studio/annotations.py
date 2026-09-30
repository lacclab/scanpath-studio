"""Per-trial researcher annotations: favorites (stars), tags, and free notes.

Annotations are keyed by ``(participant_id, trial_id)`` and live in Streamlit
session state, so they persist across reruns within a session. There is no
backend; a local run keeps them in the recovery cache, and to share them 🗂️
Data → **Annotations** exports and imports a dataset's as JSON (UX-174). The
Scanpath view's Export bundle can include the same file (UX-179).

The module is split into a *pure* core (``records_to_store`` /
``store_to_records`` / ``serialize`` / ``deserialize`` — no Streamlit, unit
tested) and a thin session-backed layer plus the small render helpers used by
``tabs.py`` and ``app.py``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import pandas as pd
import streamlit as st

from .constants import ICONS, upload_limit_mb
from .fields import PANEL_LABEL_W, panel_field, row_label

ANNOTATIONS_STATE_KEY = "trial_annotations"
SCHEMA_VERSION = 2

# Per-trial annotation widgets use this prefix so they can be cleared on import
# (forcing a re-seed from the freshly loaded store), e.g. by `restore_records`.
_WIDGET_PREFIX = "annotrial_"

# Always-available tag suggestions (users can add their own on top).
PRESET_TAGS = ["To exclude", "Review", "Good example", "Check alignment"]

# Parent entries use ``(participant_id, trial_id)``; screen entries add a third
# ``screen_id`` component. Keeping parent keys unchanged preserves filtering and
# every schema-1 annotation sidecar.
Key = tuple[str, ...]
Entry = dict[str, object]


# ---------------------------------------------------------------------------
# Pure core (no Streamlit) — unit tested in tests/test_annotations.py
# ---------------------------------------------------------------------------


def default_entry() -> Entry:
    return {"star": False, "tags": [], "note": ""}


def _normalize_entry(star: object, tags: object, note: object) -> Entry:
    clean_tags = sorted({str(t).strip() for t in (tags or []) if str(t).strip()})
    return {"star": bool(star), "tags": clean_tags, "note": str(note or "").strip()}


def is_empty_entry(entry: Entry) -> bool:
    """True when an entry carries no information (and can be dropped)."""
    return (
        not entry.get("star")
        and not entry.get("tags")
        and not str(entry.get("note") or "").strip()
    )


def records_to_store(records: list[dict]) -> dict[Key, Entry]:
    """Build a ``{(pid, tid): entry}`` store from a list of flat records."""
    store: dict[Key, Entry] = {}
    for rec in records or []:
        pid = rec.get("participant_id")
        tid = rec.get("trial_id")
        if pid is None or tid is None:
            continue
        entry = _normalize_entry(
            rec.get("star", False), rec.get("tags", []), rec.get("note", "")
        )
        if not is_empty_entry(entry):
            screen_id = rec.get("screen_id")
            key = (
                (str(pid), str(tid), str(screen_id))
                if screen_id not in (None, "")
                else (str(pid), str(tid))
            )
            store[key] = entry
    return store


def store_to_records(store: dict[Key, Entry]) -> list[dict]:
    """Flatten a store into a sorted list of records for JSON export."""
    records = []
    for key, entry in sorted(store.items()):
        pid, tid, *screen = key
        record = {
            "participant_id": pid,
            "trial_id": tid,
            "star": bool(entry.get("star", False)),
            "tags": list(entry.get("tags", [])),
            "note": str(entry.get("note", "")),
        }
        if screen:
            record["screen_id"] = screen[0]
        records.append(record)
    return records


def serialize(store: dict[Key, Entry]) -> str:
    """Serialize a store to a JSON document string."""
    return json.dumps(
        {"schema": SCHEMA_VERSION, "annotations": store_to_records(store)}, indent=2
    )


def deserialize(text: str) -> dict[Key, Entry]:
    """Parse a JSON document (object with ``annotations`` or a bare list)."""
    data = json.loads(text)
    if isinstance(data, dict):
        records = data.get("annotations", [])
    elif isinstance(data, list):
        records = data
    else:
        records = []
    return records_to_store(records)


def _trial_of(key: Key) -> tuple[str, str]:
    return (key[0], key[1])


def _trial_set(trials: Iterable[tuple[object, object]]) -> frozenset[tuple[str, str]]:
    if isinstance(trials, frozenset):
        return trials  # already built by the caller, as strings
    return frozenset((str(pid), str(tid)) for pid, tid in trials)


def records_in(store: dict[Key, Entry], trials) -> list[dict]:
    """The records of ``store`` on the trials in ``trials``, sorted.

    ``trials`` is ``(participant_id, trial_id)`` pairs — one dataset's trials.
    The store is one per session and keyed by those two ids alone, so this is
    what *a dataset's annotations* means: the ones on trials it has. A screen
    annotation belongs to its parent trial.
    """
    keep = _trial_set(trials)
    return store_to_records(
        {key: entry for key, entry in store.items() if _trial_of(key) in keep}
    )


def merge_records(
    store: dict[Key, Entry], records: list[dict], trials
) -> tuple[int, int]:
    """Add ``records`` on the trials in ``trials`` to ``store``, in place.

    An imported entry replaces the one already on its key — the file is the
    newer statement about that trial — and a record for a trial the dataset
    does not have is skipped, as a backup restore skips what does not match
    (UX-174 r2). Returns ``(applied, skipped)``.
    """
    keep = _trial_set(trials)
    incoming = records_to_store(records)
    applied = {key: entry for key, entry in incoming.items() if _trial_of(key) in keep}
    store.update(applied)
    return len(applied), len(incoming) - len(applied)


def drop_records(store: dict[Key, Entry], records: list[dict]) -> int:
    """Remove the entries ``records`` name from ``store``. Returns how many."""
    removed = 0
    for record in records:
        pid, tid = str(record["participant_id"]), str(record["trial_id"])
        screen_id = record.get("screen_id")
        key = (pid, tid, str(screen_id)) if screen_id not in (None, "") else (pid, tid)
        if store.pop(key, None) is not None:
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# Session-backed layer
# ---------------------------------------------------------------------------


def _store() -> dict[Key, Entry]:
    return st.session_state.setdefault(ANNOTATIONS_STATE_KEY, {})


def get_entry(
    participant_id: str, trial_id: str, screen_id: str | None = None
) -> Entry:
    key = (
        (str(participant_id), str(trial_id), str(screen_id))
        if screen_id not in (None, "")
        else (str(participant_id), str(trial_id))
    )
    return _store().get(key, default_entry())


def set_entry(
    participant_id: str,
    trial_id: str,
    *,
    star: bool,
    tags: list[str],
    note: str,
    screen_id: str | None = None,
) -> None:
    """Upsert an annotation; empty entries are pruned to keep the store small."""
    key = (
        (str(participant_id), str(trial_id), str(screen_id))
        if screen_id not in (None, "")
        else (str(participant_id), str(trial_id))
    )
    entry = _normalize_entry(star, tags, note)
    store = _store()
    if is_empty_entry(entry):
        store.pop(key, None)
    else:
        store[key] = entry


def known_tags() -> list[str]:
    """Preset tags plus any tag used anywhere in the store, sorted."""
    tags: set[str] = set(PRESET_TAGS)
    for entry in _store().values():
        tags.update(entry.get("tags", []))
    return sorted(tags)


def current_records() -> list[dict]:
    """All annotations as a flat record list — for embedding in a saved config."""
    return store_to_records(_store())


def restore_records(records: list[dict]) -> int:
    """Replace the session annotation store from a record list (e.g. a restored
    config) and clear the per-trial widget state so editors re-seed. Returns the
    number of annotations loaded."""
    store = records_to_store(records or [])
    st.session_state[ANNOTATIONS_STATE_KEY] = store
    _reseed_trial_editors()
    return len(store)


def forget_records(records: list[dict]) -> int:
    """Drop ``records`` from the session store; the trial editors re-seed.

    Returns how many entries were removed.
    """
    removed = drop_records(_store(), records)
    if removed:
        _reseed_trial_editors()
    return removed


def _reseed_trial_editors() -> None:
    """Drop the per-trial editors' widget state, so they re-seed from the store."""
    for key in [
        k
        for k in list(st.session_state.keys())
        if isinstance(k, str) and k.startswith(_WIDGET_PREFIX)
    ]:
        del st.session_state[key]


# ---------------------------------------------------------------------------
# UI render helpers
# ---------------------------------------------------------------------------


def _add_tag_callback(tags_key: str, newtag_key: str) -> None:
    """on_change for the 'add tag' input: append to the multiselect's state.

    Runs before the next rerun, so writing the multiselect's session_state here
    is allowed (the widget hasn't been instantiated yet that run)."""
    new_tag = str(st.session_state.get(newtag_key, "")).strip()
    if not new_tag:
        return
    current = list(st.session_state.get(tags_key, []))
    if new_tag not in current:
        st.session_state[tags_key] = current + [new_tag]
    st.session_state[newtag_key] = ""


def _save_star_callback(
    participant_id: str,
    trial_id: str,
    screen_id: str | None,
    star_key: str,
) -> None:
    """Persist a favorite before the rerun rebuilds the trial picker.

    Widget callbacks run before the app body. Without this callback the picker
    reads the previous annotation store, then ``render_trial_annotations`` saves
    the new value later in the run — making the star marker appear one click
    behind the checkbox.
    """
    entry = get_entry(participant_id, trial_id, screen_id)
    set_entry(
        participant_id,
        trial_id,
        star=bool(st.session_state.get(star_key)),
        tags=list(entry["tags"]),
        note=str(entry["note"]),
        screen_id=screen_id,
    )


def render_trial_annotations(
    participant_id: str,
    trial_id: str,
    *,
    screen_id: str | None = None,
    bare: bool = False,
) -> None:
    """Render the per-trial annotations (star / tags / notes).

    ``bare=True`` drops the expander wrapper so it can sit inside a subtab."""
    annotation_screen = None
    if screen_id is not None:
        scope_key = f"{_WIDGET_PREFIX}scope_{participant_id}__{trial_id}"
        scope = panel_field(
            st,
            "radio",
            "Annotation scope",
            options=["Parent trial", "This screen"],
            key=scope_key,
            horizontal=True,
            help="Parent annotations follow the logical trial; screen annotations "
            "describe only the active coordinate space.",
        )
        if scope == "This screen":
            annotation_screen = str(screen_id)
    entry = get_entry(participant_id, trial_id, annotation_screen)
    slug = f"{participant_id}__{trial_id}__{annotation_screen or 'parent'}"
    star_key = f"{_WIDGET_PREFIX}star_{slug}"
    tags_key = f"{_WIDGET_PREFIX}tags_{slug}"
    note_key = f"{_WIDGET_PREFIX}note_{slug}"
    newtag_key = f"{_WIDGET_PREFIX}newtag_{slug}"

    # Seed widget state once from the store (re-seeds after a JSON import, which
    # clears these keys).
    st.session_state.setdefault(star_key, entry["star"])
    st.session_state.setdefault(tags_key, list(entry["tags"]))
    st.session_state.setdefault(note_key, entry["note"])

    label = f"{ICONS['annotations']} Annotations" + (
        f" {ICONS['favorite']}" if entry["star"] else ""
    )
    if entry["tags"]:
        label += f" · {', '.join(entry['tags'])}"
    container = st.container() if bare else st.expander(label, expanded=False)
    with container:
        # UX-69: `label | field` rows, so the five stacked controls fit under the
        # plot without scrolling. Unlike the rail (`controls._labeled`'s note),
        # the checkbox is split too: here the label column is the row spine every
        # other field lines up on, and a native checkbox would put its box —
        # not its title — at that edge.
        star = panel_field(
            st,
            "checkbox",
            f"{ICONS['favorite']} Favorite (star this trial)",
            display=f"{ICONS['favorite']} Favorite",
            key=star_key,
            help="Mark this trial as a favorite.",
            on_change=_save_star_callback,
            args=(participant_id, trial_id, annotation_screen, star_key),
        )
        # Options must include every currently-selected tag (incl. ones added
        # via the input) or st.multiselect raises.
        options = sorted(
            set(known_tags())
            | set(entry["tags"])
            | set(st.session_state.get(tags_key, []))
        )
        tags_help = "Select tags or add one."
        label_col, tags_col, add_col = st.columns(
            [PANEL_LABEL_W, 0.52, 0.28],
            gap="xsmall",
            vertical_alignment="center",
        )
        row_label(label_col, "Tags", tags_help)
        # ENG-49: built directly in a column, so it does not go through
        # `fields.labeled` and needs its own `wrap` — a trial's tags are the
        # thing this row exists to show, and 1.63 would otherwise scroll all
        # but the first one or two out of sight.
        tags = tags_col.multiselect(
            "Tags",
            options=options,
            key=tags_key,
            help=tags_help,
            label_visibility="collapsed",
            wrap=True,
        )
        add_col.text_input(
            "Add a tag",
            key=newtag_key,
            placeholder="Add a new tag",
            on_change=_add_tag_callback,
            args=(tags_key, newtag_key),
            label_visibility="collapsed",
        )
        # Top-aligned: the box is ~100px tall, and a centred title would float
        # opposite the middle of an empty note rather than beside its first line.
        note = panel_field(
            st,
            "text_area",
            "Notes",
            align="top",
            key=note_key,
            placeholder="Researcher notes for this trial…",
            height=100,
        )
        set_entry(
            participant_id,
            trial_id,
            star=star,
            tags=tags,
            note=note,
            screen_id=annotation_screen,
        )
        # UX-76: no shortcut button under this — the caption names where the
        # whole dataset's annotations are listed instead.
        st.caption(
            "Every annotation on this dataset is listed on 🗂️ **Data → "
            "Annotations**, to export, import or delete."
        )


def select_keys(
    store: dict[Key, Entry],
    keys: list[Key],
    *,
    favorites_only: bool = False,
    required_tags: list[str] | None = None,
    excluded_tags: list[str] | None = None,
) -> list[Key]:
    """Pure core of :func:`filter_keys` — filter ``keys`` against ``store``.

    - ``favorites_only``: keep only starred trials.
    - ``required_tags``: keep trials carrying *any* of these tags.
    - ``excluded_tags``: drop trials carrying *any* of these tags.
    """
    required = set(required_tags or [])
    excluded = set(excluded_tags or [])
    out: list[Key] = []
    for key in keys:
        entry = store.get(key)
        tags = set(entry.get("tags", [])) if entry else set()
        starred = bool(entry.get("star")) if entry else False
        if favorites_only and not starred:
            continue
        if required and not (tags & required):
            continue
        if excluded and (tags & excluded):
            continue
        out.append(key)
    return out


def filter_keys(
    keys: list[Key],
    *,
    favorites_only: bool = False,
    required_tags: list[str] | None = None,
    excluded_tags: list[str] | None = None,
) -> list[Key]:
    """Session-backed wrapper around :func:`select_keys`."""
    return select_keys(
        _store(),
        keys,
        favorites_only=favorites_only,
        required_tags=required_tags,
        excluded_tags=excluded_tags,
    )


# ---------------------------------------------------------------------------
# 🗂️ Data → Annotations (UX-174 r2)
# ---------------------------------------------------------------------------

#: The dataset tab's widget keys. The nonce is bumped after an import or a
#: delete, which gives the uploader and the table fresh keys: an uploader keeps
#: its file (and would import it again on every rerun), and a table's row
#: selection is by position, so it would point at other rows once some are gone.
_DATASET_NONCE_KEY = "_dataset_annotations_nonce"
_DATASET_NOTE_KEY = "_dataset_annotations_note"


def _dataset_widget_key(name: str) -> str:
    return f"dataset_annotations_{name}_{st.session_state.get(_DATASET_NONCE_KEY, 0)}"


def _refresh_dataset_widgets(note: str) -> None:
    st.session_state[_DATASET_NONCE_KEY] = (
        int(st.session_state.get(_DATASET_NONCE_KEY, 0)) + 1
    )
    st.session_state[_DATASET_NOTE_KEY] = note
    _reseed_trial_editors()


def _plural(count: int, noun: str) -> str:
    return f"{count:,} {noun}{'' if count == 1 else 's'}"


def _import_dataset_annotations(uploader_key: str, trials: frozenset) -> None:
    upload = st.session_state.get(uploader_key)
    if upload is None:
        return
    try:
        records = store_to_records(deserialize(upload.getvalue().decode("utf-8")))
    except (UnicodeDecodeError, ValueError):
        st.session_state[_DATASET_NOTE_KEY] = (
            "error:That file is not an annotations JSON file."
        )
        st.session_state[_DATASET_NONCE_KEY] = (
            int(st.session_state.get(_DATASET_NONCE_KEY, 0)) + 1
        )
        return
    applied, skipped = merge_records(_store(), records, trials)
    note = f"Imported {_plural(applied, 'annotation')}."
    if skipped:
        note += (
            f" Skipped {_plural(skipped, 'annotation')} on trials this dataset "
            "doesn't have."
        )
    _refresh_dataset_widgets(note)


def _delete_dataset_annotations(records: list[dict]) -> None:
    removed = drop_records(_store(), records)
    _refresh_dataset_widgets(f"Deleted {_plural(removed, 'annotation')}.")


def _annotations_frame(records: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "Participant": [r["participant_id"] for r in records],
            "Trial": [r["trial_id"] for r in records],
            "Screen": [r.get("screen_id", "") for r in records],
            "Favorite": [r["star"] for r in records],
            "Tags": [r["tags"] for r in records],
            "Note": [r["note"] for r in records],
        }
    )
    if not frame["Screen"].astype(bool).any():
        frame = frame.drop(columns="Screen")
    return frame


def render_dataset_annotations(trials, *, dataset_name: str) -> None:
    """🗂️ Data → **Annotations**: every annotation on the open dataset's trials.

    One table — participant, trial, favorite, tags, note — with **Export** (this
    dataset's annotations as JSON), **Import** (the same file, or the
    ``annotations.json`` of an Export bundle: entries on trials the dataset has
    are added, the rest are skipped)
    and **Delete**, for the rows ticked in the table. Annotations are still made
    per trial, on 🗺️ Scanpath → Annotations; this is where they are seen whole.
    """
    trials = _trial_set(trials)
    records = records_in(_store(), trials)
    note = st.session_state.pop(_DATASET_NOTE_KEY, None)
    if note and note.startswith("error:"):
        st.error(note.removeprefix("error:"), icon=ICONS["error"])
    elif note:
        st.success(note, icon=ICONS["confirm"])

    toolbar = st.container(
        key="dataset_annotations_toolbar",
        horizontal=True,
        vertical_alignment="center",
        gap="small",
    )
    toolbar.download_button(
        "Export",
        icon=ICONS["download"],
        data=serialize(records_to_store(records)),
        file_name=f"{_file_slug(dataset_name)}_annotations.json",
        mime="application/json",
        key="dataset_annotations_export",
        disabled=not records,
        help="Download this dataset's annotations as a JSON file.",
    )
    with toolbar.popover("Import", icon=ICONS["upload"]):
        uploader_key = _dataset_widget_key("import")
        st.file_uploader(
            "Annotations file (JSON)",
            type=["json"],
            key=uploader_key,
            on_change=_import_dataset_annotations,
            args=(uploader_key, trials),
            max_upload_size=upload_limit_mb(),
        )
        st.caption(
            "A file exported here or in an Export bundle. Annotations on trials "
            "this dataset doesn't have are skipped, and an imported one replaces "
            "what its trial already had."
        )
    delete_slot = toolbar.container(width="content")

    if not records:
        st.caption(
            "No annotations on this dataset yet. Star, tag or note a trial on "
            "🗺️ **Scanpath → Annotations**."
        )
        return
    event = st.dataframe(
        _annotations_frame(records),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="multi-row",
        key=_dataset_widget_key("table"),
        column_config={
            "Favorite": st.column_config.CheckboxColumn("Favorite", width="small"),
            "Tags": st.column_config.ListColumn("Tags"),
            "Note": st.column_config.TextColumn("Note", width="large"),
        },
    )
    picked = [records[i] for i in event.selection.rows if i < len(records)]
    with delete_slot.popover(
        f"Delete ({len(picked)})" if picked else "Delete",
        icon=ICONS["delete"],
        disabled=not picked,
        help="Tick rows in the table to delete them.",
    ):
        st.write(
            f"Delete {_plural(len(picked), 'annotation')}? This cannot be undone "
            "— **Export** first to keep a copy."
        )
        st.button(
            "Delete",
            icon=ICONS["delete"],
            key="dataset_annotations_delete",
            type="primary",
            on_click=_delete_dataset_annotations,
            args=(picked,),
        )


def _file_slug(name: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in str(name)).strip("_")
    return slug.lower() or "dataset"
