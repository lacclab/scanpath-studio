"""DATA-16 / security audit S2: the corpus **Data directory** box.

It takes a free-text path from the browser, stats it, reports the result back
into the page, and — via ⬇ Download — writes into it. On a local run that is a
file picker. On any deployment someone else can reach it is a path-existence
oracle plus an arbitrary-directory write, and the app has no authentication on
any deployment.

ENG-66: unset, the gate follows the server's bind address — on for a server
listening on loopback only (``scanpath-studio run``, the desktop app), off for
one other machines can reach — and ``SCANPATH_LOCAL_FS`` overrides it either
way. ``SCANPATH_DATA_ROOT`` confines paths to a subtree and is useful either way.
"""

from __future__ import annotations

import pytest

from scanpath_studio import app as app_module
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


def _gate_app():
    import streamlit as st

    from scanpath_studio.app import local_filesystem_enabled

    st.session_state["answer"] = local_filesystem_enabled()


def _serving(monkeypatch, *, loopback: bool) -> None:
    """Pretend to run inside a Streamlit server bound to loopback, or not."""
    monkeypatch.setattr(app_module.runtime, "exists", lambda: True)
    monkeypatch.setattr(app_module, "server_bound_to_loopback", lambda: loopback)


class TestTheGate:
    def test_on_for_a_server_on_loopback(self, monkeypatch):
        """``scanpath-studio run`` and the desktop app keep their path box."""
        _serving(monkeypatch, loopback=True)
        assert local_filesystem_enabled() is True

    def test_off_for_a_server_other_machines_can_reach(self, monkeypatch):
        """ENG-66: a hosted demo is safe without remembering to set anything."""
        _serving(monkeypatch, loopback=False)
        assert local_filesystem_enabled() is False

    def test_on_outside_a_server(self, monkeypatch):
        """The API and the CLI read the user's own paths."""
        monkeypatch.setattr(app_module.runtime, "exists", lambda: False)
        assert local_filesystem_enabled() is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", " No ", "off"])
    def test_a_deployment_can_turn_it_off(self, monkeypatch, value):
        _serving(monkeypatch, loopback=True)
        monkeypatch.setenv(LOCAL_FS_ENV, value)
        assert local_filesystem_enabled() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", " ON "])
    def test_a_trusted_lab_server_can_turn_it_on(self, monkeypatch, value):
        _serving(monkeypatch, loopback=False)
        monkeypatch.setenv(LOCAL_FS_ENV, value)
        assert local_filesystem_enabled() is True

    @pytest.mark.parametrize("value", ["", "anything"])
    def test_anything_else_follows_the_bind_address(self, monkeypatch, value):
        _serving(monkeypatch, loopback=False)
        monkeypatch.setenv(LOCAL_FS_ENV, value)
        assert local_filesystem_enabled() is False

    def test_a_real_server_on_every_interface_is_off(self):
        """End to end, unpatched: an AppTest's ``server.address`` is unset, which
        is Streamlit's every-interface default — a hosted demo's setting."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_function(_gate_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["answer"] is False

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


def _servable_app():
    import streamlit as st

    from scanpath_studio.tabs import _servable_image_path

    st.session_state["_datasets"] = {"my upload": {}}
    st.session_state["answer"] = _servable_image_path(st.session_state["probe_path"])


class TestUploadedImagePaths:
    """ENG-57: the stimulus layer reads ``image_path`` off the server's disk and
    sends it to the browser. With local access off, an uploaded table's
    ``image_path`` must not reach that read — it let an upload exfiltrate any PNG
    on the server (a real file with a secret appended came back base64-encoded)."""

    def _answer(self, source, path="/srv/secret.png"):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_function(_servable_app)
        at.session_state["data_source_choice"] = source
        at.session_state["probe_path"] = path
        at.run()
        assert not at.exception, at.exception
        return at.session_state["answer"]

    def test_an_upload_on_a_shared_deployment_reads_nothing(self, monkeypatch):
        monkeypatch.setenv(LOCAL_FS_ENV, "0")
        assert self._answer("my upload") is None

    def test_an_upload_in_progress_reads_nothing_either(self, monkeypatch):
        from scanpath_studio.constants import UPLOAD_CHOICE

        monkeypatch.setenv(LOCAL_FS_ENV, "0")
        assert self._answer(UPLOAD_CHOICE) is None

    def test_a_server_side_source_keeps_its_images(self, monkeypatch):
        monkeypatch.setenv(LOCAL_FS_ENV, "0")
        assert self._answer("Bundled demo") == "/srv/secret.png"

    def test_a_server_nobody_configured_reads_nothing(self):
        """ENG-66: the demo's case — no variable set, every interface."""
        assert self._answer("my upload") is None

    def test_a_local_run_keeps_an_uploads_images(self, monkeypatch):
        monkeypatch.setenv(LOCAL_FS_ENV, "1")
        assert self._answer("my upload") == "/srv/secret.png"
