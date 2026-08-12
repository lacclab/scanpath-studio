"""Display geometry and stimulus typography: conversions, and the per-dataset
setup a corpus was recorded with (DATA-2 · DATA-22 · CMP-8).

Deliberately pure — no Streamlit, no pandas. That is what lets the headless API,
the wizard, the comparison figure and CMP-11's visual-angle mode all share one
notion of "what screen was this recorded on", and it keeps the type reachable
from `api.py` without importing `app`.

Two things live here:

* the conversions (`dpi_from_width`, `font_pt_to_px`, `pixels_per_degree`);
* `SetupSnapshot` — one dataset's canvas / physical size / typography, each of
  the three groups carrying a `Provenance` saying *how we know it*.

The provenance is the point. An uploaded corpus that never recorded its monitor
used to silently inherit a 2560x1440 guess; a snapshot instead records that the
screen was ``ASSUMED``, and anything derived from a ``SKIPPED`` group
(px/degree, pt->px) resolves to ``None`` so a caller hides it rather than
printing a number computed from a default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Mapping, Optional

# Defaults duplicated from ``constants.py`` rather than imported: this module is
# the pure bottom of the dependency graph and must stay importable on its own.
_DEFAULT_CANVAS = (2560, 1440)
_DEFAULT_MONITOR_WIDTH_MM = 597.0
_DEFAULT_VIEWING_DISTANCE_MM = 800.0
_DEFAULT_BASE_FONT_SIZE = 16
_DEFAULT_FONT_FAMILY = "monospace"
_DEFAULT_LINE_SPACING = 3.0


def dpi_from_width(width_px: float, width_mm: float) -> float:
    """Horizontal display DPI from pixel and physical widths."""
    if width_px <= 0 or width_mm <= 0:
        raise ValueError("display widths must be positive")
    return float(width_px) / (float(width_mm) / 25.4)


def font_pt_to_px(font_pt: float, dpi: float) -> float:
    """CSS/monitor pixels corresponding to a point size at ``dpi``."""
    if font_pt <= 0 or dpi <= 0:
        raise ValueError("font size and DPI must be positive")
    return float(font_pt) * float(dpi) / 72.0


def pixels_per_degree(
    viewing_distance_mm: float, width_px: float, width_mm: float
) -> float:
    """Pixels subtending one visual degree at the configured setup."""
    if viewing_distance_mm <= 0:
        raise ValueError("viewing distance must be positive")
    px_per_mm = float(width_px) / float(width_mm)
    mm_per_degree = 2.0 * float(viewing_distance_mm) * math.tan(math.radians(0.5))
    return px_per_mm * mm_per_degree


class Provenance(StrEnum):
    """How a setup group's values came to be what they are.

    ``StrEnum`` so a member serializes as its own value — the share param, the
    saved-config section and ``plot_config.json`` all write bare strings.
    """

    MEASURED = "measured"
    """The user knows the values, or the corpus declares them."""
    ESTIMATED = "estimated"
    """Derived from the uploaded data (a lower bound, not the real screen)."""
    ASSUMED = "assumed"
    """A named default was taken."""
    SKIPPED = "skipped"
    """Declined; everything derived from this group is hidden, not guessed."""


#: The three groups a user answers in the wizard's Recording-setup step, in the
#: order they are asked. ``geometry`` is the only one that may be skipped.
SETUP_GROUPS: tuple[str, ...] = ("screen", "geometry", "text")

#: Short names used on the wire (``setup_prov=screen:assumed,geom:skipped,...``).
#: Kept separate from ``SETUP_GROUPS`` so the param stays compact without
#: renaming the group everywhere else.
_GROUP_WIRE_NAMES: dict[str, str] = {
    "screen": "screen",
    "geometry": "geom",
    "text": "text",
}
_WIRE_NAME_GROUPS: dict[str, str] = {v: k for k, v in _GROUP_WIRE_NAMES.items()}

SETUP_GROUP_LABELS: dict[str, str] = {
    "screen": "Screen",
    "geometry": "Physical size & viewing distance",
    "text": "Reading text size",
}


@dataclass(frozen=True)
class SetupAnswer:
    """One group's answer in the wizard's Recording-setup step.

    ``choice`` is the radio label the user picked, kept verbatim so the review
    table can echo the wording they chose rather than a reconstruction of it.
    """

    group: str
    choice: str
    provenance: Provenance
    values: dict[str, Any]


@dataclass(frozen=True)
class SetupSnapshot:
    """The screen and typography one dataset was set up with.

    Every field is a resolved value — a snapshot never carries "unknown". What
    it carries instead is the per-group ``Provenance``, so a reader can tell a
    measured 1680x1050 from an assumed one and, for a ``SKIPPED`` group, decline
    to show the quantities that would otherwise be invented (`dpi`,
    `px_per_degree`, `stimulus_font_px`).
    """

    canvas_width: int = _DEFAULT_CANVAS[0]
    canvas_height: int = _DEFAULT_CANVAS[1]
    monitor_width_mm: float = _DEFAULT_MONITOR_WIDTH_MM
    viewing_distance_mm: float = _DEFAULT_VIEWING_DISTANCE_MM
    base_font_size: int = _DEFAULT_BASE_FONT_SIZE
    font_family: str = _DEFAULT_FONT_FAMILY
    line_spacing: float = _DEFAULT_LINE_SPACING
    scale_text_to_boxes: bool = True
    # Provenance is three scalar fields rather than a dict so the dataclass stays
    # hashable and cheap to compare (it rides inside cached values).
    screen_provenance: Provenance = Provenance.ASSUMED
    geometry_provenance: Provenance = Provenance.ASSUMED
    text_provenance: Provenance = Provenance.ASSUMED

    # -- derived ---------------------------------------------------------------

    @property
    def provenance(self) -> dict[str, Provenance]:
        """Group -> provenance, in ``SETUP_GROUPS`` order."""
        return {
            "screen": self.screen_provenance,
            "geometry": self.geometry_provenance,
            "text": self.text_provenance,
        }

    @property
    def dpi(self) -> Optional[float]:
        """Horizontal DPI, or ``None`` when the physical size was skipped.

        A DPI computed from a default monitor width is a guess wearing a
        number's clothes, so a skipped geometry group yields nothing at all.
        """
        if self.geometry_provenance is Provenance.SKIPPED:
            return None
        try:
            return dpi_from_width(self.canvas_width, self.monitor_width_mm)
        except ValueError:
            return None

    @property
    def px_per_degree(self) -> Optional[float]:
        """Pixels per degree of visual angle, or ``None`` when skipped."""
        if self.geometry_provenance is Provenance.SKIPPED:
            return None
        try:
            return pixels_per_degree(
                self.viewing_distance_mm, self.canvas_width, self.monitor_width_mm
            )
        except (ValueError, ZeroDivisionError):
            return None

    @property
    def canvas(self) -> tuple[int, int]:
        """``(width, height)`` — the shape the figure builders take."""
        return (int(self.canvas_width), int(self.canvas_height))

    def stimulus_font_px(self, font_pt: float) -> Optional[float]:
        """Convert a point size through this setup's DPI, or ``None`` if skipped."""
        dpi = self.dpi
        if dpi is None:
            return None
        try:
            return font_pt_to_px(font_pt, dpi)
        except ValueError:
            return None

    def is_answered(self) -> bool:
        """Every group carries a real provenance (the wizard's Add-dataset gate)."""
        return all(isinstance(p, Provenance) for p in self.provenance.values())

    def with_provenance(self, **groups: Provenance) -> "SetupSnapshot":
        """Copy with one or more groups' provenance replaced."""
        return replace(
            self, **{f"{group}_provenance": p for group, p in groups.items()}
        )

    # -- serialization ---------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """JSON-able form written to the stored dataset payload, the saved-setup
        JSON, the recovery-cache manifest, and bulk export's ``plot_config.json``."""
        return {
            "canvas_width": int(self.canvas_width),
            "canvas_height": int(self.canvas_height),
            "monitor_width_mm": float(self.monitor_width_mm),
            "viewing_distance_mm": float(self.viewing_distance_mm),
            "base_font_size": int(self.base_font_size),
            "font_family": str(self.font_family),
            "line_spacing": float(self.line_spacing),
            "scale_text_to_boxes": bool(self.scale_text_to_boxes),
            "provenance": {g: str(p) for g, p in self.provenance.items()},
        }

    @classmethod
    def from_dict(
        cls,
        payload: Optional[Mapping[str, Any]],
        *,
        fallback: Optional["SetupSnapshot"] = None,
    ) -> "SetupSnapshot":
        """Read a snapshot back, degrading rather than raising.

        ``fallback`` is required by the read path on purpose: a stored dataset or
        a recovery cache written before this key existed has no snapshot at all,
        and a corpus that cannot state its geometry must still open. Anything
        unparseable falls back field by field, so one bad number does not
        discard a whole valid setup.
        """
        base = fallback if fallback is not None else cls()
        if not isinstance(payload, Mapping):
            return base

        def _num(key: str, current, cast):
            try:
                value = payload[key]
            except (KeyError, TypeError):
                return current
            if value is None or isinstance(value, bool):
                return current
            try:
                return cast(value)
            except (TypeError, ValueError):
                return current

        raw_prov = payload.get("provenance")
        prov = dict(base.provenance)
        if isinstance(raw_prov, Mapping):
            for group in SETUP_GROUPS:
                parsed = _coerce_provenance(raw_prov.get(group))
                if parsed is not None:
                    prov[group] = parsed

        scale = payload.get("scale_text_to_boxes")
        return cls(
            canvas_width=_num("canvas_width", base.canvas_width, int),
            canvas_height=_num("canvas_height", base.canvas_height, int),
            monitor_width_mm=_num("monitor_width_mm", base.monitor_width_mm, float),
            viewing_distance_mm=_num(
                "viewing_distance_mm", base.viewing_distance_mm, float
            ),
            base_font_size=_num("base_font_size", base.base_font_size, int),
            font_family=str(payload.get("font_family") or base.font_family),
            line_spacing=_num("line_spacing", base.line_spacing, float),
            scale_text_to_boxes=(
                bool(scale) if isinstance(scale, bool) else base.scale_text_to_boxes
            ),
            screen_provenance=prov["screen"],
            geometry_provenance=prov["geometry"],
            text_provenance=prov["text"],
        )


def _coerce_provenance(value: Any) -> Optional[Provenance]:
    """A ``Provenance`` from a wire string, or ``None`` when unrecognised."""
    if isinstance(value, Provenance):
        return value
    if not isinstance(value, str):
        return None
    try:
        return Provenance(value.strip().lower())
    except ValueError:
        return None


def format_provenance_param(snapshot: SetupSnapshot) -> str:
    """The compact ``setup_prov`` share value, e.g.
    ``screen:assumed,geom:skipped,text:measured``.

    Provenance is metadata *about* settings rather than a setting, so it travels
    only far enough to stop a recipient being misled about numbers they did not
    choose — it changes no figure and takes no input.
    """
    return ",".join(
        f"{_GROUP_WIRE_NAMES[group]}:{snapshot.provenance[group]}"
        for group in SETUP_GROUPS
    )


def parse_provenance_param(value: Optional[str]) -> dict[str, Provenance]:
    """Parse ``setup_prov`` into ``{group: Provenance}``.

    Tolerant by contract — it reads a URL a stranger may have edited: unknown
    group names and unknown provenance words are dropped rather than raising, so
    a mangled param degrades to "no badges" instead of breaking the link.
    """
    out: dict[str, Provenance] = {}
    if not value or not isinstance(value, str):
        return out
    for chunk in value.split(","):
        name, _, raw = chunk.partition(":")
        group = _WIRE_NAME_GROUPS.get(name.strip().lower())
        if group is None:
            continue
        parsed = _coerce_provenance(raw)
        if parsed is not None:
            out[group] = parsed
    return out
