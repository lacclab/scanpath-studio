"""DATA-16 / security audit S2: the corpus **Data directory** box.

It takes a free-text path from the browser, stats it, reports the result back
into the page, and — via ⬇ Download — writes into it. On a local run that is a
file picker. On any deployment someone else can reach it is a path-existence
oracle plus an arbitrary-directory write, and the app has no authentication on
any deployment.

Default is local (flipping it would break every existing install on upgrade); a
shared deployment sets ``SCANPATH_LOCAL_FS=0``. ``SCANPATH_DATA_ROOT`` confines
paths to a subtree and is useful either way.
"""

from __future__ import annotations

import pytest

from scanpath_studio.app import (
    DATA_ROOT_ENV,
    LOCAL_FS_ENV,
    _pick_directory_dialog,
    _resolve_data_dir,
    data_root,
    local_filesystem_enabled,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(LOCAL_FS_ENV, raising=False)
    monkeypatch.delenv(DATA_ROOT_ENV, raising=False)


class TestTheGate:
    def test_local_by_default(self):
        """An existing local install must keep its path box on upgrade."""
        assert local_filesystem_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", " No "])
    def test_a_deployment_can_turn_it_off(self, monkeypatch, value):
        monkeypatch.setenv(LOCAL_FS_ENV, value)
        assert local_filesystem_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "", "anything"])
    def test_anything_else_stays_local(self, monkeypatch, value):
        monkeypatch.setenv(LOCAL_FS_ENV, value)
        assert local_filesystem_enabled() is True

    def test_the_folder_picker_refuses_on_a_shared_deployment(self, monkeypatch):
        """Degrading to None on a *headless* host was never the guarantee: on a
        host that has a display, a remote click pops a modal dialog on the
        server's own desktop and blocks the thread until someone dismisses it."""
        monkeypatch.setenv(LOCAL_FS_ENV, "0")
        assert _pick_directory_dialog() is None


class TestTheAllowRoot:
    def test_unset_means_no_confinement(self, tmp_path):
        assert data_root() is None
        assert _resolve_data_dir(str(tmp_path / "anywhere")) == str(
            tmp_path / "anywhere"
        )

    def test_an_absolute_path_is_not_rewritten_when_unconfined(self):
        """`/tmp` is a symlink on macOS; resolving it would show the user
        `/private/tmp/...` in the "Found in `…`" line instead of what they typed."""
        assert _resolve_data_dir("/tmp/OneStop") == "/tmp/OneStop"

    def test_a_path_inside_the_root_passes_through(self, monkeypatch, tmp_path):
        monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
        inside = tmp_path / "OneStop"
        assert _resolve_data_dir(str(inside)) == str(inside)

    def test_a_path_outside_the_root_collapses_to_it(self, monkeypatch, tmp_path):
        monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path / "corpora"))
        (tmp_path / "corpora").mkdir()
        assert _resolve_data_dir("/etc") == str(tmp_path / "corpora")

    def test_dot_dot_cannot_escape(self, monkeypatch, tmp_path):
        """The comparison is on the *resolved* path, so traversal is caught
        rather than string-matched."""
        root = tmp_path / "corpora"
        root.mkdir()
        monkeypatch.setenv(DATA_ROOT_ENV, str(root))
        assert _resolve_data_dir(f"{root}/../../etc") == str(root)

    def test_a_symlink_out_of_the_root_cannot_escape(self, monkeypatch, tmp_path):
        root = tmp_path / "corpora"
        root.mkdir()
        outside = tmp_path / "secrets"
        outside.mkdir()
        (root / "link").symlink_to(outside)
        monkeypatch.setenv(DATA_ROOT_ENV, str(root))
        assert _resolve_data_dir(str(root / "link")) == str(root)

    def test_the_root_itself_is_allowed(self, monkeypatch, tmp_path):
        monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
        assert _resolve_data_dir(str(tmp_path)) == str(tmp_path)

    def test_a_blank_path_stays_blank(self, monkeypatch, tmp_path):
        """The loader's own missing-data note handles it; don't invent a root."""
        monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
        assert _resolve_data_dir("") == ""
        assert _resolve_data_dir("   ") == ""

    def test_a_relative_path_still_anchors_to_the_project_root(self):
        """Unchanged behaviour without an allow-root: the server may run from
        anywhere, so `data/OneStop` must not depend on cwd."""
        resolved = _resolve_data_dir("data/OneStop")
        assert resolved.endswith("/data/OneStop")
        assert resolved.startswith("/")
