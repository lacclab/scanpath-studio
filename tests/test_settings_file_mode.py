"""A settings file puts the figure back in the mode it was saved in (schema 6).

Share → File used to save A's selection and Compare's *styles* but neither the
Animate / Compare switches nor which reading B was, so a comparison reopened as
a single static scanpath — or, in an open session, as A beside whatever B was
already selected. These drive the real writer (the Share → File panel in the
full app) and the real reader (a fresh app session handed the file), on a
multipart dataset so B's second screen is part of the round trip.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from scanpath_studio import tabs
from scanpath_studio.session_keys import (
    COMPARE_SOURCE_STATE_KEY,
    PENDING_COMPARE_STATE_KEY,
    SINGLE_ANIMATE,
    SINGLE_COMPARE_SCREEN_ID,
    SINGLE_COMPARE_TOGGLE,
)
from scanpath_studio.synthetic import make_multipart_synthetic_data
from scanpath_studio.url_state import SHARE_SECTION_KEY
from tests.conftest import APP_SCRIPT, SUBTAB_KEY, SUBTAB_SHARE

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

DATASET = "Two readers"
TRIAL = "multipart_demo"


def _two_readers() -> dict:
    """The multipart demo trial read by two readers, as a stored upload."""
    words, fixations = make_multipart_synthetic_data()
    second_words = words.assign(participant_id="reader2")
    second_fixations = fixations.assign(participant_id="reader2")
    return {
        "words": pd.concat([words, second_words], ignore_index=True),
        "fixations": pd.concat([fixations, second_fixations], ignore_index=True),
        "raw_gaze": pd.DataFrame(),
        "filter_fields": [],
        "composite_trial_columns": [],
    }


class _FakeUpload:
    """What `st.file_uploader` holds: bytes and an upload-event id."""

    def __init__(self, data: bytes, file_id: str = "settings-1"):
        self._data = data
        self.name = "scanpath_studio_settings.json"
        self.size = len(data)
        self.file_id = file_id

    def getvalue(self) -> bytes:
        return self._data


def _app() -> AppTest:
    at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
    at.session_state["_datasets"] = {DATASET: _two_readers()}
    at.session_state["data_source_choice"] = DATASET
    return at


def _save(monkeypatch, *, animate: bool, compare: bool) -> dict:
    """Set the mode (and B = the other reader, on its second screen) and save.

    A opens on `reader2` (the picker's first reading), so B is `synthetic`."""
    written: list[dict] = []
    real = tabs._build_studio_config

    def _recording(**kwargs):
        config = real(**kwargs)
        written.append(config)
        return config

    monkeypatch.setattr(tabs, "_build_studio_config", _recording)
    at = _app()
    at.run()
    assert not at.exception, at.exception
    at.session_state[SINGLE_ANIMATE] = animate
    at.session_state[SINGLE_COMPARE_TOGGLE] = compare
    if compare:
        at.session_state[PENDING_COMPARE_STATE_KEY] = {
            "participant_id": "synthetic",
            "trial_id": TRIAL,
        }
        at.session_state[SINGLE_COMPARE_SCREEN_ID] = "question"
    at.run()
    assert not at.exception, at.exception
    at.session_state[SUBTAB_KEY] = SUBTAB_SHARE
    at.session_state[SHARE_SECTION_KEY] = "File"
    at.run()
    assert not at.exception, at.exception
    assert written, "Share → File built no settings file"
    monkeypatch.setattr(tabs, "_build_studio_config", real)
    # Through JSON, as the download is.
    return json.loads(json.dumps(written[-1]))


def _restore(config: dict, *, before=None, settle: bool = True) -> AppTest:
    """A fresh session handed the file — optionally after `before(at)`."""
    at = _app()
    at.run()
    assert not at.exception, at.exception
    if before is not None:
        before(at)
    at.session_state["plot_config_upload"] = _FakeUpload(
        json.dumps(config).encode("utf-8")
    )
    at.run()
    assert not at.exception, at.exception
    if settle:  # a rerun, as the next click would cause
        at.run()
        assert not at.exception, at.exception
    return at


def _b(at: AppTest) -> tuple[str, str] | None:
    identity = at.session_state[tabs._COMPARE_IDENTITY_KEY]
    return tuple(identity) if identity else None


@pytest.mark.timeout(300)
# The default build; the experimental Preprocessing panel has its own test at
# the end of this file.
@pytest.mark.usefixtures("experimental_off")
class TestSettingsFileMode:
    @pytest.mark.parametrize(
        ("animate", "compare"),
        [(False, False), (True, False), (False, True), (True, True)],
        ids=["static", "animated", "compare", "co-animation"],
    )
    def test_the_mode_and_b_round_trip_in_a_fresh_session(
        self, monkeypatch, animate, compare
    ):
        config = _save(monkeypatch, animate=animate, compare=compare)
        assert config["schema"] == 6
        assert config["mode"] == {"animate": animate, "compare": compare}
        if compare:
            assert config["selection"]["compare"] == {
                "participant_id": "synthetic",
                "trial_id": TRIAL,
                "source": None,
                "screen_id": "question",
            }
        else:
            assert "compare" not in config["selection"]

        at = _restore(config)
        assert at.session_state[SINGLE_ANIMATE] is animate
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is compare
        assert at.session_state.get("_plot_config_skipped") == []
        if compare:
            assert _b(at) == ("synthetic", TRIAL)
            # B's second page survives, in B's own navigator.
            assert at.selectbox(key=SINGLE_COMPARE_SCREEN_ID).value == "question"

    def test_a_static_file_turns_off_a_running_comparison(self, monkeypatch):
        config = _save(monkeypatch, animate=False, compare=False)

        def _comparing(at):
            at.session_state[SINGLE_ANIMATE] = True
            at.session_state[SINGLE_COMPARE_TOGGLE] = True
            at.run()

        at = _restore(config, before=_comparing)
        assert at.session_state[SINGLE_ANIMATE] is False
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is False

    def test_an_older_file_guesses_no_comparison(self, monkeypatch):
        """A schema-5 file never said; the current mode is left alone and no
        B is invented."""
        config = _save(monkeypatch, animate=False, compare=False)
        config["schema"] = 5
        config.pop("mode")
        # Even a hand-added B in an old file is not acted on.
        config["selection"]["compare"] = {
            "participant_id": "synthetic",
            "trial_id": TRIAL,
        }
        at = _restore(config)
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is False
        assert PENDING_COMPARE_STATE_KEY not in at.session_state

    def test_an_unavailable_b_is_a_partial_restore_with_a_notice(self, monkeypatch):
        config = _save(monkeypatch, animate=True, compare=True)
        config["selection"]["compare"]["source"] = "A dataset nobody added"
        at = _restore(config)
        # The rest of the file still applies …
        assert at.session_state[SINGLE_ANIMATE] is True
        # … but no pair is guessed: Compare stays off and the file says why.
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is False
        skipped = at.session_state["_plot_config_skipped"]
        assert any(
            item.startswith("comparison (") and "A dataset nobody added" in item
            for item in skipped
        ), skipped
        assert at.session_state.get(COMPARE_SOURCE_STATE_KEY) != (
            "A dataset nobody added"
        )

    def test_a_b_missing_from_the_pool_is_a_partial_restore(self, monkeypatch):
        config = _save(monkeypatch, animate=False, compare=True)
        config["selection"]["compare"]["participant_id"] = "reader-not-here"
        at = _restore(config)
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is False
        assert any(
            "reader-not-here" in item
            for item in at.session_state["_plot_config_skipped"]
        )

    def test_a_b_missing_from_another_datasets_pool_is_reported(self, monkeypatch):
        """B in another dataset can only be checked once that dataset loads, so
        B's picker says so then rather than passing its default off as B."""
        from scanpath_studio.constants import SYNTHETIC_CHOICE

        config = _save(monkeypatch, animate=False, compare=True)
        config["selection"]["compare"].update(
            source=SYNTHETIC_CHOICE, participant_id="reader-not-there"
        )
        # The run the file is applied on is the one that resolves B.
        at = _restore(config, settle=False)
        assert at.session_state[SINGLE_COMPARE_TOGGLE] is True
        assert at.session_state[COMPARE_SOURCE_STATE_KEY] == SYNTHETIC_CHOICE
        assert any(
            "Couldn't restore scanpath B" in str(w.value)
            and "reader-not-there" in str(w.value)
            for w in at.warning
        ), [w.value for w in at.warning]


@pytest.mark.timeout(300)
def test_a_settings_file_restores_with_the_preprocessing_panel_shown(monkeypatch):
    """With `SCANPATH_EXPERIMENTAL=1` the 🧹 Preprocessing widgets render before
    the settings restore runs. Writing their keys then raised "cannot be
    modified after the widget … is instantiated" and the whole file was refused;
    they are now staged and applied before those widgets on the next run."""
    monkeypatch.setenv("SCANPATH_EXPERIMENTAL", "1")
    config = _save(monkeypatch, animate=False, compare=False)
    config["preprocessing"] = {
        **config.get("preprocessing", {}),
        "enabled": True,
        "short_policy": "Merge",
    }
    at = _restore(config, settle=False)
    assert any("Restored" in t.value for t in at.toast), [t.value for t in at.toast]
    assert at.session_state["global_preproc_enabled"] is True
    assert at.session_state["global_preproc_short_policy"] == "Merge"
    assert not any("Couldn't apply" in t.value for t in at.toast)
