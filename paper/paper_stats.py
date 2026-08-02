"""Descriptive statistics + measure validation for the manuscript (Section: Case studies).

Computes, over the bundled 3-participant OneStop demo subset that ships with
scanpath-studio:

1. Dataset counts (participants, texts, trials, word tokens, fixations).
2. Descriptive reading statistics (skipping rate, regression rates, FFD, FPRT).
   The reported regression rates are the tool's canonical `regression_in_flag` /
   `regression_out_flag` over the words fixated in first pass; the raw EyeLink
   columns are also summarized as a cross-check (they carry '.' sentinels, which
   the loader reads as "not applicable" -- see BUG-7 in the app repo's tracker).
3. Spearman correlations between word-level linguistic features (GPT-2
   surprisal, wordfreq frequency, length) and first-pass measures, over
   fixated words.
4. Measure validation: canonical measures recomputed by scanpath-studio from
   raw fixation coordinates alone (pre-computed IA columns dropped from the
   words table AND the fixation report's own word ids dropped, so the tool's
   geometric fixation->word assignment is exercised end to end) vs. the
   EyeLink Data Viewer interest-area values shipped with the corpus.

   The validation runs under BOTH word-boundary conventions, because the two
   pipelines do not share one. Interest areas are defined by the *experiment*,
   not by the tracker, and this corpus defines them so that the rectangles tile
   the line: each box is one character cell wider than its word and starts at
   the word's first glyph, so it carries the following inter-word space as
   trailing padding and a fixation in the blank space *before* a word is
   credited to the *preceding* word. (Verified against the corpus's own
   stimulus images: per line, the ink starts within 3 px of the first box's
   left edge and stops ~1 cell short of the last box's right edge.) A word
   boundary should instead sit in the middle of that space, which is what
   Scanpath Studio draws (BUG-11, `measures.word_box_bounds`). Shifting the
   word boxes right by half a space before handing them to the tool cancels
   that correction exactly, so the tool re-reads the corpus's own rectangles
   and the comparison isolates the measure definitions from the boundary
   choice.

Run from the app repo so the package + its environment resolve:

    cd app && uv run python paper/paper_stats.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

import scanpath_studio as sps
from scanpath_studio import data as _data
from scanpath_studio import measures as _measures

# Word-level columns that arrive pre-computed from the EyeLink IA report; these
# are dropped before recomputation so compute_word_metrics derives everything
# from raw fixations (pre-computed values otherwise take precedence).
PRECOMPUTED = [
    "first_fixation_ms",
    "first_pass_gaze_duration_ms",
    "regression_path_duration_ms",
    "total_fixation_duration_ms",
    "higher_pass_fixation_duration_ms",
    "last_run_dwell_time_ms",
    "n_fixations",
    "skip_flag",
    "regression_in_flag",
    "regression_out_flag",
    "regression_in_count",
    "regression_out_count",
    "trial_dwell_time_ms",
    "trial_fixation_count",
    "trial_ia_count",
]

KEY = ["participant_id", "trial_id", "word_id"]

DURATION_MEASURES = [
    ("first_fixation_ms", "FFD"),
    ("first_pass_gaze_duration_ms", "FPRT"),
    ("regression_path_duration_ms", "RPD"),
    ("total_fixation_duration_ms", "TFD"),
    ("n_fixations", "fixation count"),
]


def eyelink_flag(raw: pd.DataFrame, col: str) -> pd.Series:
    """Parse an EyeLink 0/1 flag column that may carry '.' string sentinels."""
    return pd.to_numeric(raw[col], errors="coerce")


def validate(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    eyelink: pd.DataFrame,
    raw: pd.DataFrame,
    label: str,
) -> None:
    """Recompute every measure from geometry alone and score it against EyeLink."""
    stripped = words.drop(columns=[c for c in PRECOMPUTED if c in words.columns])
    fx_geo = fixations.drop(columns=["word_id"])  # force geometric assignment
    computed = sps.compute_word_metrics(stripped, fx_geo)
    both = computed.merge(eyelink, on=KEY, suffixes=("_sps", "_el"))
    assert len(both) == len(words), "merge must stay one-to-one"

    # EyeLink regression flags re-parsed from raw (BUG-7: '.' sentinels).
    raw_flags = raw[["participant_id", "unique_trial_id", "IA_ID"]].copy()
    raw_flags.columns = KEY
    raw_flags["reg_in_el"] = eyelink_flag(raw, "IA_REGRESSION_IN").fillna(0)
    raw_flags["reg_out_el"] = eyelink_flag(raw, "IA_REGRESSION_OUT").fillna(0)
    raw_flags["word_id"] = raw_flags["word_id"].astype(both["word_id"].dtype)
    both = both.merge(raw_flags, on=KEY)

    read = both[
        (both["skip_flag_sps"].astype(float) == 0)
        & (both["skip_flag_el"].astype(float) == 0)
    ]
    print(f"\n-- {label} --")
    for meas, name in DURATION_MEASURES:
        sub = read[[f"{meas}_sps", f"{meas}_el"]].dropna().astype(float)
        a, b = sub[f"{meas}_sps"], sub[f"{meas}_el"]
        r = np.corrcoef(a, b)[0, 1]
        exact = (a == b).mean()
        mad = (a - b).abs().median()
        print(
            f"{name:15s} r={r:.4f}  exact match={exact:.4f}  "
            f"median |diff|={mad:.1f}  n={len(sub)}"
        )
    skip_sps = both["skip_flag_sps"].astype(float)
    skip_el = both["skip_flag_el"].astype(float)
    print(f"{'skip':15s} agreement={(skip_sps == skip_el).mean():.4f}  n={len(both)}")
    print(
        f"{'':15s} confusion: both read={int(((skip_sps == 0) & (skip_el == 0)).sum())}, "
        f"tool reads / EyeLink skips={int(((skip_sps == 0) & (skip_el == 1)).sum())}, "
        f"tool skips / EyeLink reads={int(((skip_sps == 1) & (skip_el == 0)).sum())}, "
        f"both skip={int(((skip_sps == 1) & (skip_el == 1)).sum())}"
    )
    for sps_col, el_col, name in [
        ("regression_in_flag_sps", "reg_in_el", "regression in"),
        ("regression_out_flag_sps", "reg_out_el", "regression out"),
    ]:
        agree = (both[sps_col].astype(float) == both[el_col].astype(float)).mean()
        print(f"{name:15s} agreement={agree:.4f}  n={len(both)}")
    print(f"{'':15s} (durations compared over n={len(read)} words fixated per both)")


def main() -> None:
    words, fixations = sps.load_sample_data()
    eyelink = sps.compute_word_metrics(words, fixations)  # IA values win
    raw = pd.read_csv(
        Path(_data.__file__).parent / "sample_data" / "ia.csv", low_memory=False
    )

    print("== Dataset counts ==")
    print(f"participants: {words['participant_id'].nunique()}")
    print(f"texts:        {words['text_id'].nunique()}")
    print(f"trials:       {words.groupby(['participant_id', 'trial_id']).ngroups}")
    print(f"word tokens:  {len(words)}")
    print(f"fixations:    {len(fixations)}")

    print("\n== Descriptives ==")
    skip = eyelink["skip_flag"].astype(float)
    fixated = eyelink[skip == 0]
    ffd = fixated["first_fixation_ms"].astype(float)
    fprt = fixated["first_pass_gaze_duration_ms"].astype(float)
    print(f"skipping rate:        {skip.mean():.3f}  (n={len(eyelink)} words)")
    print(
        f"FFD  mean (SD) ms:    {ffd.mean():.1f} ({ffd.std():.1f})  n={ffd.notna().sum()}"
    )
    print(f"FPRT mean (SD) ms:    {fprt.mean():.1f} ({fprt.std():.1f})")
    # The rates the manuscript reports: over the words fixated in first pass.
    for col, name in [
        ("regression_in_flag", "regression-in rate"),
        ("regression_out_flag", "regression-out rate"),
    ]:
        among = fixated[col].astype(float)
        allw = eyelink[col].astype(float)
        print(
            f"{name:21s} {among.mean():.3f} among fixated (n={among.notna().sum()})"
            f"  [{allw.mean():.3f} over all words]"
        )
    # Cross-check straight off the raw EyeLink columns, whose '.' sentinels mark
    # rows the tracker left undefined (all of which are skipped words).
    reg_in = eyelink_flag(raw, "IA_REGRESSION_IN")
    dot = raw["IA_REGRESSION_IN"].astype(str) == "."
    print(
        f"raw IA_REGRESSION_IN: {reg_in.mean():.3f} over defined n={reg_in.notna().sum()}"
        f"; '.'-sentinel rows also skipped: {(raw.loc[dot, 'IA_SKIP'] == 1).mean():.3f}"
    )

    print("\n== Feature correlations (Spearman, fixated words) ==")
    for feat in ("gpt2_surprisal", "wordfreq_frequency", "word_length"):
        for meas in ("first_fixation_ms", "first_pass_gaze_duration_ms"):
            sub = fixated[[feat, meas]].dropna().astype(float)
            rho, p = stats.spearmanr(sub[feat], sub[meas])
            print(f"{feat:20s} vs {meas:28s} rho={rho:+.3f}  p={p:.2g}  n={len(sub)}")

    print("\n== Measure validation: recomputed-from-raw vs EyeLink IA ==")
    # The two pipelines draw the word boundary in different places (see the
    # module docstring). Shifting x right by half an inter-word space cancels
    # the tool's mid-space correction, so it reads EyeLink's own rectangles.
    space = _measures.word_box_space_px(words)
    print(f"inter-word padding baked into the IA boxes: {space:.1f} px")
    eyelink_boxes = words.copy()
    eyelink_boxes["x"] = (
        pd.to_numeric(eyelink_boxes["x"], errors="coerce") + space / 2.0
    )

    validate(
        eyelink_boxes,
        fixations,
        eyelink,
        raw,
        "boundaries on EyeLink's own IA rectangles (isolates the measure definitions)",
    )
    validate(
        words,
        fixations,
        eyelink,
        raw,
        "boundaries mid-space, the tool's default convention (BUG-11)",
    )


if __name__ == "__main__":
    main()
