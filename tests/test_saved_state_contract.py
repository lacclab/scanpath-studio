"""What a share link carries, a settings file keeps, and a settings file keeps,
the recovery cache keeps — unless a named exclusion says why not.

The three are hand-kept lists in three modules (`url_state`'s link tables,
`session_keys.PLOT_CONFIG_*`, `persistence._SESSION_KEYS`). A setting added to
the link but not the file, or to the file but not the cache, passes every
round-trip test and is lost only when a user saves a file or restarts the app.
These tests make that omission fail, and make each deliberate exclusion carry
its reason where the next author will read it.
"""

from __future__ import annotations

import pytest

from scanpath_studio import persistence
from scanpath_studio import session_keys as sk


def test_every_link_setting_is_in_the_settings_file():
    missing = (
        sk.LINK_STATE_KEYS - sk.SETTINGS_FILE_STATE_KEYS - set(sk.NOT_IN_SETTINGS_FILE)
    )
    assert not missing, (
        f"A share link carries {sorted(missing)}, but 🔗 Share → File does not, "
        "so saving a settings file loses them. Write and read them in "
        "plot_config.build_plot_config / url_state._restore_plot_config and add "
        "them to session_keys.PLOT_CONFIG_*; or, if the file must not carry "
        "them, add them to session_keys.NOT_IN_SETTINGS_FILE with the reason."
    )


def test_every_settings_file_key_is_cached():
    missing = (
        sk.SETTINGS_FILE_STATE_KEYS
        - persistence._SESSION_KEYS
        - set(persistence.NOT_CACHED)
    )
    assert not missing, (
        f"A settings file restores {sorted(missing)}, but the recovery cache "
        "does not keep them, so closing the app loses them. Add them to "
        "persistence._SESSION_KEYS; or, if the cache must not keep them, add "
        "them to persistence.NOT_CACHED with the reason."
    )


@pytest.mark.parametrize(
    ("exclusions", "carried_by", "excluded_from"),
    [
        ("NOT_IN_SETTINGS_FILE", "LINK_STATE_KEYS", "SETTINGS_FILE_STATE_KEYS"),
        ("NOT_CACHED", "SETTINGS_FILE_STATE_KEYS", "_SESSION_KEYS"),
    ],
)
def test_every_exclusion_is_real_and_explained(exclusions, carried_by, excluded_from):
    """An exclusion names a key the earlier list carries and the later one still
    leaves out, with a reason — so a stale or empty one fails here."""
    owner = persistence if exclusions == "NOT_CACHED" else sk
    excluded = getattr(owner, exclusions)
    carried = getattr(sk, carried_by)
    later = getattr(
        persistence if excluded_from == "_SESSION_KEYS" else sk, excluded_from
    )
    for key, reason in excluded.items():
        assert key in carried, f"{exclusions} names {key!r}, which {carried_by} lacks"
        assert key not in later, f"{exclusions} names {key!r}, which is now kept"
        assert len(reason.split()) >= 5, f"{exclusions}[{key!r}] needs its reason"


def test_bs_filters_and_the_export_size_survive_the_cache(tmp_path):
    """A's fixation and saccade filters were kept and B's were not; the export
    size and DPI were in links and settings files but not the cache."""
    session = {
        "global_fixclass_short_mode": "Hide",
        "cmp1_fixclass_short_mode": "Highlight",
        "cmp1_fixclass_long_threshold_ms": 950,
        "cmp1_saccade_classes": ["forward", "skip"],
        sk.EXPORT_FIGURE_DPI: 600,
        sk.EXPORT_FIGURE_WIDTH: 85.0,
        sk.EXPORT_FIGURE_WIDTH_UNIT: "mm",
    }
    expected = dict(session)  # saving adds its own bookkeeping to `session`
    assert persistence.save_state(session, tmp_path)
    restored: dict = {}
    assert persistence.restore_state(restored, tmp_path)
    for key, value in expected.items():
        assert restored.get(key) == value, key


@pytest.mark.timeout(240)
def test_a_refresh_shows_bs_restored_filters():
    """The app keeps a cached B filter rather than re-seeding it."""
    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    at = AppTest.from_file(APP_SCRIPT)
    at.session_state[sk.SINGLE_COMPARE_TOGGLE] = True
    at.session_state["cmp1_fixclass_short_mode"] = "Highlight"
    at.session_state[sk.EXPORT_FIGURE_DPI] = 600
    at.run(timeout=120)
    assert not at.exception, at.exception
    at.run(timeout=120)
    assert at.session_state["cmp1_fixclass_short_mode"] == "Highlight"
    assert at.session_state[sk.EXPORT_FIGURE_DPI] == 600
