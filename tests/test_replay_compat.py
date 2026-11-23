"""A replay shared or saved while it always drew fixations opens with them.

The Fixation switch reaches the replay too, so a link or settings file saved
with it off now means a replay without fixations. One saved before that drew
them anyway; read as saved it would open an empty replay, or saccades alone.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio import api, cli, controls, url_state


def _open(monkeypatch, query: dict, state: dict | None = None) -> dict:
    """Apply a link to a fresh session; return the session."""
    session = {} if state is None else state
    monkeypatch.setattr(url_state.st, "session_state", session)
    monkeypatch.setattr(url_state.st, "query_params", dict(query))
    url_state._apply_url_preset()
    return session


@pytest.mark.parametrize("saccades", ["0", "1"])
def test_an_old_replay_link_draws_its_fixations(monkeypatch, saccades):
    query = {
        "show_fixations": "0",
        "show_saccades": saccades,
        "show_heatmap": "1",
        "tab": "animation",
    }
    session = _open(monkeypatch, query)
    assert session["single_animate"] is True
    assert session["global_show_fix"] is True
    # Leaving the replay returns to the static figure the link described.
    monkeypatch.setattr(controls.st, "session_state", session)
    controls.leave_animation()
    assert session["global_show_fix"] is False
    assert session["global_show_saccades"] is (saccades == "1")


def test_a_link_that_hides_the_replays_fixations_keeps_them_hidden(monkeypatch):
    query = {
        "show_fixations": "0",
        "show_saccades": "1",
        "tab": "animation",
        "replay_fixations": "0",
    }
    session = _open(monkeypatch, query)
    assert session["single_animate"] is True
    assert session["global_show_fix"] is False


def test_the_link_decides_only_the_first_run(monkeypatch):
    """The reader runs on every rerun; a fixation switch turned off in the
    replay after the link opened stays off."""
    query = {"show_fixations": "0", "show_saccades": "0", "tab": "animation"}
    session = _open(monkeypatch, query)
    session["global_show_fix"] = False
    session.pop("_auto_replay_fixations")
    _open(monkeypatch, query, session)
    assert session["global_show_fix"] is False


def test_a_static_link_keeps_its_fixations_off(monkeypatch):
    session = _open(monkeypatch, {"show_fixations": "0", "show_saccades": "1"})
    assert session["global_show_fix"] is False
    assert "single_animate" not in session


def _restored(config: dict) -> dict:
    import streamlit as st

    st.session_state.clear()
    url_state._restore_plot_config(config, pd.DataFrame(), pd.DataFrame())
    return dict(st.session_state)


def test_an_old_settings_file_draws_the_replays_fixations():
    restored = _restored(
        {
            "schema": 9,
            "mode": {"animate": True, "compare": False},
            "layers": {"fixations": False, "saccades": False, "heatmap": True},
        }
    )
    assert restored["single_animate"] is True
    assert restored["global_show_fix"] is True
    # As with the old link, leaving the replay returns to the static figure
    # the file described.
    import streamlit as st

    controls.leave_animation()
    assert st.session_state["global_show_fix"] is False
    st.session_state.clear()


def test_a_saccades_only_replay_file_stays_saccades_only():
    restored = _restored(
        {
            "schema": url_state.PLOT_CONFIG_SCHEMA,
            "mode": {"animate": True, "compare": False},
            "layers": {"fixations": False, "saccades": True},
        }
    )
    assert restored["single_animate"] is True
    assert restored["global_show_fix"] is False


def test_the_api_refuses_a_replay_with_nothing_to_draw():
    from scanpath_studio.synthetic import load_synthetic_data

    words, fixations = load_synthetic_data()
    pid, tid = fixations.iloc[0][["participant_id", "trial_id"]]
    with pytest.raises(ValueError, match="nothing to replay"):
        api.animate_scanpath(
            words, fixations, pid, tid, show_fixations=False, show_saccades=False
        )


def test_the_cli_refuses_a_replay_with_nothing_to_draw(tmp_path):
    with pytest.raises(SystemExit, match="--no-fixations and --no-saccades"):
        cli.render(
            [
                "--sample",
                "--animate",
                "--no-fixations",
                "--no-saccades",
                "-o",
                str(tmp_path / "replay.html"),
            ]
        )
    assert not (tmp_path / "replay.html").exists()


def _replay_app(query: dict):
    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT, default_timeout=180)
    for key, value in query.items():
        at.query_params[key] = value
    at.run()
    assert not at.exception, at.exception
    return at


def test_a_replay_opened_with_both_layers_off_shows_its_fixations():
    """A link the API would refuse (both layers off, no legacy reading) opens
    with fixations, so the replay draws and Share → Code stays runnable."""
    at = _replay_app(
        {
            "show_fixations": "0",
            "show_saccades": "0",
            "replay_fixations": "0",
            "tab": "animation",
        }
    )
    assert at.session_state["single_animate"] is True
    assert at.session_state["global_show_fix"] is True


def test_the_last_layer_of_a_replay_cannot_be_switched_off():
    at = _replay_app({"show_saccades": "0", "tab": "animation"})
    fixations = at.toggle(key="global_show_fix")
    assert fixations.value is True
    assert fixations.disabled
    assert "A replay draws fixations or saccades" in (fixations.help or "")
    # With both on, either can go; then the other is the one left.
    at.toggle(key="global_show_saccades").set_value(True).run()
    assert not at.toggle(key="global_show_fix").disabled
    at.toggle(key="global_show_fix").set_value(False).run()
    assert at.toggle(key="global_show_saccades").disabled
    # A static figure may hide both.
    at.toggle(key="single_animate").set_value(False).run()
    assert not at.toggle(key="global_show_saccades").disabled
