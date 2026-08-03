"""Local, single-user session persistence for Scanpath Studio.

The hosted app deliberately does not persist anything: there is no user identity
there, so a process-wide cache could expose one visitor's data to another.  A
localhost/desktop session stores uploaded datasets as Parquet plus a small JSON
manifest and restores them on the next browser or process session.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, MutableMapping, Optional
from urllib.parse import urlparse

import pandas as pd

from .annotations import ANNOTATIONS_STATE_KEY, records_to_store, store_to_records
from .session_keys import COLUMN_MAPPING_PREFIX, PLOT_CONFIG_STATE_KEYS

SCHEMA_VERSION = 1
_RESTORED_KEY = "_local_persistence_restored"
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
}


def persistence_enabled(url: str = "", environ: Optional[dict] = None) -> bool:
    """Return whether disk persistence is safe for this process.

    ``SCANPATH_STUDIO_PERSIST=1`` explicitly enables it and ``=0`` disables it.
    Without an override it is enabled only for loopback URLs, which covers the
    desktop app and ``streamlit run`` while keeping public deployments isolated.
    """
    env = os.environ if environ is None else environ
    override = str(env.get("SCANPATH_STUDIO_PERSIST", "")).strip().lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    host = (urlparse(str(url or "")).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def state_directory(environ: Optional[dict] = None) -> Path:
    env = os.environ if environ is None else environ
    configured = str(env.get("SCANPATH_STUDIO_STATE_DIR", "")).strip()
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
    temporary: Optional[Path] = None
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
    temporary: Optional[Path] = None
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
    if not reuse_datasets:
        for name, payload in dict(session.get("_datasets", {})).items():
            slug = _dataset_slug(str(name))
            metadata = {
                k: _json_safe(v) for k, v in payload.items() if k not in _FRAME_KEYS
            }
            frame_files = {}
            for frame_key in _FRAME_KEYS:
                frame = payload.get(frame_key)
                if not isinstance(frame, pd.DataFrame):
                    frame = pd.DataFrame()
                filename = f"{slug}-{frame_key}.parquet"
                _atomic_parquet(frame, frames_dir / filename)
                frame_files[frame_key] = f"datasets/{filename}"
            datasets[str(name)] = {"metadata": metadata, "frames": frame_files}

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


def restore_local_state(
    session, url: str, *, protect_data_source: bool = False
) -> bool:
    if not persistence_enabled(url):
        session[_RESTORED_KEY] = True
        return False
    protected = {"data_source_choice"} if protect_data_source else set()
    return restore_state(session, state_directory(), skip_session_keys=protected)


def save_local_state(session, url: str) -> bool:
    if not persistence_enabled(url):
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
