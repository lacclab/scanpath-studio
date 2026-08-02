# Test Suite for Scanpath Studio

This directory contains the test suite for the scanpath visualization Streamlit app — 50+ files covering the data pipeline, figure builders, app boot, and the public headless surfaces.

## Running Tests

### Install test dependencies

```bash
# Using conda/mamba (recommended)
conda env create -f environment.yml
conda activate scanpath-studio
# or with mamba (faster)
mamba env create -f environment.yml
mamba activate scanpath-studio

# Using pip (alternative)
pip install -r requirements.txt
# Or install in development mode with test dependencies:
pip install -e ".[test]"
```

### Run all tests

```bash
pytest -n auto
```

`-n auto` (pytest-xdist, a declared test dep) parallelizes the suite — the
`AppTest` integration tests are CPU-bound app boots and dominate the runtime,
so this is a ~3× wall-clock win. CI runs the same way. Plain `pytest` works
too, just slower.

### Run with coverage

```bash
pytest --cov=scanpath_studio --cov-report=html
```

### Run specific tests

```bash
pytest tests/test_measures.py
pytest tests/test_data.py::TestNormalizeWords
pytest tests/test_data.py::TestNormalizeWords::test_normalize_words_with_box_coordinates
```

## Test Structure

Roughly one `test_<module>.py` per `scanpath_studio/` module, plus
cross-cutting files. The load-bearing ones:

- `conftest.py` — shared fixtures: `sample_words_df`, `sample_fixations_df`,
  `sample_raw_gaze_df`, `normalized_words_df`, `normalized_fixations_df`,
  `synthetic_words_df`, `synthetic_fixations_df`.
- `synthetic_data.py` — the hand-traced 6-word / 2-line ground-truth trial
  with exact `EXPECTED` values (shared with `scanpath_studio/synthetic.py`);
  `test_synthetic.py` asserts every measure and geometry helper against it.
  This is the suite's correctness anchor.
- `test_measures.py`, `test_data.py`, `test_plots.py`, `test_aggregation.py`,
  `test_alignment.py`, `test_similarity.py` — the pure computation +
  figure-builder core.
- `test_apptest.py`, `test_apptest_flows.py`, and ~15 more `AppTest`-based
  files — boot the whole app headless via
  `streamlit.testing.v1.AppTest.from_file("streamlit_app.py")` and drive
  widgets. This is the house-preferred way to test app behavior (see
  `CLAUDE.md → Dev loop`); only a handful of older files still mock `st.*`.
- `test_api.py`, `test_cli.py`, `test_cli_drift.py` — the headless API and
  CLI surfaces (the four-surface rule's non-UI half).
- `test_export.py`, `test_export_naming.py`, `test_animation_export.py` —
  bulk export, path patterns, separable layers, GIF/MP4.
- `test_dataset_support.py`, `test_multipleye_enrichment.py`,
  `test_onestop_shard.py` — the public-corpus loaders.
- **Contract tests that gate CI on a rename**:
  `test_session_key_contract.py` pins the share-link / saved-config session
  keys (ENG-6) against a frozen list — a renamed key fails the test instead
  of someone's old link; `test_citation.py` enforces version parity between
  `__init__.py` and `CITATION.cff`.

## Notes

- `pytest.ini` sets `--strict-markers` and `testpaths = tests`;
  `pytest-timeout` (declared test dep) registers the `timeout` marker the
  AppTest files rely on — collection fails without it.
- Prefer `AppTest` over mocking Streamlit for new tests of app behavior.
- The AppTest files are integration-weight; keep pure logic in the
  per-module unit files so the fast core stays fast.
