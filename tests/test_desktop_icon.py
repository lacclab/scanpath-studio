from pathlib import Path

from PIL import Image
import pytest

from desktop.make_icons import draw_icon
from desktop import smoke_test


ROOT = Path(__file__).resolve().parents[1]


def test_icon_remains_distinct_at_small_sizes():
    for size in (16, 32, 64, 512):
        icon = draw_icon(size)
        assert icon.size == (size, size)
        colors = icon.convert("RGB").getcolors(maxcolors=size * size)
        assert colors is not None and len(colors) >= 4


def test_committed_desktop_icon_formats_include_required_sizes():
    png = Image.open(ROOT / "desktop" / "icons" / "icon.png")
    assert png.size == (512, 512)
    ico = Image.open(ROOT / "desktop" / "icons" / "icon.ico")
    assert {16, 32, 48, 64, 128, 256} <= {width for width, _ in ico.ico.sizes()}
    icns = Image.open(ROOT / "desktop" / "icons" / "icon.icns")
    assert max(icns.size) >= 512


def test_macos_smoke_gate_verifies_signature(monkeypatch, tmp_path):
    binary = tmp_path / "ScanpathStudio"
    binary.touch()
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")
    monkeypatch.setattr(
        smoke_test.subprocess,
        "run",
        lambda command, **kwargs: calls.append(command) or Result(),
    )
    smoke_test._verify_macos_signature(binary)
    assert calls[0][:4] == ["codesign", "--verify", "--deep", "--strict"]


def test_macos_smoke_gate_fails_on_bad_signature(monkeypatch, tmp_path):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "invalid signature"

    monkeypatch.setattr(smoke_test.sys, "platform", "darwin")
    monkeypatch.setattr(smoke_test.subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(SystemExit, match="signature FAILED"):
        smoke_test._verify_macos_signature(tmp_path / "ScanpathStudio")
