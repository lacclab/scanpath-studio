"""Per-trial researcher annotations: favorites (stars), tags, and free notes.

Annotations are keyed by ``(participant_id, trial_id)`` and live in Streamlit
session state, so they persist across reruns within a session. There is no
backend; a local run keeps them in the recovery cache, and to share them 🗂️
Data → **Annotations** exports and imports a dataset's as JSON (UX-174). The
Scanpath view's Export bundle can include the same file (UX-179).

**DATA-48 — annotations belong to a dataset**, as the metadata tables do since
DATA-47: :data:`ANNOTATIONS_STATE_KEY` holds the *selected* dataset's store only
(so every reader — the per-trial editor, the pickers' markers, the ⭐ / tag
filters, the Data page, the Export bundle — reads it unchanged), and every other
dataset's waits in :data:`DATASET_STORE_KEY`. :func:`activate_dataset`, called
by ``app.main`` beside ``metadata.activate_dataset``, swaps them when the
selection changes. Two datasets that reuse ``(participant, trial)`` ids
therefore no longer share a star, a tag or a note.

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
from .session_keys import COMPARE_SOURCE_STATE_KEY

ANNOTATIONS_STATE_KEY = "trial_annotations"
#: The annotations file (🗂️ Data → Annotations, an Export bundle's
#: ``annotations.json``). Schema 3 (DATA-48) adds the optional ``dataset`` the
#: file was exported from — for the reader, not the importer: a file of any
#: schema imports into the dataset that is open, the only one it can belong to.
SCHEMA_VERSION = 3

# Per-trial annotation widgets use this prefix so they can be cleared on import
# (forcing a re-seed from the freshly loaded store), and on a dataset swap.
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
    # A recovery-cache record is not checked like an imported file is
    # (`deserialize`), so a stray scalar here is no tags rather than a crash.
    tags = tags if isinstance(tags, (list, tuple, set, frozenset)) else []
    clean_tags = sorted({str(t).strip() for t in tags if str(t).strip()})
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


def serialize(store: dict[Key, Entry], *, dataset: str | None = None) -> str:
    """Serialize a store to a JSON document string.

    ``dataset`` names the dataset the annotations were made on (DATA-48); the
    file says so, and :func:`deserialize` does not need it back.
    """
    document: dict[str, object] = {"schema": SCHEMA_VERSION}
    if dataset:
        document["dataset"] = str(dataset)
    document["annotations"] = store_to_records(store)
    return json.dumps(document, indent=2)


def file_dataset(text: str) -> str | None:
    """The ``dataset`` an annotations file names, if any (schema 3+)."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    name = data.get("dataset") if isinstance(data, dict) else None
    return name if isinstance(name, str) and name else None


class AnnotationsFileError(ValueError):
    """A JSON document that is not an annotations file — wrong shape, not syntax."""


_ID_TYPES = (str, int, float)


def _check_record(index: int, record: object) -> None:
    """Raise :class:`AnnotationsFileError` unless ``record`` has the exported shape."""
    where = f"entry {index + 1}"
    if not isinstance(record, dict):
        raise AnnotationsFileError(f"{where} is not an annotation")
    for field in ("participant_id", "trial_id"):
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, _ID_TYPES):
            raise AnnotationsFileError(f"{where} has no usable {field}")
    screen_id = record.get("screen_id")
    if screen_id is not None and (
        isinstance(screen_id, bool) or not isinstance(screen_id, _ID_TYPES)
    ):
        raise AnnotationsFileError(f"{where} has an unusable screen_id")
    if not isinstance(record.get("star", False), bool):
        raise AnnotationsFileError(f"{where}: star must be true or false")
    tags = record.get("tags", [])
    if tags is not None and (
        not isinstance(tags, list)
        or any(isinstance(t, bool) or not isinstance(t, _ID_TYPES) for t in tags)
    ):
        raise AnnotationsFileError(f"{where}: tags must be a list of words")
    note = record.get("note", "")
    if note is not None and not isinstance(note, str):
        raise AnnotationsFileError(f"{where}: note must be text")


def deserialize(text: str) -> dict[Key, Entry]:
    """Parse a JSON document (object with ``annotations`` or a bare list).

    The shape is checked before anything is built, so a JSON file that is not
    an annotations file — another app's, a settings file, a hand edit gone
    wrong — raises :class:`AnnotationsFileError` (a ``ValueError``) rather than
    importing nothing or failing half-way. Invalid JSON raises ``ValueError``
    from :func:`json.loads`.
    """
    data = json.loads(text)
    if isinstance(data, dict):
        if "annotations" not in data:
            raise AnnotationsFileError("it has no annotations list")
        records = data["annotations"]
    else:
        records = data
    if not isinstance(records, list):
        raise AnnotationsFileError("its annotations are not a list")
    for index, record in enumerate(records):
        _check_record(index, record)
    return records_to_store(records)


def _trial_of(key: Key) -> tuple[str, str]:
    return (key[0], key[1])


def _trial_set(trials: Iterable[tuple[object, object]]) -> frozenset[tuple[str, str]]:
    if isinstance(trials, frozenset):
        return trials  # already built by the caller, as strings
    return frozenset((str(pid), str(tid)) for pid, tid in trials)


def records_in(store: dict[Key, Entry], trials) -> list[dict]:
    """The records of ``store`` on the trials in ``trials``, sorted.

    ``trials`` is ``(participant_id, trial_id)`` pairs. Keeps what an Export
    bundle writes to the trials it exports, and tells a dataset's annotations
    on trials it still has from ones it no longer has (DATA-48). A screen
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


# ---------------------------------------------------------------------------
# DATA-48 — the annotations belong to a dataset
#
# `ANNOTATIONS_STATE_KEY` holds the selected dataset's store; every other
# dataset's waits in `DATASET_STORE_KEY`, and `activate_dataset` swaps them in
# and out when the selection changes — DATA-47's design for the metadata
# tables, taken over rather than reinvented, so the two follow one selection by
# one set of rules. A dataset component in every key was the alternative; it
# would have made each of the store's readers (the editor, the pickers'
# markers, the filters, the Data page, the Export bundle) pass a dataset, where
# the swap leaves them all reading the one store they already read.
#
# These functions take the session mapping explicitly, like `metadata`'s, so
# the swap is testable on a plain dict.
# ---------------------------------------------------------------------------

#: Every dataset's annotations but the selected one's: ``{dataset: {key:
#: entry}}``. The selected dataset is never in it.
DATASET_STORE_KEY = "_annotations_by_dataset"
#: Which dataset :data:`ANNOTATIONS_STATE_KEY`'s store belongs to right now.
#: Absent until the first :func:`activate_dataset`.
OWNER_KEY = "_annotations_owner"
#: Entries that belong to no dataset yet — a pre-DATA-48 recovery cache's that
#: no upload's trials claimed (:func:`restore_payload`). The first *real*
#: dataset activated adopts them; the add wizard's never does, since nothing
#: of it is cached and they would be lost with it.
UNASSIGNED_KEY = "_annotations_unassigned"
#: Bumped on every change to the stored (not live) stores — the recovery
#: cache's cheap "did it change" test (:func:`store_signature`), the pattern
#: of ``metadata.STORE_REVISION_KEY``: serializing every dataset's annotations
#: on every rerun is not cheap once there are several thousand.
STORE_REVISION_KEY = "_annotations_store_revision"
#: The add-dataset wizard's dataset, before it has a name. The same token as
#: ``metadata.PENDING_DATASET`` (pinned by a test; not imported, since
#: `metadata` pulls in the data layer). Never cached.
PENDING_DATASET = "\x00pending"
#: CMP-8's key prefix for scanpath B's filters (``tabs._COMPARE_FILTER_PREFIX``)
#: and the picker's "same dataset" answer (``compare_source.THIS_DATASET``).
#: Pinned equal by a test; not imported, since both modules import this one.
_COMPARE_PREFIX = "cmp"
_COMPARE_SAME_DATASET = "This dataset"


def _stored(session) -> dict[str, dict[Key, Entry]]:
    store = session.get(DATASET_STORE_KEY)
    return dict(store) if isinstance(store, dict) else {}


def _live(session) -> dict[Key, Entry]:
    live = session.get(ANNOTATIONS_STATE_KEY)
    return dict(live) if isinstance(live, dict) else {}


def _unassigned(session) -> dict[Key, Entry]:
    pool = session.get(UNASSIGNED_KEY)
    return dict(pool) if isinstance(pool, dict) else {}


def _set_unassigned(session, pool: dict) -> None:
    if pool:
        session[UNASSIGNED_KEY] = pool
    else:
        session.pop(UNASSIGNED_KEY, None)


def _bump(session) -> None:
    session[STORE_REVISION_KEY] = int(session.get(STORE_REVISION_KEY) or 0) + 1


def _reseed_editors_in(session) -> None:
    """Drop the per-trial editors' widget state from ``session``.

    Their keys carry the trial's ids, not the dataset's: left in place across a
    swap, the editor of a trial the next dataset shares would seed from the last
    dataset's values and write them into the new dataset's store. Nothing typed
    is lost by it — every editor field saves itself on change (``_save_entry``),
    and a widget's callback runs before the run that swaps.
    """
    for key in [
        k
        for k in list(session.keys())
        if isinstance(k, str) and k.startswith(_WIDGET_PREFIX)
    ]:
        del session[key]


def activate_dataset(session, dataset: str, *, adopt: bool = True) -> bool:
    """Make ``dataset``'s annotations the session store; whether it changed.

    Called by ``app.main`` on every run with the dataset on screen. When that
    changed, the outgoing dataset's store is filed away and the incoming one's
    comes back. A store with no owner yet (entries put there before the first
    run) joins the :data:`UNASSIGNED_KEY` pool, which :func:`adopt_unassigned`
    hands on. ``app.main`` passes ``adopt=False`` and adopts only
    once the load has said which dataset is really shown (a missing corpus is
    shown as the demo); the default adopts here, for callers with no load.
    """
    dataset = str(dataset)
    owner = session.get(OWNER_KEY)
    if owner == dataset:
        if adopt:
            adopt_unassigned(session)
        return False
    store = _stored(session)
    live = _live(session)
    unassigned = _unassigned(session)
    if owner is None:
        unassigned = {**live, **unassigned}
    elif live:
        store[str(owner)] = live
    else:
        store.pop(str(owner), None)
    session[ANNOTATIONS_STATE_KEY] = store.pop(dataset, None) or {}
    session[DATASET_STORE_KEY] = store
    _set_unassigned(session, unassigned)
    session[OWNER_KEY] = dataset
    _bump(session)
    _reseed_editors_in(session)
    if adopt:
        adopt_unassigned(session)
    return True


def adopt_unassigned(session) -> int:
    """Give the :data:`UNASSIGNED_KEY` pool to the dataset on screen; how many.

    The pool holds a pre-DATA-48 cache's entries that no restored upload's
    trials claimed (:func:`restore_payload`) — so they are on trials of a
    built-in or public corpus, and only such a dataset may adopt them. Never
    an upload (each was asked in the claim pass, and said no), and never the
    add wizard's unnamed dataset, which is not cached. The dataset's own entry
    wins a collision with an adopted one.
    """
    pool = _unassigned(session)
    owner = session.get(OWNER_KEY)
    if not pool or owner is None or owner == PENDING_DATASET:
        return 0
    uploads = session.get("_datasets")
    if isinstance(uploads, dict) and owner in uploads:
        return 0
    session[ANNOTATIONS_STATE_KEY] = {**pool, **_live(session)}
    session.pop(UNASSIGNED_KEY, None)
    _bump(session)
    _reseed_editors_in(session)
    return len(pool)


def begin_pending_dataset(session) -> None:
    """Start the add-dataset wizard's dataset with no annotations of its own."""
    store = _stored(session)
    if store.pop(PENDING_DATASET, None) is not None:
        session[DATASET_STORE_KEY] = store
        _bump(session)


def adopt_pending_dataset(session, dataset: str) -> None:
    """✅ Add dataset: the wizard's store becomes ``dataset``'s.

    Only while the wizard's dataset is the selected one — relabelling another
    dataset's store as the new one's would move its annotations — and the new
    dataset starts clean: a stale store left under its name is dropped, not
    merged (``wizard._safe_dataset_name`` keeps such names from being chosen).
    """
    begin_pending_dataset(session)
    if session.get(OWNER_KEY) != PENDING_DATASET:
        return
    dataset = str(dataset)
    store = _stored(session)
    if store.pop(dataset, None) is not None:
        session[DATASET_STORE_KEY] = store
    session[OWNER_KEY] = dataset
    _bump(session)


def forget_dataset(session, dataset: str) -> None:
    """A removed dataset's annotations go with it."""
    dataset = str(dataset)
    store = _stored(session)
    if store.pop(dataset, None) is not None:
        session[DATASET_STORE_KEY] = store
    if session.get(OWNER_KEY) == dataset:
        session[ANNOTATIONS_STATE_KEY] = {}
        session.pop(OWNER_KEY, None)
        _reseed_editors_in(session)
    _bump(session)


def current_dataset(session) -> str | None:
    """The dataset the session store belongs to; ``None`` before the first run
    and while the add wizard's unnamed dataset is open."""
    owner = session.get(OWNER_KEY)
    return None if owner in (None, PENDING_DATASET) else str(owner)


def dataset_names(session) -> set[str]:
    """Every dataset name that holds (or owns) an annotation store."""
    names = {str(name) for name, entries in _stored(session).items() if entries}
    owner = session.get(OWNER_KEY)
    if owner is not None:
        names.add(str(owner))
    names.discard(PENDING_DATASET)
    return names


def rename_dataset(session, old: str, new: str) -> bool:
    """A renamed dataset keeps its annotations; whether they moved.

    Refuses — changing nothing — when ``new`` already holds a store of its own,
    which the rename would otherwise overwrite. ``wizard.rename_dataset`` never
    asks for such a name (``_safe_dataset_name`` avoids :func:`dataset_names`).
    """
    old, new = str(old), str(new)
    if old == new:
        return True
    store = _stored(session)
    if new in store or session.get(OWNER_KEY) == new:
        return False
    if old in store:
        session[DATASET_STORE_KEY] = {
            (new if key == old else key): value for key, value in store.items()
        }
    if session.get(OWNER_KEY) == old:
        session[OWNER_KEY] = new
    _bump(session)
    return True


def store_for(session, dataset: str) -> dict[Key, Entry]:
    """``dataset``'s annotation store — the live one while it is selected."""
    dataset = str(dataset)
    if session.get(OWNER_KEY) == dataset:
        return _live(session)
    return dict(_stored(session).get(dataset) or {})


def store_for_prefix(prefix: str = "") -> dict[Key, Entry]:
    """The store the trial filters under key ``prefix`` narrow by (DATA-48).

    The main pool's filters read the selected dataset's. Compare mode's
    scanpath B (the ``cmp`` prefix) can come from another dataset, and then its
    ⭐ / tag filters, its tag list and its picker's markers are *that*
    dataset's — the rule ``metadata.attached_for`` follows for its tables.
    Outside a script run (API, CLI) there is no store: ``{}``.
    """
    try:
        session = st.session_state
        if prefix != _COMPARE_PREFIX:
            return _live(session)
        other = session.get(COMPARE_SOURCE_STATE_KEY)
    except Exception:  # no script run context
        return {}
    if not other or other == _COMPARE_SAME_DATASET:
        return _live(session)
    return store_for(session, str(other))


def upload_trials(entry) -> frozenset[tuple[str, str]]:
    """An upload's ``(participant, trial)`` pairs, as annotations are keyed.

    The trial picker's ids: `utils.build_combo_options` lists the fixation
    table's trials under ``unique_trial_id`` when there is one, else
    ``trial_id``. A table without fixations is read from its words instead.
    """
    for key in ("fixations", "words"):
        frame = entry.get(key) if isinstance(entry, dict) else None
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        trial_col = "unique_trial_id" if "unique_trial_id" in frame else "trial_id"
        if {"participant_id", trial_col} <= set(frame.columns):
            pairs = frame[["participant_id", trial_col]].drop_duplicates()
            return frozenset(
                zip(pairs["participant_id"].astype(str), pairs[trial_col].astype(str))
            )
    return frozenset()


def dataset_records(session) -> dict[str, list[dict]]:
    """Every dataset's annotations, the selected one's live: ``{name: records}``.

    What the recovery cache writes. The wizard's unnamed dataset is left out,
    and so are entries no dataset owns yet — :func:`unassigned_records`.
    """
    stores = _stored(session)
    owner = session.get(OWNER_KEY)
    if owner is not None:
        stores[str(owner)] = _live(session)
    stores.pop(PENDING_DATASET, None)
    return {
        name: store_to_records(entries)
        for name, entries in sorted(stores.items())
        if entries
    }


def unassigned_records(session) -> list[dict]:
    """Entries no dataset owns yet — cached as such, so none is lost.

    The :data:`UNASSIGNED_KEY` pool, plus the session store itself while no
    dataset owns it (a run that returned before :func:`activate_dataset`).
    """
    pool = _unassigned(session)
    if session.get(OWNER_KEY) is None:
        pool = {**_live(session), **pool}
    return store_to_records(pool)


def cache_payload(session) -> dict:
    """The recovery cache's ``annotations`` value: ``{"datasets": …}`` (DATA-48)."""
    payload: dict[str, object] = {"datasets": dataset_records(session)}
    unassigned = unassigned_records(session)
    if unassigned:
        payload["unassigned"] = unassigned
    return payload


def store_signature(session) -> list:
    """A cheap fingerprint of every dataset's annotations, for the cache.

    The live store by content (the editor writes it directly), the rest by
    :data:`STORE_REVISION_KEY` — ``metadata.store_signature``'s pattern — so a
    rerun does not serialize every stored dataset's annotations.
    """
    return [
        int(session.get(STORE_REVISION_KEY) or 0),
        str(session.get(OWNER_KEY)),
        store_to_records(_live(session)),
        store_to_records(_unassigned(session)),
    ]


def _valid_records(records) -> list[dict]:
    """One malformed record costs that record, not the rest."""
    return [
        record
        for record in (records if isinstance(records, list) else [])
        if isinstance(record, dict)
    ]


def restore_payload(session, payload) -> int:
    """Put back what :func:`cache_payload` wrote; how many annotations landed.

    A dataset this session already holds annotations for keeps its own — the
    restore's ``setdefault`` rule.

    **The one-time migration.** A manifest written before DATA-48 stored one
    flat list of records naming no dataset; it is read as ``unassigned``. Each
    entry goes, first, to every upload whose trials include it — the uploads'
    frames are back in ``_datasets`` by now (``persistence.restore_state``
    restores them first), and an annotation on a trial only one dataset has is
    that dataset's. An entry no upload claims (one on a built-in or public
    corpus, which is not in memory to ask) waits in :data:`UNASSIGNED_KEY` for
    the first real dataset the session opens — the one the manifest had
    selected, unless a link names another. Nothing is dropped, and the next save
    writes everything back per dataset, so the conversion happens once.
    """
    if isinstance(payload, list):
        datasets, unassigned = {}, payload
    elif isinstance(payload, dict):
        datasets = payload.get("datasets")
        datasets = datasets if isinstance(datasets, dict) else {}
        unassigned = payload.get("unassigned") or []
    else:
        datasets, unassigned = {}, []
    live = _live(session)
    owner = session.get(OWNER_KEY)
    store = _stored(session)
    restored = 0

    def file_under(name: str, entries: dict) -> None:
        nonlocal live
        if name == owner:
            live = {**entries, **live}
        else:
            store[name] = {**entries, **(store.get(name) or {})}

    for name, records in datasets.items():
        name = str(name)
        entries = records_to_store(_valid_records(records))
        if not entries or name == PENDING_DATASET or name in store:
            continue
        if name == owner and live:
            continue
        file_under(name, entries)
        restored += len(entries)

    legacy = records_to_store(_valid_records(unassigned))
    if legacy:
        claimed: set[Key] = set()
        uploads = session.get("_datasets")
        for name, entry in (uploads if isinstance(uploads, dict) else {}).items():
            trials = upload_trials(entry)
            mine = {k: e for k, e in legacy.items() if _trial_of(k) in trials}
            if mine:
                file_under(str(name), mine)
                claimed.update(mine)
        rest = {k: e for k, e in legacy.items() if k not in claimed}
        _set_unassigned(session, {**rest, **_unassigned(session)})
        restored += len(legacy)
    session[ANNOTATIONS_STATE_KEY] = live
    if store:
        session[DATASET_STORE_KEY] = store
    _bump(session)
    return restored


def payload_count(payload) -> int:
    """How many annotations a cached ``annotations`` value holds, either shape."""
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    datasets = payload.get("datasets")
    total = sum(
        len(records)
        for records in (datasets.values() if isinstance(datasets, dict) else [])
        if isinstance(records, list)
    )
    unassigned = payload.get("unassigned")
    return total + (len(unassigned) if isinstance(unassigned, list) else 0)


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


def known_tags(prefix: str = "", *, trial_level: bool = False) -> list[str]:
    """Preset tags plus any tag used in the dataset's store, sorted.

    ``prefix`` picks the dataset as :func:`store_for_prefix` does, so compare
    mode's scanpath B lists its own dataset's tags (DATA-48).

    ``trial_level`` leaves out tags used only on screen annotations — what the
    trial filters offer, since they read the trial's own entry (:func:`select_keys`)
    and a screen-only tag there could never match.
    """
    tags: set[str] = set(PRESET_TAGS)
    store = store_for_prefix(prefix) if prefix else _store()
    for key, entry in store.items():
        if trial_level and len(key) > 2:
            continue
        tags.update(entry.get("tags", []))
    return sorted(tags)


def has_screen_annotations(prefix: str = "") -> bool:
    """Whether the dataset's store holds any screen annotation."""
    store = store_for_prefix(prefix) if prefix else _store()
    return any(len(key) > 2 for key in store)


def current_records() -> list[dict]:
    """The open dataset's annotations as records — the Export bundle's (UX-179)."""
    return store_to_records(_store())


def _reseed_trial_editors() -> None:
    """Drop the per-trial editors' widget state, so they re-seed from the store."""
    _reseed_editors_in(st.session_state)


# ---------------------------------------------------------------------------
# UI render helpers
# ---------------------------------------------------------------------------


def _add_tag_callback(tags_key: str, newtag_key: str, save_args: tuple) -> None:
    """on_change for the 'add tag' input: append to the multiselect's state.

    Runs before the next rerun, so writing the multiselect's session_state here
    is allowed (the widget hasn't been instantiated yet that run). Saves the
    entry too, like every other editor field (see :func:`_save_entry_callback`)."""
    new_tag = str(st.session_state.get(newtag_key, "")).strip()
    if not new_tag:
        return
    current = list(st.session_state.get(tags_key, []))
    if new_tag not in current:
        st.session_state[tags_key] = current + [new_tag]
    st.session_state[newtag_key] = ""
    _save_entry_callback(*save_args)


def _save_entry_callback(
    participant_id: str,
    trial_id: str,
    screen_id: str | None,
    star_key: str,
    tags_key: str,
    note_key: str,
) -> None:
    """Persist the editor's fields as soon as one changes, before the rerun.

    Widget callbacks run before the app body. Without this the picker reads the
    previous annotation store, then ``render_trial_annotations`` saves the new
    value later in the run — making the star marker appear one click behind the
    checkbox. And (DATA-48) the run that switches dataset drops the editors'
    widget state in ``activate_dataset`` before any editor renders: a tag or a
    note saved only by the render body would be lost with it. Saved here, it is
    already in the outgoing dataset's store when the swap files that away.
    """
    entry = get_entry(participant_id, trial_id, screen_id)
    state = st.session_state
    set_entry(
        participant_id,
        trial_id,
        star=bool(state[star_key]) if star_key in state else bool(entry["star"]),
        tags=list(state[tags_key]) if tags_key in state else list(entry["tags"]),
        note=str(state[note_key]) if note_key in state else str(entry["note"]),
        screen_id=screen_id,
    )


def widget_slug(
    participant_id: str, trial_id: str, screen_id: str | None = None
) -> str:
    """The per-trial editor's widget-key suffix: the store key, unambiguously.

    BUG-110: joining the ids with ``__`` and writing the parent scope as the
    word ``parent`` gave ``("a__b", "c")`` and ``("a", "b__c")`` — or a trial's
    parent and its screen named ``parent`` — the same widget keys, so opening
    the one seeded its editor from the other's values and saved them as its
    own. A JSON list keeps every id whole and writes the parent as ``null``.
    """
    ident = [str(participant_id), str(trial_id)]
    ident.append(None if screen_id is None else str(screen_id))
    return json.dumps(ident, ensure_ascii=False)


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
        scope_key = f"{_WIDGET_PREFIX}scope_{widget_slug(participant_id, trial_id)}"
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
    slug = widget_slug(participant_id, trial_id, annotation_screen)
    star_key = f"{_WIDGET_PREFIX}star_{slug}"
    tags_key = f"{_WIDGET_PREFIX}tags_{slug}"
    note_key = f"{_WIDGET_PREFIX}note_{slug}"
    newtag_key = f"{_WIDGET_PREFIX}newtag_{slug}"
    save_args = (
        participant_id,
        trial_id,
        annotation_screen,
        star_key,
        tags_key,
        note_key,
    )

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
            on_change=_save_entry_callback,
            args=save_args,
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
            on_change=_save_entry_callback,
            args=save_args,
        )
        add_col.text_input(
            "Add a tag",
            key=newtag_key,
            placeholder="Add a new tag",
            on_change=_add_tag_callback,
            args=(tags_key, newtag_key, save_args),
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
            on_change=_save_entry_callback,
            args=save_args,
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
            "Every annotation on this dataset is listed on "
            f"{ICONS['view_data']} **Data Management → Annotations**, to export, import "
            "or delete."
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

    Trial level only: each key is looked up as given, so a parent
    ``(participant_id, trial_id)`` key reads the trial's own annotation and
    never a screen's. That is the filters' stated scope — a screen star or tag
    neither keeps nor drops its trial, and
    the panel offers only trial-level tags (:func:`known_tags`).

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
    prefix: str = "",
) -> list[Key]:
    """Session-backed wrapper around :func:`select_keys`.

    ``prefix`` picks the dataset's store as :func:`store_for_prefix` does.
    """
    return select_keys(
        store_for_prefix(prefix) if prefix else _store(),
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


def _import_dataset_annotations(
    uploader_key: str, trials: frozenset, dataset_name: str = ""
) -> None:
    upload = st.session_state.get(uploader_key)
    if upload is None:
        return
    try:
        text = upload.getvalue().decode("utf-8")
        records = store_to_records(deserialize(text))
    except (UnicodeDecodeError, ValueError) as exc:
        # Nothing was merged yet, so the dataset's annotations are untouched,
        # and the fresh uploader key below lets another file be chosen.
        reason = f" ({exc})" if isinstance(exc, AnnotationsFileError) else ""
        st.session_state[_DATASET_NOTE_KEY] = (
            f"error:That file is not an annotations JSON file{reason}. "
            "Nothing was imported."
        )
        st.session_state[_DATASET_NONCE_KEY] = (
            int(st.session_state.get(_DATASET_NONCE_KEY, 0)) + 1
        )
        return
    # DATA-48: into the open dataset, whatever the file names — a file from
    # before annotations were per dataset names none, and one exported from
    # another dataset is still the user's call to bring here. The name is said.
    applied, skipped = merge_records(_store(), records, trials)
    note = f"Imported {_plural(applied, 'annotation')}."
    source = file_dataset(text)
    if source and source != dataset_name:
        note = f"Imported {_plural(applied, 'annotation')} exported from **{source}**."
    if skipped:
        note += (
            f" Skipped {_plural(skipped, 'annotation')} on trials this dataset "
            "doesn't have."
        )
    _refresh_dataset_widgets(note)


def _delete_dataset_annotations(records: list[dict]) -> None:
    removed = drop_records(_store(), records)
    _refresh_dataset_widgets(f"Deleted {_plural(removed, 'annotation')}.")


def _annotations_frame(records: list[dict], trials: frozenset) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "Participant": [r["participant_id"] for r in records],
            "Trial": [r["trial_id"] for r in records],
            "Screen": [r.get("screen_id", "") for r in records],
            "Favorite": [r["star"] for r in records],
            "Tags": [r["tags"] for r in records],
            "Note": [r["note"] for r in records],
            "In dataset": [
                (str(r["participant_id"]), str(r["trial_id"])) in trials
                for r in records
            ],
        }
    )
    if not frame["Screen"].astype(bool).any():
        frame = frame.drop(columns="Screen")
    if frame["In dataset"].all():
        frame = frame.drop(columns="In dataset")
    return frame


def render_dataset_annotations(trials, *, dataset_name: str) -> None:
    """🗂️ Data → **Annotations**: every annotation the open dataset holds.

    One table — participant, trial, favorite, tags, note — with **Export** (this
    dataset's annotations as JSON), **Import** (the same file, or the
    ``annotations.json`` of an Export bundle: entries on trials the dataset has
    are added, the rest are skipped)
    and **Delete**, for the rows ticked in the table. Annotations are still made
    per trial, on 🗺️ Scanpath → Annotations; this is where they are seen whole.

    DATA-48: the session store *is* the dataset's now, so the table lists all
    of it — including any entry on a trial the dataset has not loaded: one made
    under another selection of a corpus' parts, or one a recovery cache from
    before annotations were per dataset assigned here (:func:`restore_payload`).
    Those are flagged rather than hidden, so an entry is never out of reach:
    exported from here, it imports into the dataset it belongs to.
    """
    trials = _trial_set(trials)
    records = store_to_records(_store())
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
        data=serialize(records_to_store(records), dataset=dataset_name),
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
            args=(uploader_key, trials, dataset_name),
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
            f"{ICONS['view_scanpath']} **Scanpath → Annotations**."
        )
        return
    elsewhere = len(records) - len(records_in(_store(), trials))
    if elsewhere:
        st.caption(
            f"{_plural(elsewhere, 'annotation')} here "
            f"{'is' if elsewhere == 1 else 'are'} on trials this dataset hasn't "
            "loaded (*In dataset* unticked) — from an earlier load of it, or "
            "saved before annotations were kept per dataset. They stay with this "
            "dataset; to move them to another, **Export** them here and "
            "**Import** them there."
        )
    event = st.dataframe(
        _annotations_frame(records, trials),
        hide_index=True,
        width="stretch",
        on_select="rerun",
        selection_mode="multi-row",
        key=_dataset_widget_key("table"),
        column_config={
            "Favorite": st.column_config.CheckboxColumn("Favorite", width="small"),
            "Tags": st.column_config.ListColumn("Tags"),
            "Note": st.column_config.TextColumn("Note", width="large"),
            "In dataset": st.column_config.CheckboxColumn(
                "In dataset",
                width="small",
                help="Whether this dataset has the annotated trial.",
            ),
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
