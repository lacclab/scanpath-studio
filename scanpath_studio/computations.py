"""The computation register (VAL-5).

Every operation that **derives or semantically changes a value** a user, an
export or an API consumer can see, recorded once with its formula, its units,
its missing-data behaviour, and how far it has actually been verified. Pure UI
layout and byte-preserving file I/O are out of scope; filtering, precedence and
assignment are in, because they change *which observations* a result stands for
even when no arithmetic happens.

This module is data, not behaviour. It exists so that

* ``tests/test_computations.py`` can assert the catalogue has not drifted from
  the code — every ``aggregation.MEASURES`` entry, every drift-correction
  algorithm and every similarity metric must map to an entry here, and every
  entry must point at a function that exists;
* ``docs/computations.md`` can be generated from one source rather than
  maintained in parallel with it (``python -m scanpath_studio.computations``).

**Verification tiers.** ``A`` a hand-calculated synthetic oracle · ``B`` an
independent reference implementation or corpus comparison · ``C`` property /
invariant tests · ``D`` cross-surface parity (UI, API, CLI, export agree).

**Status is deliberately conservative.** *Verified* means a semantic oracle
exists and passes — not that a line of code was executed. Tier B is
systematically absent: it needs an independent implementation to compare
against, which is #VAL-4, on hold at the user's request until the register
itself has been read. Every scientific measure therefore reads *Partially
verified* even where its hand oracle is exact, and that is the honest state of
the world rather than a gap to paper over. *Convention* marks a choice that
cannot be right or wrong, only documented — a display transform, a tie-break, a
default threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Bumped when an entry's *meaning* changes (a formula, a unit, a default), not
#: when prose is edited. Exported alongside results so a bundle can name the
#: methodology it was produced under.
REGISTER_VERSION = "1"

CATEGORY_IMPORTED = "Imported / precomputed"
CATEGORY_NORMALIZATION = "Normalization / inference"
CATEGORY_ASSIGNMENT = "Assignment / classification"
CATEGORY_PREPROCESSING = "Preprocessing"
CATEGORY_MEASURE = "Scientific measure"
CATEGORY_AGGREGATION = "Statistical aggregation / test"
CATEGORY_SIMILARITY = "Similarity"
CATEGORY_GEOMETRY = "Unit / coordinate conversion"
CATEGORY_DISPLAY = "Display / export transformation"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_IMPORTED,
    CATEGORY_NORMALIZATION,
    CATEGORY_ASSIGNMENT,
    CATEGORY_PREPROCESSING,
    CATEGORY_MEASURE,
    CATEGORY_AGGREGATION,
    CATEGORY_SIMILARITY,
    CATEGORY_GEOMETRY,
    CATEGORY_DISPLAY,
)

STATUS_VERIFIED = "Verified"
STATUS_PARTIAL = "Partially verified"
STATUS_UNVERIFIED = "Unverified"
STATUS_CONVENTION = "Intentional convention"

STATUSES: tuple[str, ...] = (
    STATUS_VERIFIED,
    STATUS_PARTIAL,
    STATUS_UNVERIFIED,
    STATUS_CONVENTION,
)


@dataclass(frozen=True)
class Computation:
    """One derived value, with everything needed to reproduce and judge it."""

    id: str
    name: str
    category: str
    summary: str
    formula: str
    code: str
    output: str = ""
    unit: str = ""
    grouping: str = ""
    missing: str = ""
    precedence: str = ""
    tiers: str = ""
    status: str = STATUS_UNVERIFIED
    reference: str = ""
    consumers: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)

    @property
    def module(self) -> str:
        return self.code.split(":", 1)[0]

    @property
    def symbol(self) -> str:
        return self.code.split(":", 1)[1] if ":" in self.code else ""


_UI = "UI"
_API = "API"
_CLI = "CLI"
_EXPORT = "Export"
_CORPUS = "Corpus Analysis"
_INSPECT = "Data Inspection"


REGISTER: tuple[Computation, ...] = (
    # ------------------------------------------------------------------
    # Normalization / inference
    # ------------------------------------------------------------------
    Computation(
        id="norm.words",
        name="Word table normalization",
        category=CATEGORY_NORMALIZATION,
        summary="Map an arbitrary word/IA export onto the canonical word columns.",
        formula=(
            "For each canonical field, `pick_column` walks a candidate list and "
            "takes the first column that exists; the user's mapping overrides it. "
            "Unmapped optional fields are dropped unless listed in "
            "`WORD_OPTIONAL_FIELDS`."
        ),
        code="scanpath_studio/data.py:normalize_words",
        output="participant_id, trial_id, text_id, word_id, text, x, y, width, height",
        precedence="An explicit user mapping always beats auto-detection.",
        missing="A missing *required* field raises with the columns it looked for.",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_data.py", "tests/test_column_mapping.py"),
    ),
    Computation(
        id="norm.fixations",
        name="Fixation table normalization",
        category=CATEGORY_NORMALIZATION,
        summary="Map an arbitrary fixation report onto the canonical columns.",
        formula=(
            "As `norm.words`, over the fixation candidate lists. `order_in_trial` "
            "is assigned by sorting each trial on `timestamp_ms`; `fixation_id` is "
            "synthesized per trial when the export carries none."
        ),
        code="scanpath_studio/data.py:normalize_fixations",
        output="participant_id, trial_id, x, y, duration_ms, timestamp_ms, …",
        grouping="(participant_id, trial_id[, screen_id])",
        missing="Rows with no coordinates survive when a word/AoI id is mapped.",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_data.py",),
    ),
    Computation(
        id="norm.box_edges",
        name="Word box from edges",
        category=CATEGORY_NORMALIZATION,
        summary="Convert EyeLink IA edges to origin+size.",
        formula=(
            "x = IA_LEFT · y = IA_TOP · width = IA_RIGHT − IA_LEFT · "
            "height = IA_BOTTOM − IA_TOP."
        ),
        code="scanpath_studio/data.py:normalize_words",
        output="x, y, width, height",
        unit="px (screen coordinates, y increasing downwards)",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_word_box_geometry.py",),
    ),
    Computation(
        id="norm.trial_id_composite",
        name="Composite trial identity",
        category=CATEGORY_NORMALIZATION,
        summary="Build one unique trial id from several columns.",
        formula=(
            "The mapped Trial ID columns are joined in the order given, "
            "separated by `_`, after casting each to string."
        ),
        code="scanpath_studio/data.py:normalize_fixations",
        output="trial_id",
        missing="A row missing any component keeps the literal string of that part.",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_trial_identity.py",),
    ),
    Computation(
        id="norm.flags",
        name="Flag coercion",
        category=CATEGORY_NORMALIZATION,
        summary="Read EyeLink's string booleans as booleans (BUG-7).",
        formula=(
            "Numbers go by `!= 0`. Strings are matched case-insensitively "
            "against `{'', '.', '0', '0.0', 'false', 'f', 'no', 'n', 'na', "
            "'nan', '-'}` → False; anything else → True."
        ),
        code="scanpath_studio/data.py:coerce_flag",
        output="bool",
        missing="NaN → False.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        reference="Guards the `'.'`-as-missing convention in EyeLink IA reports.",
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_data.py",),
    ),
    Computation(
        id="norm.stimulus_broadcast",
        name="Stimulus-level word broadcast",
        category=CATEGORY_NORMALIZATION,
        summary="Share one stimulus' word boxes across every reader of it.",
        formula=(
            "Words with no participant column are replicated once per "
            "participant found in the fixations for the same text."
        ),
        code="scanpath_studio/data.py:harmonize_frames",
        missing="No fixations for a text ⇒ its words are not broadcast.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_data.py",),
    ),
    Computation(
        id="norm.aoi_center_placement",
        name="AoI-only fixation placement",
        category=CATEGORY_NORMALIZATION,
        summary="Place a fixation with no x/y at its word box's center.",
        formula="x = word.x + width/2 · y = word.y + height/2.",
        code="scanpath_studio/data.py:harmonize_frames",
        unit="px",
        precedence="Only when x/y are absent; recorded coordinates always win.",
        missing="No matching word box ⇒ the fixation keeps no coordinates.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_data.py",),
    ),
    Computation(
        id="norm.participant_metadata",
        name="Participant metadata join",
        category=CATEGORY_NORMALIZATION,
        summary="Attach a participant-level table without broadcasting it (DATA-20).",
        formula=(
            "Left join on string `participant_id`. Duplicate ids that agree "
            "collapse; duplicate ids that **disagree** are dropped and reported, "
            "so no `groupby.first()` winner is ever invented. A field is "
            "projected onto the per-trial frame, never onto word/fixation rows."
        ),
        code="scanpath_studio/metadata.py:build_participant_metadata",
        output="One column per registered field, at participant grain",
        missing="A reader with no row reads as missing everywhere, never as a default.",
        precedence="A real recorded column of the same name always wins.",
        tiers="A, C, D",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI, _EXPORT, _INSPECT),
        tests=("tests/test_metadata.py",),
    ),
    # ------------------------------------------------------------------
    # Assignment / classification
    # ------------------------------------------------------------------
    Computation(
        id="assign.fixation_to_word",
        name="Fixation → word assignment",
        category=CATEGORY_ASSIGNMENT,
        summary="The single highest-risk step: which word a fixation counts for.",
        formula=(
            "1. Bounding-box containment against the trial's word boxes, using "
            "the BUG-11 corrected edges (`word_box_bounds`), so a fixation in the "
            "whitespace *before* a word is credited to that word. "
            "2. Otherwise the nearest word **center** within "
            "`LINE_MISREGISTRATION_PX` = 50 px. "
            "3. Otherwise `word_id = NaN` (out of text)."
        ),
        code="scanpath_studio/measures.py:assign_fixations_to_words",
        output="word_id",
        grouping="(participant_id, trial_id[, screen_id]) — never across screens",
        missing="Unassignable fixations keep NaN and are excluded from word measures.",
        precedence="An imported `word_id` is kept unless `overwrite=True`.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        reference=(
            "The nearest-center fallback is common practice for line "
            "misregistration; the 50 px radius is this app's choice, not a "
            "standard."
        ),
        consumers=(_UI, _API, _CLI, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="assign.in_text",
        name="Out-of-text flag",
        category=CATEGORY_ASSIGNMENT,
        summary="Whether a fixation landed on any word of the stimulus.",
        formula="`word_id` is not NaN after `assign.fixation_to_word`.",
        code="scanpath_studio/measures.py:fixation_in_text_mask",
        output="bool mask",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CORPUS),
        tests=("tests/test_synthetic.py",),
    ),
    Computation(
        id="assign.line_cluster",
        name="Visual line clustering",
        category=CATEGORY_ASSIGNMENT,
        summary="Derive text lines from word-box geometry, not from `line_idx`.",
        formula=(
            "Word boxes are sorted by `y` and split wherever the gap between "
            "consecutive centers exceeds `tol_frac` (0.5) of the median box "
            "height. Exists because `line_idx` is a constant in many IA exports."
        ),
        code="scanpath_studio/measures.py:cluster_word_lines",
        output="line index per word",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="assign.runs",
        name="Runs and passes",
        category=CATEGORY_ASSIGNMENT,
        summary="Trial run, line run, and per-word visit/pass indices (PRE-16).",
        formula=(
            "Consecutive fixations on the same word form one *visit*; the n-th "
            "visit to a word is its n-th pass. Line runs break whenever the "
            "assigned line changes."
        ),
        code="scanpath_studio/measures.py:materialize_runs",
        output="run, linerun, word_runid, pass_index",
        grouping="Ordered by `timestamp_ms` within a trial",
        precedence="An imported `pass_index` / `reread` column is kept.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="assign.progression",
        name="Progression and regression flags",
        category=CATEGORY_ASSIGNMENT,
        summary="Whether the *outgoing* saccade moves forward in the text.",
        formula=(
            "`progression = sign(next word_id − word_id)`. "
            "`is_regression = word_id < running max word_id in the trial` — i.e. "
            "relative to the furthest word reached, not to the previous fixation."
        ),
        code="scanpath_studio/measures.py:enrich_fixations",
        output="progression ∈ {−1, 0, 1}, is_regression",
        grouping="Per trial, in timestamp order",
        missing="Unassigned fixations give progression 0.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="assign.saccade_class",
        name="Saccade reading class",
        category=CATEGORY_ASSIGNMENT,
        summary="Label each outgoing saccade by its reading role (VIZ-8).",
        formula=(
            "Forward within a line, return sweep (large leftward drop to the "
            "next line), within-line regression, or between-line regression, "
            "from the assigned line and word order."
        ),
        code="scanpath_studio/measures.py:classify_saccades",
        output="saccade_type",
        precedence="An imported `saccade_type` / `NEXT_SAC_DIRECTION` is kept.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_saccade_class_filter.py",),
    ),
    # ------------------------------------------------------------------
    # Scientific measures
    # ------------------------------------------------------------------
    Computation(
        id="measure.ffd",
        name="First fixation duration (FFD)",
        category=CATEGORY_MEASURE,
        summary="Duration of the first fixation on a word during first pass.",
        formula="Duration of the first fixation of the word's first-pass run.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="first_fixation_ms",
        unit="ms",
        grouping="(participant, trial, word)",
        missing="Skipped word ⇒ NaN, not 0.",
        precedence="A precomputed `IA_FIRST_FIXATION_DURATION` wins.",
        tiers="A, D",
        status=STATUS_PARTIAL,
        reference="Rayner (1998), standard reading-measure definitions.",
        consumers=(_UI, _API, _CLI, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.fprt",
        name="First-pass gaze duration (FPRT)",
        category=CATEGORY_MEASURE,
        summary="Sum of first-pass fixations on a word.",
        formula=(
            "Sum of every fixation in the word's **first** run, i.e. before the "
            "gaze leaves the word for the first time."
        ),
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="first_pass_gaze_duration_ms",
        unit="ms",
        grouping="(participant, trial, word)",
        missing="Skipped word ⇒ NaN.",
        precedence="A precomputed IA gaze duration wins.",
        tiers="A, D",
        status=STATUS_PARTIAL,
        reference="Rayner (1998).",
        consumers=(_UI, _API, _CLI, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.rpd",
        name="Regression-path duration (RPD / go-past)",
        category=CATEGORY_MEASURE,
        summary="First entry to the word until the gaze passes it to the right.",
        formula=(
            "Total time from the first first-pass fixation on the word until the "
            "first fixation on a **later** word — including any regressions to "
            "earlier words in between."
        ),
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="regression_path_duration_ms",
        unit="ms",
        grouping="(participant, trial, word)",
        missing="Skipped word ⇒ NaN.",
        tiers="A",
        status=STATUS_PARTIAL,
        reference=(
            "Definitions differ across toolkits (go-past vs regression path); "
            "#PRE-4 names `eyekit` as the intended comparison. Unresolved until "
            "#VAL-4 runs."
        ),
        consumers=(_UI, _API, _CLI, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.tfd",
        name="Total fixation duration (TFD)",
        category=CATEGORY_MEASURE,
        summary="All time spent on a word across the whole trial.",
        formula="Sum of every fixation assigned to the word, any pass.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="total_fixation_duration_ms",
        unit="ms",
        missing="Never fixated ⇒ 0 (the word *was* read past; it got no time).",
        precedence="A precomputed IA dwell time wins.",
        tiers="A, D",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.nfix",
        name="Fixations per word",
        category=CATEGORY_MEASURE,
        summary="Count of fixations assigned to a word.",
        formula="Row count of the word's assigned fixations.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="n_fixations",
        missing="Never fixated ⇒ 0.",
        tiers="A",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_synthetic.py",),
    ),
    Computation(
        id="measure.skip",
        name="Skip flag / skip rate",
        category=CATEGORY_MEASURE,
        summary="Whether a word received no first-pass fixation.",
        formula="`skip_flag = no fixation in the word's first pass`.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="skip_flag",
        unit="rate when aggregated (0–1)",
        missing="A word fixated only after a regression still counts as skipped.",
        tiers="A",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.regressions",
        name="Regression in/out flags",
        category=CATEGORY_MEASURE,
        summary="Whether a word was returned to, or left backwards.",
        formula=(
            "`regression_in_flag` — some later fixation lands on this word after "
            "the gaze had moved past it. `regression_out_flag` — a fixation on "
            "this word is followed by a fixation on an earlier word."
        ),
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="regression_in_flag, regression_out_flag",
        unit="rate when aggregated (0–1)",
        precedence="Precomputed IA regression flags win (see `norm.flags`).",
        tiers="A",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py", "tests/test_synthetic.py"),
    ),
    Computation(
        id="measure.landing_position",
        name="Initial landing position",
        category=CATEGORY_MEASURE,
        summary="Where in the word the first fixation landed, in letters.",
        formula=(
            "`char_width = geom.word_char_advance`; "
            "`offset = first_fix_x − word.x` (LTR) or "
            "`word.x + width − first_fix_x` (RTL); "
            "`landing_position = offset / char_width + 1` — so the first letter "
            "starts at 1 and its centre is 1.5."
        ),
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="initial_landing_position",
        unit="letters",
        missing="No first-pass fixation, zero width, or no text ⇒ NaN.",
        precedence=(
            "VAL-5: the scale is `geom.word_char_advance`, not the local "
            "`width / len(text)` this used before — on a tiling corpus that "
            "divided a box of `n + 1` advances by `n` characters, reporting "
            "every landing ~`(n+1)/n` too far into the word."
        ),
        tiers="A",
        status=STATUS_PARTIAL,
        reference=(
            "Assumes a monospaced advance within the word box — exact for the "
            "app's monospace default, approximate for proportional fonts."
        ),
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="measure.landing_distance",
        name="Centred landing distance",
        category=CATEGORY_MEASURE,
        summary="Landing position relative to the word's centre.",
        formula="`landing_position − (len(text) + 1) / 2`.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="initial_landing_distance",
        unit="letters (0 = word centre, negative = left of centre)",
        missing="As `measure.landing_position`.",
        tiers="A",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="measure.second_pass",
        name="Second-pass duration",
        category=CATEGORY_MEASURE,
        summary="Time spent on the word during its second visit.",
        formula="Sum of the fixations in the word's second run.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="second_pass_duration_ms",
        unit="ms",
        missing="Fewer than two passes ⇒ 0.",
        tiers="A",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="measure.single_fix",
        name="Single-fixation duration",
        category=CATEGORY_MEASURE,
        summary="First-pass duration when the first pass was exactly one fixation.",
        formula="FFD when the word's first run has length 1, else NaN.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="single_fixation_duration_ms",
        unit="ms",
        missing="Multi-fixation or skipped first pass ⇒ NaN.",
        tiers="A",
        status=STATUS_PARTIAL,
        reference="Rayner (1998).",
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="measure.reg_in_count",
        name="Regressions into word",
        category=CATEGORY_MEASURE,
        summary="How many times the gaze came back to this word.",
        formula="Number of runs on the word after the first.",
        code="scanpath_studio/measures.py:compute_per_word_measures",
        output="number_of_regressions_in",
        missing="Never revisited ⇒ 0.",
        tiers="A",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="fix.saccade_amplitude",
        name="Saccade amplitude",
        category=CATEGORY_MEASURE,
        summary="Distance between consecutive fixations — always pixels (BUG-25).",
        formula="`sqrt(dx² + dy²)` between consecutive fixations in the trial.",
        code="scanpath_studio/measures.py:enrich_fixations",
        output="saccade_amplitude",
        unit="px",
        grouping="Per trial, in timestamp order; the first fixation has none.",
        missing="First fixation of a trial ⇒ NaN.",
        precedence=(
            "A source column literally named `saccade_amplitude` is assumed to "
            "be pixels and kept. EyeLink's **degree**-valued "
            "`NEXT_SAC_AMPLITUDE` / `PREVIOUS_SAC_AMPLITUDE` normalize to "
            "`next_/prev_saccade_amplitude_deg` and never reach this column — "
            "they are different quantities *and* different saccades."
        ),
        tiers="A, C",
        status=STATUS_VERIFIED,
        reference=(
            "#BUG-25: before the fix, one column meant px or deg depending on "
            "which columns the export carried (~78x apart on the bundled demo) "
            "under a hard-coded 'px' label."
        ),
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="fix.angles",
        name="Saccade angles",
        category=CATEGORY_MEASURE,
        summary="Incoming and outgoing saccade direction.",
        formula=(
            "`angle_incoming = degrees(atan2(−dy, dx))` from the previous "
            "fixation; `angle_outgoing` is the next fixation's incoming angle. "
            "`−dy` because screen y grows downwards, so 0° is rightward and "
            "positive is up."
        ),
        code="scanpath_studio/measures.py:enrich_fixations",
        output="angle_incoming, angle_outgoing",
        unit="degrees (−180, 180]",
        missing="Trial edges ⇒ NaN.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="fix.rebased_onsets",
        name="Rebased fixation onsets",
        category=CATEGORY_MEASURE,
        summary="Trial-relative onset times for animation and time series.",
        formula=(
            "Cumulative onsets rebased so the trial starts at 0, from "
            "`timestamp_ms` where present, else by accumulating durations."
        ),
        code="scanpath_studio/measures.py:rebased_fixation_onsets",
        output="onset array",
        unit="ms",
        missing="A backwards clock restarts the accumulation (see VAL-7).",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_measures.py",),
    ),
    # ------------------------------------------------------------------
    # Preprocessing
    # ------------------------------------------------------------------
    Computation(
        id="pre.merge_short",
        name="Short-fixation merging",
        category=CATEGORY_PREPROCESSING,
        summary="Fold a short fixation into a neighbour within a character distance.",
        formula=(
            "A fixation below the short threshold is merged into the nearer "
            "adjacent fixation when that neighbour is within the merge distance, "
            "expressed in characters and converted to px via "
            "`geom.word_char_advance`. Durations add; position follows the "
            "survivor."
        ),
        precedence=(
            "#BUG-27: the conversion reads the shared letter scale. It used to "
            'divide by `len(text)`, so on a tiling corpus "within 1 character" '
            "meant 1.25 characters for a four-letter word and 1.07 for a "
            "fifteen-letter one — a threshold whose meaning varied with the word "
            "it was applied to."
        ),
        code="scanpath_studio/preprocessing.py:merge_short_fixations",
        output="A reduced fixation frame",
        unit="ms threshold, characters distance",
        missing="Off by default; original rows stay available.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        reference="A common cleaning step; thresholds are the user's choice.",
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.exclude_short",
        name="Short/long fixation exclusion",
        category=CATEGORY_PREPROCESSING,
        summary="Soft-exclude fixations outside a duration window.",
        formula="Drop fixations shorter than / longer than the chosen bounds.",
        code="scanpath_studio/preprocessing.py:preprocess_fixations",
        unit="ms",
        missing="Soft: excluded rows are reported, not deleted from the source.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.blink_adjacent",
        name="Blink-adjacent exclusion",
        category=CATEGORY_PREPROCESSING,
        summary="Drop fixations immediately before/after a blink.",
        formula="Exclude the fixations neighbouring any row flagged `is_blink`.",
        code="scanpath_studio/preprocessing.py:preprocess_fixations",
        missing="No blink column ⇒ the option has no effect.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.cleaning_report",
        name="Cleaning QA report",
        category=CATEGORY_PREPROCESSING,
        summary="What the preprocessing pass would remove, and why.",
        formula="Counts per exclusion reason over the unfiltered frame.",
        code="scanpath_studio/preprocessing.py:cleaning_report",
        output="Cleaning QA table",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _EXPORT, _INSPECT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.sentence_measures",
        name="Sentence-level measures",
        category=CATEGORY_PREPROCESSING,
        summary="Per-sentence reading time and counts.",
        formula=(
            "Words are grouped into sentences by `infer_sentence_ids` "
            "(terminal punctuation), then the word measures are summed per "
            "sentence."
        ),
        code="scanpath_studio/preprocessing.py:sentence_measures",
        output="Sentences table",
        unit="ms, counts",
        missing="Sentence inference is textual, not annotated — approximate.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _INSPECT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.saccade_table",
        name="Saccade table",
        category=CATEGORY_PREPROCESSING,
        summary="One row per saccade, with amplitude, angle and class.",
        formula=(
            "Consecutive fixation pairs within a trial; amplitude in px, and in "
            "degrees only when `pixels_per_degree` is supplied."
        ),
        code="scanpath_studio/preprocessing.py:saccade_table",
        output="Saccades table",
        unit="px, deg (when geometry is known), ms",
        missing="Assumed geometry ⇒ the degree columns inherit that assumption.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _EXPORT, _INSPECT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.character_grid",
        name="Character grid",
        category=CATEGORY_PREPROCESSING,
        summary="Per-character boxes derived from word boxes.",
        formula=(
            "Character `k` of a word spans `x + (k−1) × advance` to `x + k × "
            "advance`, where the advance is `geom.word_char_advance`."
        ),
        code="scanpath_studio/preprocessing.py:character_grid",
        unit="px",
        missing="Proportional fonts make this an approximation.",
        precedence=(
            "#BUG-27: the advance is the shared letter scale, not `width / "
            "len(text)` — which on a tiling corpus stretched the glyph row "
            "across the trailing inter-word padding, so each character box after "
            "the first sat progressively further right than its glyph."
        ),
        tiers="A, C",
        status=STATUS_CONVENTION,
        consumers=(_UI, _EXPORT, _INSPECT),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.rtl",
        name="Right-to-left detection",
        category=CATEGORY_PREPROCESSING,
        summary="Whether a word's script runs right to left.",
        formula="Unicode range test over the word's characters.",
        code="scanpath_studio/preprocessing.py:detect_right_to_left",
        output="right_to_left",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CORPUS),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="pre.sensitivity",
        name="Measure sensitivity",
        category=CATEGORY_PREPROCESSING,
        summary="How much a measure moves under different cleaning settings.",
        formula="The measure is recomputed per setting and compared to baseline.",
        code="scanpath_studio/preprocessing.py:measure_sensitivity",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API),
        tests=("tests/test_preprocessing.py",),
    ),
    Computation(
        id="align.algorithms",
        name="Vertical drift correction",
        category=CATEGORY_PREPROCESSING,
        summary="Line-assignment algorithms, ported natively (PRE-3).",
        formula=(
            "The ten Carr et al. algorithms — `attach`, `chain`, `cluster`, "
            "`compare`, `merge`, `regress`, `segment`, `split`, `stretch`, "
            "`warp` — plus `slice` and a `consensus` vote over them. Each "
            "reassigns fixation *y* to a text line. Hidden unless "
            "`SCANPATH_EXPERIMENTAL=1` (#PRE-21)."
        ),
        code="scanpath_studio/alignment.py:correct",
        output="Corrected fixation y (display only; exported tables stay raw)",
        missing="Off by default; the original coordinates are never overwritten.",
        tiers="B, C",
        status=STATUS_PARTIAL,
        reference=(
            "Carr, Pescuma, Furlan, Ktori & Crepaldi (2021), *Algorithms for the "
            "automated correction of vertical drift in eye-tracking data*, "
            "Behavior Research Methods. Ported from the reference implementation "
            "— the one entry with a genuine tier-B comparison."
        ),
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_alignment.py", "tests/test_cli_drift.py"),
    ),
    # ------------------------------------------------------------------
    # Aggregation / statistics
    # ------------------------------------------------------------------
    Computation(
        id="agg.measure_values",
        name="Measure value extraction",
        category=CATEGORY_AGGREGATION,
        summary="Pull one registered measure's values out of a frame.",
        formula=(
            "The `aggregation.MEASURES` entry names the frame (words or "
            "fixations), the column and the unit; values are coerced numeric and "
            "NaNs dropped."
        ),
        code="scanpath_studio/aggregation.py:measure_values",
        missing="Non-numeric entries become NaN and are dropped, not zeroed.",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.aggregate_value",
        name="Central tendency",
        category=CATEGORY_AGGREGATION,
        summary="The Aggregate selector: mean / median / sum.",
        formula="`np.nanmean` · `np.nanmedian` · `np.nansum` over the values.",
        code="scanpath_studio/aggregation.py:aggregate_value",
        missing="NaN-skipping throughout; an all-NaN input gives NaN.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.spread",
        name="Spread band",
        category=CATEGORY_AGGREGATION,
        summary="The error band drawn around an aggregate.",
        formula=(
            "`SD` → ±1 sample std (ddof=1) · `SEM` → ±std/√n · `IQR` → the 25th "
            "and 75th percentiles · `Bootstrap CI` → `agg.bootstrap_ci`. With "
            "`agg='sum'`, SD/SEM fall back to the bootstrap: the spread of "
            "individual observations does not bracket a total."
        ),
        code="scanpath_studio/aggregation.py:spread_bounds",
        missing="Empty input or NaN centre ⇒ a zero-width band.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.bootstrap_ci",
        name="Bootstrap confidence interval",
        category=CATEGORY_AGGREGATION,
        summary="Percentile bootstrap CI of the chosen aggregate.",
        formula=(
            "1000 resamples with replacement; the CI is the 2.5th and 97.5th "
            "percentiles of the resampled statistic."
        ),
        code="scanpath_studio/aggregation.py:bootstrap_ci",
        unit="same as the measure",
        missing="n < 2 ⇒ a degenerate interval at the point estimate.",
        precedence="Seeded (`seed=0`) — the same data gives the same interval.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        reference="Percentile bootstrap; no bias correction.",
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.effect_size",
        name="Group comparison and effect size",
        category=CATEGORY_AGGREGATION,
        summary="Mean difference, Cohen's d, and a significance test (AN-21).",
        formula=(
            "`mean_diff = mean(A) − mean(B)`. Cohen's *d* uses the pooled SD "
            "`sqrt(((nA−1)·varA + (nB−1)·varB) / (nA+nB−2))` with ddof=1. The "
            "test is Mann–Whitney U (two-sided) or Welch's t-test."
        ),
        code="scanpath_studio/aggregation.py:group_effect_size",
        output="mean_a, mean_b, mean_diff, cohen_d, statistic, p_value, n_a, n_b",
        missing=(
            "n < 2 in either group ⇒ NaN statistics. A zero pooled SD gives "
            "**NaN**, not 0.0, so it cannot read as 'no effect' beside a "
            "non-zero mean difference."
        ),
        tiers="A, C",
        status=STATUS_PARTIAL,
        reference=(
            "**Exploratory, not pre-registered.** No multiple-comparison "
            "correction is applied; the p-value is descriptive."
        ),
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.group_mask",
        name="Group definition",
        category=CATEGORY_AGGREGATION,
        summary="Which rows belong to a cohort.",
        formula=(
            "A spec maps column → allowed values; the mask is the conjunction of "
            "membership tests. Two modes: split one field, or two independent "
            "filter sets."
        ),
        code="scanpath_studio/aggregation.py:group_mask",
        missing="A column absent from the frame contributes no constraint.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.word_profile",
        name="Per-word cohort profile",
        category=CATEGORY_AGGREGATION,
        summary="A measure per word position, aggregated across readers.",
        formula="Group the word measures by word id and apply `agg.aggregate_value`.",
        code="scanpath_studio/aggregation.py:cohort_word_profile",
        missing="A minimum-readers threshold drops thinly-sampled words.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.word_rates",
        name="Skip / regression rate profile",
        category=CATEGORY_AGGREGATION,
        summary="Rate measures per word.",
        formula="Mean of the 0/1 flag over readers — a proportion in [0, 1].",
        code="scanpath_studio/aggregation.py:word_rate_profile",
        unit="proportion",
        missing="Words with no reader are omitted, not shown as 0.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.reader_summary",
        name="Per-reader summary",
        category=CATEGORY_AGGREGATION,
        summary="One row per reader: totals, means and rates.",
        formula=(
            "Counts and NaN-skipping means over that reader's rows. "
            "`mean_saccade_px` is the mean of `fix.saccade_amplitude` and is "
            "genuinely pixels since #BUG-25."
        ),
        code="scanpath_studio/aggregation.py:reader_summary_table",
        output="Readers table",
        unit="ms, px, counts, proportions",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS, _EXPORT, _INSPECT, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.trial_summary",
        name="Per-trial summary",
        category=CATEGORY_AGGREGATION,
        summary="One row per trial: reading time, counts, rates.",
        formula="Counts and sums over the trial's fixations and word measures.",
        code="scanpath_studio/aggregation.py:trial_summary_table",
        output="Trials table",
        unit="ms, counts",
        tiers="C, D",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS, _EXPORT, _INSPECT, _API),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.normalize",
        name="Normalized measure column",
        category=CATEGORY_AGGREGATION,
        summary="Rescale a measure for cross-reader comparison.",
        formula="Per-reader z-scoring or min–max, as chosen by the Normalize toggle.",
        code="scanpath_studio/aggregation.py:add_normalized_column",
        missing="Zero variance ⇒ the normalized column is NaN, not 0.",
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS,),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.landing_curve",
        name="Landing-position curve",
        category=CATEGORY_AGGREGATION,
        summary="Distribution of initial landing positions by word length.",
        formula=(
            "Histogram of the landing position as a *fraction* of the word's "
            "glyph run — `(first_fix_x − word.x) / (len(text) × "
            "geom.word_char_advance)`, so 0 is the first glyph's left edge and 1 "
            "the last glyph's right edge — binned per word length."
        ),
        code="scanpath_studio/aggregation.py:landing_positions",
        unit="fraction of the word (0–1), or px with `as_fraction=False`",
        precedence=(
            "#BUG-27: measured from the word's `x` and its glyph run, not from "
            "the `geom.word_box_bounds` AOI edge and the padded `width` — those "
            "put 0 half an inter-word space before the word and 1 half a space "
            "after it, so this disagreed with `measure.landing_position` on the "
            "same landing."
        ),
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS,),
        tests=("tests/test_aggregation.py",),
    ),
    Computation(
        id="agg.over_time",
        name="Trend over time",
        category=CATEGORY_AGGREGATION,
        summary="A measure by trial index or fixation index.",
        formula="Aggregate per index position across the selection.",
        code="scanpath_studio/aggregation.py:metric_over_time",
        missing="Index positions with no data are gaps, not zeros.",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_CORPUS,),
        tests=("tests/test_aggregation.py",),
    ),
    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------
    Computation(
        id="sim.nld",
        name="Normalized Levenshtein distance",
        category=CATEGORY_SIMILARITY,
        summary="Scanpath similarity over AoI sequences (gated by PRE-21).",
        formula=(
            "`levenshtein(a, b) / max(len(a), len(b))` ∈ [0, 1]; 0 is identical. "
            "Two empty sequences give 0."
        ),
        code="scanpath_studio/similarity.py:normalized_levenshtein",
        unit="dimensionless (0–1)",
        missing="Hidden unless `SCANPATH_EXPERIMENTAL=1`.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        reference="Standard edit-distance scanpath comparison.",
        consumers=(_UI, _API),
        tests=("tests/test_similarity.py",),
    ),
    Computation(
        id="sim.aoi_sequence",
        name="AoI sequence",
        category=CATEGORY_SIMILARITY,
        summary="The symbol string an NLD comparison runs on.",
        formula=(
            "Assigned `word_id`s in fixation order, with unassigned fixations "
            "dropped and (optionally) immediate repeats collapsed."
        ),
        code="scanpath_studio/similarity.py:aoi_sequence",
        missing="A trial with no assigned fixations yields an empty sequence.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API),
        tests=("tests/test_similarity.py",),
    ),
    Computation(
        id="sim.windowed",
        name="NLD by fixation index / time",
        category=CATEGORY_SIMILARITY,
        summary="Similarity restricted to a window of the scanpath.",
        formula="`sim.nld` over the sub-sequence inside the index or time window.",
        code="scanpath_studio/similarity.py:nld_by_fixation_index",
        tiers="C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API),
        tests=("tests/test_similarity.py",),
    ),
    # ------------------------------------------------------------------
    # Unit / coordinate conversion
    # ------------------------------------------------------------------
    Computation(
        id="geom.pixels_per_degree",
        name="Pixels per degree of visual angle",
        category=CATEGORY_GEOMETRY,
        summary="The screen-geometry conversion every angular unit depends on.",
        formula=(
            "`px_per_mm = canvas_width_px / monitor_width_mm`; "
            "`mm_per_degree = 2 · viewing_distance_mm · tan(0.5°)`; "
            "`px_per_degree = px_per_mm · mm_per_degree`."
        ),
        code="scanpath_studio/experimental_setup.py:pixels_per_degree",
        unit="px / degree",
        missing="Any missing geometry ⇒ no conversion is offered at all.",
        precedence=(
            "**Provenance matters more than the number.** Every built-in corpus "
            "carries `ASSUMED` geometry, so a degree-valued result inherits that "
            "assumption — see the *Recording setup* panel."
        ),
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_experimental_setup.py",),
    ),
    Computation(
        id="geom.font_pt_to_px",
        name="Font point size to pixels",
        category=CATEGORY_GEOMETRY,
        summary="Typography conversion for true-scale text rendering.",
        formula="`px = pt · dpi / 72`.",
        code="scanpath_studio/experimental_setup.py:font_pt_to_px",
        unit="px",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI),
        tests=("tests/test_experimental_setup.py",),
    ),
    Computation(
        id="geom.word_box_bounds",
        name="Corrected word-box edges",
        category=CATEGORY_GEOMETRY,
        summary="Where one word's box ends and the next begins (BUG-11).",
        formula=(
            "The inter-word gap is split so the whitespace before a word belongs "
            "to that word, rather than extending the previous box across it."
        ),
        code="scanpath_studio/measures.py:word_box_bounds",
        unit="px",
        precedence=(
            "Used by `assign.fixation_to_word` and by `agg.word_rates`' left "
            "edge — the boundary *between* words. A position *inside* a word "
            "goes through `geom.word_char_advance` instead, whose origin is the "
            "word's `x` (its first glyph); the two are half an advance apart by "
            "construction, which is what #BUG-27 settled."
        ),
        tiers="A, C",
        status=STATUS_PARTIAL,
        consumers=(_UI, _API, _CORPUS),
        tests=("tests/test_word_box_geometry.py", "tests/test_word_id_offset.py"),
    ),
    Computation(
        id="geom.word_box_space_px",
        name="Inter-word padding baked into each box",
        category=CATEGORY_GEOMETRY,
        summary="Detects a tiling layout that carries one trailing space per box.",
        formula=(
            "Median of `width / (len(text) + 1)` across one trial's words — the "
            "advance — reported only when the boxes are consistently that wide "
            "**and** actually tile (no gaps). Anything else ⇒ `0.0`, i.e. "
            "'these AOIs are glyph-tight, don't touch them'."
        ),
        code="scanpath_studio/measures.py:word_box_space_px",
        unit="px",
        missing="No usable words ⇒ 0.0 (no correction), never a guess.",
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT),
        tests=("tests/test_measures.py",),
    ),
    Computation(
        id="geom.word_char_advance",
        name="Character advance within a word",
        category=CATEGORY_GEOMETRY,
        summary="How wide one letter is — the scale for every within-word position.",
        formula=(
            "`width / (len(text) + 1)` when `geom.word_box_space_px` finds "
            "trailing padding, else `width / len(text)`."
        ),
        code="scanpath_studio/measures.py:word_char_advance",
        unit="px / character",
        missing="No `text`/`width` ⇒ NaN, and the letter measures report NaN.",
        precedence=(
            "The single accessor for the letter scale, as `geom.word_box_bounds` "
            "is for the boundary between words: `measure.landing_position`, "
            "`measure.landing_distance`, `agg.landing_curve` and the saccade "
            "table's launch/landing letter all read it. #BUG-27 — before that "
            "each derived its own `width / len(text)`, which is one advance too "
            "wide on a tiling corpus, by a factor that varied with word length."
        ),
        tiers="A, C",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _EXPORT, _CORPUS),
        tests=("tests/test_measures.py",),
    ),
    # ------------------------------------------------------------------
    # Display / export transformations
    # ------------------------------------------------------------------
    Computation(
        id="disp.marker_sizes",
        name="Fixation marker sizing",
        category=CATEGORY_DISPLAY,
        summary="Dot area encodes fixation duration.",
        formula=(
            "Durations are scaled between a minimum and maximum marker size "
            "across the drawn set. **Display only** — never a recorded value."
        ),
        code="scanpath_studio/plots.py:_compute_marker_sizes",
        unit="px (marker diameter)",
        precedence=(
            "Shared by single-trial, comparison and export builders so the same "
            "trial renders identically everywhere."
        ),
        tiers="C, D",
        status=STATUS_CONVENTION,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_plots.py", "tests/test_builder_parity.py"),
    ),
    Computation(
        id="disp.axis_ranges",
        name="Axis ranges and inversion",
        category=CATEGORY_DISPLAY,
        summary="Screen coordinates, drawn the way the screen is.",
        formula=(
            "The y axis is inverted (`y_range = [max, min]`) so the figure "
            "matches the display; ranges come from the canvas, not the data, "
            "when a canvas size is known."
        ),
        code="scanpath_studio/plots.py:_compute_axis_ranges",
        unit="px",
        tiers="C, D",
        status=STATUS_CONVENTION,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_plots.py",),
    ),
    Computation(
        id="disp.true_scale",
        name="True-scale text rendering",
        category=CATEGORY_DISPLAY,
        summary="One line of text fills its share of the recorded line pitch.",
        formula=(
            "Text is drawn at `1/line_spacing` of the word-box height the data "
            "already encodes, so the stimulus keeps the geometry it was read at."
        ),
        code="scanpath_studio/tabs.py:_render_true_scale_chart",
        precedence=(
            "The spatial plot must stay on this path — `st.plotly_chart` loses "
            "the scale guarantee."
        ),
        tiers="D",
        status=STATUS_CONVENTION,
        consumers=(_UI,),
        tests=("tests/test_plots.py",),
    ),
    Computation(
        id="disp.animation_timing",
        name="Animation timing",
        category=CATEGORY_DISPLAY,
        summary="How recorded time maps to playback time.",
        formula=(
            "Frames follow `fix.rebased_onsets`, scaled by the playback speed. "
            "A multipart replay changes screen at the boundary and draws no "
            "connector across canvases."
        ),
        code="scanpath_studio/plots.py:make_scanpath_animation",
        unit="ms (recorded) → ms (playback)",
        tiers="C, D",
        status=STATUS_CONVENTION,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_animation_export.py",),
    ),
    Computation(
        id="disp.illustration",
        name="Illustration disclosure",
        category=CATEGORY_DISPLAY,
        summary="When a figure stops being a faithful record.",
        formula=(
            "Geometry-changing or synthetic views (drift correction applied, "
            "authored scanpaths, model-generated paths) are detected and labelled "
            "so a display transform is never read as recorded data."
        ),
        code="scanpath_studio/illustration.py:illustration_reasons",
        tiers="C, D",
        status=STATUS_VERIFIED,
        consumers=(_UI, _API, _CLI, _EXPORT),
        tests=("tests/test_illustration.py", "tests/test_disclosure.py"),
    ),
)

BY_ID = {entry.id: entry for entry in REGISTER}


def entries_in(category: str) -> tuple[Computation, ...]:
    """Every register entry in one category, in declaration order."""
    return tuple(entry for entry in REGISTER if entry.category == category)


def to_markdown() -> str:
    """Render the register as the ``docs/computations.md`` page.

    Generated rather than hand-maintained so the documentation cannot drift
    from the catalogue the integrity tests check.
    """
    lines: list[str] = [
        "<!-- Generated by `python -m scanpath_studio.computations`. Do not edit. -->",
        "",
        "# Computations & methodology",
        "",
        f"Register version **{REGISTER_VERSION}** · "
        f"{len(REGISTER)} entries across {len(CATEGORIES)} categories.",
        "",
        "Every operation that derives or semantically changes a value you can "
        "see, export, or fetch through the API is listed here with its formula, "
        "its units, and how far it has actually been verified. Pure layout and "
        "byte-preserving file I/O are out of scope; filtering, precedence and "
        "assignment are in, because they change *which observations* a result "
        "stands for.",
        "",
        "## How to read the status column",
        "",
        "| Status | Means |",
        "| --- | --- |",
        "| **Verified** | A hand-calculated oracle or exact invariant exists and passes. |",
        "| **Partially verified** | Tested, but without an independent reference implementation. |",
        "| **Unverified** | Exercised by tests only for execution, not for meaning. |",
        "| **Intentional convention** | A choice that can only be documented, not proved. |",
        "",
        "Verification tiers: **A** hand-calculated synthetic oracle · **B** "
        "independent reference implementation · **C** property/invariant tests · "
        "**D** cross-surface parity (UI, API, CLI, export agree).",
        "",
        '!!! note "Tier B is largely absent, on purpose"',
        "",
        "    Comparing against an independent implementation is "
        "[VAL-4](https://github.com/lacclab/scanpath-studio), which is on hold. "
        "Scientific measures therefore read *Partially verified* even where "
        "their hand oracle is exact. The one real exception is the drift-"
        "correction port, which was written against a published reference.",
        "",
        "## Summary",
        "",
        "| ID | Name | Category | Unit | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in REGISTER:
        lines.append(
            f"| `{entry.id}` | {entry.name} | {entry.category} | "
            f"{entry.unit or '—'} | {entry.status} |"
        )
    lines.append("")
    for category in CATEGORIES:
        entries = entries_in(category)
        if not entries:
            continue
        lines += [f"## {category}", ""]
        for entry in entries:
            lines += [
                f"### `{entry.id}` — {entry.name}",
                "",
                entry.summary,
                "",
                f"**Formula.** {entry.formula}",
                "",
            ]
            rows = [
                ("Output", entry.output),
                ("Unit", entry.unit),
                ("Grouping / ordering", entry.grouping),
                ("Missing & edge cases", entry.missing),
                ("Precedence & caveats", entry.precedence),
                ("Reference", entry.reference),
                ("Code", f"`{entry.code}`"),
                ("Consumers", ", ".join(entry.consumers)),
                ("Tests", ", ".join(f"`{t}`" for t in entry.tests)),
                ("Verification", f"tier {entry.tiers} — **{entry.status}**"),
            ]
            lines += ["| | |", "| --- | --- |"]
            for label, value in rows:
                if value:
                    lines.append(f"| **{label}** | {value} |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:  # pragma: no cover - thin CLI wrapper
    from pathlib import Path

    target = Path(__file__).resolve().parents[1] / "docs" / "computations.md"
    target.write_text(to_markdown(), encoding="utf-8")
    print(f"Wrote {target} ({len(REGISTER)} entries)")


if __name__ == "__main__":  # pragma: no cover
    main()
