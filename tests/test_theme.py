"""BUG-6: the branded theme applies regardless of launch directory.

Streamlit only auto-loads ``.streamlit/config.toml`` relative to the launch
directory, so ``python -m scanpath_studio`` from outside ``app/`` misses it and
falls back to the default red accent. ``cli.launch_app`` injects the theme as
``--theme.*`` flags instead; these tests pin that behaviour and guard against the
CLI-flag values drifting from the bundled config file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import streamlit.config as st_config
import streamlit.web.cli as st_cli

from scanpath_studio import cli
from scanpath_studio.constants import APP_THEME, APP_THEME_DARK

_CONFIG_TOML = Path(__file__).resolve().parents[1] / ".streamlit" / "config.toml"
_DOCS_CSS = Path(__file__).resolve().parents[1] / "docs" / "stylesheets" / "extra.css"


def test_config_toml_matches_theme_constants():
    """The bundled config file and the Python source of truth stay in sync."""
    theme = tomllib.loads(_CONFIG_TOML.read_text())["theme"]
    dark = theme.pop("dark", {})
    assert theme == APP_THEME
    assert dark == APP_THEME_DARK


def test_docs_stylesheet_matches_theme_constants():
    """The docs site's brand palette mirrors the app theme constants.

    ``docs/stylesheets/extra.css`` hand-mirrors the primary colors (CSS can't
    import Python); this guards a rebrand in ``constants.py`` from silently
    leaving the published docs on the old palette."""
    css = _DOCS_CSS.read_text()
    assert APP_THEME["primaryColor"] in css
    assert APP_THEME_DARK["primaryColor"] in css


def test_theme_flags_are_valid_config_options():
    """Every injected ``--theme.*`` flag names a real Streamlit config option."""
    st_config.get_config_options()
    valid = set(st_config._config_options_template)
    for flag in cli._theme_cli_flags():
        name = flag[len("--") :].split("=", 1)[0]
        assert name in valid, f"{name} is not a Streamlit config option"


def _run_launch(monkeypatch, extra_args):
    """Invoke ``launch_app`` with Streamlit stubbed out; return the built argv."""
    seen: dict[str, list[str]] = {}

    def fake_main():
        seen["argv"] = list(cli.sys.argv)
        return 0

    monkeypatch.setattr(st_cli, "main", fake_main)
    monkeypatch.setattr(cli.sys, "exit", lambda *a, **k: None)
    cli.launch_app(extra_args)
    return seen["argv"]


def test_launch_app_injects_branded_theme(monkeypatch):
    argv = _run_launch(monkeypatch, [])
    assert argv[:2] == ["streamlit", "run"]
    assert "--theme.primaryColor=#1f77b4" in argv
    assert "--theme.dark.primaryColor=#5aa9e6" in argv
    assert "--theme.base=light" in argv


def test_launch_app_forwards_extra_args_after_theme(monkeypatch):
    argv = _run_launch(monkeypatch, ["--server.port", "8502"])
    assert "--theme.primaryColor=#1f77b4" in argv
    # User flags still reach Streamlit, and come after the injected theme.
    assert argv[-2:] == ["--server.port", "8502"]


def test_launch_app_respects_user_theme_override(monkeypatch):
    argv = _run_launch(monkeypatch, ["--theme.primaryColor=#ff0000"])
    # When the caller sets their own theme, the branded flags are NOT injected.
    assert "--theme.primaryColor=#1f77b4" not in argv
    assert "--theme.primaryColor=#ff0000" in argv
