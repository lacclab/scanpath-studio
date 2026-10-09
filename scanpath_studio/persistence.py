"""Local, single-user session persistence for Scanpath Studio.

The hosted app deliberately does not persist anything: there is no user identity
there, so a process-wide cache could expose one visitor's data to another.  A
session served on loopback only (the desktop app, a launch bound to
``127.0.0.1``) stores uploaded datasets as Parquet plus a small JSON manifest and
restores them on the next browser or process session. Which of the two a server
is comes from its own bind address, never from the browser — see
:func:`persistence_enabled`.

Storing a researcher's tables on their disk is invisible by nature, so the cache
is also *inspectable*: :func:`cache_status` reports what is stored, where, how
big it is and when it was written without importing Streamlit, and it backs the
in-app 🗂️ Data → *Saved on this computer* section
(``app._render_saved_here_section``, UX-179), the ``scanpath-studio cache`` CLI
subcommand and ``api.cache_status``. The stored files are deleted from outside
the app — ``scanpath-studio cache --clear`` / ``api.clear_cache``, both
:func:`clear_local_state`. Saving is paused for a session by BUG-71's breaker
and when a manifest exists but cannot be read (:func:`persistence_paused`,
:func:`cache_failure`); opting out is a launch choice
(``run --no-persist`` / ``SCANPATH_STUDIO_PERSIST=0``).

Each stored dataset restores on its own. One whose files are missing or
unreadable is held back (:func:`failed_datasets`) — the others, the settings,
the annotations and the metadata tables restore regardless — and its manifest
entry and files are written back unchanged by every save until the user retries
it (:func:`retry_failed_datasets`) or removes it (:func:`discard_failed_dataset`).

A save is all or nothing (#412). The manifest is the only file it replaces:
a dataset whose frames changed, and metadata tables that changed, are written
to files of their own under fresh names, and the manifest that names them is
swapped in last. Until that swap the previous manifest names only the previous
files, untouched, so a save that fails part-way — a full disk, a killed
process — leaves the whole previous session, never some of each. Files no
manifest names any more are removed after the swap (:func:`_remove_unreferenced`).
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import re
import secrets
import tempfile
import threading
import time
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

import scanpath_studio.annotations as annotations_mod

from . import progress
from .constants import (
    DATASET_COUNTS_STORE_KEY,
    DATASET_DESCRIPTIONS_KEY,
    DATASET_SETUP_OVERRIDES_KEY,
    DOWNLOAD_DIR_KEY,
    RAW_GAZE_SEEDED_FOR_KEY,
    RAW_GAZE_SNAP_RESTORE_KEY,
    SETUP_OVERRIDE_FOR_KEY,
    SETUP_OVERRIDE_RESTORE_KEY,
    SETUP_OVERRIDE_SESSION_KEYS,
)
from .session_keys import (
    COLUMN_MAPPING_PREFIX,
    DESIGN_PRESETS,
    PLOT_CONFIG_STATE_KEYS,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
    SINGLE_PLAYBACK_SPEED,
    compare_state_keys,
    keep_legacy_marker_scale,
    rename_legacy_keys,
)

SCHEMA_VERSION = 1

#: The default cache folder's name. Versioned by :data:`SCHEMA_VERSION` rather
#: than by the app's version, and derived from it so the two cannot drift: the
#: "v1" a user sees in the path is the *cache format's* version, so it stays put
#: across app releases, and a format change starts a new folder beside this one
#: instead of overwriting a session the new code could not read.
CACHE_DIR_NAME = f"session-v{SCHEMA_VERSION}"
PERSIST_ENV_VAR = "SCANPATH_STUDIO_PERSIST"
STATE_DIR_ENV_VAR = "SCANPATH_STUDIO_STATE_DIR"
_RESTORED_KEY = "_local_persistence_restored"
_RESTORED_PAYLOAD_KEY = "_local_persistence_restored_payload"
_PAUSED_KEY = "_local_persistence_paused"
_LAST_FINGERPRINT_KEY = "_local_persistence_fingerprint"
_LAST_DATASET_IDENTITY_KEY = "_local_persistence_dataset_identity"
_LAST_DATASET_ENTRIES_KEY = "_local_persistence_dataset_entries"
#: BUG-71 — the crash-loop breaker. Written beside the manifest just before a
#: restore is applied, removed once a run that applied one reaches
#: `save_local_state` (the epilogue, i.e. the run rendered). Finding it at the
#: start of a session means the last session to restore this cache never got
#: that far, so this one opens without it — see `restore_local_state`.
RESTORE_MARKER_NAME = "restore-in-progress"
_RESTORE_PENDING_KEY = "_local_persistence_restore_pending"
_RESTORE_SKIPPED_KEY = "_local_persistence_restore_skipped"
#: Stored datasets this session could not read back, ``{name: {"entry": the
#: manifest entry, verbatim, "reason": why}}``. Each dataset restores on its own:
#: one with a missing or unreadable file stays out of the session, and its entry
#: and files stay in the cache — every save writes the entry back unchanged —
#: until the user retries it or removes it (:func:`retry_failed_datasets`,
#: :func:`discard_failed_dataset`).
_FAILED_DATASETS_KEY = "_local_persistence_failed_datasets"
#: Why the manifest itself could not be read, when it could not. A cache that
#: exists but cannot be read pauses saving, so this session cannot replace it;
#: an absent or cleared cache saves normally.
_CACHE_FAILURE_KEY = "_local_persistence_cache_failure"
#: The metadata tables' file, when the manifest points at it and it would not
#: read (round 10): ``{"pointer": …, "reason": …}``. Held back like a dataset —
#: every save keeps the pointer and leaves the file as it is — until
#: :func:`retry_failed_metadata` reads it or :func:`discard_failed_metadata`
#: removes it.
_FAILED_METADATA_KEY = "_local_persistence_failed_metadata"
_FRAME_KEYS = ("words", "fixations", "raw_gaze")
#: DATA-38 — the attached metadata tables live beside the manifest, not in it,
#: and are rewritten only when their content changes: the manifest is rewritten
#: on every durable settings change (a layer toggle, a trial switch), and a
#: trial table can run to tens of thousands of rows. #412: each write is a new
#: ``metadata-<token>.json`` that the manifest's pointer names; this is the one
#: name every cache written before that used, and a pointer to it still reads.
METADATA_FILE = "metadata.json"
_LAST_METADATA_SIGNATURE_KEY = "_local_persistence_metadata_signature"
#: DATA-47 — the manifest pointer written with that file, reused while nothing
#: changed (it lists every dataset's tables, which the signature does not).
_LAST_METADATA_POINTER_KEY = "_local_persistence_metadata_pointer"
#: #412 — the cache files the manifest this session last wrote or restored
#: names, as paths relative to the cache folder. What the next save's manifest
#: no longer names is this session's to remove at once (see `_remove_unreferenced`).
_LAST_REFERENCED_KEY = "_local_persistence_referenced"
#: The files this module writes, and so may remove: a dataset's frames — a
#: random token per write, or before #412 a slug of its name — and the metadata
#: sidecar, ``metadata.json`` before #412 and ``metadata-<token>.json`` since.
_FRAME_FILE_RE = re.compile(r"^[0-9a-f]+-(?:words|fixations|raw_gaze)\.parquet$")
_METADATA_FILE_RE = re.compile(r"^metadata(?:-[0-9a-f]+)?\.json$")
#: An unnamed file this session did not retire itself is removed only by the
#: session's first save — a pass at startup, not one per save, since a file
#: another tab or process sharing the folder still names would otherwise be
#: swept from under it on every save, and re-encoded by it on every next one —
#: and only once it is this old, in seconds: a younger one may be another
#: process's save not yet swapped in. Anything older is an interrupted save's
#: leftover, or a manifest's that has since been replaced.
_STALE_AFTER_S = 600.0
_SWEPT_KEY = "_local_persistence_swept"
_STATE_LOCK = threading.RLock()
_LOGGER = logging.getLogger(__name__)
_SESSION_KEYS = frozenset(PLOT_CONFIG_STATE_KEYS) | {
    "data_source_choice",
    "main_nav",
    "single_select_trial_mode",
    "single_trial_id",
    "single_participant",
    "single_slider",
    "single_animate",
    "wizard_filter_fields",
    "_composite_trial_columns",
    # VIZ-39 — the saved design library. It is the user's own work, not a
    # setting derived from a dataset, so it belongs in the cache for the same
    # reason annotations do: closing the app must not be how you lose it.
    DESIGN_PRESETS,
    # BUG-72 — Compare mode and the replay speed: `single_animate` was already
    # here, so a restart kept Animate but dropped Compare, its layout, whose
    # stimulus an overlay draws, and each scanpath's styling.
    SINGLE_COMPARE_TOGGLE,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_PLAYBACK_SPEED,
    *compare_state_keys(0),
    *compare_state_keys(1),
    # UX-174 r2 — the descriptions the user wrote: their own words, like the
    # design library. A plain session key so editing one never touches the
    # stored frames (see `constants.DATASET_DESCRIPTIONS_KEY`).
    DATASET_DESCRIPTIONS_KEY,
    # VIZ-45 — which dataset the raw-gaze layer's default was last decided for,
    # and what it overwrote. Without them a relaunch onto a raw-gaze-only
    # dataset decides again and turns back on a layer the user switched off.
    RAW_GAZE_SEEDED_FOR_KEY,
    RAW_GAZE_SNAP_RESTORE_KEY,
    # UX-184 — the folder the user chose for corpus downloads. A preference,
    # like the design library: a restart must not send the next download back
    # to the default folder.
    DOWNLOAD_DIR_KEY,
    # The recording setup the user saved for a built-in or public dataset, and
    # which one the `global_*` keys hold now with what they held before — all
    # three, or a relaunch would stash the override as the "before" it restores.
    DATASET_SETUP_OVERRIDES_KEY,
    SETUP_OVERRIDE_FOR_KEY,
    SETUP_OVERRIDE_RESTORE_KEY,
}


def is_loopback_url(url: str = "") -> bool:
    """Return whether ``url`` is addressed to this machine's loopback interface."""
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _is_loopback_host(host: str) -> bool:
    name = str(host or "").strip().strip("[]").lower()
    if name == "localhost":
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def server_bound_to_loopback() -> bool:
    """Whether the running Streamlit server listens on a loopback address only.

    This is the server's *own* configuration (``server.address``), which is what a
    locality decision has to rest on. The page URL is not: Streamlit copies
    ``st.context.url`` from the browser's own message, so any client can claim to
    be at ``http://localhost/``. Unset — Streamlit's default, which listens on
    every interface — is not loopback. Imports Streamlit lazily so the cache CLI
    and API stay Streamlit-free.
    """
    try:
        import streamlit as st

        address = st.get_option("server.address")
    except Exception:
        return False
    return _is_loopback_host(address or "")


def persistence_enabled(url: str = "", environ: dict | None = None) -> bool:
    """Return whether disk persistence is safe for this process.

    ``SCANPATH_STUDIO_PERSIST=1`` explicitly enables it and ``=0`` disables it.
    Without an override, inside a Streamlit server it is enabled only when that
    server listens on loopback alone (:func:`server_bound_to_loopback`) — the
    desktop app and ``scanpath-studio run`` bind ``127.0.0.1``; a bare
    ``streamlit run``, which listens on every interface, does not persist unless
    opted in.

    ENG-56: this used to ask whether ``url`` was a loopback URL, and the app
    passes ``st.context.url`` — which Streamlit copies from the browser's own
    message. So any machine that could reach the port could claim to be at
    ``http://localhost/`` and have the owner's cached datasets restored into its
    session. The URL is still consulted **outside** a Streamlit server (the
    ``cache`` CLI, the API, tests), where no browser supplies it and the caller
    is describing where the app would be served.
    """
    env = os.environ if environ is None else environ
    override = str(env.get(PERSIST_ENV_VAR, "")).strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    try:
        from streamlit import runtime

        serving = runtime.exists()
    except Exception:  # pragma: no cover - streamlit is a hard dependency
        serving = False
    return server_bound_to_loopback() if serving else is_loopback_url(url)


def state_directory(environ: dict | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = str(env.get(STATE_DIR_ENV_VAR, "")).strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache" / "scanpath-studio" / CACHE_DIR_NAME


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _metadata_signature(session: MutableMapping[str, Any]) -> list:
    """DATA-38 — the attached metadata tables' content fingerprint.

    Imported here rather than at module level: `metadata` pulls in `data`, and
    with it Streamlit, which :func:`cache_status` (the CLI's `cache` subcommand)
    promises not to import.
    """
    from . import metadata as metadata_mod

    return metadata_mod.store_signature(session)


def _dataset_identity(session: MutableMapping[str, Any]) -> list:
    """Cheap session identity for datasets whose frames are immutable objects."""
    datasets = []
    for name, payload in sorted(dict(session.get("_datasets", {})).items()):
        frames = []
        for frame_key in _FRAME_KEYS:
            frame = payload.get(frame_key)
            frames.append(
                (
                    frame_key,
                    id(frame),
                    tuple(frame.shape) if isinstance(frame, pd.DataFrame) else None,
                )
            )
        metadata = {
            k: _json_safe(v) for k, v in payload.items() if k not in _FRAME_KEYS
        }
        datasets.append((str(name), frames, metadata))
    return datasets


def _state_fingerprint(
    session: MutableMapping[str, Any], metadata_signature: list | None = None
) -> str:
    """Cheap rerun fingerprint over datasets plus durable UI state."""
    if metadata_signature is None:
        metadata_signature = _metadata_signature(session)
    datasets = _dataset_identity(session)
    values = {
        key: _json_safe(value)
        for key, value in session.items()
        if key in _SESSION_KEYS or str(key).startswith(COLUMN_MAPPING_PREFIX)
    }
    # DATA-48: the live store by content, every other dataset's by revision.
    annotations = annotations_mod.store_signature(session)
    encoded = json.dumps(
        [
            datasets,
            values,
            annotations,
            metadata_signature,
            sorted(_failed(session)),
            # Round 10: resolving held-back metadata tables changes what the
            # manifest says, so it is a change worth saving.
            failed_metadata(session),
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _atomic_parquet(frame: pd.DataFrame, destination: Path) -> None:
    """Write one frame without exposing a partial Parquet file to readers."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.stem}.",
            suffix=".parquet.tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        frame.to_parquet(temporary, index=False)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_text(source: str, destination: Path) -> None:
    """Atomically replace a UTF-8 text file using a unique sibling temporary."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(source)
            temporary = Path(handle.name)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _new_token() -> str:
    """A fresh name for one write's files (#412): never one a manifest names."""
    return secrets.token_hex(8)


def _write_dataset(payload: dict, frames_dir: Path, written: list[Path]) -> dict:
    """Write one dataset's frames under a fresh token; its manifest entry.

    Each path goes into ``written`` before its write, so a save that fails
    can remove what it left (see :func:`save_state`).
    """
    token = _new_token()
    metadata = {k: _json_safe(v) for k, v in payload.items() if k not in _FRAME_KEYS}
    frame_files = {}
    frame_rows = {}
    for frame_key in _FRAME_KEYS:
        frame = payload.get(frame_key)
        if not isinstance(frame, pd.DataFrame):
            frame = pd.DataFrame()
        filename = f"{token}-{frame_key}.parquet"
        written.append(frames_dir / filename)
        _atomic_parquet(frame, frames_dir / filename)
        frame_files[frame_key] = f"datasets/{filename}"
        frame_rows[frame_key] = len(frame)
    # ``rows`` is reporting-only (cache_status / the in-app panel say how
    # much is stored without opening the Parquet files). The restore path
    # reads ``frames`` alone, so an older manifest without it still loads.
    return {"metadata": metadata, "frames": frame_files, "rows": frame_rows}


def _manifest_for(
    session: MutableMapping[str, Any],
    root: Path,
    dataset_identity: list,
    written: list[Path],
) -> dict:
    """The manifest this save writes, with the frames of every changed dataset
    written beside it under new names (``written`` lists them).

    A dataset reuses its last entry — no Parquet is written — when its
    identity is the one that entry was written for and the files it names are
    still there; any other is written afresh. Per dataset, so adding one never
    rewrites the others. The existence check is a ``stat`` per frame: another
    session sharing the folder may have removed them since (#412).
    """
    cached_entries = session.get(_LAST_DATASET_ENTRIES_KEY)
    last_entries = cached_entries if isinstance(cached_entries, dict) else {}
    last_identity = {
        item[0]: item for item in session.get(_LAST_DATASET_IDENTITY_KEY) or ()
    }
    identity = {item[0]: item for item in dataset_identity}
    frames_dir = root / "datasets"
    frames_dir.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name, payload in dict(session.get("_datasets", {})).items():
        name = str(name)
        entry = last_entries.get(name)
        if (
            isinstance(entry, dict)
            and name in last_identity
            and last_identity[name] == identity.get(name)
            and _entry_files_present(root, entry)
        ):
            if not entry.get("rows") and isinstance(payload, dict):
                # A manifest written before ``rows`` existed is still
                # restorable, and restoring seeds these entries verbatim — so
                # without this backfill an upgraded install would reuse row-less
                # entries forever and the panel would read "1 dataset · 0 rows ·
                # 812 MB". Reuse means the live frames ARE the ones on disk, so
                # counting them is accurate and free (len is O(1)).
                entry = {
                    **entry,
                    "rows": {
                        frame_key: len(payload[frame_key])
                        for frame_key in _FRAME_KEYS
                        if isinstance(payload.get(frame_key), pd.DataFrame)
                    },
                }
            datasets[name] = entry
            continue
        datasets[name] = _write_dataset(payload, frames_dir, written)

    # A stored dataset this session could not read goes back exactly as it was
    # found — entry and files untouched — so a save never costs the cache a
    # dataset it merely failed to open. A dataset of the same name added since
    # is the user's newer work and takes the name (see `save_state`).
    for name, record in _failed(session).items():
        datasets.setdefault(name, record["entry"])

    values = {key: _json_safe(session[key]) for key in _SESSION_KEYS if key in session}
    values.update(
        {
            key: _json_safe(value)
            for key, value in session.items()
            if str(key).startswith(COLUMN_MAPPING_PREFIX)
        }
    )
    return {
        "schema": SCHEMA_VERSION,
        "datasets": datasets,
        "session": values,
        # DATA-48: `{"datasets": {name: [records]}}` — each dataset's own.
        "annotations": annotations_mod.cache_payload(session),
    }


def _save_metadata(
    session: MutableMapping[str, Any],
    root: Path,
    signature: list,
    written: list[Path],
) -> tuple[dict | None, dict]:
    """DATA-38 — write the attached tables to a new sidecar if they changed.

    Returns the manifest's pointer to them (``None`` when nothing is attached)
    and the bookkeeping to keep once a manifest naming it is in place —
    ``{key: value}``, ``None`` meaning "forget". The tables are `metadata`'s
    JSON payloads; the pointer is optional, so a manifest without it (every
    one written before DATA-38) still restores, and the schema version does
    not move.

    #412: a change is written to a new ``metadata-<token>.json`` (listed in
    ``written``), never over the file the current manifest names, and nothing
    is deleted here — the old file goes once the new manifest is in place.
    """
    from . import metadata as metadata_mod

    held = session.get(_FAILED_METADATA_KEY)
    if isinstance(held, dict):
        # Round 10: the stored tables did not read back. Writing this session's
        # (often none) would replace or delete them, so the file and the
        # manifest's pointer stay as they are until a retry or a discard.
        pointer = held.get("pointer")
        return (dict(pointer) if isinstance(pointer, dict) else None), {}
    forget = {_LAST_METADATA_SIGNATURE_KEY: None, _LAST_METADATA_POINTER_KEY: None}
    if not signature:
        return None, forget
    pointer = session.get(_LAST_METADATA_POINTER_KEY)
    if (
        session.get(_LAST_METADATA_SIGNATURE_KEY) == signature
        and isinstance(pointer, dict)
        and not _metadata_file_problem(root, pointer)
    ):
        return pointer, {}
    # DATA-47: one entry per dataset, `{"datasets": {name: {grain: …}}}`.
    datasets = metadata_mod.dataset_payloads(session)
    if not datasets:
        return None, forget
    # No `sort_keys`: each row keeps its columns in the table's own order.
    encoded = json.dumps(_json_safe({"datasets": datasets}), ensure_ascii=False)
    name = f"metadata-{_new_token()}.json"
    written.append(root / name)
    _atomic_text(encoded, root / name)
    pointer = {
        "file": name,
        "tables": [
            f"{dataset}:{grain}"
            for dataset, tables in datasets.items()
            for grain in tables
        ],
    }
    return pointer, {
        _LAST_METADATA_SIGNATURE_KEY: signature,
        _LAST_METADATA_POINTER_KEY: pointer,
    }


def save_state(session: MutableMapping[str, Any], root: Path) -> bool:
    """Save local datasets and durable session preferences, all or nothing.

    #412: what changed is written to new files, and the manifest naming them
    replaces the old one in a single atomic rename — the save's only
    replacement. A failure before it leaves the old manifest and every file it
    names as they were (the new files are removed again), so the next launch
    restores the whole previous session; after it, the whole new one. Files no
    manifest names any longer are removed only once the new one is in place.
    """
    with _STATE_LOCK:
        failed = _failed(session)
        live_names = {str(name) for name in dict(session.get("_datasets", {}))}
        if failed.keys() & live_names:
            # Re-added under the same name: the new dataset is the one to keep.
            _set_failed(
                session, {k: v for k, v in failed.items() if k not in live_names}
            )
        metadata_signature = _metadata_signature(session)
        fingerprint = _state_fingerprint(session, metadata_signature)
        if session.get(_LAST_FINGERPRINT_KEY) == fingerprint:
            return False
        root.mkdir(parents=True, exist_ok=True)
        dataset_identity = _dataset_identity(session)
        written: list[Path] = []
        swapped = False
        try:
            manifest = _manifest_for(session, root, dataset_identity, written)
            metadata, metadata_bookkeeping = _save_metadata(
                session, root, metadata_signature, written
            )
            if metadata:
                manifest["metadata"] = metadata
            # DATA-32: the dataset table's remembered counts ride along with the
            # datasets they describe — one small dict, and it is what stops a
            # restored session recounting every corpus it has ever opened.
            # Written here rather than inside `_manifest_for` because it is
            # session state, not a frame on disk.
            counts = session.get(DATASET_COUNTS_STORE_KEY)
            if isinstance(counts, dict) and counts:
                manifest["dataset_counts"] = _json_safe(counts)
            encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
            # The commit point: before this rename the old manifest is the
            # cache, after it the new one is.
            _atomic_text(encoded, root / "manifest.json")
            swapped = True
        finally:
            if not swapped:
                # Named by no manifest: this save's files would only be litter.
                for path in written:
                    _unlink_quietly(path)
        session[_LAST_FINGERPRINT_KEY] = fingerprint
        session[_LAST_DATASET_IDENTITY_KEY] = dataset_identity
        # The live datasets' entries only: a held-back one is merged in by
        # `_manifest_for` from its own record on every save, and must leave the
        # manifest the moment that record is removed.
        held_back = _failed(session)
        session[_LAST_DATASET_ENTRIES_KEY] = {
            name: entry
            for name, entry in manifest["datasets"].items()
            if name not in held_back
        }
        for key, value in metadata_bookkeeping.items():
            if value is None:
                session.pop(key, None)
            else:
                session[key] = value
        referenced = _manifest_references(root, manifest)
        previous = session.get(_LAST_REFERENCED_KEY)
        retired = (set(previous) if isinstance(previous, list) else set()) - referenced
        session[_LAST_REFERENCED_KEY] = sorted(referenced)
        _remove_unreferenced(
            root, referenced, retired, sweep=not session.get(_SWEPT_KEY)
        )
        session[_SWEPT_KEY] = True
        return True


def _manifest_references(root: Path, manifest: Any) -> set[str]:
    """The cache files ``manifest`` names, relative to ``root`` (#412).

    Tolerant of any shape, since a manifest on disk can hold anything: what
    does not name a file inside the cache folder names nothing to keep.
    """
    referenced: set[str] = set()
    if not isinstance(manifest, dict):
        return referenced
    datasets = manifest.get("datasets")
    for entry in datasets.values() if isinstance(datasets, dict) else ():
        frames = entry.get("frames") if isinstance(entry, dict) else None
        for relative in frames.values() if isinstance(frames, dict) else ():
            plain = _plain_frame_file(relative)
            if plain:
                referenced.add(plain)
                continue
            try:
                referenced.add(f"datasets/{_frame_path(root, relative).name}")
            except (ValueError, OSError):
                continue
    pointer = manifest.get("metadata")
    if isinstance(pointer, dict):
        try:
            referenced.add(_metadata_path(root, pointer).name)
        except (ValueError, OSError):
            pass
    return referenced


def _plain_frame_file(relative: Any) -> str | None:
    """``relative`` when it is a frame path of the shape this module writes —
    ``datasets/<name>`` with one of its own file names, which nothing can
    resolve outside the cache folder — else ``None``.

    The save path's shortcut past :func:`_frame_path`'s two ``resolve`` calls
    per frame, which were most of a settings-only save's time; anything else
    still goes through it.
    """
    if not isinstance(relative, str):
        return None
    folder, _, name = relative.partition("/")
    return relative if folder == "datasets" and _FRAME_FILE_RE.match(name) else None


def _entry_files_present(root: Path, entry: dict) -> bool:
    """Whether every frame a reused entry names is still on disk (#412)."""
    frames = entry.get("frames")
    if not isinstance(frames, dict):
        return False
    plain = [_plain_frame_file(relative) for relative in frames.values()]
    if all(plain):
        return all((root / relative).is_file() for relative in plain)
    return not _entry_problem(root, entry)


def _owned(relative: str) -> bool:
    """Whether ``relative`` (to the cache folder) names a file of this module's."""
    folder, _, name = relative.rpartition("/")
    if folder == "datasets":
        return bool(_FRAME_FILE_RE.match(name))
    return not folder and bool(_METADATA_FILE_RE.match(name))


def _remove_unreferenced(
    root: Path, referenced: set[str], retired: set[str], *, sweep: bool
) -> None:
    """Remove the cache files the manifest just written does not name (#412).

    Run after the swap, never before: until then the old manifest is the
    cache. What this session's previous manifest named (``retired``) goes at
    once. With ``sweep`` — the session's first save — every other unnamed file
    of ours goes too, once it is :data:`_STALE_AFTER_S` old: the leftovers of an
    interrupted save, or of a manifest another session replaced. Only this
    module's own file names are touched, and a file that will not go is left.
    """
    now = time.time()
    candidates = [(relative, root / relative) for relative in retired]
    folders = ((root / "datasets", "datasets/"), (root, "")) if sweep else ()
    for folder, prefix in folders:
        try:
            candidates += [(f"{prefix}{path.name}", path) for path in folder.iterdir()]
        except OSError:
            continue  # a folder that will not list is left to a later session
    for relative, path in candidates:
        if not _owned(relative):
            continue
        if relative in referenced:
            continue
        if relative not in retired:
            try:
                if now - path.stat().st_mtime < _STALE_AFTER_S:
                    continue
            except OSError:
                continue
        _unlink_quietly(path)


def restore_state(
    session: MutableMapping[str, Any], root: Path, *, skip_session_keys=()
) -> bool:
    """Restore a manifest once, without overwriting already-seeded values.

    Returns whether a manifest was found and applied — the *mechanism*. Whether
    that is worth telling the user about is a different question, answered by
    :func:`restored_summary` / :func:`restored_from_cache` and asked by
    :func:`restore_local_state`; see UX-136 there.
    """
    if session.get(_RESTORED_KEY):
        return False
    session[_RESTORED_KEY] = True
    with _STATE_LOCK:
        return _restore_manifest(session, root, skip_session_keys)


def _restore_manifest(
    session: MutableMapping[str, Any], root: Path, skip_session_keys
) -> bool:
    """The body of :func:`restore_state`, under its lock."""
    path = root / "manifest.json"
    if not path.exists():
        return False
    try:
        # BUG-71: read and check the manifest's *shape* before touching the
        # session. It is a file on disk, so any JSON value can be in it —
        # `[]`, `null`, a dataset entry that is a string — and each of those
        # used to escape as an AttributeError on every launch.
        manifest = _as_mapping(json.loads(path.read_text(encoding="utf-8")))
        schema = int(manifest.get("schema", 0))
        if schema != SCHEMA_VERSION:
            raise ValueError(
                f"it was saved by another version (format {schema}; this one "
                f"reads {SCHEMA_VERSION})"
            )
        stored_datasets = _as_mapping(manifest.get("datasets", {}))
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        # The cache is there but cannot be read as a whole. Opening without
        # it is right — a damaged cache must never stop the app — but
        # overwriting it is not: the next save would replace whatever is
        # still recoverable with this session's empty state. So saving
        # pauses and the app says why (`cache_failure`), with a way to try
        # again or to clear it.
        session[_CACHE_FAILURE_KEY] = _failure_reason(exc)
        session[_PAUSED_KEY] = True
        _LOGGER.warning("Could not read the recovery cache at %s: %s", root, exc)
        return False
    # #412: what the manifest on disk names, so the save that replaces it
    # removes what the new one no longer does.
    session[_LAST_REFERENCED_KEY] = sorted(_manifest_references(root, manifest))

    # Each dataset restores on its own: one with a missing or damaged file
    # costs that dataset — held back, entry and files kept — never the
    # others, the settings, the annotations or the metadata tables.
    restored_datasets = {}
    stored_entries = {}
    failed = {}
    for index, (name, entry) in enumerate(stored_datasets.items(), start=1):
        try:
            restored_datasets[str(name)] = _read_dataset(root, entry)
            stored_entries[str(name)] = entry
        except Exception as exc:  # any failure costs this dataset, nothing more
            failed[str(name)] = {
                "entry": _json_safe(entry),
                "reason": _failure_reason(exc),
            }
            _LOGGER.warning(
                "Could not restore the cached dataset %r: %s", str(name), exc
            )
        progress.report(index, len(stored_datasets), unit="datasets")
    try:
        stored_session = _restorable_session(manifest.get("session", {}))
    except (ValueError, TypeError, AttributeError) as exc:
        # Settings are rewritten from this session on the next save; a block
        # that is not even an object has nothing in it worth keeping.
        _LOGGER.warning("Ignored the recovery cache's settings: %s", exc)
        stored_session = {}
    existing = dict(session.get("_datasets", {}))
    if restored_datasets:
        session["_datasets"] = {**restored_datasets, **existing}
    _set_failed(session, {k: v for k, v in failed.items() if k not in existing})
    # Only the names that were not already open actually *landed* — an
    # in-memory dataset of the same name shadows the stored one above.
    summary = {"datasets": len(set(restored_datasets) - set(existing))}
    skip = set(skip_session_keys)
    # Counted before the loop below writes it: `setdefault` means a
    # design library already in this session keeps its own, so the stored
    # one restored nothing.
    summary["designs"] = (
        len(stored_session.get(DESIGN_PRESETS) or {})
        if DESIGN_PRESETS not in skip and DESIGN_PRESETS not in session
        else 0
    )
    for key, value in stored_session.items():
        if key not in skip:
            session.setdefault(key, value)
    # DATA-48 — per dataset, `{"datasets": {name: [records]}}`. A
    # manifest from before that holds one flat list naming no dataset;
    # `restore_payload` hands it to the dataset this session opens on
    # (the one the manifest had selected), once — see its docstring. A
    # held-back dataset's annotations restore too: they are filed under
    # its name and written back with it.
    try:
        summary["annotations"] = annotations_mod.restore_payload(
            session, manifest.get("annotations")
        )
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        _LOGGER.warning("Could not restore the cached annotations: %s", exc)
        summary["annotations"] = 0
    # DATA-38 — the attached metadata tables. Counted, because a user
    # recognises their participant table coming back (UX-136's test for
    # what is worth announcing), unlike a restored canvas width.
    summary["metadata"] = _restore_metadata(session, root, manifest.get("metadata"))
    # A clean restore can reuse the Parquet files on the first rendered
    # settings change. Pre-existing in-memory datasets still need a save.
    if not existing:
        session[_LAST_DATASET_IDENTITY_KEY] = _dataset_identity(session)
        session[_LAST_DATASET_ENTRIES_KEY] = stored_entries
    counts = manifest.get("dataset_counts")
    if isinstance(counts, dict):
        # DATA-32 — a manifest written before this existed simply has
        # none, and the table recounts what it can, as it always did.
        session[DATASET_COUNTS_STORE_KEY] = dict(counts)
    # Separate from _RESTORED_KEY, which only records that a restore was
    # *attempted* this session. The app reads this one to tell the user
    # their previous session came back (restored_from_cache), so it holds
    # the summary rather than a bare flag — see the docstring.
    session[_RESTORED_PAYLOAD_KEY] = summary
    return True


def _failure_reason(exc: BaseException) -> str:
    """A short, user-facing reason for a part of the cache that would not read."""
    if isinstance(exc, FileNotFoundError):
        name = Path(str(exc.filename or "")).name
        return f"a stored file is missing ({name})" if name else "a file is missing"
    if isinstance(exc, PermissionError):
        return "a stored file can't be opened (permission denied)"
    if isinstance(exc, json.JSONDecodeError):
        return "its index file (manifest.json) is damaged"
    message = str(exc).strip()
    if isinstance(exc, ValueError) and message.startswith("it "):
        return message
    # The class and message are for a bug report, not for the warning.
    _LOGGER.warning("Saved data unreadable: %s: %s", type(exc).__name__, message)
    return "it can't be read (damaged, or written by another version)"


def _frame_path(root: Path, relative: Any) -> Path:
    """Where a manifest entry's frame lives — only ever inside the cache folder."""
    base = (root / "datasets").resolve()
    path = (root / str(relative)).resolve()
    if path.parent != base:
        raise ValueError(f"it names a file outside the cache folder ({relative})")
    return path


def _read_dataset(root: Path, entry: Any) -> dict:
    """One stored dataset's payload, frames read — or the exception that stopped it."""
    entry = _as_mapping(entry)
    payload = dict(_as_mapping(entry.get("metadata", {})))
    for frame_key, relative in _as_mapping(entry.get("frames", {})).items():
        payload[frame_key] = pd.read_parquet(_frame_path(root, relative))
    for frame_key in _FRAME_KEYS:
        payload.setdefault(frame_key, pd.DataFrame())
    return payload


def _failed(session: MutableMapping[str, Any]) -> dict:
    value = session.get(_FAILED_DATASETS_KEY)
    return dict(value) if isinstance(value, dict) else {}


def _set_failed(session: MutableMapping[str, Any], failed: dict) -> None:
    if failed:
        session[_FAILED_DATASETS_KEY] = dict(failed)
    else:
        session.pop(_FAILED_DATASETS_KEY, None)


def failed_datasets(session) -> dict[str, str]:
    """The cached datasets this session could not read back: ``{name: reason}``.

    Their entries and files stay in the cache — every save writes them back as
    they were — until :func:`retry_failed_datasets` reads them or
    :func:`discard_failed_dataset` removes them.
    """
    return {
        name: str(record.get("reason", "")) for name, record in _failed(session).items()
    }


def cache_failure(session) -> str | None:
    """Why this session could not read the cache at all, or ``None``.

    Set only when a manifest *exists* and failed to read; saving is paused for
    the session then, so the stored copy is not replaced. An absent cache — never
    written, or cleared on purpose — is not a failure and saves normally.
    """
    reason = session.get(_CACHE_FAILURE_KEY)
    return str(reason) if reason else None


def retry_failed_datasets(session, root: Path | None = None) -> dict[str, str]:
    """Try the held-back datasets again; returns those that still fail.

    One that now reads joins the session's datasets (a dataset of the same name
    opened since keeps its place, and the stored copy is dropped from the
    held-back list).
    """
    directory = state_directory() if root is None else root
    failed = _failed(session)
    if not failed:
        return {}
    with _STATE_LOCK:
        live = dict(session.get("_datasets", {}))
        entries = session.get(_LAST_DATASET_ENTRIES_KEY)
        # The reuse bookkeeping stays valid only if it described the session
        # before these were added; extend it rather than force a full rewrite.
        reusable = isinstance(entries, dict) and session.get(
            _LAST_DATASET_IDENTITY_KEY
        ) == _dataset_identity(session)
        recovered = {}
        for name, record in list(failed.items()):
            if name in live:
                failed.pop(name)
                continue
            try:
                payload = _read_dataset(directory, record.get("entry"))
            except Exception as exc:  # still unreadable: it stays held back
                failed[name] = {**record, "reason": _failure_reason(exc)}
                continue
            live[name] = payload
            recovered[name] = record.get("entry")
            failed.pop(name)
        if recovered:
            session["_datasets"] = live
            if reusable:
                session[_LAST_DATASET_ENTRIES_KEY] = {**entries, **recovered}
                session[_LAST_DATASET_IDENTITY_KEY] = _dataset_identity(session)
        _set_failed(session, failed)
    return failed_datasets(session)


def discard_failed_dataset(session, name: str, root: Path | None = None) -> bool:
    """Remove one held-back dataset from the cache: its entry and its files.

    The next save writes the manifest without it. Its annotations and metadata
    tables are kept — they are filed by name, like every dataset's, and are the
    user's own work — so a dataset added again under that name finds them.
    """
    directory = state_directory() if root is None else root
    failed = _failed(session)
    record = failed.pop(str(name), None)
    if record is None:
        return False
    with _STATE_LOCK:
        entry = record.get("entry")
        frames = entry.get("frames") if isinstance(entry, dict) else None
        # Only the files its entry names. Not guessed from its name: since #412
        # a rename keeps a dataset's files where they are, so the files named
        # after this one's slug may be another's now. A file an entry too
        # damaged to name it leaves behind goes with the next save's sweep.
        paths = set()
        for relative in frames.values() if isinstance(frames, dict) else ():
            try:
                paths.add(_frame_path(directory, relative))
            except ValueError:
                continue  # never delete outside the cache folder
        for path in paths:
            _unlink_quietly(path)
        _set_failed(session, failed)
    return True


def retry_cache_restore(session, url: str) -> bool:
    """Try a cache that could not be read again, from scratch, this session.

    Clears the failure and the pause it set, and restores as at launch — what a
    reload would do, without losing what the session already holds.
    """
    session.pop(_CACHE_FAILURE_KEY, None)
    session.pop(_PAUSED_KEY, None)
    session.pop(_RESTORED_KEY, None)
    return restore_local_state(session, url)


def _as_mapping(value: Any) -> dict:
    """``value`` if it is a JSON object, else ``ValueError`` (BUG-71)."""
    if not isinstance(value, dict):
        raise ValueError(
            f"expected an object in the manifest, got {type(value).__name__}"
        )
    return value


def _restorable_session(stored: Any) -> dict:
    """The manifest's ``session`` block, cut down to what is safe to seed (BUG-71).

    Only keys this module writes are restored — the durable settings and the
    column mapping — so a hand-edited or foreign manifest cannot seed arbitrary
    session state. Each value is held to its widget's rules by
    ``url_state.sanitize_session_value`` (clamped into range, or dropped): a
    restored value is seeded before its widget renders, exactly like a deep link,
    so an opacity of 7 or a colour of ``"zzz"`` stopped the app on every launch.
    Dropping it costs the user that one setting. Imported here, not at the top,
    because ``url_state`` pulls in Streamlit and the cache CLI must not.
    """
    from .url_state import sanitize_session_value

    clean = {}
    # Renamed keys move to their new names before the allow-list sees them.
    for key, value in rename_legacy_keys(_as_mapping(stored)).items():
        if not isinstance(key, str) or not (
            key in _SESSION_KEYS or key.startswith(COLUMN_MAPPING_PREFIX)
        ):
            continue
        if key == DATASET_DESCRIPTIONS_KEY:
            # UX-174 r2 — ``{dataset: sentence}``; anything else is dropped.
            if isinstance(value, dict):
                clean[key] = {
                    str(name): str(text)
                    for name, text in value.items()
                    if isinstance(text, str)
                }
            continue
        if key == DOWNLOAD_DIR_KEY:
            # UX-184 — a path seeds a text box: only a string may.
            if isinstance(value, str):
                clean[key] = value
            continue
        if key == DATASET_SETUP_OVERRIDES_KEY:
            # ``{dataset: setup}``, each read back through `SetupSnapshot`,
            # which degrades a bad field rather than the whole setup.
            if isinstance(value, dict):
                from .experimental_setup import SetupSnapshot

                clean[key] = {
                    str(name): SetupSnapshot.from_dict(setup).to_dict()
                    for name, setup in value.items()
                    if isinstance(setup, dict)
                }
            continue
        if key == SETUP_OVERRIDE_FOR_KEY:
            if isinstance(value, str):
                clean[key] = value
            continue
        if key == SETUP_OVERRIDE_RESTORE_KEY:
            # ``{global_* key: value or None}`` — each value held to its own
            # control's rules, and a key that is not a setup key dropped.
            if isinstance(value, dict):
                restore = {}
                for name, saved in value.items():
                    if name not in SETUP_OVERRIDE_SESSION_KEYS:
                        continue
                    try:
                        restore[name] = (
                            None
                            if saved is None
                            else sanitize_session_value(name, saved)
                        )
                    except (TypeError, ValueError, OverflowError):
                        continue
                clean[key] = restore
            continue
        if key == DESIGN_PRESETS:
            # The design library is the user's own work: keep every well-formed
            # design rather than all-or-nothing.
            # One saved before the fixed duration scale keeps the relative one.
            if isinstance(value, dict):
                from .controls import sanitize_design

                clean[key] = {
                    str(name): sanitize_design(
                        keep_legacy_marker_scale(rename_legacy_keys(design))
                    )[0]
                    for name, design in value.items()
                    if isinstance(design, dict)
                }
            continue
        try:
            clean[key] = sanitize_session_value(key, value)
        except (TypeError, ValueError, OverflowError):
            _LOGGER.warning(
                "Dropped %s from the recovery cache: %.80r is not a value its "
                "control accepts.",
                key,
                value,
            )
    # A session saved before the fixed duration scale reopens on the relative
    # one it was drawn with, as an old design or Share link does.
    return keep_legacy_marker_scale(clean)


def _restore_metadata(session: MutableMapping[str, Any], root: Path, pointer) -> int:
    """DATA-38 — re-attach the tables :func:`_save_metadata` wrote; how many.

    DATA-47: they come back into the per-dataset store, each dataset's own, and
    reach the session keys when that dataset is selected. Its own error
    boundary: a missing or unreadable sidecar costs the tables, never the
    datasets and settings the rest of the manifest restores — and it is held
    back (:func:`failed_metadata`), so no save replaces it (round 10).
    """
    if not isinstance(pointer, dict) or not pointer.get("file"):
        return 0
    from . import metadata as metadata_mod

    try:
        payloads = _read_metadata_file(root, pointer)
        return metadata_mod.restore_dataset_payloads(session, payloads)
    except Exception as exc:  # any failure costs the tables, nothing more
        session[_FAILED_METADATA_KEY] = {
            "pointer": _json_safe(pointer),
            "reason": _metadata_failure_reason(exc),
        }
        _LOGGER.warning("Could not restore the cached metadata tables: %s", exc)
        return 0


def _metadata_path(root: Path, pointer: Any) -> Path:
    """Where a manifest's metadata pointer leads — only ever inside the cache
    folder, directly (``metadata.json`` before #412, ``metadata-<token>.json``
    since)."""
    name = str(_as_mapping(pointer).get("file") or "")
    path = (root / name).resolve()
    if not name or path.parent != root.resolve():
        raise ValueError(f"it names a file outside the cache folder ({name})")
    return path


def _read_metadata_file(root: Path, pointer: Any) -> Any:
    """The metadata sidecar's JSON, from inside the cache folder only."""
    return json.loads(_metadata_path(root, pointer).read_text("utf-8"))


def _metadata_failure_reason(exc: BaseException) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "its file is not valid JSON"
    if isinstance(exc, FileNotFoundError):
        return f"its file is missing ({METADATA_FILE})"
    return _failure_reason(exc)


def failed_metadata(session) -> str | None:
    """Why the cached metadata tables did not read back, or ``None``."""
    held = session.get(_FAILED_METADATA_KEY)
    return str(held.get("reason", "")) if isinstance(held, dict) else None


def retry_failed_metadata(session, root: Path | None = None) -> str | None:
    """Read the held-back metadata tables again; the reason if they still fail.

    Tables that read join the store (a dataset holding tables of its own keeps
    them), and saving them resumes.
    """
    held = session.get(_FAILED_METADATA_KEY)
    if not isinstance(held, dict):
        return None
    directory = state_directory() if root is None else root
    from . import metadata as metadata_mod

    with _STATE_LOCK:
        try:
            payloads = _read_metadata_file(directory, held.get("pointer"))
            metadata_mod.restore_dataset_payloads(session, payloads)
        except Exception as exc:  # still unreadable: it stays held back
            reason = _metadata_failure_reason(exc)
            session[_FAILED_METADATA_KEY] = {**held, "reason": reason}
            return reason
        session.pop(_FAILED_METADATA_KEY, None)
        # Written afresh on the next save, from the store as it now stands.
        session.pop(_LAST_METADATA_SIGNATURE_KEY, None)
    return None


def discard_failed_metadata(session, root: Path | None = None) -> bool:
    """Delete the held-back metadata tables' file; saving them resumes.

    Only that copy: the datasets, their annotations and the tables attached
    this session are left alone, and the next save writes the latter.
    """
    held = session.pop(_FAILED_METADATA_KEY, None)
    if not isinstance(held, dict):
        return False
    directory = state_directory() if root is None else root
    with _STATE_LOCK:
        try:
            path = _metadata_path(directory, held.get("pointer"))
        except ValueError:
            # A pointer that names no file in the cache folder is not followed.
            path = directory / METADATA_FILE
        _unlink_quietly(path)
        session.pop(_LAST_METADATA_SIGNATURE_KEY, None)
        session.pop(_LAST_METADATA_POINTER_KEY, None)
    return True


def _metadata_files(root: Path) -> list[Path]:
    """Every metadata sidecar in ``root``: the pre-#412 one and the versioned."""
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.iterdir()
        if _METADATA_FILE_RE.match(path.name) and path.is_file()
    )


def forget_state(root: Path) -> None:
    """Remove the known persistence files without recursively deleting ``root``."""
    with _STATE_LOCK:
        manifest = root / "manifest.json"
        if manifest.exists():
            manifest.unlink()
        (root / RESTORE_MARKER_NAME).unlink(missing_ok=True)
        for path in _metadata_files(root):
            path.unlink(missing_ok=True)
        frames_dir = root / "datasets"
        if frames_dir.is_dir():
            for path in frames_dir.glob("*.parquet"):
                path.unlink()
            try:
                frames_dir.rmdir()
            except OSError:
                pass


def rename_cached_dataset(
    session: MutableMapping[str, Any],
    old: str,
    new: str,
    root: Path | None = None,
) -> bool:
    """Follow a dataset rename (DATA-23) through the cache instead of rewriting it.

    A dataset's Parquet files are not named after the dataset (#412 — a token
    per write; a cache from before that names them after the old name's slug,
    and keeps those names), so a rename moves no file: re-keying
    ``manifest.json`` — one atomic replacement — and this session's reuse
    bookkeeping keeps the next :func:`save_state` on the cheap reuse path, which
    rewrites the manifest only and leaves no orphan behind.

    Call it **after** the store itself has been re-keyed: the new reuse identity is
    read from the live ``session["_datasets"]``. Best-effort like the rest of this
    module — on any failure the session's bookkeeping is dropped so the next save
    rebuilds the cache in full rather than trusting it.
    """
    if old == new:
        return False
    directory = state_directory() if root is None else root
    with _STATE_LOCK:
        try:
            manifest_path = directory / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                datasets = dict(manifest.get("datasets", {}))
                if old in datasets:
                    datasets[new] = datasets.pop(old)
                    manifest["datasets"] = datasets
                    values = dict(manifest.get("session", {}))
                    if values.get("data_source_choice") == old:
                        values["data_source_choice"] = new
                        manifest["session"] = values
                    _atomic_text(
                        json.dumps(
                            manifest, ensure_ascii=False, sort_keys=True, indent=2
                        ),
                        manifest_path,
                    )
            entries = session.get(_LAST_DATASET_ENTRIES_KEY)
            if isinstance(entries, dict) and old in entries:
                entries = dict(entries)
                entries[new] = entries.pop(old)
                session[_LAST_DATASET_ENTRIES_KEY] = entries
                session[_LAST_DATASET_IDENTITY_KEY] = _dataset_identity(session)
            return True
        except (OSError, ValueError, TypeError, KeyError):
            for key in (
                _LAST_FINGERPRINT_KEY,
                _LAST_DATASET_IDENTITY_KEY,
                _LAST_DATASET_ENTRIES_KEY,
            ):
                session.pop(key, None)
            _LOGGER.warning(
                "Could not follow a dataset rename through the local cache.",
                exc_info=True,
            )
            return False


def restore_local_state(
    session, url: str, *, protect_data_source: bool = False
) -> bool:
    """Restore this machine's cached session, once, and say whether to announce it.

    UX-136: the return value is **not** "a manifest was applied" — that is
    :func:`restore_state`'s answer, and the app used to toast "Recovered your
    last session from this computer" on it. Every rerun writes the cache, so a
    session that has only ever changed view settings still leaves a manifest
    behind, and restoring one announced a recovery that the user could not see
    anywhere — worst of all immediately after they had cleared the cache by
    hand, where it reads as "clearing it did nothing". So the announcement is
    gated on something a user would *recognise* coming back: a dataset they
    added, an annotation they wrote, a design they saved. Settings still restore;
    they just do it silently, because nobody can tell a restored canvas width
    from the default one.
    """
    if not persistence_enabled(url):
        session[_RESTORED_KEY] = True
        return False
    if session.get(_RESTORED_KEY):
        return False
    root = state_directory()
    marker = root / RESTORE_MARKER_NAME
    if marker.is_file():
        # BUG-71: the last session that applied this cache never finished a run,
        # and a restore that breaks the app breaks it before the Data page can
        # offer a reset — so every launch would break again. Open
        # without it, once. The files stay, and saving is paused so this
        # session's (empty) state cannot overwrite them; the marker goes, so a
        # reload tries again — one strike, because a tab closed mid-way through a
        # slow first run leaves the marker too, and that must not cost the cache.
        session[_RESTORED_KEY] = True
        session[_RESTORE_SKIPPED_KEY] = True
        session[_PAUSED_KEY] = True
        _unlink_quietly(marker)
        _LOGGER.warning(
            "The previous session never finished opening with the recovery cache "
            "at %s; opened without restoring it (the files are kept).",
            root,
        )
        return False
    if (root / "manifest.json").is_file():
        try:
            marker.write_text(datetime.now().isoformat(timespec="seconds"), "utf-8")
            session[_RESTORE_PENDING_KEY] = str(marker)
        except OSError:
            pass  # a cache we cannot write to simply goes without the breaker
    protected = {"data_source_choice"} if protect_data_source else set()
    if not restore_state(session, root, skip_session_keys=protected):
        _finish_restore(session)
        return False
    return restored_from_cache(session)


def local_state_restored(session) -> bool:
    """Whether this session has had its one restore attempt already.

    Set by :func:`restore_local_state` on its first call whatever the outcome —
    restored, nothing cached, persistence off, or skipped (BUG-71) — and every
    later call returns at once. The app opens the restore card only before it
    (UX-166): a card around a call that does nothing cost each run a timer
    thread and a task for nothing.
    """
    return bool(session.get(_RESTORED_KEY))


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        _LOGGER.warning("Could not remove %s.", path)


def _finish_restore(session) -> None:
    """This session's restore held (or never happened): drop its marker."""
    marker = session.pop(_RESTORE_PENDING_KEY, None)
    if marker:
        _unlink_quietly(Path(marker))


def consume_restore_skipped(session) -> bool:
    """Whether this session opened without its cache because the last one broke.

    One-shot, so the app says it once: the notice belongs to the launch, not to
    every rerun after it. See :func:`restore_local_state` (BUG-71).
    """
    return bool(session.pop(_RESTORE_SKIPPED_KEY, False))


def restored_summary(session) -> dict:
    """How much of *what* this session got back from the cache, by kind.

    ``{"datasets": n, "annotations": n, "designs": n, "metadata": n}`` — what
    the *Saved on this computer* section counts, and what a user would recognise as
    their last session (``metadata`` is the number of attached participant /
    trial / text tables, DATA-38). View settings are deliberately absent: they restore, but
    silently (UX-136 — see :func:`restore_state`). Empty when no restore
    happened, and after :func:`clear_local_state`.
    """
    summary = session.get(_RESTORED_PAYLOAD_KEY)
    return dict(summary) if isinstance(summary, dict) else {}


def session_was_restored(session) -> bool:
    """Whether this session applied a saved manifest at all (#374 F32).

    Wider than :func:`restored_from_cache`: settings alone count, since they
    still say the app was used here before. The welcome tour reads it."""
    return isinstance(session.get(_RESTORED_PAYLOAD_KEY), dict)


def restored_from_cache(session) -> bool:
    """Whether this session got back something the user would recognise.

    Not "was a manifest read" — see :func:`restore_state` for why the two came
    apart.
    """
    return any(restored_summary(session).values())


def persistence_paused(session) -> bool:
    """Whether saving is paused for this session.

    Set by :func:`restore_local_state`'s BUG-71 breaker, after a launch that
    never finished opening with the cache, and by a manifest that exists but
    cannot be read (:func:`cache_failure`): this session then leaves the stored
    copy untouched, and a reload — or :func:`retry_cache_restore` — tries it
    again. :func:`clear_local_state` lifts it.
    """
    return bool(session.get(_PAUSED_KEY))


def clear_local_state(session=None, root: Path | None = None) -> bool:
    """Delete the stored cache and forget what this session had written.

    The in-memory datasets are deliberately left alone — this removes the copy
    on disk, it does not close the user's work.

    Deleting the files is best-effort: a locked or read-only cache directory
    must not wedge ``scanpath-studio cache --clear``, which a user reaches for
    precisely when the session is already broken. An :class:`OSError` is logged and reported as ``False``; the
    in-session bookkeeping is cleared either way.
    """
    removed = True
    try:
        forget_state(state_directory() if root is None else root)
    except OSError as exc:
        removed = False
        _LOGGER.warning("Could not delete the recovery cache: %s", exc)
    if session is not None:
        for key in (
            _LAST_FINGERPRINT_KEY,
            _LAST_DATASET_IDENTITY_KEY,
            _LAST_DATASET_ENTRIES_KEY,
            _RESTORED_PAYLOAD_KEY,
            _LAST_METADATA_SIGNATURE_KEY,
            _LAST_METADATA_POINTER_KEY,
            _LAST_REFERENCED_KEY,
            # DATA-32: the remembered counts are part of what "forget this
            # session" means — the ask named clearing the cache explicitly.
            DATASET_COUNTS_STORE_KEY,
            # Nothing is left to protect or to retry: a cleared cache saves
            # normally, like one that never existed.
            _FAILED_DATASETS_KEY,
            _FAILED_METADATA_KEY,
            _CACHE_FAILURE_KEY,
            _PAUSED_KEY,
        ):
            session.pop(key, None)
    return removed


def clear_saved_work(session) -> bool:
    """Delete what is saved on this computer and start over.

    The Data page's *Clear what is saved…* (#374 F33). Deleting the files alone
    would be undone within a click, because every run ends in
    ``save_local_state`` and this tab still holds the datasets, annotations and
    settings. So the session is emptied too: the next run is a first visit (the
    default dataset and settings), and saving carries on from there as usual.
    Returns whether the files were removed.
    """
    removed = clear_local_state(session)
    session.clear()
    return removed


def _cache_files(root: Path) -> list:
    """The files this module owns under ``root`` (mirrors forget_state)."""
    files = [root / "manifest.json", root / RESTORE_MARKER_NAME, *_metadata_files(root)]
    frames_dir = root / "datasets"
    if frames_dir.is_dir():
        files.extend(sorted(frames_dir.glob("*.parquet")))
    return [path for path in files if path.is_file()]


def human_size(num_bytes: int) -> str:
    """Format a byte count for the cache panel / CLI (1 decimal, binary units)."""
    size = float(max(int(num_bytes), 0))
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"  # pragma: no cover - unreachable, loop returns first


def cache_status(
    root: Path | None = None,
    *,
    url: str = "",
    environ: dict | None = None,
) -> dict:
    """Describe the on-device recovery cache — the whole read-only surface.

    Streamlit-free on purpose: the same dict backs the in-app panel, the
    ``scanpath-studio cache`` subcommand and ``api.cache_status``. Reading is
    best-effort — a partial or corrupt manifest reports ``readable=False``
    rather than raising, exactly as ``restore_state`` refuses to break the app
    over one. ``rows`` is ``None`` (not ``0``) when a stored dataset predates
    the manifest's ``rows`` field: "0 rows · 812 MB on disk" would be a lie,
    "size only" is the truth. The next save backfills it.
    """
    env = os.environ if environ is None else environ
    override = str(env.get(PERSIST_ENV_VAR, "")).strip().lower()
    directory = state_directory(env) if root is None else Path(root)
    manifest_path = directory / "manifest.json"
    status = {
        "enabled": persistence_enabled(url, env),
        "override": (
            "on"
            if override in {"1", "true", "yes", "on"}
            else "off"
            if override in {"0", "false", "no", "off"}
            else ""
        ),
        "directory": str(directory),
        "exists": manifest_path.is_file(),
        "readable": False,
        "schema": None,
        "datasets": [],
        "rows": 0,
        "annotations": 0,
        "designs": 0,
        "metadata": 0,
        "settings": 0,
        "bytes": 0,
        "saved_at": None,
        # Stored datasets the app cannot restore: ``[{"name", "reason"}]``.
        "damaged": [],
        # Why the stored metadata tables cannot restore, or "" (round 10).
        "damaged_metadata": "",
    }
    if not directory.is_dir():
        # The common hosted case: one stat, then out — no glob over a folder
        # this deployment never creates.
        return status
    status["bytes"] = sum(path.stat().st_size for path in _cache_files(directory))
    if not status["exists"]:
        return status
    try:
        status["saved_at"] = datetime.fromtimestamp(
            manifest_path.stat().st_mtime
        ).isoformat(timespec="seconds")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        schema = int(manifest.get("schema", 0))
        status["schema"] = schema
        datasets = dict(manifest.get("datasets", {}))
        # Each stored dataset is described on its own, and one that cannot be
        # restored — an entry of the wrong shape, a file that is gone — is
        # listed under `damaged` with the reason, as the app's restore holds it
        # back. A stat per file, never a Parquet read: this runs on every
        # render of the Data page. (A file that is present but corrupt shows
        # only when the app tries to read it.)
        good, damaged = [], []
        for name, entry in sorted(datasets.items()):
            reason = _entry_problem(directory, entry)
            if reason:
                damaged.append({"name": str(name), "reason": reason})
                continue
            good.append(
                {
                    "name": str(name),
                    "rows": {
                        key: int(value)
                        for key, value in dict(entry.get("rows") or {}).items()
                    },
                }
            )
        status["datasets"] = good
        status["damaged"] = damaged
        status["rows"] = (
            sum(sum(entry["rows"].values()) for entry in status["datasets"])
            if all(entry["rows"] for entry in status["datasets"])
            else None
        )
        status["annotations"] = annotations_mod.payload_count(
            manifest.get("annotations")
        )
        stored_session = dict(manifest.get("session", {}))
        status["designs"] = len(dict(stored_session.get(DESIGN_PRESETS, {})))
        pointer = dict(manifest.get("metadata") or {})
        status["metadata"] = len(list(pointer.get("tables") or []))
        if pointer:
            status["damaged_metadata"] = _metadata_file_problem(directory, pointer)
        status["settings"] = len(stored_session)
        # A newer/unknown schema is present but will not restore — say so here
        # rather than let the panel claim the work is safely stored.
        status["readable"] = schema == SCHEMA_VERSION
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        status["readable"] = False
    return status


def _metadata_file_problem(root: Path, pointer: dict) -> str:
    """Why the manifest's metadata tables cannot restore, by a ``stat``; ``""``
    when nothing is wrong that one can see (a corrupt file shows only when the
    app reads it, as for datasets)."""
    try:
        path = _metadata_path(root, pointer)
    except ValueError:
        return "its entry in the manifest is damaged"
    if not path.is_file():
        return f"its file is missing ({path.name})"
    return ""


def _entry_problem(root: Path, entry: Any) -> str:
    """Why a manifest dataset entry cannot restore, by its shape and files.

    ``""`` when nothing is wrong that a ``stat`` can see.
    """
    if not isinstance(entry, dict) or not isinstance(entry.get("frames", {}), dict):
        return "its entry in the manifest is damaged"
    for relative in entry.get("frames", {}).values():
        try:
            path = _frame_path(root, relative)
        except ValueError as exc:
            return str(exc)
        if not path.is_file():
            return f"a stored file is missing ({path.name})"
    return ""


def save_local_state(session, url: str) -> bool:
    # BUG-71: reaching the epilogue means this run rendered, so a restore it
    # applied is not the kind that breaks the app — before any early return, since
    # a paused save still ran to here.
    _finish_restore(session)
    if not persistence_enabled(url) or persistence_paused(session):
        return False
    try:
        return save_state(session, state_directory())
    except Exception:
        # Persistence is a recovery convenience, never a reason for the app to
        # stop rendering (read-only homes, full disks, or unsupported Parquet
        # values are all recoverable by continuing without this save).
        _LOGGER.warning(
            "Could not persist the local Scanpath Studio session.", exc_info=True
        )
        return False
