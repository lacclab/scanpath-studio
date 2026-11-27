"""What a share link carries, a settings file keeps; what either restores, the
recovery cache keeps — unless a named exclusion says why not.

The three are hand-kept lists in three modules (`url_state`'s link tables,
`session_keys.PLOT_CONFIG_*`, `persistence._SESSION_KEYS`). A setting added to
the link but not the file, or to either but not the cache, passes every
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


def test_every_restored_key_is_cached():
    missing = (
        (sk.LINK_STATE_KEYS | sk.SETTINGS_FILE_STATE_KEYS)
        - persistence._SESSION_KEYS
        - set(persistence.NOT_CACHED)
    )
    assert not missing, (
        f"A link or a settings file restores {sorted(missing)}, but the recovery "
        "cache does not keep them, so closing the app loses them. Add them to "
        "persistence._SESSION_KEYS; or, if the cache must not keep them, add "
        "them to persistence.NOT_CACHED with the reason."
    )


@pytest.mark.parametrize(
    ("owner", "exclusions", "carried_by", "excluded_from"),
    [
        (
            sk,
            "NOT_IN_SETTINGS_FILE",
            sk.LINK_STATE_KEYS,
            sk.SETTINGS_FILE_STATE_KEYS,
        ),
        (
            persistence,
            "NOT_CACHED",
            sk.LINK_STATE_KEYS | sk.SETTINGS_FILE_STATE_KEYS,
            persistence._SESSION_KEYS,
        ),
    ],
    ids=["settings-file", "cache"],
)
def test_every_exclusion_is_real_and_explained(
    owner, exclusions, carried_by, excluded_from
):
    """An exclusion names a key the earlier list carries and the later one still
    leaves out, with a reason — so a stale or empty one fails here."""
    for key, reason in getattr(owner, exclusions).items():
        assert key in carried_by, f"{exclusions} names {key!r}, which nothing carries"
        assert key not in excluded_from, (
            f"{exclusions} names {key!r}, which is now kept"
        )
        assert len(reason.split()) >= 5, f"{exclusions}[{key!r}] needs its reason"


def test_bs_filters_the_export_size_and_view_preferences_survive_the_cache(tmp_path):
    session = {
        "global_fixclass_short_mode": "Hide",
        "cmp1_fixclass_short_mode": "Highlight",
        "cmp1_fixclass_long_threshold_ms": 950,
        "cmp1_saccade_classes": ["forward", "skip"],
        sk.EXPORT_FIGURE_DPI: 600,
        sk.EXPORT_FIGURE_WIDTH: 85.0,
        sk.EXPORT_FIGURE_WIDTH_UNIT: "in",
        sk.SINGLE_SHOW_CHIPS: False,
        "single_fix_range_all_trials": True,
    }
    expected = dict(session)  # saving adds its own bookkeeping to `session`
    assert persistence.save_state(session, tmp_path)
    restored: dict = {}
    assert persistence.restore_state(restored, tmp_path)
    for key, value in expected.items():
        assert restored.get(key) == value, key


def test_a_blank_export_width_is_kept_and_a_foreign_unit_is_not(tmp_path):
    """A blank Width box (the figure's own size) is a value its control takes,
    so it is restored quietly; a unit the box does not offer is dropped."""
    session = {sk.EXPORT_FIGURE_WIDTH: None, sk.EXPORT_FIGURE_WIDTH_UNIT: "cm"}
    assert persistence.save_state(session, tmp_path)
    restored: dict = {}
    assert persistence.restore_state(restored, tmp_path)
    assert sk.EXPORT_FIGURE_WIDTH in restored
    assert restored[sk.EXPORT_FIGURE_WIDTH] is None
    assert sk.EXPORT_FIGURE_WIDTH_UNIT not in restored


@pytest.mark.timeout(240)
def test_a_refresh_shows_bs_cached_filter(tmp_path):
    """Through the cache, as a refresh restores it: the app shows the cached
    B filter and DPI rather than re-seeding them."""
    from streamlit.testing.v1 import AppTest

    from tests.conftest import APP_SCRIPT

    kept = {
        sk.SINGLE_COMPARE_TOGGLE: True,
        "cmp1_fixclass_short_mode": "Highlight",
        sk.EXPORT_FIGURE_DPI: 600,
    }
    assert persistence.save_state(dict(kept), tmp_path)
    restored: dict = {}
    assert persistence.restore_state(restored, tmp_path)
    at = AppTest.from_file(APP_SCRIPT)
    for key in kept:
        at.session_state[key] = restored[key]
    at.run(timeout=120)
    assert not at.exception, at.exception
    at.run(timeout=120)
    assert at.session_state["cmp1_fixclass_short_mode"] == "Highlight"
    assert at.session_state[sk.EXPORT_FIGURE_DPI] == 600
