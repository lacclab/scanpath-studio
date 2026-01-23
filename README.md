# Scanpath Visualization App

Streamlit workbench for exploring reading scanpaths: layered word boxes, fixations, saccades, density heatmaps, comparisons, and word-level measures. Bundled demo data lets users try it instantly.

## Installation

```bash
pip install scanpath-visualization-app
```

Run the app after installation:

```bash
scanpath-visualization
# or
python -m scanpath_visualization_app
```

## Development Setup

Choose your preferred tool:

### Using uv (fastest, recommended)

```bash
# Install dependencies with uv
uv sync

# Run the app
uv run streamlit run scanpath_visualization_app/app.py
# or
uv run python -m scanpath_visualization_app
```

### Using mamba/conda

```bash
# Create and activate environment (mamba is faster)
mamba env create -f environment.yml
mamba activate scanpath-visualization
# or with conda
conda env create -f environment.yml
conda activate scanpath-visualization

# Run the app
streamlit run scanpath_visualization_app/app.py
# or
python -m scanpath_visualization_app
```

### Using pip

```bash
# Install in editable mode with test dependencies
pip install -e ".[test]"

# Run the app
streamlit run scanpath_visualization_app/app.py
# or
python -m scanpath_visualization_app
```

Tested on Python 3.11 through 3.13.

## Data expectations

Upload Feather tables for words/IA and fixations. Columns are auto-detected using common names (participant/trial IDs, IA/word IDs, text labels, bounding boxes, fixation duration/timestamps/x/y). Missing required fields trigger friendly errors; optional fields drive coloring, filters, and tooltips. Sample Feather files ship with the package under `sample_data/`.

## Packaging & release

- Build artifacts: `python -m build` (produces `dist/` wheel + sdist).
- Verify package data: ensure `sample_data/*.csv` appear in the wheel.
- Upload to PyPI/TestPyPI with `twine upload dist/*`.
