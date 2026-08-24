"""Local, single-user session persistence for Scanpath Studio.

The hosted app deliberately does not persist anything: there is no user identity
there, so a process-wide cache could expose one visitor's data to another.  A
localhost/desktop session stores uploaded datasets as Parquet plus a small JSON
manifest and restores them on the next browser or process session.

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
)

SCHEMA_VERSION = 1
PERSIST_ENV_VAR = "SCANPATH_STUDIO_PERSIST"
STATE_DIR_ENV_VAR = "SCANPATH_STUDIO_STATE_DIR"
_RESTORED_KEY = "_local_persistence_restored"
_RESTORED_PAYLOAD_KEY = "_local_persistence_restored_payload"
_PAUSED_KEY = "_local_persistence_paused"
_SKIP_NEXT_SAVE_KEY = "_local_persistence_skip_next_save"
_LAST_FINGERPRINT_KEY = "_local_persistence_fingerprint"
_LAST_DATASET_IDENTITY_KEY = "_local_persistence_dataset_identity"
_LAST_DATASET_ENTRIES_KEY = "_local_persistence_dataset_entries"
_FRAME_KEYS = ("words", "fixations", "raw_gaze")
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
}


def is_loopback_url(url: str = "") -> bool:
    """Return whether ``url`` is addressed to this machine's loopback interface."""
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def persistence_enabled(url: str = "", environ: dict | None = None) -> bool:
    """Return whether disk persistence is safe for this process.

    ``SCANPATH_STUDIO_PERSIST=1`` explicitly enables it and ``=0`` disables it.
    Without an override it is enabled only for loopback URLs, which covers the
    desktop app and ``streamlit run`` while keeping public deployments isolated.
    """
    env = os.environ if environ is None else environ
    override = str(env.get(PERSIST_ENV_VAR, "")).strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    return is_loopback_url(url)


def state_directory(environ: dict | None = None) -> Path:
    env = os.environ if environ is None else environ
    configured = str(env.get(STATE_DIR_ENV_VAR, "")).strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".cache" / "scanpath-studio" / "session-v1"


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


def _state_fingerprint(session: MutableMapping[str, Any]) -> str:
    """Cheap rerun fingerprint over datasets plus durable UI state."""
    datasets = _dataset_identity(session)
    values = {
        key: _json_safe(value)
        for key, value in session.items()
        if key in _SESSION_KEYS or str(key).startswith(COLUMN_MAPPING_PREFIX)
    }
    annotations = store_to_records(session.get(ANNOTATIONS_STATE_KEY, {}))
    encoded = json.dumps(
        [datasets, values, annotations], ensure_ascii=False, sort_keys=True
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


def save_state(session: MutableMapping[str, Any], root: Path) -> bool:
    """Atomically save local datasets and durable session preferences."""
    with _STATE_LOCK:
        fingerprint = _state_fingerprint(session)
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
    """Restore a manifest once, without overwriting already-seeded values."""
    if session.get(_RESTORED_KEY):
        return False
    session[_RESTORED_KEY] = True
    with _STATE_LOCK:
        path = root / "manifest.json"
        if not path.exists():
            return False
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if int(manifest.get("schema", 0)) != SCHEMA_VERSION:
                return False
            restored_datasets = {}
            for name, entry in dict(manifest.get("datasets", {})).items():
                payload = dict(entry.get("metadata", {}))
                for frame_key, relative in dict(entry.get("frames", {})).items():
                    frame_path = root / str(relative)
                    payload[frame_key] = pd.read_parquet(frame_path)
                for frame_key in _FRAME_KEYS:
                    payload.setdefault(frame_key, pd.DataFrame())
                restored_datasets[str(name)] = payload
            existing = dict(session.get("_datasets", {}))
            if restored_datasets:
                session["_datasets"] = {**restored_datasets, **existing}
            skip = set(skip_session_keys)
            for key, value in dict(manifest.get("session", {})).items():
                if key not in skip:
                    session.setdefault(key, value)
            if ANNOTATIONS_STATE_KEY not in session:
                session[ANNOTATIONS_STATE_KEY] = records_to_store(
                    list(manifest.get("annotations", []))
                )
            # A clean restore can reuse the Parquet files on the first rendered
            # settings change. Pre-existing in-memory datasets still need a save.
            if not existing:
                session[_LAST_DATASET_IDENTITY_KEY] = _dataset_identity(session)
                session[_LAST_DATASET_ENTRIES_KEY] = dict(manifest.get("datasets", {}))
            counts = manifest.get("dataset_counts")
            if isinstance(counts, dict):
                # DATA-32 — a manifest written before this existed simply has
                # none, and the table recounts what it can, as it always did.
                session[DATASET_COUNTS_STORE_KEY] = dict(counts)
            # Separate from _RESTORED_KEY, which only records that a restore was
            # *attempted* this session. The app reads this one to tell the user
            # their previous session came back (restored_from_cache).
            session[_RESTORED_PAYLOAD_KEY] = True
            return True
        except (OSError, ValueError, TypeError, KeyError):
            # A partial/corrupt cache must never prevent the app from opening. The
            # user can simply work normally; the next successful save replaces it.
            return False


def forget_state(root: Path) -> None:
    """Remove the known persistence files without recursively deleting ``root``."""
    with _STATE_LOCK:
        manifest = root / "manifest.json"
        if manifest.exists():
            manifest.unlink()
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
    if not persistence_enabled(url):
        session[_RESTORED_KEY] = True
        return False
    protected = {"data_source_choice"} if protect_data_source else set()
    return restore_state(session, state_directory(), skip_session_keys=protected)


def restored_from_cache(session) -> bool:
    """Whether this session actually got its state back from the cache."""
    return bool(session.get(_RESTORED_PAYLOAD_KEY))


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
            # DATA-32: the remembered counts are part of what "forget this
            # session" means — the ask named clearing the cache explicitly.
            DATASET_COUNTS_STORE_KEY,
        ):
            session.pop(key, None)
    return removed


def _cache_files(root: Path) -> list:
    """The files this module owns under ``root`` (mirrors forget_state)."""
    files = [root / "manifest.json"]
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
        status["settings"] = len(stored_session)
        # A newer/unknown schema is present but will not restore — say so here
        # rather than let the panel claim the work is safely stored.
        status["readable"] = schema == SCHEMA_VERSION
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        status["readable"] = False
    return status


def save_local_state(session, url: str) -> bool:
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
