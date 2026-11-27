"""Session-local undo and redo for edits to the Scanpath plot."""

from __future__ import annotations

from dataclasses import dataclass, field

from .session_keys import (
    COMPARE_FIX_RANGE_PARAM,
    FIX_RANGE_PARAM,
    SINGLE_COMPARE_FIX_RANGE,
    SINGLE_FIX_RANGE,
)

_LIMIT = 30
_WINDOW_QUERY = {
    SINGLE_FIX_RANGE: f"?{FIX_RANGE_PARAM}",
    SINGLE_COMPARE_FIX_RANGE: f"?{COMPARE_FIX_RANGE_PARAM}",
}


@dataclass(frozen=True)
class Design:
    selection: str | None = None
    custom: dict | None = None
    drifted_from: tuple | None = None

    def without_window(self, window: str) -> Design:
        def prune(settings):
            if not settings or window not in settings:
                return settings
            if window == SINGLE_FIX_RANGE and settings.get(
                "single_fix_range_all_trials"
            ):
                return settings
            return {k: v for k, v in settings.items() if k != window}

        custom = prune(self.custom)
        drift = self.drifted_from
        if drift:
            drift = (drift[0], prune(drift[1]))
        return Design(self.selection, custom, drift)


@dataclass
class Edit:
    """Only changed settings. A missing key on one side means automatic."""

    before: dict
    after: dict
    designs: tuple[Design, Design]
    all_trials: tuple[bool, bool]

    def action_label(self, *, redo: bool) -> str:
        """Describe the first restored control and how many others move with it."""
        action = "Redo" if redo else "Undo"
        changed = dict.fromkeys([*self.before, *self.after])
        keys = [key for key in changed if not key.startswith("?")] or list(changed)
        if not keys:
            return f"{action} plot change"
        key = keys[0]
        name = {
            "global_show_order": "fixation index labels",
            "global_fixation_opacity": "marker opacity",
            "global_show_fix": "fixation visibility",
            "global_show_saccades": "saccade visibility",
            "global_show_heatmap": "heatmap visibility",
            "global_x_field": "horizontal axis",
            "global_y_field": "vertical axis",
        }.get(key) or (
            key.removeprefix("?")
            .removeprefix("global_")
            .removeprefix("single_")
            .replace("_", " ")
        )
        target = self.after if redo else self.before
        value = target.get(key)
        if value is None:
            restored = "automatic"
        elif isinstance(value, bool):
            restored = "on" if value else "off"
        elif key.endswith("_opacity") and isinstance(value, (float, int)):
            restored = f"{value:.0%}"
        elif isinstance(value, (tuple, list)) and 0 < len(value) <= 3:
            restored = " to ".join(map(str, value))
        elif isinstance(value, (dict, tuple, list)):
            restored = ""
        else:
            restored = str(value)
        label = f"{action} {name} change"
        if restored and len(restored) <= 60:
            label += f", restore {restored}"
        if len(keys) > 1:
            label += f", and {len(keys) - 1} other setting" + (
                "s" if len(keys) > 2 else ""
            )
        return label


@dataclass
class PlotHistory:
    dataset: str
    past: list[Edit] = field(default_factory=list)
    future: list[Edit] = field(default_factory=list)
    settings: dict | None = None
    design: Design = field(default_factory=Design)
    readings: tuple = ()
    restoring: bool = False

    def observe(self, settings: dict, design: Design, readings: tuple) -> None:
        """Record one rendered edit. Moving to another reading only changes the baseline."""
        comparison_changed = self.settings is not None and (
            self.settings.get("single_compare_toggle")
            != settings.get("single_compare_toggle")
        )
        if (
            self.settings is not None
            and self.readings != readings
            and not comparison_changed
        ):
            for old, new, window in zip(
                self.readings, readings, _WINDOW_QUERY, strict=True
            ):
                if old != new:
                    # A trial-specific window cannot be replayed on a different reading.
                    design = design.without_window(window)
                    for stack in (self.past, self.future):
                        for edit in stack:
                            for side, all_trials in zip(
                                (edit.before, edit.after), edit.all_trials, strict=True
                            ):
                                if window != SINGLE_FIX_RANGE or not all_trials:
                                    side.pop(window, None)
                                    side.pop(_WINDOW_QUERY[window], None)
                            edit.designs = tuple(
                                d.without_window(window) for d in edit.designs
                            )
                        stack[:] = [edit for edit in stack if edit.before or edit.after]
        elif (
            self.settings is not None
            and not self.restoring
            and self.settings != settings
        ):
            before = {
                k: v
                for k, v in self.settings.items()
                if k not in settings or settings[k] != v
            }
            after = {
                k: v
                for k, v in settings.items()
                if k not in self.settings or self.settings[k] != v
            }
            scopes = (
                bool(self.settings.get("single_fix_range_all_trials")),
                bool(settings.get("single_fix_range_all_trials")),
            )
            self.past.append(Edit(before, after, (self.design, design), scopes))
            del self.past[:-_LIMIT]
            self.future.clear()
        self.settings, self.design, self.readings = settings, design, readings
        self.restoring = False

    def step(self, *, redo: bool) -> tuple[set, dict, Design] | None:
        source, destination = (
            (self.future, self.past) if redo else (self.past, self.future)
        )
        if not source:
            return None
        edit = source.pop()
        destination.append(edit)
        self.restoring = True
        return (
            edit.before.keys() | edit.after.keys(),
            edit.after if redo else edit.before,
            edit.designs[int(redo)],
        )
