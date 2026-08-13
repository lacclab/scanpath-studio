"""Optional reading-data preprocessing and derived analysis tables.

The stage is deliberately pure and disabled by default (PRE-1). It soft-marks
excluded rows, preserves originals for any changed value, and exposes the same
functions to the UI, CLI, public API, and bulk export.
"""

from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .measures import materialize_runs
from .multipart import SCREEN_ID, grouping_columns

DEFAULT_PREPROCESSING = {
    "enabled": False,
    "short_policy": "Off",
    "short_threshold_ms": 80.0,
    "merge_distance_chars": 1.0,
    "discard_blink_adjacent": True,
}


def detect_right_to_left(text: str) -> bool:
    """Majority-script direction detection for Hebrew/Arabic trial text."""
    rtl = ltr = 0
    for char in str(text or ""):
        code = ord(char)
        if 0x0590 <= code <= 0x08FF or 0xFB1D <= code <= 0xFEFC:
            rtl += 1
        elif char.isalpha():
            ltr += 1
    return rtl > ltr


def add_text_direction(words: pd.DataFrame) -> pd.DataFrame:
    """Attach ``right_to_left`` unless the dataset already supplies it (PRE-6)."""
    if words.empty or "right_to_left" in words or "text" not in words:
        return words
    out = words.copy()
    keys = grouping_columns(out)
    if keys:
        # Detect ONCE PER TRIAL and let `transform` broadcast the scalar, rather
        # than materialising the whole trial's joined text on every row and then
        # scanning it per row. The old form was quadratic in trial length — for a
        # 500-word trial it scanned ~500x more characters than it needed to, and
        # on an ordinary upload it was the single slowest step of the load
        # (measured 18.3s -> 0.30s on 144k words), all of it *after* the wizard
        # had already said "Dataset added" — so it read as the app hanging.
        out["right_to_left"] = out.groupby(keys, sort=False)["text"].transform(
            lambda values: detect_right_to_left(" ".join(values.astype(str)))
        )
    else:
        out["right_to_left"] = detect_right_to_left(" ".join(out["text"].astype(str)))
    return out


def _character_width(words: pd.DataFrame, word_id) -> float:
    """One character's width for this word — BUG-27's shared letter scale.

    This scales the *merge distance*, which the user sets in **characters** and
    which travels on the share link and the saved config
    (`session_keys.GLOBAL_PREPROC_MERGE_DISTANCE_CHARS`). It used to divide by
    `len(text)`, so on a tiling corpus "merge within 1 character" silently meant
    1.25 characters for a four-letter word and 1.07 for a fifteen-letter one —
    the same length-dependent error BUG-27 fixed in the landing measures, on a
    setting whose whole point is to mean one thing.
    """
    from .measures import word_char_advance

    match = words[pd.to_numeric(words.get("word_id"), errors="coerce") == word_id]
    if match.empty:
        return 1.0
    # `layout=words`: tiling is a property of the whole line, and a one-row
    # subset reads as glyph-tight.
    advance = word_char_advance(match, layout=words)
    value = float(advance[0]) if len(advance) else np.nan
    return max(value, 1.0) if np.isfinite(value) else 1.0


def merge_short_fixations(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    *,
    threshold_ms: float = 80.0,
    distance_chars: float = 1.0,
    discard_unmerged: bool | str = False,
) -> tuple[pd.DataFrame, int, int]:
    """Merge short-and-close fixations into a temporal neighbour (PRE-14)."""
    if fixations.empty:
        return fixations.copy(), 0, 0
    out = fixations.sort_values(
        grouping_columns(fixations)
        + (["timestamp_ms"] if "timestamp_ms" in fixations else []),
        kind="stable",
    ).copy()
    out["original_duration_ms"] = pd.to_numeric(out["duration_ms"], errors="coerce")
    excluded = (
        out.get("excluded", pd.Series(False, index=out.index)).astype(bool).copy()
    )
    reasons = (
        out.get("excluded_reason", pd.Series("", index=out.index))
        .fillna("")
        .astype(str)
        .copy()
    )
    merged = dropped = 0
    keys = grouping_columns(out)
    groups = out.groupby(keys, sort=False).groups.values() if keys else [out.index]
    for indices in groups:
        indices = list(indices)
        for position, index in enumerate(indices):
            duration = float(
                pd.to_numeric(out.at[index, "duration_ms"], errors="coerce")
            )
            if (
                not np.isfinite(duration)
                or duration >= threshold_ms
                or excluded.at[index]
            ):
                continue
            candidates = []
            for neighbor_pos in (position - 1, position + 1):
                if 0 <= neighbor_pos < len(indices):
                    neighbor = indices[neighbor_pos]
                    if not excluded.at[neighbor]:
                        distance = abs(
                            float(out.at[index, "x"]) - float(out.at[neighbor, "x"])
                        )
                        char_width = _character_width(
                            words,
                            pd.to_numeric(out.at[index, "word_id"], errors="coerce"),
                        )
                        if distance <= distance_chars * char_width:
                            candidates.append((distance, neighbor))
            if candidates:
                _, target = min(candidates)
                out.at[target, "duration_ms"] = (
                    float(out.at[target, "duration_ms"]) + duration
                )
                excluded.at[index] = True
                reasons.at[index] = "merged_short"
                merged += 1
            elif discard_unmerged is True or (
                discard_unmerged == "terminal" and position == len(indices) - 1
            ):
                excluded.at[index] = True
                reasons.at[index] = "short_unmerged"
                dropped += 1
    out["excluded"] = excluded
    out["excluded_reason"] = reasons
    return out.sort_index(), merged, dropped


def _blink_flags(fixations: pd.DataFrame) -> pd.Series:
    for column in ("is_blink", "blink", "blink_flag"):
        if column in fixations:
            return fixations[column].fillna(False).astype(bool)
    return pd.Series(False, index=fixations.index)


def preprocess_fixations(
    fixations: pd.DataFrame,
    words: pd.DataFrame,
    *,
    settings: Optional[Mapping] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the optional PRE-1 stage and return ``(fixations, QA report)``.

    When disabled, the original dataframe is returned byte-for-byte and the
    report is empty. Enabled rows are never hard-dropped; ``excluded`` and
    ``excluded_reason`` retain the audit trail.
    """
    cfg = {**DEFAULT_PREPROCESSING, **dict(settings or {})}
    if not cfg["enabled"]:
        return fixations, pd.DataFrame()
    out = fixations.copy()
    out["excluded"] = out.get("excluded", False)
    out["excluded_reason"] = out.get("excluded_reason", "")
    blink = _blink_flags(out)
    out["is_blink"] = blink
    keys = grouping_columns(out)
    if keys:
        grouped = out.groupby(keys, sort=False)
        out["blink_before"] = grouped["is_blink"].shift(-1).fillna(False).astype(bool)
        out["blink_after"] = grouped["is_blink"].shift(1).fillna(False).astype(bool)
    else:
        out["blink_before"] = blink.shift(-1).fillna(False)
        out["blink_after"] = blink.shift(1).fillna(False)
    if cfg["discard_blink_adjacent"]:
        mask = out["blink_before"] | out["blink_after"] | out["is_blink"]
        out.loc[mask, "excluded"] = True
        out.loc[mask, "excluded_reason"] = "blink_adjacent"

    policy = str(cfg["short_policy"])
    merged = dropped = 0
    if policy in {"Merge", "Merge then discard"}:
        prior_excluded = out["excluded"].copy()
        out, merged, dropped = merge_short_fixations(
            out,
            words,
            threshold_ms=float(cfg["short_threshold_ms"]),
            distance_chars=float(cfg["merge_distance_chars"]),
            discard_unmerged=True if policy == "Merge then discard" else "terminal",
        )
        out["excluded"] = out["excluded"] | prior_excluded
    elif policy == "Discard":
        mask = pd.to_numeric(out["duration_ms"], errors="coerce") < float(
            cfg["short_threshold_ms"]
        )
        out.loc[mask, "excluded"] = True
        out.loc[mask, "excluded_reason"] = "short"
        dropped = int(mask.sum())
    out = materialize_runs(out)
    report = cleaning_report(out, short_policy=policy)
    if not report.empty:
        report["n_merged"] = merged
        report["n_short_discarded"] = dropped
    return out, report


def cleaning_report(
    fixations: pd.DataFrame, *, short_policy: str = "Off", high_word_fixations: int = 12
) -> pd.DataFrame:
    """One exportable QA/provenance row per trial (PRE-15)."""
    if fixations.empty:
        return pd.DataFrame()
    keys = grouping_columns(fixations)
    rows = []
    for identity, chunk in fixations.groupby(keys, sort=False, dropna=False):
        identity = identity if isinstance(identity, tuple) else (identity,)
        excluded = chunk.get("excluded", pd.Series(False, index=chunk.index)).astype(
            bool
        )
        reasons = chunk.get("excluded_reason", pd.Series("", index=chunk.index)).astype(
            str
        )
        retained = chunk.loc[~excluded]
        word_counts = (
            retained.dropna(subset=["word_id"]).groupby("word_id").size()
            if "word_id" in chunk
            else pd.Series(dtype=int)
        )
        n = len(chunk)
        row = dict(zip(keys, identity))
        row.update(
            n_fixations_before=n,
            n_fixations_after=int((~excluded).sum()),
            n_excluded=int(excluded.sum()),
            excluded_pct=float(excluded.mean()) if n else 0.0,
            n_blink_adjacent=int(reasons.eq("blink_adjacent").sum()),
            blink_adjacent_pct=float(reasons.eq("blink_adjacent").mean()) if n else 0.0,
            n_short_discarded=int(reasons.isin(["short", "short_unmerged"]).sum()),
            short_discarded_pct=float(reasons.isin(["short", "short_unmerged"]).mean())
            if n
            else 0.0,
            n_merged=int(reasons.eq("merged_short").sum()),
            merged_pct=float(reasons.eq("merged_short").mean()) if n else 0.0,
            short_policy=short_policy,
            max_fixations_on_word=int(word_counts.max())
            if not word_counts.empty
            else 0,
            suspicious_word_load=bool(
                not word_counts.empty and int(word_counts.max()) >= high_word_fixations
            ),
        )
        rows.append(row)
    return pd.DataFrame(rows)


def infer_sentence_ids(words: pd.DataFrame) -> pd.DataFrame:
    """Preserve dataset sentence ids or infer them from terminal punctuation."""
    if words.empty or "sentence_id" in words:
        return words.copy()
    out = words.copy()
    keys = grouping_columns(out)
    pieces = []
    for _, chunk in out.groupby(keys, sort=False, dropna=False):
        chunk = chunk.sort_values([c for c in ("line_idx", "word_id") if c in chunk])
        endings = chunk["text"].astype(str).str.contains(r"[.!?][\"'”’)]*$", regex=True)
        chunk["sentence_id"] = endings.shift(fill_value=False).cumsum() + 1
        pieces.append(chunk)
    return pd.concat(pieces).sort_index()


def sentence_measures(words: pd.DataFrame, fixations: pd.DataFrame) -> pd.DataFrame:
    """First-class per-sentence reading table derived from run structure (PRE-11)."""
    words = infer_sentence_ids(words)
    if words.empty:
        return pd.DataFrame()
    identity = grouping_columns(words)
    word_keys = [*identity, "word_id"]
    join = words[[*word_keys, "sentence_id"]].drop_duplicates()
    fix = materialize_runs(fixations).merge(join, on=word_keys, how="left")
    rows = []
    included = (
        ~fix["excluded"].fillna(False).astype(bool)
        if "excluded" in fix
        else pd.Series(True, index=fix.index)
    )
    analysis_fix = fix.loc[included]
    sentence_keys = [*identity, "sentence_id"]
    for group_key, wchunk in words.groupby(sentence_keys, sort=False):
        values = group_key if isinstance(group_key, tuple) else (group_key,)
        selected = dict(zip(sentence_keys, values))
        sentence_id = selected["sentence_id"]
        fx_mask = pd.Series(True, index=analysis_fix.index)
        for column, value in selected.items():
            fx_mask &= analysis_fix[column] == value
        fx = analysis_fix[fx_mask]
        first_run = pd.to_numeric(
            fx.get("word_run", pd.Series(1, index=fx.index)), errors="coerce"
        ).fillna(1)
        first = fx[first_run.eq(1)]
        reread = fx.drop(first.index)
        duration = pd.to_numeric(
            fx.get("duration_ms", pd.Series(np.nan, index=fx.index)), errors="coerce"
        ).sum()
        n_words = int(wchunk["word_id"].nunique())
        trial_mask = pd.Series(True, index=analysis_fix.index)
        for column in identity:
            trial_mask &= analysis_fix[column] == selected[column]
        trial_sequence = analysis_fix[trial_mask].sort_values("timestamp_ms")
        sentence_sequence = pd.to_numeric(
            trial_sequence.get("sentence_id"), errors="coerce"
        )
        transitions = sentence_sequence.diff()
        reg_in = bool(((sentence_sequence == sentence_id) & transitions.lt(0)).any())
        reg_out = bool(
            ((sentence_sequence.shift() == sentence_id) & transitions.lt(0)).any()
        )
        first_position = np.flatnonzero(sentence_sequence.to_numpy() == sentence_id)
        gopast = np.nan
        gopast_sel = np.nan
        firstpass = trial_sequence.iloc[0:0]
        first_forward = trial_sequence.iloc[0:0]
        first_reread = trial_sequence.iloc[0:0]
        lookback = trial_sequence.iloc[0:0]
        lookfrom = trial_sequence.iloc[0:0]
        if len(first_position):
            start = int(first_position[0])
            later = np.flatnonzero(
                sentence_sequence.iloc[start:].to_numpy() > sentence_id
            )
            stop = start + int(later[0]) if len(later) else len(trial_sequence)
            window = trial_sequence.iloc[start:stop]
            window_sentence = pd.to_numeric(window["sentence_id"], errors="coerce")
            firstpass = window[window_sentence.eq(sentence_id)]
            lookback = window[window_sentence.lt(sentence_id)]
            if lookback.empty:
                first_forward = firstpass
            else:
                first_lookback_time = lookback.index[0]
                before = window.index.get_loc(first_lookback_time)
                forward_window = window.iloc[:before]
                reread_window = window.iloc[before:]
                first_forward = forward_window[
                    pd.to_numeric(forward_window["sentence_id"], errors="coerce").eq(
                        sentence_id
                    )
                ]
                first_reread = reread_window[
                    pd.to_numeric(reread_window["sentence_id"], errors="coerce").eq(
                        sentence_id
                    )
                ]
            lookfrom = trial_sequence.iloc[stop:][
                pd.to_numeric(
                    trial_sequence.iloc[stop:]["sentence_id"], errors="coerce"
                ).eq(sentence_id)
            ]
            gopast = float(pd.to_numeric(window["duration_ms"], errors="coerce").sum())
            selective = window[
                pd.to_numeric(window["sentence_id"], errors="coerce") >= sentence_id
            ]
            gopast_sel = float(
                pd.to_numeric(selective["duration_ms"], errors="coerce").sum()
            )
        rows.append(
            {
                **{column: selected[column] for column in identity},
                "text_id": wchunk.iloc[0].get(
                    "text_id", wchunk.iloc[0].get("unique_text_id", pd.NA)
                ),
                "sentence_id": sentence_id,
                "n_words": n_words,
                "skip": fx.empty,
                "nrun": int(fx["word_runid"].nunique())
                if not fx.empty and "word_runid" in fx
                else 0,
                "reread": not reread.empty,
                "reg_in": reg_in,
                "reg_out": reg_out,
                "total_n_fixations": len(fx),
                "total_dur": float(duration),
                "rate_wpm": n_words / (duration / 60_000) if duration > 0 else np.nan,
                "firstpass_n_fixations": len(firstpass),
                "firstpass_dur": float(
                    pd.to_numeric(
                        firstpass.get(
                            "duration_ms", pd.Series(np.nan, index=firstpass.index)
                        ),
                        errors="coerce",
                    ).sum()
                ),
                "gopast": gopast,
                "gopast_sel": gopast_sel,
                "firstpass_forward_n_fixations": len(first_forward),
                "firstpass_forward_dur": float(
                    pd.to_numeric(
                        first_forward.get(
                            "duration_ms", pd.Series(np.nan, index=first_forward.index)
                        ),
                        errors="coerce",
                    ).sum()
                ),
                "firstpass_reread_n_fixations": len(first_reread),
                "firstpass_reread_dur": float(
                    pd.to_numeric(
                        first_reread.get(
                            "duration_ms", pd.Series(np.nan, index=first_reread.index)
                        ),
                        errors="coerce",
                    ).sum()
                ),
                "lookback_n_fixations": len(lookback),
                "lookback_dur": float(
                    pd.to_numeric(
                        lookback.get(
                            "duration_ms", pd.Series(np.nan, index=lookback.index)
                        ),
                        errors="coerce",
                    ).sum()
                ),
                "lookfrom_n_fixations": len(lookfrom),
                "lookfrom_dur": float(
                    pd.to_numeric(
                        lookfrom.get(
                            "duration_ms", pd.Series(np.nan, index=lookfrom.index)
                        ),
                        errors="coerce",
                    ).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def character_grid(words: pd.DataFrame) -> pd.DataFrame:
    """Expand word AOIs to comparable letter-position geometry (PRE-19)."""
    rows = []
    words = infer_sentence_ids(words)
    if words.empty:
        return pd.DataFrame()
    if "line_idx" not in words:
        from .measures import cluster_word_lines

        words = words.copy()
        words["line_idx"] = cluster_word_lines(words)
    keys = grouping_columns(words)
    groups = words.groupby(keys, sort=False, dropna=False) if keys else [((), words)]
    for _, trial in groups:
        trial = trial.sort_values(["line_idx", "word_id"], kind="stable")
        global_position = 0
        line_positions: dict[object, int] = {}
        words_seen: dict[object, int] = {}
        # One advance per word, resolved once for the trial — tiling detection is
        # a property of the layout, so it must not run per word.
        from .measures import word_char_advance

        advances = dict(zip(trial.index, word_char_advance(trial, layout=words)))
        for word in trial.itertuples():
            text = str(getattr(word, "text", ""))
            if not text:
                continue
            line_id = getattr(word, "line_idx", 0)
            if words_seen.get(line_id, 0):
                line_positions[line_id] += 1  # inter-word space
                global_position += 1
            words_seen[line_id] = words_seen.get(line_id, 0) + 1
            line_positions.setdefault(line_id, 0)
            # BUG-27: one advance, not `width / len(text)` — on a tiling corpus
            # the latter stretches the glyph row across the trailing padding, so
            # every character box after the first sat progressively too far right.
            char_width = advances.get(word.Index, float(getattr(word, "width")))
            rtl = bool(getattr(word, "right_to_left", False))
            for physical_offset in range(len(text)):
                logical_offset = (
                    len(text) - physical_offset - 1 if rtl else physical_offset
                )
                char = text[logical_offset]
                x = float(word.x) + physical_offset * char_width
                letword = logical_offset + 1
                letline = line_positions[line_id] + letword
                letternum = global_position + letword
                rows.append(
                    {
                        "participant_id": getattr(word, "participant_id", pd.NA),
                        "trial_id": getattr(word, "trial_id", pd.NA),
                        **(
                            {SCREEN_ID: getattr(word, SCREEN_ID)}
                            if hasattr(word, SCREEN_ID)
                            else {}
                        ),
                        "word_id": word.word_id,
                        "sentence_id": getattr(word, "sentence_id", pd.NA),
                        "line_idx": line_id,
                        "right_to_left": rtl,
                        "character": char,
                        "letternum": letternum,
                        "letline": letline,
                        "letword": letword,
                        "x": x,
                        "y": float(word.y),
                        "center_x": x + char_width / 2.0,
                        "center_y": float(word.y) + float(word.height) / 2.0,
                        "width": char_width,
                        "height": float(word.height),
                    }
                )
            line_positions[line_id] += len(text)
            global_position += len(text)
    return pd.DataFrame(rows)


def duration_mass_table(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    *,
    sigma_chars: float = 1.0,
) -> pd.DataFrame:
    """Distribute fixation duration over nearby character centres (PRE-8).

    Each fixation contributes a Gaussian kernel whose weights sum to its
    duration. The returned character table is therefore a reproducible support
    surface and preserves total included dwell time.
    """
    chars = character_grid(words)
    if chars.empty:
        return chars.assign(duration_mass_ms=pd.Series(dtype=float))
    out = chars.copy()
    out["duration_mass_ms"] = 0.0
    analysis = fixations
    if "excluded" in analysis:
        analysis = analysis.loc[~analysis["excluded"].fillna(False).astype(bool)]
    keys = grouping_columns(analysis)
    if keys != grouping_columns(out):
        raise ValueError("Character and fixation tables use different part identities.")
    groups = (
        analysis.groupby(keys, sort=False, dropna=False) if keys else [((), analysis)]
    )
    for identity, chunk in groups:
        identity = identity if isinstance(identity, tuple) else (identity,)
        support = out
        for key, value in zip(keys, identity):
            support = support[support[key] == value]
        if support.empty:
            continue
        widths = pd.to_numeric(support["width"], errors="coerce").dropna()
        sigma_px = max(float(widths.median()) * float(sigma_chars), 1e-6)
        sx = support["center_x"].to_numpy(dtype=float)
        sy = support["center_y"].to_numpy(dtype=float)
        for fixation in chunk.itertuples():
            x = pd.to_numeric(getattr(fixation, "x", np.nan), errors="coerce")
            y = pd.to_numeric(getattr(fixation, "y", np.nan), errors="coerce")
            duration = pd.to_numeric(
                getattr(fixation, "duration_ms", np.nan), errors="coerce"
            )
            if pd.isna(x) or pd.isna(y) or pd.isna(duration) or duration <= 0:
                continue
            kernel = np.exp(
                -((sx - float(x)) ** 2 + (sy - float(y)) ** 2) / (2 * sigma_px**2)
            )
            total = float(kernel.sum())
            if total <= 0:
                kernel[int(np.argmin((sx - float(x)) ** 2 + (sy - float(y)) ** 2))] = (
                    1.0
                )
                total = 1.0
            out.loc[support.index, "duration_mass_ms"] += (
                kernel / total * float(duration)
            )
    return out


def _word_letter_geometry(
    words: Optional[pd.DataFrame], keys: Sequence[str]
) -> dict[tuple, tuple[float, float, float, bool]]:
    """``(identity…, word_id) -> (x, glyph run, character advance, right_to_left)``.

    Built once per :func:`saccade_table` call so the per-saccade letter-position
    lookup is a dict hit rather than a scan of the whole words frame (PERF-3).
    The first row wins for a duplicated key, which is what the old
    ``target.iloc[0]`` did.

    BUG-27: the advance comes from :func:`measures.word_char_advance` rather than
    the local ``width / len(text)`` this used to divide by — the same accessor
    the per-word landing measures use, so a saccade's launch/landing letter and
    the word's landing position are on one scale (they disagreed by the
    inter-word padding on a tiling corpus). The second slot is the **glyph run**
    (``n × advance``) and not the box ``width`` for the same reason: it is only
    read to mirror an RTL offset, and the padded width would put an RTL landing
    one whole advance late.
    """
    if words is None or words.empty or "word_id" not in words:
        return {}
    from .measures import word_char_advance, word_char_counts

    ids = pd.to_numeric(words["word_id"], errors="coerce")
    present = [key for key in keys if key in words]
    has_text = "text" in words
    counts = word_char_counts(words) if has_text else None
    advances = word_char_advance(words, chars=counts) if has_text else None
    rtl = words["right_to_left"] if "right_to_left" in words else None
    geometry: dict[tuple, tuple[float, float, float, bool]] = {}
    for position, word_id in enumerate(ids.to_numpy()):
        if pd.isna(word_id):
            continue
        key = tuple(words[column].iat[position] for column in present) + (
            float(word_id),
        )
        if key in geometry:
            continue
        width = float(words["width"].iat[position])
        advance = float(advances[position]) if advances is not None else width
        run = advance * float(counts[position]) if counts is not None else width
        geometry[key] = (
            float(words["x"].iat[position]),
            run,
            advance,
            bool(rtl.iat[position]) if rtl is not None else False,
        )
    return geometry


def _letter_position_in_word(
    event: dict,
    geometry: dict[tuple, tuple[float, float, int, bool]],
    identity: tuple,
) -> float:
    """Which character of its word a fixation landed on, 1-based."""
    word_id = event.get("word_id")
    if not geometry or pd.isna(word_id):
        return np.nan
    found = geometry.get(identity + (float(word_id),))
    if found is None:  # a words frame without the identity columns
        found = geometry.get((float(word_id),))
    if found is None:
        return np.nan
    word_x, glyph_run, advance, right_to_left = found
    if not np.isfinite(advance) or advance <= 0:
        return np.nan
    offset = float(event["x"]) - word_x
    if right_to_left:
        offset = glyph_run - offset
    return offset / advance + 1


def saccade_table(
    fixations: pd.DataFrame,
    *,
    pixels_per_degree: Optional[float] = None,
    raw_gaze: Optional[pd.DataFrame] = None,
    words: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Materialize one row per saccade with geometry and visual-angle units."""
    if fixations.empty:
        return pd.DataFrame()
    out = []
    analysis = fixations
    if "excluded" in analysis:
        analysis = analysis.loc[~analysis["excluded"].fillna(False).astype(bool)]
    keys = grouping_columns(analysis)
    # PERF-3: the letter-position of a saccade's launch and landing used to be
    # resolved by scanning the WHOLE words frame per fixation — a `to_numeric`
    # over every word id plus a boolean mask, twice per saccade. On the bundled
    # demo that was ~19 s of a rerun on its own, and it grew with corpus × trial
    # count. Index the geometry once instead: (identity…, word_id) → the four
    # numbers the formula needs.
    word_geometry = _word_letter_geometry(words, keys)
    for identity, chunk in analysis.groupby(keys, sort=False, dropna=False):
        identity = identity if isinstance(identity, tuple) else (identity,)
        chunk = chunk.sort_values("timestamp_ms")
        records = chunk.to_dict("records")
        for start, end in zip(records, records[1:]):
            dx, dy = float(end["x"] - start["x"]), float(end["y"] - start["y"])
            distance = math.hypot(dx, dy)
            start_duration = pd.to_numeric(start.get("duration_ms", 0), errors="coerce")
            start_end = float(start["timestamp_ms"]) + (
                float(start_duration) if pd.notna(start_duration) else 0.0
            )
            duration = max(float(end["timestamp_ms"]) - start_end, 0.0)
            peak_velocity = np.nan
            if raw_gaze is not None and not raw_gaze.empty and pixels_per_degree:
                gaze = raw_gaze
                for key, value in zip(keys, identity):
                    if key in gaze:
                        gaze = gaze[gaze[key] == value]
                if "timestamp_ms" in gaze:
                    gaze = gaze[
                        pd.to_numeric(gaze["timestamp_ms"], errors="coerce").between(
                            start_end, float(end["timestamp_ms"])
                        )
                    ].sort_values("timestamp_ms")
                    if len(gaze) >= 2:
                        dt = pd.to_numeric(gaze["timestamp_ms"], errors="coerce").diff()
                        gd = np.hypot(
                            pd.to_numeric(gaze["x"], errors="coerce").diff(),
                            pd.to_numeric(gaze["y"], errors="coerce").diff(),
                        )
                        speed = gd / dt.replace(0, np.nan) / pixels_per_degree * 1000
                        peak_velocity = float(speed.max())

            def _letter_position(event, _identity=identity):
                return _letter_position_in_word(event, word_geometry, _identity)

            row = dict(zip(keys, identity))
            row.update(
                xs=start["x"],
                ys=start["y"],
                xe=end["x"],
                ye=end["y"],
                dX=dx,
                dY=dy,
                distance_px=distance,
                duration_ms=duration,
                angle=math.degrees(math.atan2(-dy, dx)),
                amplitude_deg=distance / pixels_per_degree
                if pixels_per_degree and pixels_per_degree > 0
                else np.nan,
                peak_velocity_deg_s=peak_velocity,
                blink_before=bool(start.get("blink_before", False)),
                blink_after=bool(end.get("blink_after", False)),
                launch_word_id=start.get("word_id"),
                landing_word_id=end.get("word_id"),
                launch_line=start.get("line_id", start.get("line_idx")),
                landing_line=end.get("line_id", end.get("line_idx")),
                launch_letter=_letter_position(start),
                landing_letter=_letter_position(end),
            )
            out.append(row)
    return pd.DataFrame(out)


def measure_sensitivity(
    words: pd.DataFrame,
    fixations: pd.DataFrame,
    methods: tuple[str, ...] = ("attach", "slice", "consensus"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Word-measure spread under several line assignments (PRE-18)."""
    from . import alignment
    from .measures import compute_per_word_measures

    trial_keys = grouping_columns(fixations)
    if trial_keys != grouping_columns(words):
        raise ValueError("Words and fixations use different part identities.")
    combined_parts = []
    report_parts = []
    groups = (
        fixations.groupby(trial_keys, sort=False, dropna=False)
        if trial_keys
        else [((), fixations)]
    )
    for identity, trial_fixations in groups:
        identity = identity if isinstance(identity, tuple) else (identity,)
        trial_words = words
        for key, value in zip(trial_keys, identity):
            trial_words = trial_words[trial_words[key] == value]
        if trial_words.empty:
            continue
        trial_combined, trial_report = alignment.correction_sensitivity(
            trial_fixations, trial_words, methods
        )
        for key, value in zip(trial_keys, identity):
            trial_report[key] = value
        combined_parts.append(trial_combined)
        report_parts.append(trial_report)
    combined = (
        pd.concat(combined_parts).sort_index() if combined_parts else fixations.copy()
    )
    correction_report = (
        pd.concat(report_parts, ignore_index=True)
        if report_parts
        else pd.DataFrame(columns=[*trial_keys, "algorithm"])
    )
    keys = grouping_columns(words, include_word=True)
    merged = words[keys].drop_duplicates().copy()
    headline = (
        "first_fixation_ms",
        "first_pass_gaze_duration_ms",
        "regression_path_duration_ms",
        "total_fixation_duration_ms",
    )
    for method in methods:
        corrected = fixations.copy()
        corrected["y"] = combined[f"y_{method}"]
        measured = compute_per_word_measures(corrected, words)
        keep = [column for column in headline if column in measured]
        measured = measured[keys + keep].rename(
            columns={column: f"{column}_{method}" for column in keep}
        )
        merged = merged.merge(measured, on=keys, how="left")
    for metric in headline:
        columns = [
            f"{metric}_{method}" for method in methods if f"{metric}_{method}" in merged
        ]
        if columns:
            merged[f"{metric}_spread"] = merged[columns].max(axis=1) - merged[
                columns
            ].min(axis=1)
    return merged, correction_report
