"""The *second* dataset a comparison can draw scanpath B from (CMP-8 §2).

Compare mode used to pick B out of the same loaded corpus as A. This module is
what lets it reach a different one — a PoTeC reader beside a OneStop reader, or
the same text read under two corpora.

**The one hard constraint: nothing here may render.** The app's public-corpus
loaders (`app._load_public_dataset`) draw directory inputs, *Expected files*
layouts and ⬇ Download buttons; none of that can appear inside the compare
picker, which is a selectbox in the middle of the plot column. So this module
reads the *location state those loaders already wrote* (`<prefix>_dir`) and goes
straight to the widget-free `datasets.load_*` functions. A corpus whose location
has never been set is offered **disabled** with a reason, never loaded blind.

`app` is imported lazily inside the functions, not at module scope: `app`
imports `tabs`, `tabs` imports this, so a module-level import would close the
cycle (the same reason `wizard.py` is imported lazily by `app`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from .constants import (
    DEMO_CHOICE,
    MULTIPLEYE_DEFAULT_DIR,
    ONESTOP_LACCLAB_DEFAULT_DIR,
    ONESTOP_PUBLIC_CHOICE,
    ONESTOP_PUBLIC_DEFAULT_DIR,
    POTEC_DEFAULT_DIR,
    SYNTHETIC_CHOICE,
)
from .experimental_setup import Provenance, SetupSnapshot
from .session_keys import COMPARE_SOURCE_STATE_KEY

#: The picker's "stay in this dataset" entry — compare mode's behaviour before
#: CMP-8, and still the default.
THIS_DATASET = "This dataset"

#: Session key holding the picked secondary source name. Re-exported from
#: `session_keys` rather than spelled again: it is a deep-link-seeded key, and
#: two literals for one wire-format name is exactly the drift `session_keys.py`
#: exists to prevent.
COMPARE_SOURCE_KEY = COMPARE_SOURCE_STATE_KEY

#: `<key_prefix>_dir` session keys written by `app._dataset_dir_input`, plus the
#: default each loader passes it. Read-only here: this module never writes a
#: location, it only reports whether one is usable.
_MULTIPLEYE_LABEL_HINT = "MultiplEYE"
_POTEC_LABEL_HINT = "PoTeC"


@dataclass(frozen=True, eq=False)
class SecondaryDataset:
    """One loaded comparison source: normalized frames plus what they were shown on.

    ``eq=False`` because the frames make dataclass equality ambiguous (pandas
    raises on a truth-valued comparison), and nothing compares these.
    """

    name: str
    words: pd.DataFrame
    fixations: pd.DataFrame
    combos: pd.DataFrame
    setup: SetupSnapshot
    composite_trial_columns: Tuple[str, ...] = field(default=())


def _resolved_dir(key: str, default_dir: str) -> str:
    """The directory a public-corpus loader would read, without rendering it.

    Mirrors `app._dataset_dir_input`'s return value: the session key the text
    input wrote, else the loader's default, resolved against the project root.
    """
    from scanpath_studio import app

    raw = str(st.session_state.get(key) or "").strip() or default_dir
    if app.data_root() and not app.local_filesystem_enabled():
        # S2: on a shared deployment the path box isn't rendered at all and the
        # location comes from the server's environment — the same rule the
        # loader itself follows.
        return str(app.data_root())
    return app._resolve_data_dir(raw)


def _public_location(label: str) -> Tuple[str, dict]:
    """``(root, loader kwargs)`` for a `PUBLIC_DATASET_REGISTRY` label.

    The kwargs are the *user's current* source options (OneStop's variant /
    regime / parts, MultiplEYE's fixation source) — the same session keys the
    sidebar widgets own, read rather than re-rendered.
    """
    from scanpath_studio import datasets

    if label == ONESTOP_PUBLIC_CHOICE:
        variant = str(st.session_state.get("onestop_variant") or "public")
        default = (
            os.environ.get("ONESTOP_LACCLAB_DIR", "").strip()
            or ONESTOP_LACCLAB_DEFAULT_DIR
            if variant == "lacclab"
            else ONESTOP_PUBLIC_DEFAULT_DIR
        )
        parts = tuple(
            st.session_state.get("onestop_parts") or datasets.ONESTOP_DEFAULT_PARTS
        )
        return _resolved_dir(f"onestop_{variant}_dir", default), {
            "variant": variant,
            "regime": str(st.session_state.get("onestop_regime") or "ordinary"),
            "parts": parts,
        }
    if _POTEC_LABEL_HINT in label:
        return _resolved_dir("potec_dir", POTEC_DEFAULT_DIR), {}
    if _MULTIPLEYE_LABEL_HINT in label:
        return _resolved_dir("multipleye_dir", MULTIPLEYE_DEFAULT_DIR), {
            "fixation_source": str(
                st.session_state.get("multipleye_fixation_source") or "scanpaths"
            ),
        }
    return "", {}


def _public_ready(label: str) -> Tuple[bool, str]:
    """Whether a public corpus can be loaded *silently*, and why not if it can't.

    Uses the existing readiness helpers — `datasets.potec_present` /
    `onestop_present` / `multipleye_inventory` — so a corpus is never offered as
    B unless the very same check the main source picker runs says its files are
    there. A download is deliberately never triggered from here.

    Cached on the resolved location + source options: this runs for *every*
    registry entry on every rerun that Compare is on, and `multipleye_inventory`
    walks each session directory (`app._cached_multipleye_inventory` wraps the
    same call for the same reason). Location changes bust the key.
    """
    root, kwargs = _public_location(label)
    return _public_ready_cached(label, root, tuple(sorted(kwargs.items())))


@st.cache_data(show_spinner=False)
def _public_ready_cached(label: str, root: str, options: tuple) -> Tuple[bool, str]:
    from scanpath_studio import datasets

    kwargs = dict(options)
    short = label.split(" — ")[0]
    if not root:
        return False, f"{short} isn't loadable as a comparison dataset."
    hint = f"Open {short} as the main dataset once to set its location."
    try:
        if label == ONESTOP_PUBLIC_CHOICE:
            present = datasets.onestop_present(
                root,
                regime=kwargs["regime"],
                parts=list(kwargs["parts"]),
                variant=kwargs["variant"],
            )
        elif _POTEC_LABEL_HINT in label:
            present = datasets.potec_present(root)
        elif _MULTIPLEYE_LABEL_HINT in label:
            sessions, _ = datasets.multipleye_inventory(
                root, fixation_source=kwargs["fixation_source"]
            )
            present = bool(sessions)
        else:
            return False, f"{short} isn't loadable as a comparison dataset."
    except (OSError, ValueError):
        present = False
    return (True, "") if present else (False, hint)


def secondary_dataset_options(
    *, exclude: Optional[str] = None
) -> list[tuple[str, bool, str]]:
    """Every source compare mode could draw B from: ``(name, ready, why_not)``.

    Stored uploads, the bundled demo and the synthetic trial are always ready —
    they are in memory or in the package. Public corpora are *always offered* but
    ready only when their files are already where the main picker last looked;
    an unready entry renders disabled with ``why_not`` rather than disappearing,
    so the capability is discoverable instead of mysteriously absent.

    The ``$ONESTOP_DATA_DIR`` **server bundle is deliberately not offered.**
    `data.load_onestop_server_bundle` is sub-second only when it is given a
    participant to load a per-pid shard for; without one it falls back to the
    full CSV exports — its own docstring says ~3 min and ~60 GB for the L2
    cohort. The picker has no participant to give at the moment it builds its
    options, so offering the bundle would mean blocking the whole app for
    minutes, and possibly OOM-ing the server, to draw one comparison trial. The
    same corpus is reachable as the public *OneStop* entry below.

    ``exclude`` drops one name (the active source — comparing a dataset with
    itself is what `THIS_DATASET` already means).
    """
    from scanpath_studio import app

    options: list[tuple[str, bool, str]] = [
        (name, True, "") for name in sorted(st.session_state.get("_datasets") or {})
    ]
    options.append((DEMO_CHOICE, True, ""))
    options.append((SYNTHETIC_CHOICE, True, ""))
    if app.public_datasets_enabled():
        options.extend(
            (label, *_public_ready(label)) for label in app.PUBLIC_DATASET_REGISTRY
        )
    return [option for option in options if option[0] != exclude]


@st.cache_data(show_spinner="Loading comparison dataset…")
def _load_public_frames(
    label: str, root: str, options: tuple
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normalized frames for a public corpus, keyed on its location + options.

    Goes through the `datasets.load_*` entry points (which normalize internally
    via `api.load_scanpath_data`), never `app.prepare_data` — that one takes a
    ``mapping_host`` and renders the column-mapping panels.
    """
    from scanpath_studio import datasets

    kwargs = dict(options)
    if label == ONESTOP_PUBLIC_CHOICE:
        return datasets.load_onestop(
            root,
            regime=kwargs["regime"],
            parts=list(kwargs["parts"]),
            variant=kwargs["variant"],
        )
    if _POTEC_LABEL_HINT in label:
        return datasets.load_potec(root)
    return datasets.load_multipleye(root, fixation_source=kwargs["fixation_source"])


@st.cache_data(show_spinner="Loading comparison dataset…")
def _load_builtin_frames(name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Normalized frames for the bundled demo / synthetic trial.

    Both are small and packaged, so caching the *normalized* result here is the
    whole cost — the raw loaders they call are already cached themselves.
    """
    from scanpath_studio import api
    from scanpath_studio.data import load_sample_data
    from scanpath_studio.synthetic import load_synthetic_data

    raw = load_sample_data() if name == DEMO_CHOICE else load_synthetic_data()
    return api.load_scanpath_data(raw[0], raw[1])


def _snapshot_for(
    name: str, words: pd.DataFrame, fixations: pd.DataFrame
) -> SetupSnapshot:
    """B's own screen — never the live ``global_*`` keys, which describe **A**.

    A stored upload carries the snapshot its wizard captured. Anything else goes
    through the one source→monitor table (`app.resolve_source_monitor`): a corpus
    that declares a presentation monitor reports ``MEASURED``, and a corpus whose
    canvas is inferred from data extents reports ``ESTIMATED``. Physical size,
    viewing distance and typography stay at their defaults, marked ``ASSUMED`` —
    no registry entry records them, and B's panel does not use them.
    """
    from scanpath_studio import app

    stored = (st.session_state.get("_datasets") or {}).get(name)
    if isinstance(stored, dict) and isinstance(stored.get("setup"), dict):
        return SetupSnapshot.from_dict(stored["setup"], fallback=SetupSnapshot())
    width, height, authoritative = app.resolve_source_monitor(name, words, fixations)
    return SetupSnapshot(
        canvas_width=int(width),
        canvas_height=int(height),
        screen_provenance=(
            Provenance.MEASURED if authoritative else Provenance.ESTIMATED
        ),
        geometry_provenance=Provenance.ASSUMED,
        text_provenance=Provenance.ASSUMED,
    )


def load_secondary_dataset(name: Optional[str]) -> Optional[SecondaryDataset]:
    """Load one comparison source by name, or ``None`` when there is nothing to load.

    ``None`` / `THIS_DATASET` / an unready name all return ``None`` — the caller
    then behaves exactly as it did before CMP-8 (B out of A's own pool).
    """
    from scanpath_studio.utils import build_combo_options_for

    if not name or name == THIS_DATASET:
        return None
    stored = (st.session_state.get("_datasets") or {}).get(name)
    if isinstance(stored, dict):
        words, fixations = stored["words"], stored["fixations"]
        composite = tuple(stored.get("composite_trial_columns") or ())
    else:
        from scanpath_studio import app

        if name in app.PUBLIC_DATASET_REGISTRY:
            # Re-check readiness directly rather than rebuilding the whole option
            # list: that would re-sweep *every* corpus' filesystem a second time
            # on the very rerun a cross-dataset pick already costs the most.
            if not _public_ready(name)[0]:
                return None
            root, options = _public_location(name)
            words, fixations = _load_public_frames(
                name, root, tuple(sorted(options.items()))
            )
        elif name in (DEMO_CHOICE, SYNTHETIC_CHOICE):
            words, fixations = _load_builtin_frames(name)
        else:
            return None
        composite = ()
    if fixations is None or fixations.empty:
        return None
    combos, _, _ = build_combo_options_for(fixations, composite)
    return SecondaryDataset(
        name=name,
        words=words,
        fixations=fixations,
        combos=combos,
        setup=_snapshot_for(name, words, fixations),
        composite_trial_columns=composite,
    )
