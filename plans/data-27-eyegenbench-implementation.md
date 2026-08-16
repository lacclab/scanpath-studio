# EyeGenBench Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship all 39 EyeGenBench corpora as one built-in Scanpath Studio data source, with per-dataset screen geometry recovered at the best fidelity available.

**Architecture:** An offline prep script runs EyeGenBench's own `prepare_data()` per dataset, then — while the raw downloads are still on disk — resolves screen geometry in three tiers (`real` parsed from the raw files, `reconstructed` from published display parameters, `synthesized` from defaults) and emits an app-native Parquet bundle. The app never imports EyeGenBench; it reads only the bundle, through the same auto-detect → normalize pipeline as an upload.

**Tech Stack:** pandas, pyarrow, Streamlit (app surface only), pytest. The prep script additionally needs EyeGenBench and its torch/lightning/pandera stack, in a **separate venv**.

**Spec:** [`plans/data-27-eyegenbench-datasets.md`](data-27-eyegenbench-datasets.md) — read it before starting. This plan argues from it.

## Global Constraints

- **`scanpath_studio/eyegenbench.py` and `eyegenbench_geometry.py` import no Streamlit** — pandas plus the standard library only, like `datasets.py`. They must work from a plain script.
- **Ruff before every commit**: `ruff check --exclude other_vis .` **and** `ruff format --exclude other_vis .`. CI gates on both. A `.claude/hooks/ruff-on-edit.sh` hook also runs on every edited `.py`.
- **Never add a `Co-Authored-By: Claude` trailer** to commit messages.
- **Python is `.venv/bin/python`** (Streamlit 1.61.1). The `streamlit` on `PATH` is 1.58 and crashes the app — never use it.
- **No corpus data is vendored.** `data/EyeGenBench/` is gitignored. Downloads come from each corpus' own host, via EyeGenBench.
- **Every extra column must be registered** in `data.WORD_OPTIONAL_FIELDS` / `FIX_OPTIONAL_FIELDS` as a 4-tuple `(source_name, canonical_name, kind, category)`. Normalization builds a fresh frame and silently drops anything unregistered — no error.
- **Update `CHANGELOG.md`** in the two-tier shape (headline list + `### Details`) as you go, under `[Unreleased]`.
- **Tracker**: flip DATA-27 to `In progress` and set `"owner"` at Task 1; finish into `Review`, never `Closed`.
- **Provisional defaults, pending the user's call** (recorded in DATA-27's *Waiting on you* box). Each is a single constant, changed in one place:
  - Tier-3 canvas: `1920 × 1080`, monospace, `font_px = 20`. → `eyegenbench_geometry.DEFAULT_SPEC`
  - Dataset picker grouping: by language. → `app._eyegenbench_picker_groups`

## File Structure

| File | Responsibility |
| --- | --- |
| `scanpath_studio/eyegenbench_geometry.py` (create) | `DisplaySpec`, the shared layout engine, the Tier-2 spec table with citations, Tier-1 extractors, and `resolve_geometry` |
| `scanpath_studio/eyegenbench.py` (create) | Bundle → raw `(words, fixations)` frames; schemas; `_present`; `load_*`; manifest access |
| `scripts/prepare_eyegenbench.py` (create) | Offline prep: run EyeGenBench, resolve geometry, emit bundle + manifest |
| `scanpath_studio/constants.py` (modify) | `EYEGENBENCH_DEFAULT_DIR` |
| `scanpath_studio/data.py` (modify) | Register `geometry_source` in both optional-field lists |
| `scanpath_studio/app.py` (modify) | `_load_eyegenbench_source`, registry entry, dataset picker |
| `scanpath_studio/url_state.py` (modify) | `_SHAREABLE_SOURCES` entry + dataset param |
| `scanpath_studio/cli.py` (modify) | `--eyegenbench` / `--eyegenbench-dataset` |
| `scanpath_studio/__init__.py` (modify) | `_DATASET_EXPORTS` + `__all__` |
| `tests/test_eyegenbench_geometry.py` (create) | Layout engine + tier resolution |
| `tests/test_eyegenbench.py` (create) | Loader, presence, failure paths |
| `docs/eyegenbench.md` (create) | Datasets page |

`eyegenbench_geometry.py` is split from `eyegenbench.py` deliberately: geometry is the part with real algorithmic content and the most tests, and it changes for different reasons than the loader.

---

### Task 1: The layout engine (Tier 3)

Pure function, no I/O. Everything downstream builds on it.

**Files:**
- Create: `scanpath_studio/eyegenbench_geometry.py`
- Test: `tests/test_eyegenbench_geometry.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `DisplaySpec` (frozen dataclass: `width_px: int`, `height_px: int`, `font_px: float`, `char_width_px: float`, `line_pitch_px: float`, `monospaced: bool`, `margin_px: int`, `source: str`); `DEFAULT_SPEC: DisplaySpec`; `layout_words(ia_list: list[str], spec: DisplaySpec) -> pd.DataFrame` returning columns `word_id, text, line, start_x, end_x, start_y, end_y`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eyegenbench_geometry.py
import pandas as pd
import pytest

from scanpath_studio.eyegenbench_geometry import DEFAULT_SPEC, DisplaySpec, layout_words

SPEC = DisplaySpec(
    width_px=200,
    height_px=100,
    font_px=10,
    char_width_px=10,
    line_pitch_px=30,
    monospaced=True,
    margin_px=10,
    source="test",
)


def test_layout_places_words_left_to_right_on_one_line():
    words = layout_words(["ab", "cd"], SPEC)
    assert list(words["word_id"]) == [0, 1]
    assert list(words["text"]) == ["ab", "cd"]
    assert list(words["line"]) == [0, 0]
    # margin 10, "ab" = 2 chars * 10px = 20 -> [10, 30); space then "cd".
    assert words.loc[0, "start_x"] == 10
    assert words.loc[0, "end_x"] == 30
    assert words.loc[1, "start_x"] == 40
    assert words.loc[1, "end_x"] == 60


def test_layout_wraps_when_the_line_is_full():
    # usable width = 200 - 2*10 = 180px = 18 chars.
    words = layout_words(["aaaaaaaaaa", "bbbbbbbbbb"], SPEC)
    assert list(words["line"]) == [0, 1]
    assert words.loc[1, "start_x"] == 10
    assert words.loc[1, "start_y"] == words.loc[0, "start_y"] + 30


def test_layout_boxes_never_overlap_and_advance_monotonically():
    words = layout_words(["the", "quick", "brown", "fox", "jumps"], SPEC)
    for line, group in words.groupby("line"):
        assert group["start_x"].is_monotonic_increasing
        assert (group["start_x"].shift(-1).dropna() >= group["end_x"][:-1]).all()


def test_layout_rejects_an_empty_word_list():
    with pytest.raises(ValueError, match="at least one interest area"):
        layout_words([], SPEC)


def test_default_spec_is_a_usable_screen():
    words = layout_words(["hello", "world"], DEFAULT_SPEC)
    assert (words["end_x"] <= DEFAULT_SPEC.width_px).all()
    assert isinstance(words, pd.DataFrame)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scanpath_studio.eyegenbench_geometry'`

- [ ] **Step 3: Write minimal implementation**

```python
# scanpath_studio/eyegenbench_geometry.py
"""Screen geometry for EyeGenBench corpora.

EyeGenBench's harmonised output records *which* interest area each fixation
landed on and *where within it* (a 0-1 offset), but no pixel coordinates and no
word boxes. Scanpath Studio needs boxes. This module recovers them at the best
fidelity available -- see `resolve_geometry` for the three tiers.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DisplaySpec:
    """How one corpus presented its text, in pixels.

    ``source`` cites where the numbers came from (e.g. ``"pymovements:potec"``),
    so a reconstructed layout can always be traced back to its evidence.
    """

    width_px: int
    height_px: int
    font_px: float
    char_width_px: float
    line_pitch_px: float
    monospaced: bool
    margin_px: int
    source: str


# Provisional -- DATA-27 open decision. A synthesized layout needs *some*
# screen; this is the one used when nothing at all is published for a corpus.
DEFAULT_SPEC = DisplaySpec(
    width_px=1920,
    height_px=1080,
    font_px=20,
    char_width_px=12.0,  # Courier-family advance width at 20px.
    line_pitch_px=60.0,  # Double-spaced, the reading-study norm.
    monospaced=True,
    margin_px=100,
    source="default",
)


def layout_words(ia_list: list[str], spec: DisplaySpec) -> pd.DataFrame:
    """Lay ``ia_list`` out as word boxes on ``spec``'s screen.

    Greedy left-to-right wrapping with one space between words. Shared by the
    reconstructed and synthesized tiers -- same code, different ``spec``.
    """
    if not len(ia_list):
        raise ValueError("layout_words needs at least one interest area")

    usable = spec.width_px - 2 * spec.margin_px
    space = spec.char_width_px
    rows = []
    x, line = spec.margin_px, 0
    for word_id, text in enumerate(ia_list):
        width = max(len(str(text)), 1) * spec.char_width_px
        if x > spec.margin_px and (x + width) > (spec.margin_px + usable):
            x, line = spec.margin_px, line + 1
        top = spec.margin_px + line * spec.line_pitch_px
        rows.append(
            {
                "word_id": word_id,
                "text": str(text),
                "line": line,
                "start_x": x,
                "end_x": x + width,
                "start_y": top,
                "end_y": top + spec.font_px,
            }
        )
        x += width + space
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Claim the tracker item, then commit**

In `tracker/data.js`, set DATA-27's `"status"` to `"In progress"` and `"owner"` to one of the names in `TRACKER.people` (`Maya` or `Shubi`).

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench_geometry.py tests/test_eyegenbench_geometry.py tracker/data.js
git commit -m "DATA-27: EyeGenBench text layout engine"
```

---

### Task 2: The published display-parameter table (Tier 2)

**Files:**
- Modify: `scanpath_studio/eyegenbench_geometry.py`
- Test: `tests/test_eyegenbench_geometry.py`

**Interfaces:**
- Consumes: `DisplaySpec`, `DEFAULT_SPEC` (Task 1).
- Produces: `DISPLAY_SPECS: dict[str, DisplaySpec]` keyed by lowercase EyeGenBench dataset name; `display_spec_for(dataset: str) -> DisplaySpec` (falls back to `DEFAULT_SPEC`).

The numbers come from the spec's research section. `char_width_px` for a monospaced font is derived from characters-per-degree where reported, else from `font_px * 0.6` (the Courier/Consolas advance ratio). `line_pitch_px = font_px * 2` for a corpus documented as double-spaced, else `font_px * 1.5`.

- [ ] **Step 1: Write the failing test**

```python
from scanpath_studio.eyegenbench_geometry import (
    DEFAULT_SPEC,
    DISPLAY_SPECS,
    display_spec_for,
)


def test_known_corpus_uses_its_published_screen():
    spec = display_spec_for("potec")
    assert (spec.width_px, spec.height_px) == (1680, 1050)
    assert spec.source.startswith("pymovements")


def test_copco_uses_its_paper_reported_font():
    spec = display_spec_for("copco")
    assert (spec.width_px, spec.height_px) == (1920, 1080)
    assert spec.monospaced is True
    # Courier 14, double-spaced (Hollenstein et al. 2022).
    assert spec.line_pitch_px == spec.font_px * 2
    assert "copco" in spec.source or "paper" in spec.source


def test_unknown_corpus_falls_back_to_the_default_screen():
    assert display_spec_for("no-such-corpus") is DEFAULT_SPEC


def test_lookup_is_case_insensitive():
    assert display_spec_for("PoTeC") == display_spec_for("potec")


def test_every_spec_cites_a_source_and_is_physically_sane():
    for name, spec in DISPLAY_SPECS.items():
        assert spec.source, f"{name} has no citation"
        assert spec.width_px > 0 and spec.height_px > 0, name
        assert spec.char_width_px > 0 and spec.line_pitch_px >= spec.font_px, name
        assert 2 * spec.margin_px < spec.width_px, name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -k spec -v`
Expected: FAIL — `ImportError: cannot import name 'DISPLAY_SPECS'`

- [ ] **Step 3: Write minimal implementation**

Append to `eyegenbench_geometry.py`. Cite every entry; the citation is the point.

```python
def _spec(
    width_px,
    height_px,
    font_px,
    *,
    source,
    mono=True,
    chars_per_deg=None,
    double_spaced=False,
    distance_cm=None,
    width_cm=None,
    margin_px=100,
):
    """Build a DisplaySpec from what a corpus actually reported.

    ``chars_per_deg`` + ``distance_cm`` + ``width_cm`` gives a measured
    character width; otherwise fall back to the monospace advance ratio.
    """
    if chars_per_deg and distance_cm and width_cm:
        px_per_cm = width_px / width_cm
        cm_per_deg = 2 * distance_cm * 0.00872686779  # tan(0.5 deg)
        char_width = (cm_per_deg * px_per_cm) / chars_per_deg
    else:
        char_width = font_px * 0.6
    return DisplaySpec(
        width_px=width_px,
        height_px=height_px,
        font_px=font_px,
        char_width_px=char_width,
        line_pitch_px=font_px * (2.0 if double_spaced else 1.5),
        monospaced=mono,
        margin_px=margin_px,
        source=source,
    )


# Published display parameters, best source first: pymovements dataset YAMLs ->
# the UZH dataset review table -> the corpus' own paper. Anything not listed
# here falls back to DEFAULT_SPEC and is stamped `synthesized`.
DISPLAY_SPECS: dict[str, DisplaySpec] = {
    "potec": _spec(
        1680, 1050, 20, source="pymovements:potec", width_cm=47.5, distance_cm=65
    ),
    "copco": _spec(
        1920,
        1080,
        14,
        source="pymovements:copco + paper:Hollenstein2022",
        double_spaced=True,
        width_cm=59.0,
        distance_cm=85,
    ),
    "emtec": _spec(
        1280,
        1024,
        14,
        source="pymovements:emtec + uzh",
        chars_per_deg=2.86,
        width_cm=38.2,
        distance_cm=60,
    ),
    "colagaze": _spec(
        1280,
        1024,
        17,
        source="pymovements:colagaze + uzh",
        chars_per_deg=2.0,
        width_cm=54.37,
        distance_cm=60,
    ),
    "interead": _spec(
        1920,
        1080,
        16,
        source="pymovements:interead + uzh",
        width_cm=52.8,
        distance_cm=57,
    ),
    "ggtg": _spec(
        1100,
        900,
        20,
        source="pymovements:ggtg + uzh",
        mono=False,
        double_spaced=True,
        width_cm=31.2,
        distance_cm=66,
    ),
    "etdd70": _spec(
        1680, 1050, 20, source="pymovements:etdd70 + uzh", mono=False, distance_cm=65
    ),
    "gaze4hate": _spec(
        2560, 1440, 20, source="pymovements:gaze4hate", width_cm=59.8, distance_cm=78.0
    ),
    "raccoons": _spec(
        1920, 1080, 20, source="pymovements:raccoons", width_cm=56.8, distance_cm=105.5
    ),
    "sbsat": _spec(
        1024, 768, 20, source="pymovements:sb_sat", width_cm=44.5, distance_cm=70
    ),
    "provo": _spec(
        1600,
        900,
        20,
        source="paper:LukeChristianson2018",
        chars_per_deg=3.0,
        width_cm=40.0,
        distance_cm=60,
    ),
    "psr": _spec(
        1024, 768, 18, source="uzh", chars_per_deg=2.38, distance_cm=73, width_cm=47.0
    ),
    "eyevoicespan": _spec(
        1280, 960, 24, source="uzh", chars_per_deg=2.22, distance_cm=60, width_cm=40.0
    ),
    "iitbhgc": _spec(1920, 1080, 20, source="uzh", mono=False, distance_cm=70),
    "bsc": _spec(
        1024, 768, 20, source="uzh", chars_per_deg=0.75, distance_cm=43, width_cm=36.0
    ),
    "chinesereading": _spec(1024, 768, 20, source="uzh", distance_cm=58),
    "cuentos": _spec(1920, 1080, 24, source="uzh", distance_cm=55),
    "zuco1": _spec(1920, 1080, 20, source="paper:Hollenstein2018", mono=False),
    "zuco2": _spec(1920, 1080, 20, source="paper:Hollenstein2020", mono=False),
    "mecol2w2": _spec(1920, 1080, 21, source="uzh + paper:MECO-L2-W2"),
}


def display_spec_for(dataset: str) -> DisplaySpec:
    """The published screen for ``dataset``, or ``DEFAULT_SPEC`` if none is known."""
    return DISPLAY_SPECS.get(str(dataset).lower(), DEFAULT_SPEC)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench_geometry.py tests/test_eyegenbench_geometry.py
git commit -m "DATA-27: published display parameters for 20 EyeGenBench corpora"
```

---

### Task 3: The generic EyeLink box extractor (Tier 1)

**Files:**
- Modify: `scanpath_studio/eyegenbench_geometry.py`
- Test: `tests/test_eyegenbench_geometry.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `parse_ia_data(series: pd.Series) -> pd.DataFrame` (columns `start_x, start_y, end_x, end_y`); `extract_eyelink_boxes(frame, *, paragraph_col="unique_paragraph_id", ia_col="ia_index", data_col="CURRENT_FIX_INTEREST_AREA_DATA") -> pd.DataFrame` (columns `unique_paragraph_id, ia_index, start_x, start_y, end_x, end_y`, one row per interest area).

`CURRENT_FIX_INTEREST_AREA_DATA` is EyeLink's `[STATIC, RECTANGLE, left, top, right, bottom]` — the word's real on-screen box. Because it rides on *fixations*, it only covers interest areas that were fixated; unfixated ones are filled in Task 4.

- [ ] **Step 1: Write the failing test**

```python
import numpy as np

from scanpath_studio.eyegenbench_geometry import extract_eyelink_boxes, parse_ia_data


def test_parse_ia_data_reads_the_eyelink_rectangle():
    boxes = parse_ia_data(pd.Series(["[STATIC, RECTANGLE, 10, 20, 60, 40]"]))
    assert boxes.loc[0, "start_x"] == 10
    assert boxes.loc[0, "start_y"] == 20
    assert boxes.loc[0, "end_x"] == 60
    assert boxes.loc[0, "end_y"] == 40


def test_parse_ia_data_yields_nan_for_unparseable_rows():
    boxes = parse_ia_data(pd.Series([".", "", None]))
    assert boxes["start_x"].isna().all()


def test_extract_dedupes_repeat_fixations_on_one_interest_area():
    frame = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1", "p1"],
            "ia_index": [0, 0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    boxes = extract_eyelink_boxes(frame)
    assert len(boxes) == 2
    assert list(boxes["ia_index"]) == [0, 1]
    assert boxes.loc[boxes["ia_index"] == 1, "start_x"].item() == 70


def test_extract_returns_empty_when_the_column_is_absent():
    frame = pd.DataFrame({"unique_paragraph_id": ["p1"], "ia_index": [0]})
    assert extract_eyelink_boxes(frame).empty
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -k eyelink -v`
Expected: FAIL — `ImportError: cannot import name 'extract_eyelink_boxes'`

- [ ] **Step 3: Write minimal implementation**

```python
IA_DATA_COLUMN = "CURRENT_FIX_INTEREST_AREA_DATA"
_BOX_COLUMNS = ["start_x", "start_y", "end_x", "end_y"]


def parse_ia_data(series: pd.Series) -> pd.DataFrame:
    """EyeLink ``[STATIC, RECTANGLE, left, top, right, bottom]`` -> box columns.

    This is the corpus' *real* on-screen word box. EyeGenBench reads it, divides
    it into a normalised landing position, and discards it; we keep it.
    """
    parts = series.astype(str).str.strip("[]").str.split(",", expand=True)
    if parts.shape[1] < 6:
        return pd.DataFrame(
            {c: [float("nan")] * len(series) for c in _BOX_COLUMNS}, index=series.index
        )
    out = pd.DataFrame(index=series.index)
    for name, idx in zip(_BOX_COLUMNS, (2, 3, 4, 5)):
        out[name] = pd.to_numeric(parts[idx].str.strip(), errors="coerce")
    return out


def extract_eyelink_boxes(
    frame: pd.DataFrame,
    *,
    paragraph_col: str = "unique_paragraph_id",
    ia_col: str = "ia_index",
    data_col: str = IA_DATA_COLUMN,
) -> pd.DataFrame:
    """One real box per ``(paragraph, interest area)`` found in ``frame``.

    Only interest areas that were *fixated* appear -- the column rides on
    fixations. `fill_missing_boxes` completes the rest.
    """
    if data_col not in frame.columns:
        return pd.DataFrame(columns=[paragraph_col, ia_col, *_BOX_COLUMNS])
    boxes = pd.concat(
        [
            frame[[paragraph_col, ia_col]].reset_index(drop=True),
            parse_ia_data(frame[data_col]).reset_index(drop=True),
        ],
        axis=1,
    )
    boxes = boxes.dropna(subset=_BOX_COLUMNS)
    boxes = boxes.drop_duplicates(subset=[paragraph_col, ia_col], keep="first")
    return boxes.sort_values([paragraph_col, ia_col]).reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench_geometry.py tests/test_eyegenbench_geometry.py
git commit -m "DATA-27: parse real word boxes out of EyeLink IA data"
```

---

### Task 4: Fill unfixated interest areas

**Files:**
- Modify: `scanpath_studio/eyegenbench_geometry.py`
- Test: `tests/test_eyegenbench_geometry.py`

**Interfaces:**
- Consumes: `_BOX_COLUMNS` (Task 3).
- Produces: `fill_missing_boxes(boxes: pd.DataFrame, ia_counts: dict[str, int], spec: DisplaySpec) -> tuple[pd.DataFrame, float]` — returns the completed box table plus the fraction of boxes that were interpolated rather than real.

A word nobody fixated has no box. Interpolate it on its neighbours' line: same `start_y`/`end_y` as the preceding real box, `start_x` continuing after it at the spec's character width. The returned fraction is what the manifest reports, because interpolation is a weaker claim than a real box.

- [ ] **Step 1: Write the failing test**

```python
from scanpath_studio.eyegenbench_geometry import fill_missing_boxes


def _boxes(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "unique_paragraph_id",
            "ia_index",
            "start_x",
            "start_y",
            "end_x",
            "end_y",
        ],
    )


def test_fill_inserts_the_gap_between_two_real_boxes():
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 2, 130, 20, 180, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 3}, SPEC)
    assert list(filled["ia_index"]) == [0, 1, 2]
    gap = filled[filled["ia_index"] == 1].iloc[0]
    assert gap["start_x"] >= 60 and gap["end_x"] <= 130
    assert gap["start_y"] == 20 and gap["end_y"] == 40
    assert interpolated == pytest.approx(1 / 3)


def test_fill_is_a_no_op_when_every_area_is_real():
    boxes = _boxes([["p1", 0, 10, 20, 60, 40], ["p1", 1, 70, 20, 120, 40]])
    filled, interpolated = fill_missing_boxes(boxes, {"p1": 2}, SPEC)
    assert len(filled) == 2
    assert interpolated == 0.0


def test_fill_handles_a_leading_gap_before_any_real_box():
    boxes = _boxes([["p1", 1, 70, 20, 120, 40]])
    filled, _ = fill_missing_boxes(boxes, {"p1": 2}, SPEC)
    first = filled[filled["ia_index"] == 0].iloc[0]
    assert first["end_x"] <= 70
    assert first["start_y"] == 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -k fill -v`
Expected: FAIL — `ImportError: cannot import name 'fill_missing_boxes'`

- [ ] **Step 3: Write minimal implementation**

```python
def fill_missing_boxes(
    boxes: pd.DataFrame, ia_counts: dict[str, int], spec: DisplaySpec
) -> tuple[pd.DataFrame, float]:
    """Complete ``boxes`` so every interest area of every paragraph has one.

    Real boxes only cover *fixated* areas. A skipped word is placed on its
    left neighbour's line, one character-width along; a leading gap is placed
    back from its right neighbour. Returns ``(filled, interpolated_fraction)``
    so the manifest can report how much of the geometry is inferred.
    """
    width = spec.char_width_px * 4
    out, n_filled, n_total = [], 0, 0
    for paragraph, count in ia_counts.items():
        present = boxes[boxes["unique_paragraph_id"] == paragraph]
        by_index = {int(r.ia_index): r for r in present.itertuples()}
        n_total += count
        last = None
        for ia_index in range(count):
            row = by_index.get(ia_index)
            if row is not None:
                last = row
                out.append(
                    {
                        "unique_paragraph_id": paragraph,
                        "ia_index": ia_index,
                        "start_x": row.start_x,
                        "start_y": row.start_y,
                        "end_x": row.end_x,
                        "end_y": row.end_y,
                    }
                )
                continue
            n_filled += 1
            if last is not None:
                start_x = last.end_x + spec.char_width_px
                start_y, end_y = last.start_y, last.end_y
            else:
                nxt = next(
                    (by_index[i] for i in range(ia_index + 1, count) if i in by_index),
                    None,
                )
                if nxt is None:
                    start_x, start_y, end_y = (
                        spec.margin_px,
                        spec.margin_px,
                        spec.margin_px + spec.font_px,
                    )
                else:
                    start_x = max(
                        spec.margin_px, nxt.start_x - width - spec.char_width_px
                    )
                    start_y, end_y = nxt.start_y, nxt.end_y
            out.append(
                {
                    "unique_paragraph_id": paragraph,
                    "ia_index": ia_index,
                    "start_x": start_x,
                    "start_y": start_y,
                    "end_x": start_x + width,
                    "end_y": end_y,
                }
            )
    fraction = (n_filled / n_total) if n_total else 0.0
    return pd.DataFrame(out), fraction
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench_geometry.py tests/test_eyegenbench_geometry.py
git commit -m "DATA-27: interpolate boxes for unfixated interest areas"
```

---

### Task 5: Tier resolution and fixation placement

**Files:**
- Modify: `scanpath_studio/eyegenbench_geometry.py`
- Test: `tests/test_eyegenbench_geometry.py`

**Interfaces:**
- Consumes: `display_spec_for`, `layout_words`, `extract_eyelink_boxes`, `fill_missing_boxes`.
- Produces: constants `GEOMETRY_REAL = "real"`, `GEOMETRY_RECONSTRUCTED = "reconstructed"`, `GEOMETRY_SYNTHESIZED = "synthesized"`; `resolve_geometry(dataset: str, text_df: pd.DataFrame, raw_fix_df: pd.DataFrame | None) -> tuple[pd.DataFrame, dict]` returning the word table (`unique_paragraph_id, ia_index, ia_label, line, start_x, start_y, end_x, end_y, geometry_source`) and a report dict (`geometry_source`, `interpolated_fraction`, `display_source`); `place_fixations(fix_df, words) -> pd.DataFrame` adding `x`, `y`.

`place_fixations` inverts EyeGenBench's own formula — `x = left + fix_landing_position * width` — so the round trip is lossless wherever the box is real.

- [ ] **Step 1: Write the failing test**

```python
from scanpath_studio.eyegenbench_geometry import (
    GEOMETRY_REAL,
    GEOMETRY_RECONSTRUCTED,
    GEOMETRY_SYNTHESIZED,
    place_fixations,
    resolve_geometry,
)

TEXTS = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1"],
        "text": ["ab cd"],
        "text_language": ["en"],
        "ia_list": [["ab", "cd"]],
    }
)


def test_real_geometry_wins_when_ia_data_is_present():
    raw = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "CURRENT_FIX_INTEREST_AREA_DATA": [
                "[STATIC, RECTANGLE, 10, 20, 60, 40]",
                "[STATIC, RECTANGLE, 70, 20, 120, 40]",
            ],
        }
    )
    words, report = resolve_geometry("onestop", TEXTS, raw)
    assert report["geometry_source"] == GEOMETRY_REAL
    assert report["interpolated_fraction"] == 0.0
    assert words.loc[words["ia_index"] == 0, "start_x"].item() == 10
    assert (words["geometry_source"] == GEOMETRY_REAL).all()


def test_reconstructed_when_no_raw_boxes_but_a_published_screen():
    words, report = resolve_geometry("potec", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_RECONSTRUCTED
    assert report["display_source"].startswith("pymovements")
    assert len(words) == 2


def test_synthesized_when_nothing_is_known():
    words, report = resolve_geometry("cfiltsarcasm", TEXTS, None)
    assert report["geometry_source"] == GEOMETRY_SYNTHESIZED
    assert (words["geometry_source"] == GEOMETRY_SYNTHESIZED).all()


def test_words_carry_their_interest_area_labels():
    words, _ = resolve_geometry("potec", TEXTS, None)
    assert list(words["ia_label"]) == ["ab", "cd"]


def test_place_fixations_inverts_the_landing_position_formula():
    words = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "start_x": [10.0],
            "end_x": [60.0],
            "start_y": [20.0],
            "end_y": [40.0],
        }
    )
    fix = pd.DataFrame(
        {"unique_paragraph_id": ["p1"], "ia_index": [0], "fix_landing_position": [0.5]}
    )
    placed = place_fixations(fix, words)
    assert placed.loc[0, "x"] == 35.0  # 10 + 0.5 * 50
    assert placed.loc[0, "y"] == 30.0  # box vertical centre
    # Round-trip invariant: recovering the landing position reproduces the input.
    recovered = (placed.loc[0, "x"] - 10.0) / 50.0
    assert recovered == pytest.approx(0.5)


def test_place_fixations_drops_rows_with_no_matching_box():
    words = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1"],
            "ia_index": [0],
            "start_x": [10.0],
            "end_x": [60.0],
            "start_y": [20.0],
            "end_y": [40.0],
        }
    )
    fix = pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p9"],
            "ia_index": [0, 3],
            "fix_landing_position": [0.5, 0.5],
        }
    )
    assert len(place_fixations(fix, words)) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -k "resolve or place" -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_geometry'`

- [ ] **Step 3: Write minimal implementation**

```python
GEOMETRY_REAL = "real"
GEOMETRY_RECONSTRUCTED = "reconstructed"
GEOMETRY_SYNTHESIZED = "synthesized"


def resolve_geometry(
    dataset: str, text_df: pd.DataFrame, raw_fix_df: pd.DataFrame | None
) -> tuple[pd.DataFrame, dict]:
    """Word boxes for ``dataset``, at the best fidelity available.

    Three tiers, first hit wins: real boxes parsed out of the raw files
    EyeGenBench downloaded; a layout reconstructed from the corpus' published
    display parameters; a synthesized layout on default defaults. The chosen
    tier is stamped on every row and returned in the report.
    """
    spec = display_spec_for(dataset)
    ia_lists = dict(zip(text_df["unique_paragraph_id"], text_df["ia_list"]))
    ia_counts = {pid: len(ia) for pid, ia in ia_lists.items()}

    boxes = (
        extract_eyelink_boxes(raw_fix_df) if raw_fix_df is not None else pd.DataFrame()
    )
    if not boxes.empty:
        words, interpolated = fill_missing_boxes(boxes, ia_counts, spec)
        source, interpolated_fraction = GEOMETRY_REAL, interpolated
        words["line"] = words.groupby("unique_paragraph_id")["start_y"].transform(
            lambda s: s.rank(method="dense").astype(int) - 1
        )
    else:
        source = (
            GEOMETRY_RECONSTRUCTED if spec is not DEFAULT_SPEC else GEOMETRY_SYNTHESIZED
        )
        interpolated_fraction = 0.0
        frames = []
        for paragraph, ia_list in ia_lists.items():
            laid = layout_words(list(ia_list), spec)
            laid["unique_paragraph_id"] = paragraph
            laid = laid.rename(columns={"word_id": "ia_index"})
            frames.append(laid.drop(columns=["text"]))
        words = pd.concat(frames, ignore_index=True)

    labels = [
        {"unique_paragraph_id": pid, "ia_index": i, "ia_label": str(label)}
        for pid, ia_list in ia_lists.items()
        for i, label in enumerate(ia_list)
    ]
    words = words.merge(
        pd.DataFrame(labels), on=["unique_paragraph_id", "ia_index"], how="left"
    )
    words["geometry_source"] = source
    report = {
        "geometry_source": source,
        "interpolated_fraction": round(float(interpolated_fraction), 4),
        "display_source": spec.source,
    }
    return words, report


def place_fixations(fix_df: pd.DataFrame, words: pd.DataFrame) -> pd.DataFrame:
    """Add ``x``/``y`` to fixations from their interest area's box.

    Exactly inverts EyeGenBench's landing-position formula
    (``(fix_x - left) / (right - left)``), so wherever the box is real the
    round trip is lossless. Fixations with no matching box are dropped -- they
    cannot be placed, and a wrong placement is worse than a missing one.
    """
    cols = ["unique_paragraph_id", "ia_index", "start_x", "end_x", "start_y", "end_y"]
    merged = fix_df.merge(
        words[cols], on=["unique_paragraph_id", "ia_index"], how="inner"
    )
    landing = (
        pd.to_numeric(merged.get("fix_landing_position", 0.5), errors="coerce")
        .fillna(0.5)
        .clip(0.0, 1.0)
    )
    merged["x"] = merged["start_x"] + landing * (merged["end_x"] - merged["start_x"])
    merged["y"] = (merged["start_y"] + merged["end_y"]) / 2.0
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench_geometry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench_geometry.py tests/test_eyegenbench_geometry.py
git commit -m "DATA-27: three-tier geometry resolution and fixation placement"
```

---

### Task 6: The bundle loader

**Files:**
- Create: `scanpath_studio/eyegenbench.py`
- Create: `tests/test_eyegenbench.py`
- Modify: `scanpath_studio/constants.py` (add `EYEGENBENCH_DEFAULT_DIR`)

**Interfaces:**
- Consumes: nothing from `eyegenbench_geometry` at runtime (the bundle is already built).
- Produces: `EYEGENBENCH_WORD_SCHEMA`, `EYEGENBENCH_FIX_SCHEMA`; `eyegenbench_manifest(root) -> dict`; `eyegenbench_datasets(root) -> list[dict]`; `eyegenbench_present(root, dataset=None) -> bool`; `eyegenbench_monitor(root, dataset) -> tuple[int, int] | None` (Task 11R/I3: `None` when the manifest records only `monitor_source: "default"`, the pipeline's invented screen — the shared rule is `declared_monitor(entry)`, which the app's registry entry and `cli render --eyegenbench` both read); `eyegenbench_raw_frames(root, *, dataset) -> tuple[pd.DataFrame, pd.DataFrame]`; `load_eyegenbench(root, *, dataset) -> tuple[pd.DataFrame, pd.DataFrame]`; `load_eyegenbench_participants(root, dataset) -> pd.DataFrame`.

Word tables are **stimulus-level** (`participant=None`), which `data.broadcast_stimulus_words` expands across readers — exactly as PoTeC's word AOIs work.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eyegenbench.py
import json

import pandas as pd
import pytest

from scanpath_studio import data, eyegenbench


@pytest.fixture
def bundle(tmp_path):
    """A minimal two-word, two-fixation EyeGenBench bundle."""
    root = tmp_path / "EyeGenBench"
    ds = root / "PoTeC"
    ds.mkdir(parents=True)
    pd.DataFrame(
        {
            "unique_paragraph_id": ["p1", "p1"],
            "ia_index": [0, 1],
            "ia_label": ["ab", "cd"],
            "line": [0, 0],
            "start_x": [10.0, 70.0],
            "end_x": [60.0, 120.0],
            "start_y": [20.0, 20.0],
            "end_y": [40.0, 40.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "words.parquet")
    pd.DataFrame(
        {
            "unique_trial_id": ["t1", "t1"],
            "unique_participant_id": ["r1", "r1"],
            "unique_paragraph_id": ["p1", "p1"],
            "fix_index": [0, 1],
            "ia_index": [0, 1],
            "fix_duration": [200, 180],
            "x": [35.0, 95.0],
            "y": [30.0, 30.0],
            "geometry_source": ["real", "real"],
        }
    ).to_parquet(ds / "fixations.parquet")
    pd.DataFrame(
        {"unique_participant_id": ["r1"], "participant_language": ["de"]}
    ).to_parquet(ds / "participants.parquet")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "datasets": [
                    {
                        "name": "PoTeC",
                        "language": "German",
                        "geometry_source": "real",
                        "monitor": [1680, 1050],
                        "n_readers": 1,
                        "n_texts": 1,
                        "n_fixations": 2,
                        "interpolated_fraction": 0.0,
                        "display_source": "pymovements:potec",
                    }
                ]
            }
        )
    )
    return root


def test_present_is_true_for_a_complete_bundle(bundle):
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is True


def test_present_is_false_when_a_parquet_is_missing(bundle):
    (bundle / "PoTeC" / "fixations.parquet").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_present_is_false_without_a_manifest(bundle):
    (bundle / "manifest.json").unlink()
    assert eyegenbench.eyegenbench_present(bundle, "PoTeC") is False


def test_datasets_lists_the_manifest_entries(bundle):
    names = [d["name"] for d in eyegenbench.eyegenbench_datasets(bundle)]
    assert names == ["PoTeC"]


def test_monitor_comes_from_the_manifest(bundle):
    assert eyegenbench.eyegenbench_monitor(bundle, "PoTeC") == (1680, 1050)


def test_raw_frames_returns_both_tables(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert list(words["ia_label"]) == ["ab", "cd"]
    assert len(fixations) == 2


def test_auto_detection_agrees_with_our_schemas(bundle):
    words, fixations = eyegenbench.eyegenbench_raw_frames(bundle, dataset="PoTeC")
    assert data.validate_word_schema(data.propose_word_schema(words)) == []
    assert data.validate_fix_schema(data.propose_fix_schema(fixations)) == []


def test_load_normalizes_and_broadcasts_to_the_reader(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["participant_id"]) == {"r1"}
    assert set(["x", "y", "width", "height"]) <= set(words.columns)
    assert fixations.loc[0, "duration_ms"] == 200


def test_geometry_source_survives_normalization(bundle):
    words, fixations = eyegenbench.load_eyegenbench(bundle, dataset="PoTeC")
    assert set(words["geometry_source"]) == {"real"}
    assert set(fixations["geometry_source"]) == {"real"}


def test_unknown_dataset_raises_value_error(bundle):
    with pytest.raises(ValueError, match="not in the bundle"):
        eyegenbench.eyegenbench_raw_frames(bundle, dataset="NoSuchCorpus")


def test_missing_bundle_says_what_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="prepare_eyegenbench.py"):
        eyegenbench.eyegenbench_raw_frames(tmp_path, dataset="PoTeC")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: FAIL — `ImportError: cannot import name 'eyegenbench'`

- [ ] **Step 3: Write minimal implementation**

Add to `constants.py`, next to `POTEC_DEFAULT_DIR` (line 413):

```python
EYEGENBENCH_DEFAULT_DIR = "data/EyeGenBench"
```

```python
# scanpath_studio/eyegenbench.py
"""Loader for EyeGenBench bundles -- 39 harmonised reading corpora.

EyeGenBench (https://github.com/EyeBench/EyeGenBench) harmonises many public
eye-tracking-while-reading corpora into one schema, but discards screen
geometry. `scripts/prepare_eyegenbench.py` runs their pipeline, recovers the
geometry, and writes the bundle this module reads. See
`docs/eyegenbench.md` and `plans/data-27-eyegenbench-datasets.md`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

MANIFEST_NAME = "manifest.json"
_TABLES = ("words", "fixations", "participants")

# Stimulus-level: `participant=None` marks one shared layout rather than one row
# per reader, so `data.broadcast_stimulus_words` expands it (as for PoTeC).
EYEGENBENCH_WORD_SCHEMA = dict(
    participant=None,
    trial="unique_paragraph_id",
    word_id="ia_index",
    text="ia_label",
    line="line",
    left="start_x",
    right="end_x",
    top="start_y",
    bottom="end_y",
)

EYEGENBENCH_FIX_SCHEMA = dict(
    participant="unique_participant_id",
    trial="unique_trial_id",
    duration="fix_duration",
    x="x",
    y="y",
    fixation_id="fix_index",
    word_id="ia_index",
)


def _manifest_path(root) -> Path:
    return Path(root) / MANIFEST_NAME


def eyegenbench_manifest(root) -> dict:
    """The bundle manifest, or a `FileNotFoundError` naming the fix."""
    path = _manifest_path(root)
    if not path.is_file():
        raise FileNotFoundError(
            f"No EyeGenBench bundle at {root!s} (missing {MANIFEST_NAME}). "
            "Build one with: python scripts/prepare_eyegenbench.py --all"
        )
    return json.loads(path.read_text())


def eyegenbench_datasets(root) -> list:
    """Manifest entries, one per prepared dataset. Cheap -- no Parquet is read."""
    return list(eyegenbench_manifest(root).get("datasets", []))


def eyegenbench_present(root, dataset: Optional[str] = None) -> bool:
    """True when the bundle holds everything a load needs. Path stats only.

    Strict on purpose: a lenient check passes a partial tree and then crashes
    mid-load, whereas a strict one lets the app offer the fix.
    """
    root = Path(root)
    if not _manifest_path(root).is_file():
        return False
    try:
        entries = eyegenbench_datasets(root)
    except (OSError, ValueError):
        return False
    names = [e["name"] for e in entries] if dataset is None else [dataset]
    if not names:
        return False
    return all(
        all((root / name / f"{table}.parquet").is_file() for table in _TABLES)
        for name in names
    )


def declared_monitor(entry) -> Optional[Tuple[int, int]]:
    """The row's screen when the corpus documents one; `None` otherwise.

    Task 11R/I3: `monitor_source: "default"` is the pipeline's invented
    1920x1080 for a corpus that documents no screen, and neither surface may
    snap a canvas to it. One rule, read by the app's registry entry and by the
    CLI, or the same corpus renders at two different scales.
    """
    monitor = entry.get("monitor")
    if not monitor or entry.get("monitor_source") == "default":
        return None
    return int(monitor[0]), int(monitor[1])


def eyegenbench_monitor(root, dataset: str) -> Optional[Tuple[int, int]]:
    """The corpus' documented screen in pixels, or `None`."""
    entry = _find_entry(root, dataset)
    if entry is None:
        raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")
    return declared_monitor(entry)


def _dataset_dir(root, dataset: str) -> Path:
    root = Path(root)
    eyegenbench_manifest(root)  # raises FileNotFoundError with the fix
    for entry in eyegenbench_datasets(root):
        if entry["name"].lower() == str(dataset).lower():
            return root / entry["name"]
    raise ValueError(f"{dataset!r} is not in the bundle at {root!s}")


def eyegenbench_raw_frames(root, *, dataset: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Raw (pre-normalization) ``(words, fixations)`` frames for ``dataset``."""
    directory = _dataset_dir(root, dataset)
    return (
        pd.read_parquet(directory / "words.parquet"),
        pd.read_parquet(directory / "fixations.parquet"),
    )


def load_eyegenbench(root, *, dataset: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load an EyeGenBench corpus as normalized ``(words, fixations)``."""
    from .api import load_scanpath_data

    words, fixations = eyegenbench_raw_frames(root, dataset=dataset)
    return load_scanpath_data(
        words,
        fixations,
        word_schema=EYEGENBENCH_WORD_SCHEMA,
        fix_schema=EYEGENBENCH_FIX_SCHEMA,
    )


def load_eyegenbench_participants(root, dataset: str) -> pd.DataFrame:
    """Per-reader metadata -- the DATA-20 participant-metadata table.

    Never broadcast onto the word/fixation frames.
    """
    return pd.read_parquet(_dataset_dir(root, dataset) / "participants.parquet")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: PASS, except `test_geometry_source_survives_normalization`, which FAILS — normalization drops unregistered columns. Task 7 fixes it. Mark it `@pytest.mark.xfail(reason="geometry_source registered in Task 7", strict=True)` and remove the marker in Task 7.

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/eyegenbench.py scanpath_studio/constants.py tests/test_eyegenbench.py
git commit -m "DATA-27: EyeGenBench bundle loader"
```

---

### Task 7: Register `geometry_source` so normalization keeps it

**Files:**
- Modify: `scanpath_studio/data.py:1612` (`WORD_OPTIONAL_FIELDS`), `scanpath_studio/data.py:1711` (`FIX_OPTIONAL_FIELDS`)
- Modify: `tests/test_eyegenbench.py` (drop the xfail marker)

**Interfaces:**
- Consumes: the bundle loader (Task 6).
- Produces: `geometry_source` surviving into both canonical frames.

Normalization builds a *fresh* frame and silently drops anything unregistered — skip this and the tier vanishes between the loader and the first plot, with no error.

- [ ] **Step 1: Remove the xfail marker to re-expose the failure**

Delete the `@pytest.mark.xfail(...)` line above `test_geometry_source_survives_normalization`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py::test_geometry_source_survives_normalization -v`
Expected: FAIL — `KeyError: 'geometry_source'`

- [ ] **Step 3: Write minimal implementation**

Add to **both** lists, keeping each list's existing formatting:

```python
# DATA-27: which tier the EyeGenBench word boxes came from --
# "real" | "reconstructed" | "synthesized". Carried so the UI can badge a
# reconstructed layout rather than pass it off as the original screen.
(("geometry_source", "geometry_source", "passthrough", "meta"),)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/data.py tests/test_eyegenbench.py
git commit -m "DATA-27: keep geometry_source through normalization"
```

---

### Task 8: The prep script

**Files:**
- Create: `scripts/prepare_eyegenbench.py`
- Test: `tests/test_prepare_eyegenbench.py`

**Interfaces:**
- Consumes: `resolve_geometry`, `place_fixations`, `GEOMETRY_*` (Task 5).
- Produces: `build_bundle(dataset, fix_df, text_df, participant_df, raw_fix_df, out_root) -> dict` (the manifest entry); `main(argv) -> int`.

EyeGenBench is imported **lazily inside `run_prepare_data`** so the pure-pandas conversion stays testable without torch. The script runs in its own venv (`python -m venv .venv-eyegenbench && .venv-eyegenbench/bin/pip install -e ../../EyeGenBench/code`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prepare_eyegenbench.py
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_eyegenbench.py"
spec = importlib.util.spec_from_file_location("prepare_eyegenbench", SCRIPT)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)

TEXTS = pd.DataFrame(
    {
        "unique_paragraph_id": ["p1"],
        "text": ["ab cd"],
        "text_language": ["en"],
        "ia_list": [["ab", "cd"]],
    }
)
FIX = pd.DataFrame(
    {
        "unique_trial_id": ["t1", "t1"],
        "unique_participant_id": ["r1", "r1"],
        "unique_paragraph_id": ["p1", "p1"],
        "fix_index": [0, 1],
        "ia_index": [0, 1],
        "fix_duration": [200, 180],
        "fix_landing_position": [0.5, 0.5],
    }
)
PARTS = pd.DataFrame({"unique_participant_id": ["r1"], "participant_language": ["de"]})


def test_build_bundle_writes_three_parquets_and_an_entry(tmp_path):
    entry = prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    for table in ("words", "fixations", "participants"):
        assert (tmp_path / "PoTeC" / f"{table}.parquet").is_file()
    assert entry["name"] == "PoTeC"
    assert entry["geometry_source"] == "reconstructed"
    assert entry["n_readers"] == 1 and entry["n_fixations"] == 2
    assert entry["monitor"] == [1680, 1050]


def test_build_bundle_places_fixations_inside_their_boxes(tmp_path):
    prep.build_bundle("PoTeC", FIX, TEXTS, PARTS, None, tmp_path)
    words = pd.read_parquet(tmp_path / "PoTeC" / "words.parquet")
    fixations = pd.read_parquet(tmp_path / "PoTeC" / "fixations.parquet")
    box = words[words["ia_index"] == 0].iloc[0]
    placed = fixations[fixations["ia_index"] == 0].iloc[0]
    assert box["start_x"] <= placed["x"] <= box["end_x"]


def test_write_manifest_merges_entries_across_runs(tmp_path):
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [1, 2]}])
    prep.write_manifest(tmp_path, [{"name": "B", "monitor": [3, 4]}])
    names = [
        d["name"]
        for d in json.loads((tmp_path / "manifest.json").read_text())["datasets"]
    ]
    assert sorted(names) == ["A", "B"]


def test_write_manifest_replaces_a_rerun_dataset(tmp_path):
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [1, 2]}])
    prep.write_manifest(tmp_path, [{"name": "A", "monitor": [9, 9]}])
    datasets = json.loads((tmp_path / "manifest.json").read_text())["datasets"]
    assert len(datasets) == 1 and datasets[0]["monitor"] == [9, 9]


def test_free_space_guard_stops_before_filling_the_disk(monkeypatch):
    monkeypatch.setattr(prep, "_free_gb", lambda path: 10.0)
    with pytest.raises(prep.OutOfDiskError, match="15 GB"):
        prep.check_free_space(Path("."))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prepare_eyegenbench.py -v`
Expected: FAIL — `FileNotFoundError: scripts/prepare_eyegenbench.py`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
"""Build Scanpath Studio bundles from EyeGenBench corpora.

Runs EyeGenBench's own `prepare_data()` unmodified, then -- while the raw
downloads are still on disk -- recovers screen geometry and writes an
app-native Parquet bundle. Run in a venv that has EyeGenBench installed:

    python -m venv .venv-eyegenbench
    .venv-eyegenbench/bin/pip install -e ../../EyeGenBench/code
    .venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --all
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from scanpath_studio.eyegenbench_geometry import (  # noqa: E402
    place_fixations,
    resolve_geometry,
)

MIN_FREE_GB = 15.0
MANIFEST_NAME = "manifest.json"

# The 39 loadable EyeGenBench datasets. `gazebasereading` is excluded -- still a
# NotImplementedError stub upstream.
DATASETS = [
    "adegbts",
    "bsc",
    "bscii",
    "celer",
    "cfiltcoreference",
    "cfiltessaygrading",
    "cfiltsarcasm",
    "cfiltscanpath",
    "cfiltsentiment",
    "chinesereading",
    "colagaze",
    "copco",
    "cuentos",
    "emtec",
    "etdd70",
    "eyevoicespan",
    "gaze4hate",
    "ggtg",
    "iitbhgc",
    "interead",
    "mecol1w1",
    "mecol1w2",
    "mecol2w1",
    "mecol2w2",
    "oasstetc",
    "onestop",
    "potec",
    "provo",
    "psc2",
    "psr",
    "raccoons",
    "readingbrain",
    "readingbrainl2",
    "rsc",
    "sbsat",
    "uclcorpus",
    "vqamhug",
    "zuco1",
    "zuco2",
]


# Licence + citation per corpus, so attribution travels into export bundles
# (spec §8). Populate from the "Data license" column of the UZH dataset review
# table (https://pub.cl.uzh.ch/projects/eyetracker/datasets.html -- the values
# are in the page's inline `const DATA` array, alongside a `const BIBTEX` map
# for the citations). Leave a corpus out rather than guessing: the default
# below tells the reader to consult the corpus itself.
CORPUS_INFO: dict[str, dict] = {
    "potec": {"license": "CC-BY-4.0", "citation": "Jakobi et al. 2024"},
    "onestop": {"license": "CC-BY-4.0", "citation": "Berzak et al. 2025"},
    "copco": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2022"},
    "provo": {"license": "CC-BY-4.0", "citation": "Luke & Christianson 2018"},
    "zuco1": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2018"},
    "zuco2": {"license": "CC-BY-4.0", "citation": "Hollenstein et al. 2020"},
}


class OutOfDiskError(RuntimeError):
    """Raised when free space drops below MIN_FREE_GB."""


def _free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / (1024**3)


def check_free_space(path: Path) -> None:
    """Stop before filling the disk. Raw downloads are kept, never deleted."""
    free = _free_gb(path)
    if free < MIN_FREE_GB:
        raise OutOfDiskError(
            f"Only {free:.1f} GB free; need {MIN_FREE_GB:.0f} GB. "
            "Free space or move the raw downloads, then rerun."
        )


def build_bundle(dataset, fix_df, text_df, participant_df, raw_fix_df, out_root):
    """Write one dataset's bundle and return its manifest entry."""
    from scanpath_studio.eyegenbench_geometry import display_spec_for

    words, report = resolve_geometry(dataset, text_df, raw_fix_df)
    fixations = place_fixations(fix_df, words)
    fixations["geometry_source"] = report["geometry_source"]

    name = str(dataset)
    directory = Path(out_root) / name
    directory.mkdir(parents=True, exist_ok=True)
    words.to_parquet(directory / "words.parquet", index=False)
    fixations.to_parquet(directory / "fixations.parquet", index=False)
    if participant_df is None:
        participant_df = pd.DataFrame({"unique_participant_id": []})
    participant_df.to_parquet(directory / "participants.parquet", index=False)

    spec = display_spec_for(dataset)
    languages = sorted(set(text_df["text_language"].astype(str)))
    info = CORPUS_INFO.get(str(dataset).lower(), {})
    return {
        "name": name,
        "language": ", ".join(languages),
        "monitor": [spec.width_px, spec.height_px],
        "n_readers": int(fix_df["unique_participant_id"].nunique()),
        "n_texts": int(text_df["unique_paragraph_id"].nunique()),
        "n_fixations": int(len(fixations)),
        # Spec §8: attribution travels with the data into export bundles.
        "license": info.get("license", "unknown - consult the corpus"),
        "citation": info.get("citation", ""),
        **report,
    }


def write_manifest(out_root: Path, entries: list) -> None:
    """Merge ``entries`` into the manifest, replacing any rerun dataset."""
    path = Path(out_root) / MANIFEST_NAME
    existing = json.loads(path.read_text())["datasets"] if path.is_file() else []
    merged = {e["name"]: e for e in existing}
    merged.update({e["name"]: e for e in entries})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"datasets": sorted(merged.values(), key=lambda e: e["name"])}, indent=1
        )
    )


def run_prepare_data(dataset: str, eyegenbench_root: Path):
    """Run EyeGenBench's pipeline; return (fix, text, participant, raw_fix).

    `load_dataset` resolves its config and data paths *relative to the
    EyeGenBench repo root*, so we chdir there for the call. Raw downloads land
    in `<eyegenbench_root>/data/<Name>/`, which is also where we look for the
    interim file that still carries the real interest-area boxes.
    """
    import os  # noqa: PLC0415

    import eyegenbench.data  # noqa: F401, PLC0415 - registers every datamodule
    from eyegenbench.data.utils.load import load_dataset  # noqa: PLC0415

    previous = Path.cwd()
    try:
        os.chdir(eyegenbench_root)
        fix_df, text_df, participant_df = load_dataset(dataset)
    finally:
        os.chdir(previous)

    raw = None
    interim = eyegenbench_root / "data" / _canonical_name(dataset) / "interim"
    for candidate in sorted(interim.glob("*.csv")) if interim.is_dir() else []:
        try:
            head = pd.read_csv(candidate, nrows=0)
        except Exception:  # noqa: BLE001 - a non-CSV in interim is not fatal
            continue
        if "CURRENT_FIX_INTEREST_AREA_DATA" in head.columns:
            raw = pd.read_csv(candidate)
            break
    return fix_df, text_df, participant_df, raw


def _canonical_name(dataset: str) -> str:
    """EyeGenBench's CamelCase directory name for a lowercase dataset key."""
    from eyegenbench.data.utils.factory import DataModuleFactory  # noqa: PLC0415

    for name in DataModuleFactory.datamodules:
        if name.lower() == str(dataset).lower():
            return name
    return str(dataset)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", help="Repeatable.")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--eyegenbench-root",
        default="../EyeGenBench/code",
        help="Checkout of github.com/EyeBench/EyeGenBench. Raw downloads land "
        "in its data/ directory and are kept, never deleted.",
    )
    parser.add_argument("--out", default="data/EyeGenBench")
    args = parser.parse_args(argv)

    names = DATASETS if args.all else (args.dataset or [])
    if not names:
        parser.error("pass --dataset NAME (repeatable) or --all")

    eyegenbench_root = Path(args.eyegenbench_root).resolve()
    if not (eyegenbench_root / "eyegenbench").is_dir():
        parser.error(f"{eyegenbench_root} is not an EyeGenBench checkout")
    out_root = Path(args.out)
    entries, skipped = [], []
    for name in names:
        try:
            check_free_space(eyegenbench_root)
            fix, text, parts, raw = run_prepare_data(name, eyegenbench_root)
            entry = build_bundle(name, fix, text, parts, raw, out_root)
            write_manifest(out_root, [entry])
            entries.append(entry)
            print(
                f"[ok]   {name}: {entry['geometry_source']}, "
                f"{entry['n_fixations']} fixations, {entry['n_readers']} readers"
            )
        except OutOfDiskError as exc:
            print(f"[stop] {exc}")
            break
        except Exception as exc:  # noqa: BLE001 - one corpus must not stop the run
            skipped.append((name, str(exc)))
            print(f"[skip] {name}: {exc}")

    print(f"\nPrepared {len(entries)}; skipped {len(skipped)}.")
    for name, reason in skipped:
        print(f"  {name}: {reason}")
    return 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prepare_eyegenbench.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scripts/prepare_eyegenbench.py tests/test_prepare_eyegenbench.py
git commit -m "DATA-27: EyeGenBench bundle prep script"
```

---

### Task 9: Headless API + package exports

**Files:**
- Modify: `scanpath_studio/__init__.py:39` (`_DATASET_EXPORTS`, `__all__`)
- Modify: `docs/api.md`
- Test: `tests/test_eyegenbench.py`

**Interfaces:**
- Consumes: `load_eyegenbench` (Task 6).
- Produces: `scanpath_studio.load_eyegenbench` importable from the package root.

- [ ] **Step 1: Write the failing test**

```python
def test_load_eyegenbench_is_exported_from_the_package_root():
    import scanpath_studio

    assert "load_eyegenbench" in scanpath_studio.__all__
    assert callable(scanpath_studio.load_eyegenbench)


def test_package_import_does_not_pull_in_pandas_eagerly():
    # The lazy __getattr__ keeps `import scanpath_studio` cheap.
    import scanpath_studio

    assert "load_eyegenbench" in dir(scanpath_studio)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -k exported -v`
Expected: FAIL — `AssertionError: 'load_eyegenbench' not in __all__`

- [ ] **Step 3: Write minimal implementation**

In `__init__.py`, add `"load_eyegenbench"` to `__all__` and extend line 39:

```python
_DATASET_EXPORTS = frozenset(
    {"load_potec", "load_multipleye", "load_onestop", "load_eyegenbench"}
)
```

In `docs/api.md`, beside the other dataset loaders. Note the module path is
`scanpath_studio.eyegenbench`, **not** `scanpath_studio.datasets` — the other
three corpora live in `datasets.py`, this one does not:

```markdown
::: scanpath_studio.eyegenbench.load_eyegenbench
::: scanpath_studio.eyegenbench.eyegenbench_datasets
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/__init__.py docs/api.md tests/test_eyegenbench.py
git commit -m "DATA-27: export load_eyegenbench from the package root"
```

---

### Task 10: CLI surface

**Files:**
- Modify: `scanpath_studio/cli.py:199` (input group), `cli.py:1076` (exactly-one-input message)
- Test: `tests/test_eyegenbench.py`

**Interfaces:**
- Consumes: `load_eyegenbench` (Task 6).
- Produces: `render --eyegenbench DIR --eyegenbench-dataset NAME`.

- [ ] **Step 1: Write the failing test**

```python
def test_cli_accepts_the_eyegenbench_input(bundle, tmp_path):
    from scanpath_studio import cli

    out = tmp_path / "fig.png"
    code = cli.main(
        [
            "render",
            "--eyegenbench",
            str(bundle),
            "--eyegenbench-dataset",
            "PoTeC",
            "--participant",
            "r1",
            "--trial",
            "t1",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    assert out.is_file()


def test_cli_rejects_eyegenbench_combined_with_sample(bundle, capsys):
    from scanpath_studio import cli

    with pytest.raises(SystemExit):
        cli.main(["render", "--sample", "--eyegenbench", str(bundle)])
    assert "exactly one input" in capsys.readouterr().err.lower()


def test_cli_requires_a_dataset_name_with_eyegenbench(bundle, capsys):
    from scanpath_studio import cli

    with pytest.raises(SystemExit):
        cli.main(["render", "--eyegenbench", str(bundle), "--out", "x.png"])
    assert "--eyegenbench-dataset" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -k cli -v`
Expected: FAIL — `error: unrecognized arguments: --eyegenbench`

- [ ] **Step 3: Write minimal implementation**

In `cli.py`, beside `--potec` (line 199):

```python
    group.add_argument(
        "--eyegenbench",
        metavar="DIR",
        help="EyeGenBench bundle directory (built by "
        "scripts/prepare_eyegenbench.py). Pick the corpus with "
        "--eyegenbench-dataset.",
    )
    parser.add_argument(
        "--eyegenbench-dataset",
        metavar="NAME",
        help="Which EyeGenBench corpus to render, e.g. PoTeC.",
    )
```

Add `args.eyegenbench` to the exactly-one-input check at line 1076 and to its
message, then in the loader branch:

```python
    if args.eyegenbench:
        if not args.eyegenbench_dataset:
            parser.error("--eyegenbench requires --eyegenbench-dataset NAME")
        from .eyegenbench import load_eyegenbench

        words, fixations = load_eyegenbench(
            args.eyegenbench, dataset=args.eyegenbench_dataset
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/cli.py tests/test_eyegenbench.py
git commit -m "DATA-27: --eyegenbench CLI input"
```

---

### Task 11: UI source + registry entry + dataset picker

**Files:**
- Modify: `scanpath_studio/app.py` (add `_load_eyegenbench_source`, `_EYEGENBENCH_STRUCTURE_MD`, `_eyegenbench_picker_groups`, one `PUBLIC_DATASET_REGISTRY` entry)
- Modify: `tests/test_apptest.py:881` (monkeypatched constants tuple)

**Interfaces:**
- Consumes: `eyegenbench_present`, `eyegenbench_datasets`, `eyegenbench_raw_frames`, `eyegenbench_monitor`, `constants.EYEGENBENCH_DEFAULT_DIR`.
- Produces: a `"EyeGenBench — 39 harmonised reading corpora"` entry in `PUBLIC_DATASET_REGISTRY`.

Use the shared helpers so every corpus looks the same: `_dataset_dir_input` (directory box + folder picker + *Expected files* tree) and `_dataset_access_status` (found/missing). The dataset picker goes in the DATA-9 `options_host` sub-slot. Cache the read in a module-level `@st.cache_data` function keyed on plain strings; when the data isn't there, `return load_sample_data()` so the app stays usable.

- [ ] **Step 1: Write the failing test**

```python
def test_registry_lists_eyegenbench():
    from scanpath_studio import app

    entry = app.PUBLIC_DATASET_REGISTRY["EyeGenBench — 39 harmonised reading corpora"]
    assert entry["short"] == "EyeGenBench"
    assert callable(entry["loader"])
    assert entry["link"].startswith("https://github.com/EyeBench")


def test_picker_groups_datasets_by_language():
    from scanpath_studio import app

    groups = app._eyegenbench_picker_groups(
        [{"name": "PoTeC", "language": "de"}, {"name": "Provo", "language": "en"}]
    )
    assert groups["de"] == ["PoTeC"]
    assert groups["en"] == ["Provo"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -k "registry or picker" -v`
Expected: FAIL — `KeyError: 'EyeGenBench — 39 harmonised reading corpora'`

- [ ] **Step 3: Write minimal implementation**

Add the entry beside the PoTeC one (`app.py:1349`):

```python
    "EyeGenBench — 39 harmonised reading corpora": dict(
        loader=_load_eyegenbench_source,
        monitor=(1920, 1080),  # Per-corpus; overridden from the manifest on load.
        short="EyeGenBench",
        language="Multilingual",
        size="39 corpora",
        description="The EyeGenBench benchmark suite, harmonised to one schema. "
        "Screen geometry is recovered per corpus and badged real / "
        "reconstructed / synthesized.",
        link="https://github.com/EyeBench/EyeGenBench",
    ),
```

And the grouping helper:

```python
def _eyegenbench_picker_groups(entries) -> dict:
    """Manifest entries -> ``{language: [dataset name, ...]}`` for the picker.

    Provisional grouping (DATA-27 open decision); by language keeps 39 entries
    navigable without the user knowing each corpus by name.
    """
    groups: dict = {}
    for entry in entries:
        groups.setdefault(str(entry.get("language") or "Unknown"), []).append(
            entry["name"]
        )
    return {key: sorted(value) for key, value in sorted(groups.items())}
```

Add `"EYEGENBENCH_DEFAULT_DIR"` to the monkeypatched tuple at `tests/test_apptest.py:881` — without it the test reads your real data directory and passes or fails depending on what the dev machine has downloaded.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py tests/test_apptest.py -v`
Expected: PASS. `test_apptest.py` loops the registry and boots the app for each entry, so the new source is exercised automatically.

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/app.py tests/test_apptest.py tests/test_eyegenbench.py
git commit -m "DATA-27: EyeGenBench data source in the sidebar"
```

---

### Task 12: Deep link / Share

**Files:**
- Modify: `scanpath_studio/url_state.py:417` (`_SHAREABLE_SOURCES`), plus `_apply_url_preset` / `_build_share_query`
- Test: `tests/test_eyegenbench.py`

**Interfaces:**
- Consumes: the registry entry (Task 11).
- Produces: `?source=eyegenbench&eyegenbench_dataset=<name>` round-tripping.

Skipping this works, but a shared link can't reopen the corpus — which is the whole point of Share.

- [ ] **Step 1: Write the failing test**

```python
def test_eyegenbench_is_shareable():
    from scanpath_studio import url_state

    assert url_state._SHAREABLE_SOURCES[url_state.EYEGENBENCH_CHOICE] == "eyegenbench"


def test_share_query_carries_the_chosen_dataset():
    from scanpath_studio import url_state

    query = url_state._build_share_query(
        url_state.EYEGENBENCH_CHOICE, {"eyegenbench_dataset": "PoTeC"}
    )
    assert query["source"] == "eyegenbench"
    assert query["eyegenbench_dataset"] == "PoTeC"


def test_source_param_inverts_back_to_the_data_choice():
    from scanpath_studio import url_state

    assert (
        url_state._source_choice_for_param("eyegenbench")
        == url_state.EYEGENBENCH_CHOICE
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -k "shareable or share_query or source_param" -v`
Expected: FAIL — `AttributeError: module 'scanpath_studio.url_state' has no attribute 'EYEGENBENCH_CHOICE'`

- [ ] **Step 3: Write minimal implementation**

Add `EYEGENBENCH_CHOICE = "EyeGenBench — 39 harmonised reading corpora"` next to the other `*_CHOICE` constants, then extend `_SHAREABLE_SOURCES`:

```python
    # DATA-27: the corpus choice rides alongside via `_build_share_query`, the
    # same way DATA-3 carries OneStop's variant/regime/parts.
    EYEGENBENCH_CHOICE: "eyegenbench",
```

In `_build_share_query`, when the source is `EYEGENBENCH_CHOICE`, emit
`eyegenbench_dataset`; in `_apply_url_preset`, seed the picker's session key from
that param before any widget renders.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_eyegenbench.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add scanpath_studio/url_state.py tests/test_eyegenbench.py
git commit -m "DATA-27: share links reopen an EyeGenBench corpus"
```

---

### Task 13: Docs

**Files:**
- Create: `docs/eyegenbench.md`
- Modify: `mkdocs.yml` (`nav:` under **Datasets**)
- Modify: `CHANGELOG.md`

A page that isn't in the nav still builds, but nothing links to it.

- [ ] **Step 1: Write the page**

Match the voice of [`docs/onestop.md`](../docs/onestop.md) and
[`docs/multipleye.md`](../docs/multipleye.md). Fill the counts from
`data/EyeGenBench/manifest.json` after Task 14's sweep:

````markdown
# EyeGenBench

[EyeGenBench](https://github.com/EyeBench/EyeGenBench) harmonises 39 public
eye-tracking-while-reading corpora into a single schema. Scanpath Studio reads
a *bundle* built from it — the harmonised tables plus the screen geometry
EyeGenBench itself does not keep.

## Building a bundle

```bash
python -m venv .venv-eyegenbench
.venv-eyegenbench/bin/pip install -e path/to/EyeGenBench/code
.venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --all
```

Each corpus downloads from its own host, so the first run takes hours and needs
tens of GB. Raw downloads are kept; the script stops if free space drops below
15 GB. A corpus needing manual or credentialed access is reported as skipped and
the run continues.

## Where the coordinates come from

EyeGenBench records *which* word each fixation landed on and *where within it*,
but no pixel coordinates and no word boxes — so Scanpath Studio recovers them,
at one of three fidelities. Every trial carries a `geometry_source` column, and
the app badges it.

| Tier | What it means | Corpora |
| --- | --- | --- |
| `real` | Word boxes parsed from the corpus' own files — EyeLink interest-area exports carry the actual on-screen rectangle | *(fill from the manifest)* |
| `reconstructed` | Text laid out using the corpus' published screen, font and spacing | *(fill from the manifest)* |
| `synthesized` | Nothing published; generic monospace defaults | *(fill from the manifest)* |

**What each tier is worth.** `real` is the original screen. For a *monospaced*
corpus, `reconstructed` is genuinely true-to-scale — resolution, font size and
characters-per-degree determine the layout. For a proportional font (Arial,
Noto Sans, Times) it fixes the canvas and the line pitch, but within-line word
positions are approximate. `synthesized` preserves reading order, durations and
word identities; its geometry is a readable stand-in, not a measurement.

Where boxes are `real` but a word was never fixated, its box is interpolated
from its neighbours — the manifest's `interpolated_fraction` says how much of a
corpus that covers.
````

- [ ] **Step 2: Verify the docs build**

Run: `.venv/bin/mkdocs build --strict 2>&1 | tail -5`
Expected: no warnings; `eyegenbench.md` present in the built `site/`.

- [ ] **Step 3: Update the CHANGELOG**

Under `[Unreleased]` → `Added`, headline list then `### Details` → `#### Added`:

```markdown
- **EyeGenBench: 39 harmonised reading corpora as a built-in source** (DATA-27)
```

- [ ] **Step 4: Commit**

```bash
ruff check --exclude other_vis . && ruff format --exclude other_vis .
git add docs/eyegenbench.md mkdocs.yml CHANGELOG.md
git commit -m "DATA-27: document the EyeGenBench source"
```

---

### Task 14: Run the prep across all 39 corpora

This is the one task whose output is data, not code. It is slow (hours of downloads) and partially expected to fail — several corpora need manual or credentialed access.

- [ ] **Step 1: Build the prep venv**

```bash
python3 -m venv .venv-eyegenbench
.venv-eyegenbench/bin/pip install -e /Users/shubi/Projects/EyeGenBench/code
```

- [ ] **Step 2: Smoke-test on one small corpus**

```bash
.venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --dataset potec
```

Expected: `[ok] potec: real|reconstructed, N fixations, 75 readers`, and
`data/EyeGenBench/PoTeC/{words,fixations,participants}.parquet` on disk.

- [ ] **Step 3: Verify it loads and plots**

```bash
.venv/bin/python -m scanpath_studio render --eyegenbench data/EyeGenBench \
  --eyegenbench-dataset PoTeC --participant PoTeC_0 --trial PoTeC_0_b0 --out /tmp/potec.png
```

Expected: a PNG showing a scanpath over laid-out text.

- [ ] **Step 4: Run the full sweep**

```bash
.venv-eyegenbench/bin/python scripts/prepare_eyegenbench.py --all 2>&1 | tee /tmp/eyegenbench-prep.log
```

Expected: a per-corpus `[ok]`/`[skip]` line, then a summary. The run stops with `[stop]` if free space drops below 15 GB — raw downloads are kept, never deleted.

- [ ] **Step 5: Record the outcome and hand over**

Record in DATA-27's `whatWasDone`: how many corpora prepared, the tier split (how many `real` / `reconstructed` / `synthesized`), and every skipped corpus with its reason. Set `"status": "Review"` and put the review ask in `decisions` — name the judgement calls (tier-3 canvas, picker grouping) and the surfaces to click. Never jump straight to `Closed`.

```bash
git add tracker/data.js
git commit -m "DATA-27: record EyeGenBench prep results"
```

---

## Before opening the PR

- [ ] `ruff check --exclude other_vis .` and `ruff format --exclude other_vis .` both clean
- [ ] `.venv/bin/python -m pytest tests/ -q` passes
- [ ] Run the two repo subagents on the diff: `surface-parity-reviewer` (four-surface rule, wire-format keys, true-scale chart path) and `perf-reviewer` (`@st.cache_data` + `frame_fingerprint` conventions)
- [ ] DATA-27 is `Review`, not `Closed`, with the review ask in `decisions`
