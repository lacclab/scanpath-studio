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

    @property
    def rate_per_s(self) -> float | None:
        """Units finished per second so far, or ``None`` before there are any."""
        if not self.completed or not self.elapsed_s:
            return None
        return self.completed / self.elapsed_s

    @property
    def remaining_s(self) -> float | None:
        """Seconds left at the rate observed so far (PERF-6).

        ``None`` until the first unit finishes: with nothing done there is no
        rate, and an estimate invented from one would be a guess wearing a
        number. Deliberately the naive rate over the *whole* run rather than a
        recent window — a bulk export's per-trial cost is near-constant, and an
        estimate that lurches with each slow trial reads as broken.
        """
        rate = self.rate_per_s
        if rate is None or self.total is None:
            return None
        return max(0.0, (self.total - self.completed) / rate)


StatusCallback = Callable[[ExportStatus], None]


def format_duration(seconds: float | None) -> str:
    """A duration as a person would say it: ``2h 15m``, ``1m 15s``, ``9s``."""
    if seconds is None:
        return ""
    if seconds < 1:
        return "under a second"
    seconds = round(seconds)  # round() on a float already returns an int
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def progress_caption(status: ExportStatus) -> str:
    """One line under the bar: how far, how fast, how much longer.

    A bulk export over a real corpus runs for hours, and "1,203 / 20,000" only
    answers the first of those. The rate is what makes the estimate legible —
    it lets someone sanity-check the number rather than take it on faith.
    """
    if status.completed is None or status.total is None:
        return status.message
    parts = [f"{status.completed:,}/{status.total:,} trials"]
    rate = status.rate_per_s
    if rate is not None:
        parts.append(f"{rate:.3g}/s" if rate < 10 else f"{rate:.0f}/s")
    remaining = status.remaining_s
    if remaining is not None:
        parts.append(
            "finishing…" if remaining < 1 else f"{format_duration(remaining)} left"
        )
    parts.append(status.message)
    return " · ".join(parts)


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
