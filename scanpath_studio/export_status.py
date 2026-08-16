"""Shared, honest progress vocabulary for static, animation, and bulk exports."""

from __future__ import annotations

import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

EXPORTER_VERSION = "exp6-v1"


class ExportStage(str, Enum):
    PREPARING = "preparing"
    STARTING_RENDERER = "starting_renderer"
    RASTERIZING = "rasterizing"
    ENCODING_WRITING = "encoding_writing"
    FINALIZING = "finalizing"
    READY = "ready"
    ERROR = "error"


@dataclass(frozen=True)
class ExportStatus:
    """One observable job state; counts appear only when real units exist."""

    stage: ExportStage
    message: str
    completed: int | None = None
    total: int | None = None
    elapsed_s: float = 0.0
    error: str | None = None

    @property
    def fraction(self) -> float | None:
        if self.completed is None or self.total is None or self.total <= 0:
            return None
        return min(max(self.completed / self.total, 0.0), 1.0)


StatusCallback = Callable[[ExportStatus], None]


def emit_status(
    callback: StatusCallback | None,
    stage: ExportStage,
    message: str,
    *,
    started_at: float | None = None,
    completed: int | None = None,
    total: int | None = None,
    error: str | None = None,
) -> ExportStatus:
    """Validate and emit one status while remaining cheap when no UI listens."""
    if (completed is None) != (total is None):
        raise ValueError("completed and total must be supplied together")
    if completed is not None and (completed < 0 or total is None or total < 0):
        raise ValueError("progress counts must be non-negative")
    if completed is not None and total is not None and completed > total:
        raise ValueError("completed progress cannot exceed total")
    status = ExportStatus(
        stage=stage,
        message=message,
        completed=completed,
        total=total,
        elapsed_s=max(0.0, time.perf_counter() - started_at) if started_at else 0.0,
        error=error,
    )
    if callback is not None:
        callback(status)
    return status


def static_export_signature(
    fig: Any,
    *,
    fmt: str,
    width: int,
    height: int,
    scale: float,
    exporter_version: str = EXPORTER_VERSION,
) -> str:
    """Hash every output-affecting input for safe static-byte reuse."""
    if int(width) <= 0 or int(height) <= 0:
        raise ValueError("export width and height must be positive")
    if not math.isfinite(float(scale)) or float(scale) <= 0:
        raise ValueError("export scale must be a positive finite number")
    digest = hashlib.sha256()
    for value in (
        exporter_version,
        str(fmt).lower(),
        str(int(width)),
        str(int(height)),
        f"{float(scale):.12g}",
    ):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    digest.update(fig.to_json().encode("utf-8"))
    return digest.hexdigest()
