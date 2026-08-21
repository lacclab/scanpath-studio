"""Streamlit workbench + headless API for scanpath visualization."""

from __future__ import annotations

__all__ = [
    "__version__",
    "alignment_sensitivity",
    "analysis_tables",
    "animate_scanpath",
    "build_authored_scanpath",
    "cache_status",
    "clear_cache",
    "compare_scanpaths",
    "compute_word_metrics",
    "list_parts",
    "list_trials",
    "load_authored_scanpath",
    "load_eyegenbench",
    "load_multipleye",
    "load_onestop",
    "load_participant_metadata",
    "load_potec",
    "load_sample_data",
    "load_scanpath_data",
    "main",
    "plot_corpus_figure",
    "plot_scanpath",
    "preprocess_data",
    "reader_summary",
    "render_parent_trial",
    "save_figure",
    "save_figure_layers",
    "trial_summary",
]
__version__ = "0.29.0"

# Public headless API (see api.py / datasets.py / eyegenbench.py). Resolved lazily so
# `import scanpath_studio` stays cheap and doesn't pull in pandas/plotly/
# streamlit until first use.
_DATASET_EXPORTS = frozenset({"load_potec", "load_multipleye", "load_onestop"})
_EYEGENBENCH_EXPORTS = frozenset({"load_eyegenbench"})
_API_EXPORTS = (
    frozenset(__all__)
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
    """Programmatic entry point — `from scanpath_studio import main`."""
    from .app import main as _main

    _main()
