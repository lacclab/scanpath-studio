"""Streamlit workbench + headless API for scanpath visualization."""

from __future__ import annotations

__all__ = [
    "ScanpathData",
    "__version__",
    "animate_scanpath",
    "build_authored_scanpath",
    "cache_status",
    "check_data_health",
    "clear_cache",
    "compare_scanpaths",
    "figure_code",
    "figure_options",
    "list_parts",
    "list_trials",
    "load_authored_scanpath",
    "load_onestop",
    "load_participant_metadata",
    "load_potec",
    "load_raw_gaze",
    "load_sample_data",
    "load_sample_raw_gaze",
    "load_scanpath_data",
    "load_text_metadata",
    "load_trial_metadata",
    "main",
    "plot_corpus_figure",
    "plot_scanpath",
    "propose_schema",
    "render_parent_trial",
    "save_figure",
    "save_figure_layers",
]
__version__ = "0.36.0"

# Public headless API (see api.py / datasets.py / eyegenbench.py). Resolved lazily so
# `import scanpath_studio` stays cheap and doesn't pull in pandas/plotly/
# streamlit until first use.
# The MultiplEYE and benchmark-corpus loaders stay importable but are left out
# of `__all__`: those corpora are held back from this release
# (`constants.multipleye_enabled` / `benchmark_corpora_enabled`).
# The app's own computed measures are held back the same way
# (`constants.computed_measures_enabled`): importable, but not advertised —
# they raise without SCANPATH_EXPERIMENTAL=1 (#374).
_HELD_BACK_EXPORTS = frozenset(
    {
        "alignment_sensitivity",
        "analysis_tables",
        "compute_word_metrics",
        "preprocess_data",
        "reader_summary",
        "trial_summary",
    }
)
_DATASET_EXPORTS = frozenset({"load_potec", "load_multipleye", "load_onestop"})
_EYEGENBENCH_EXPORTS = frozenset({"load_eyegenbench", "eyegenbench_datasets"})
_API_EXPORTS = (
    (frozenset(__all__) | _HELD_BACK_EXPORTS)
    - {"__version__", "main"}
    - _DATASET_EXPORTS
    - _EYEGENBENCH_EXPORTS
)


def __getattr__(name: str):
    if name in _API_EXPORTS:
        from . import api

        return getattr(api, name)
    if name in _DATASET_EXPORTS:
        from . import datasets

        return getattr(datasets, name)
    if name in _EYEGENBENCH_EXPORTS:
        from . import eyegenbench

        return getattr(eyegenbench, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list:
    return sorted(set(globals()) | set(__all__))


def main() -> None:
    """The app's Streamlit script body. To open the app, run `scanpath-studio`;
    from Python, use the headless API instead."""
    from .app import main as _main

    _main()
