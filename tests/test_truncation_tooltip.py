"""UX-196 — the hover tooltip for cut-off dropdown labels."""

from __future__ import annotations

import json
from pathlib import Path

from scanpath_studio import truncation_tooltip


def test_script_installs_once_into_the_parent_document():
    script = truncation_tooltip.tooltip_script()
    assert script.startswith("<script>") and script.endswith("</script>")
    assert "window.parent.document" in script
    # The id guard is what keeps a rerun's re-mount from stacking listeners.
    assert f"getElementById({json.dumps(truncation_tooltip.SCRIPT_ID)})" in script


def test_script_targets_options_and_the_closed_box():
    script = truncation_tooltip.tooltip_script()
    assert "role=" in script and "option" in script
    assert "combobox" in script


def test_app_mounts_it():
    source = (
        Path(truncation_tooltip.__file__)
        .with_name("app.py")
        .read_text(encoding="utf-8")
    )
    assert "render_truncation_tooltips()" in source
