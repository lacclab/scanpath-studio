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
in-app "🗄️ Recovery cache" panel (``app._render_recovery_cache_panel``), the
``scanpath-studio cache`` CLI subcommand and ``api.cache_status``. Saving can be
paused for the session (:func:`set_persistence_paused`) and the stored files
deleted (:func:`clear_local_state`). A clear initiated in the app uses
:func:`skip_next_local_save` so the end of that rerun does not immediately
recreate the files without changing the user's saving preference.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import os
import tempfile
import threading
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from .annotations import ANNOTATIONS_STATE_KEY, records_to_store, store_to_records
from .constants import DATASET_COUNTS_STORE_KEY
from .session_keys import (
    COLUMN_MAPPING_PREFIX,
    DESIGN_PRESETS,
    PLOT_CONFIG_STATE_KEYS,
    SINGLE_COMPARE_LAYOUT,
    SINGLE_COMPARE_STIMULUS,
    SINGLE_COMPARE_TOGGLE,
    SINGLE_PLAYBACK_SPEED,
    compare_state_keys,
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
_SKIP_NEXT_SAVE_KEY = "_local_persistence_skip_next_save"
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
_FRAME_KEYS = ("words", "fixations", "raw_gaze")
#: DATA-38 — the attached metadata tables live beside the manifest, not in it,
#: and are rewritten only when their content changes: the manifest is rewritten
#: on every durable settings change (a layer toggle, a trial switch), and a
#: trial table can run to tens of thousands of rows.
METADATA_FILE = "metadata.json"
_LAST_METADATA_SIGNATURE_KEY = "_local_persistence_metadata_signature"
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

    return metadata_mod.session_signature(session)


def _dataset_slug(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:20]


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
    annotations = store_to_records(session.get(ANNOTATIONS_STATE_KEY, {}))
    encoded = json.dumps(
        [datasets, values, annotations, metadata_signature],
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


def _manifest_for(
    session: MutableMapping[str, Any], root: Path, *, reuse_datasets: bool
) -> dict:
    cached_entries = session.get(_LAST_DATASET_ENTRIES_KEY)
    datasets = (
        dict(cached_entries)
        if reuse_datasets and isinstance(cached_entries, dict)
        else {}
    )
    frames_dir = root / "datasets"
    frames_dir.mkdir(parents=True, exist_ok=True)
    if reuse_datasets:
        # A manifest written before ``rows`` existed is still restorable, and
        # restoring seeds these entries verbatim — so without this backfill an
        # upgraded install would reuse row-less entries forever and the panel
        # would read "1 dataset · 0 rows · 812 MB". Reuse means the live frames
        # ARE the ones on disk (_dataset_identity matched), so counting them is
        # accurate and free (len is O(1)); no Parquet is rewritten.
        live = dict(session.get("_datasets", {}))
        for name, entry in list(datasets.items()):
            if isinstance(entry, dict) and not entry.get("rows"):
                payload = live.get(name)
                if isinstance(payload, dict):
                    datasets[name] = {
                        **entry,
                        "rows": {
                            frame_key: len(payload[frame_key])
                            for frame_key in _FRAME_KEYS
                            if isinstance(payload.get(frame_key), pd.DataFrame)
                        },
                    }
    if not reuse_datasets:
        for name, payload in dict(session.get("_datasets", {})).items():
            slug = _dataset_slug(str(name))
            metadata = {
                k: _json_safe(v) for k, v in payload.items() if k not in _FRAME_KEYS
            }
            frame_files = {}
            frame_rows = {}
            for frame_key in _FRAME_KEYS:
                frame = payload.get(frame_key)
                if not isinstance(frame, pd.DataFrame):
                    frame = pd.DataFrame()
                filename = f"{slug}-{frame_key}.parquet"
                _atomic_parquet(frame, frames_dir / filename)
                frame_files[frame_key] = f"datasets/{filename}"
                frame_rows[frame_key] = len(frame)
            # ``rows`` is reporting-only (cache_status / the in-app panel say how
            # much is stored without opening the Parquet files). The restore path
            # reads ``frames`` alone, so an older manifest without it still loads.
            datasets[str(name)] = {
                "metadata": metadata,
                "frames": frame_files,
                "rows": frame_rows,
            }

    values = {key: _json_safe(session[key]) for key in _SESSION_KEYS if key in session}
    values.update(
        {
            key: _json_safe(value)
            for key, value in session.items()
            if str(key).startswith(COLUMN_MAPPING_PREFIX)
        }
    )
    annotations = store_to_records(session.get(ANNOTATIONS_STATE_KEY, {}))
    return {
        "schema": SCHEMA_VERSION,
        "datasets": datasets,
        "session": values,
        "annotations": annotations,
    }


def _save_metadata(
    session: MutableMapping[str, Any], root: Path, signature: list
) -> dict | None:
    """DATA-38 — write the attached tables to :data:`METADATA_FILE` if they changed.

    Returns the manifest's pointer to them, or ``None`` (and removes the file)
    when nothing is attached. The tables are the same payloads 💾 Save & restore
    writes; the pointer is optional, so a manifest without it (every one written
    before this) still restores, and the schema version does not move.
    """
    path = root / METADATA_FILE
    if not signature:
        path.unlink(missing_ok=True)
        session.pop(_LAST_METADATA_SIGNATURE_KEY, None)
        return None
    if session.get(_LAST_METADATA_SIGNATURE_KEY) != signature or not path.is_file():
        from . import metadata as metadata_mod

        payloads = _json_safe(metadata_mod.session_payloads(session))
        # No `sort_keys`: each row keeps its columns in the table's own order.
        _atomic_text(json.dumps(payloads, ensure_ascii=False), path)
        session[_LAST_METADATA_SIGNATURE_KEY] = signature
    return {"file": METADATA_FILE, "tables": [entry[0] for entry in signature]}


def save_state(session: MutableMapping[str, Any], root: Path) -> bool:
    """Atomically save local datasets and durable session preferences."""
    with _STATE_LOCK:
        metadata_signature = _metadata_signature(session)
        fingerprint = _state_fingerprint(session, metadata_signature)
        if session.get(_LAST_FINGERPRINT_KEY) == fingerprint:
            return False
        root.mkdir(parents=True, exist_ok=True)
        dataset_identity = _dataset_identity(session)
        reuse_datasets = session.get(
            _LAST_DATASET_IDENTITY_KEY
        ) == dataset_identity and isinstance(
            session.get(_LAST_DATASET_ENTRIES_KEY), dict
        )
        manifest = _manifest_for(session, root, reuse_datasets=reuse_datasets)
        # Written before the manifest, so a manifest never names a file that is
        # not there yet.
        metadata = _save_metadata(session, root, metadata_signature)
        if metadata:
            manifest["metadata"] = metadata
        # DATA-32: the dataset table's remembered counts ride along with the
        # datasets they describe — one small dict, and it is what stops a
        # restored session recounting every corpus it has ever opened. Written
        # here rather than inside `_manifest_for` because it is session state,
        # not a frame on disk.
        counts = session.get(DATASET_COUNTS_STORE_KEY)
        if isinstance(counts, dict) and counts:
            manifest["dataset_counts"] = _json_safe(counts)
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        _atomic_text(encoded, root / "manifest.json")
        session[_LAST_FINGERPRINT_KEY] = fingerprint
        session[_LAST_DATASET_IDENTITY_KEY] = dataset_identity
        session[_LAST_DATASET_ENTRIES_KEY] = dict(manifest["datasets"])
        return True


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
        path = root / "manifest.json"
        if not path.exists():
            return False
        try:
            # BUG-71: read and check the whole manifest *before* touching the
            # session. It is a file on disk, so any JSON value can be in it —
            # `[]`, `null`, a dataset entry that is a string — and each of those
            # used to escape as an AttributeError the handler below did not
            # catch, on every launch. A wrong shape now abandons the restore
            # with nothing half-applied.
            manifest = _as_mapping(json.loads(path.read_text(encoding="utf-8")))
            if int(manifest.get("schema", 0)) != SCHEMA_VERSION:
                return False
            restored_datasets = {}
            stored_entries = {}
            for name, entry in _as_mapping(manifest.get("datasets", {})).items():
                entry = _as_mapping(entry)
                payload = dict(_as_mapping(entry.get("metadata", {})))
                for frame_key, relative in _as_mapping(entry.get("frames", {})).items():
                    frame_path = root / str(relative)
                    payload[frame_key] = pd.read_parquet(frame_path)
                for frame_key in _FRAME_KEYS:
                    payload.setdefault(frame_key, pd.DataFrame())
                restored_datasets[str(name)] = payload
                stored_entries[str(name)] = entry
            stored_session = _restorable_session(manifest.get("session", {}))
            annotations = manifest.get("annotations", [])
            # One malformed record costs that record, not the rest.
            records = [
                record
                for record in (annotations if isinstance(annotations, list) else [])
                if isinstance(record, dict)
            ]
            store = records_to_store(records)

            existing = dict(session.get("_datasets", {}))
            if restored_datasets:
                session["_datasets"] = {**restored_datasets, **existing}
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
            summary["annotations"] = 0
            if ANNOTATIONS_STATE_KEY not in session:
                session[ANNOTATIONS_STATE_KEY] = store
                summary["annotations"] = len(records)
            # DATA-38 — the attached metadata tables. Counted, because a user
            # recognises their participant table coming back (UX-136's test for
            # what is worth announcing), unlike a restored canvas width.
            summary["metadata"] = _restore_metadata(
                session, root, manifest.get("metadata")
            )
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
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            # A partial/corrupt cache must never prevent the app from opening. The
            # user can simply work normally; the next successful save replaces it.
            # AttributeError is the backstop for a shape `_as_mapping` did not
            # anticipate (BUG-71) — it is what every wrong shape used to raise.
            return False


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
    for key, value in _as_mapping(stored).items():
        if not isinstance(key, str) or not (
            key in _SESSION_KEYS or key.startswith(COLUMN_MAPPING_PREFIX)
        ):
            continue
        if key == DESIGN_PRESETS:
            # The design library is the user's own work: keep every well-formed
            # design rather than all-or-nothing.
            if isinstance(value, dict):
                clean[key] = {
                    str(name): dict(design)
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
    return clean


def _restore_metadata(session: MutableMapping[str, Any], root: Path, pointer) -> int:
    """DATA-38 — re-attach the tables :func:`_save_metadata` wrote; how many.

    Its own error boundary: a missing or unreadable sidecar costs the tables,
    never the datasets and settings the rest of the manifest restores.
    """
    if not isinstance(pointer, dict) or not pointer.get("file"):
        return 0
    try:
        payloads = json.loads((root / str(pointer["file"])).read_text("utf-8"))
    except (OSError, ValueError):
        return 0
    from . import metadata as metadata_mod

    return metadata_mod.restore_payloads(session, payloads)


def forget_state(root: Path) -> None:
    """Remove the known persistence files without recursively deleting ``root``."""
    with _STATE_LOCK:
        manifest = root / "manifest.json"
        if manifest.exists():
            manifest.unlink()
        (root / RESTORE_MARKER_NAME).unlink(missing_ok=True)
        (root / METADATA_FILE).unlink(missing_ok=True)
        frames_dir = root / "datasets"
        if frames_dir.is_dir():
            for path in frames_dir.glob("*.parquet"):
                path.unlink()
            try:
                frames_dir.rmdir()
            except OSError:
                pass


def _reslug_entry(entry: Any, slug: str) -> dict:
    """One manifest dataset entry with its frame paths moved onto ``slug``."""
    frames = {
        frame_key: f"datasets/{slug}-{frame_key}.parquet"
        for frame_key in dict(entry.get("frames", {}))
    }
    return {**dict(entry), "frames": frames}


def rename_cached_dataset(
    session: MutableMapping[str, Any],
    old: str,
    new: str,
    root: Path | None = None,
) -> bool:
    """Follow a dataset rename (DATA-23) through the cache instead of rewriting it.

    A dataset's Parquet files are named after ``_dataset_slug(name)``, so a rename
    would otherwise leave the old slug's files behind as orphans nothing deletes,
    and make the next save re-encode every frame under the new slug. Renaming the
    files, re-keying ``manifest.json`` and re-keying this session's reuse
    bookkeeping keeps the next :func:`save_state` on the cheap ``reuse_datasets``
    path — it rewrites the manifest only.

    Call it **after** the store itself has been re-keyed: the new reuse identity is
    read from the live ``session["_datasets"]``. Best-effort like the rest of this
    module — on any failure the session's bookkeeping is dropped so the next save
    rebuilds the cache in full rather than trusting a half-moved one.
    """
    if old == new:
        return False
    directory = state_directory() if root is None else root
    with _STATE_LOCK:
        try:
            old_slug, new_slug = _dataset_slug(old), _dataset_slug(new)
            frames_dir = directory / "datasets"
            for frame_key in _FRAME_KEYS:
                source = frames_dir / f"{old_slug}-{frame_key}.parquet"
                if source.is_file():
                    os.replace(source, frames_dir / f"{new_slug}-{frame_key}.parquet")
            manifest_path = directory / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                datasets = dict(manifest.get("datasets", {}))
                if old in datasets:
                    datasets[new] = _reslug_entry(datasets.pop(old), new_slug)
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
                entries[new] = _reslug_entry(entries.pop(old), new_slug)
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
        # and a restore that breaks the app breaks it before the 💾 Session
        # dialog can offer a reset — so every launch would break again. Open
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
    the 🗄️ Automatic recovery panel counts, and what a user would recognise as
    their last session (``metadata`` is the number of attached participant /
    trial / text tables, DATA-38). View settings are deliberately absent: they restore, but
    silently (UX-136 — see :func:`restore_state`). Empty when no restore
    happened, and after :func:`clear_local_state`.
    """
    summary = session.get(_RESTORED_PAYLOAD_KEY)
    return dict(summary) if isinstance(summary, dict) else {}


def restored_from_cache(session) -> bool:
    """Whether this session got back something the user would recognise.

    Not "was a manifest read" — see :func:`restore_state` for why the two came
    apart.
    """
    return any(restored_summary(session).values())


def persistence_paused(session) -> bool:
    """Whether the user switched saving off for this session (UI opt-out)."""
    return bool(session.get(_PAUSED_KEY))


def set_persistence_paused(session, paused: bool) -> None:
    """Pause/resume saving for this session only.

    Resuming clears the save fingerprint so the next run writes the current
    session out in full, even though nothing about it changed while paused.
    ``SCANPATH_STUDIO_PERSIST=0`` is the durable, process-wide opt-out.
    """
    session[_PAUSED_KEY] = bool(paused)
    if not paused:
        session.pop(_LAST_FINGERPRINT_KEY, None)


def skip_next_local_save(session) -> None:
    """Suppress exactly one end-of-run persistence write.

    Clearing the recovery cache triggers a full app rerun before ``main``
    reaches its persistence epilogue. The fresh run must not write the same
    live session straight back to disk, but it also must not turn off automatic
    saving. A one-shot marker expresses that distinction; the following user
    change saves normally.
    """
    session[_SKIP_NEXT_SAVE_KEY] = True


def clear_local_state(session=None, root: Path | None = None) -> bool:
    """Delete the stored cache and forget what this session had written.

    The in-memory datasets are deliberately left alone — this removes the copy
    on disk, it does not close the user's work. Callers clearing it from a
    widget-driven rerun can use :func:`skip_next_local_save` to prevent the
    immediate epilogue write without changing the saving preference.

    Deleting the files is best-effort: a locked or read-only cache directory
    must not wedge *"Clear recovery cache"* or *"Reset everything"*, which are
    the two actions a user reaches for precisely when the session is already
    broken. An :class:`OSError` is logged and reported as ``False``; the
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
            # DATA-32: the remembered counts are part of what "forget this
            # session" means — the ask named clearing the cache explicitly.
            DATASET_COUNTS_STORE_KEY,
        ):
            session.pop(key, None)
    return removed


def _cache_files(root: Path) -> list:
    """The files this module owns under ``root`` (mirrors forget_state)."""
    files = [root / "manifest.json", root / RESTORE_MARKER_NAME, root / METADATA_FILE]
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
        status["datasets"] = [
            {
                "name": str(name),
                "rows": {
                    key: int(value)
                    for key, value in dict(entry.get("rows", {})).items()
                },
            }
            for name, entry in sorted(datasets.items())
        ]
        status["rows"] = (
            sum(sum(entry["rows"].values()) for entry in status["datasets"])
            if all(entry["rows"] for entry in status["datasets"])
            else None
        )
        status["annotations"] = len(list(manifest.get("annotations", [])))
        stored_session = dict(manifest.get("session", {}))
        status["designs"] = len(dict(stored_session.get(DESIGN_PRESETS, {})))
        status["metadata"] = len(
            list(dict(manifest.get("metadata") or {}).get("tables") or [])
        )
        status["settings"] = len(stored_session)
        # A newer/unknown schema is present but will not restore — say so here
        # rather than let the panel claim the work is safely stored.
        status["readable"] = schema == SCHEMA_VERSION
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        status["readable"] = False
    return status


def save_local_state(session, url: str) -> bool:
    # BUG-71: reaching the epilogue means this run rendered, so a restore it
    # applied is not the kind that breaks the app — before any early return, since
    # a paused or skipped save still ran to here.
    _finish_restore(session)
    if session.pop(_SKIP_NEXT_SAVE_KEY, False):
        return False
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
