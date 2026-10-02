"""UX-184 — one Download folder for every public corpus, chosen by the user."""

from __future__ import annotations

import os

import pytest

from scanpath_studio import app, cli
from scanpath_studio.constants import DOWNLOAD_DIR_ENV, DOWNLOAD_DIR_KEY


def test_a_corpus_default_lands_in_the_download_folder(monkeypatch, tmp_path):
    monkeypatch.setenv(DOWNLOAD_DIR_ENV, str(tmp_path))
    assert app._download_target("data/PoTeC") == str(tmp_path / "PoTeC")
    assert app._download_target("data/OneStop") == str(tmp_path / "OneStop")


def test_a_pinned_absolute_default_is_left_alone(monkeypatch, tmp_path):
    monkeypatch.setenv(DOWNLOAD_DIR_ENV, str(tmp_path / "elsewhere"))
    pinned = str(tmp_path / "potec")
    assert app._download_target(pinned) == pinned
    assert app._download_target("") == ""


def test_unset_it_is_the_folder_downloads_always_used(monkeypatch):
    monkeypatch.delenv(DOWNLOAD_DIR_ENV, raising=False)
    assert app._download_target("data/PoTeC") == app._resolve_data_dir("data/PoTeC")


@pytest.mark.parametrize(
    "extra", [["--download-dir", "D:/corpora"], ["--download-dir=D:/corpora"]]
)
def test_the_run_flag_sets_the_default_and_is_not_forwarded(monkeypatch, extra):
    monkeypatch.delenv(DOWNLOAD_DIR_ENV, raising=False)
    rest = cli._consume_download_dir([*extra, "--server.port", "8600"])
    assert rest == ["--server.port", "8600"]
    assert os.environ[DOWNLOAD_DIR_ENV] == "D:/corpora"


def test_the_run_flag_needs_a_folder():
    with pytest.raises(SystemExit):
        cli._consume_download_dir(["--download-dir"])


def test_the_choice_survives_a_restart_and_only_as_a_string():
    from scanpath_studio.persistence import _SESSION_KEYS, _restorable_session

    assert DOWNLOAD_DIR_KEY in _SESSION_KEYS
    assert _restorable_session({DOWNLOAD_DIR_KEY: "/corpora"}) == {
        DOWNLOAD_DIR_KEY: "/corpora"
    }
    assert DOWNLOAD_DIR_KEY not in _restorable_session({DOWNLOAD_DIR_KEY: 7})


@pytest.mark.timeout(180)
def test_the_data_page_box_follows_the_folder_until_edited(tmp_path):
    """Choosing a folder moves an untouched Data directory box with it; a box
    the user typed into keeps what they typed."""
    from streamlit.testing.v1 import AppTest

    from scanpath_studio.constants import _VIEW_DATA
    from tests.conftest import APP_SCRIPT, pin_view

    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["data_source_choice"] = app.PUBLIC_DATASETS_CHOICE
    at.session_state["public_dataset_choice"] = "PoTeC — Potsdam Textbook Corpus"
    at.session_state[DOWNLOAD_DIR_KEY] = str(tmp_path / "first")
    pin_view(at, _VIEW_DATA)
    at.run()
    assert not at.exception, at.exception
    assert at.text_input(key="potec_dir").value == str(tmp_path / "first" / "PoTeC")
    folder = at.text_input(key=DOWNLOAD_DIR_KEY)
    assert folder.value == str(tmp_path / "first")
    assert any(
        f"saves it to `{tmp_path / 'first' / 'PoTeC'}`" in str(i.value) for i in at.info
    )

    pin_view(at, _VIEW_DATA)  # AppTest forgets the page between runs
    folder.set_value(str(tmp_path / "second")).run()
    assert not at.exception, at.exception
    assert at.text_input(key="potec_dir").value == str(tmp_path / "second" / "PoTeC")

    mine = str(tmp_path / "mine")
    pin_view(at, _VIEW_DATA)
    at.text_input(key="potec_dir").set_value(mine).run()
    pin_view(at, _VIEW_DATA)
    at.text_input(key=DOWNLOAD_DIR_KEY).set_value(str(tmp_path / "third")).run()
    assert not at.exception, at.exception
    assert at.text_input(key="potec_dir").value == mine


def test_compare_looks_in_the_download_folder_too(monkeypatch, tmp_path):
    """Dataset B for a comparison is read before its own box ever renders (and
    after every restart), so it has to default to the same folder."""
    import streamlit as st

    from scanpath_studio import compare_source

    monkeypatch.setenv(DOWNLOAD_DIR_ENV, str(tmp_path))
    for key in ("potec_dir", "onestop_public_dir", "onestop_variant"):
        st.session_state.pop(key, None)
    root, _ = compare_source._public_location("PoTeC — Potsdam Textbook Corpus")
    assert root == str(tmp_path / "PoTeC")
    root, _ = compare_source._public_location(app.ONESTOP_REGIME_CHOICES["repeated"])
    assert root == str(tmp_path / "OneStop")
