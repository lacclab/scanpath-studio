"""EXP-7 — the API / CLI code that reproduces the figure currently on screen.

The hand-off from *exploring* to *scripting*: someone tunes a figure in the app
for a paper, then wants that exact figure rebuilt headlessly for a batch of
trials without reverse-engineering which of the ~dozens of options they actually
changed.

This is the **third** rendering of one state, after the deep link
(``url_state._build_share_query``) and the 💾 saved plot config — so it is
deliberately *not* a fourth reading of ``session_state``. All three take the same
input: the settings dict the figure was built from
(``controls._collect_viz_settings`` → ``tabs._build_figure_settings``). The app
publishes that dict, plus the trial identity and the render context, as a
:class:`FigureState` at the point the figure is built (``_snippet_state``), and
this module is a pure serializer over it with two back ends. Nothing here knows
about Streamlit, and nothing here decides plot semantics.

"Only the non-defaults" is answered by :func:`api.figure_options`, which already
returns every figure keyword → its *effective* default. :func:`figure_kwargs`
diffs the live settings against it; ``explicit=True`` emits the full form
instead.

The two back ends are not symmetric: the Python API takes every figure keyword
as itself, while the CLI spells each one as a flag in its own vocabulary.
:data:`_CLI_EMITTERS` is that mapping spelled out, and anything a snippet needs
but the CLI cannot say comes back in :attr:`ReproductionCode.cli_unsupported` —
a live audit of the four-surface rule rather than a silent drop. Since EXP-20
every figure option has a flag, so the list is empty unless an option is added
without one, which `tests/test_render_every_option.py` refuses.
"""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass, field
from typing import Any

#: Where ``tabs._publish_snippet_state`` parks the :class:`FigureState` the
#: Share subtab writes its snippet from. Session-local and never serialized —
#: it is derived from state that *is* on the wire, so it carries no contract of
#: its own and is deliberately absent from ``session_keys``.
SNIPPET_STATE_KEY = "_snippet_state"

#: How to get the package the snippets import. Shown *above* both flavours in
#: the app (`url_state._render_code_snippet_body`) rather than baked into
#: :func:`python_snippet` / :func:`cli_snippet`: a snippet pulled through
#: ``api.figure_code`` is being composed by something that already has the
#: package installed, so the line is presentation for the reader who is about to
#: paste this into a fresh notebook or shell, not part of the recipe.
INSTALL_COMMAND = "pip install scanpath-studio"

#: The figure kinds a snippet can reproduce, matching ``api.figure_options``.
KINDS = ("static", "animation", "comparison")

#: The API entry point each kind is reproduced with.
_API_FUNCTION = {
    "static": "plot_scanpath",
    "animation": "animate_scanpath",
    "comparison": "compare_scanpaths",
}

# ---------------------------------------------------------------------------
# The data half
# ---------------------------------------------------------------------------
#: Source kinds. Each one knows how to write *both* halves of its loader — the
#: Python call and the CLI flags — so a new data source is one entry in
#: `_SOURCE_WRITERS` rather than a branch in each emitter.
SOURCE_DEMO = "demo"
SOURCE_SYNTHETIC = "synthetic"
SOURCE_FILES = "files"
SOURCE_AUTHOR = "author"
SOURCE_POTEC = "potec"
SOURCE_ONESTOP = "onestop"
SOURCE_MULTIPLEYE = "multipleye"
SOURCE_BENCHMARK = "benchmark"
#: VIZ-45: a dataset recorded as raw gaze alone — no words or fixations table,
#: so its data half is the samples (``options["raw_gaze"]``, the paths) and the
#: builder is handed ``None`` for the other two.
SOURCE_RAW_GAZE = "raw_gaze"
#: A dataset added through the app: its files are placeholders, but the column
#: mapping it was added with is written out, table by table (see
#: :func:`upload_source`).
SOURCE_UPLOAD = "upload"
SOURCE_UNKNOWN = "unknown"

#: What a snippet says when it cannot name the data. An uploaded table lives in
#: the browser session, not at a path the server can quote back — writing a
#: guessed path would produce a snippet that runs and loads the wrong thing.
UNKNOWN_SOURCE_NOTE = (
    "This dataset was uploaded into the app, so the snippet can't name the "
    "files it came from — fill in the paths to your own tables."
)


@dataclass(frozen=True)
class SnippetSource:
    """How the snippet's data half is written.

    ``kind`` is one of the ``SOURCE_*`` constants; ``options`` carries whatever
    that kind's writer needs (a corpus root, a regime, a list of paths).
    ``note`` is a human-readable caveat shown beside the snippet when the code
    can't fully name the data — the same honesty the Share link's caveats give.
    """

    kind: str = SOURCE_UNKNOWN
    label: str = ""
    options: dict = field(default_factory=dict)
    note: str = ""
    #: Loader options this source needs that ``render`` has no flag for, folded
    #: into :attr:`ReproductionCode.cli_unsupported` beside the figure ones.
    cli_unsupported: tuple[str, ...] = ()


#: The file a snippet saves to when the caller names none, per figure kind. An
#: animation is interactive HTML — `render --animate` refuses anything else —
#: while the static and comparison figures raster. EXP-14: `api.figure_code`
#: used `scanpath.png` for every kind, so its animation command exited on its
#: first line. The Share subtab keeps its own copy (`url_state._SNIPPET_OUTPUT`).
DEFAULT_OUTPUT = {
    "static": "scanpath.png",
    "comparison": "comparison.png",
    "animation": "scanpath.html",
}


def source_canvas(kind: str) -> tuple[int, int] | None:
    """The screen ``render`` assumes for a source when ``--canvas`` is omitted.

    EXP-14: one table for both surfaces. `render --sample` drew the demo at its
    real 2560×1440 monitor while the Python snippet ``api.figure_code`` wrote
    for the same request estimated 960×480 from the data extents, so the two
    flavours of one recipe produced different figures. ``None`` means the
    screen is read off the data (or, for a benchmark corpus, its manifest)."""
    if kind in (SOURCE_DEMO, SOURCE_ONESTOP):
        # OneStop's Dell U2715H — cited in eyegenbench_geometry.DISPLAY_SPECS
        # ["onestop"] (Berzak et al. 2025); the demo is a subset of OneStop.
        from .constants import DEFAULT_FIGURE_SIZE

        return tuple(DEFAULT_FIGURE_SIZE)
    if kind == SOURCE_POTEC:
        return (1680, 1050)  # PoTeC monitor (DELL P2210)
    if kind == SOURCE_AUTHOR:
        return (1200, 800)
    if kind == SOURCE_MULTIPLEYE:
        # Coordinates are offset onto the centred stimulus on the real screen.
        from .datasets import MULTIPLEYE_MONITOR

        return tuple(MULTIPLEYE_MONITOR)
    return None


def _root(source: SnippetSource, fallback: str) -> str:
    return str(source.options.get("root") or fallback)


def _demo_python(source: SnippetSource) -> list[str]:
    return ["words, fixations = sps.load_sample_data()"]


def _synthetic_python(source: SnippetSource) -> list[str]:
    return [
        "from scanpath_studio.synthetic import load_synthetic_data",
        "",
        "words, fixations = load_synthetic_data()",
    ]


def _files_python(source: SnippetSource) -> list[str]:
    words = source.options.get("words") or ["words.csv"]
    fixations = source.options.get("fixations") or ["fixations.csv"]
    return [
        "words, fixations = sps.load_scanpath_data(",
        f"    {_py(_one_or_list(words))},",
        f"    {_py(_one_or_list(fixations))},",
        ")",
    ]


def _author_python(source: SnippetSource) -> list[str]:
    path = source.options.get("path") or "scanpath.json"
    return [f"words, fixations = sps.load_authored_scanpath({_py(str(path))})"]


def _potec_python(source: SnippetSource) -> list[str]:
    return [
        "words, fixations = sps.load_potec(",
        f"    {_py(_root(source, 'data/PoTeC'))}, download=True",
        ")",
    ]


def _onestop_python(source: SnippetSource) -> list[str]:
    lines = [
        "words, fixations = sps.load_onestop(",
        f"    {_py(_root(source, 'data/OneStop'))},",
    ]
    for name, default in (("regime", "ordinary"), ("variant", "public")):
        value = source.options.get(name)
        if value:
            lines.append(f"    {name}={_py(str(value))},")
        else:
            lines.append(f"    {name}={_py(default)},")
    parts = source.options.get("parts") or ["Paragraph"]
    lines.append(f"    parts={_py([str(p) for p in parts])},")
    # The public reports are an OSF download; the lacclab variant reads a local
    # export and rejects `download=True`, so it is written per variant.
    if str(source.options.get("variant") or "public") == "public":
        lines.append("    download=True,")
    lines.append(")")
    return lines


def _multipleye_python(source: SnippetSource) -> list[str]:
    lines = [
        "words, fixations = sps.load_multipleye(",
        f"    {_py(_root(source, 'data/MultiplEYE'))},",
    ]
    fixation_source = source.options.get("fixation_source")
    if fixation_source and fixation_source != "scanpaths":
        lines.append(f"    fixation_source={_py(str(fixation_source))},")
    lines.append(")")
    return lines


def _benchmark_python(source: SnippetSource) -> list[str]:
    dataset = str(source.options.get("dataset") or "PoTeC")
    return [
        "from scanpath_studio.eyegenbench import load_eyegenbench",
        "",
        "words, fixations = load_eyegenbench(",
        f"    {_py(_root(source, 'data/eyegenbench'))}, dataset={_py(dataset)}",
        ")",
    ]


def _unknown_python(source: SnippetSource) -> list[str]:
    return [
        "# Point these at your own tables — the app can't name an uploaded file.",
        'words, fixations = sps.load_scanpath_data("words.csv", "fixations.csv")',
    ]


def _demo_cli(source: SnippetSource) -> list[str]:
    return ["--sample"]


def _files_cli(source: SnippetSource) -> list[str]:
    argv = []
    words = source.options.get("words") or ["words.csv"]
    fixations = source.options.get("fixations") or ["fixations.csv"]
    argv += ["--words", *[str(p) for p in words]]
    argv += ["--fixations", *[str(p) for p in fixations]]
    return argv


def _author_cli(source: SnippetSource) -> list[str]:
    return ["--authoring", str(source.options.get("path") or "scanpath.json")]


def _potec_cli(source: SnippetSource) -> list[str]:
    return ["--potec", _root(source, "data/PoTeC")]


def _onestop_cli(source: SnippetSource) -> list[str]:
    argv = ["--onestop", _root(source, "data/OneStop")]
    argv += ["--onestop-regime", str(source.options.get("regime") or "ordinary")]
    argv += ["--onestop-variant", str(source.options.get("variant") or "public")]
    for part in source.options.get("parts") or ["Paragraph"]:
        argv += ["--onestop-part", str(part)]
    return argv


def _multipleye_cli(source: SnippetSource) -> list[str]:
    return ["--source", "multipleye", "--export", _root(source, "data/MultiplEYE")]


def _benchmark_cli(source: SnippetSource) -> list[str]:
    return [
        "--eyegenbench",
        _root(source, "data/eyegenbench"),
        "--eyegenbench-dataset",
        str(source.options.get("dataset") or "PoTeC"),
    ]


def _unknown_cli(source: SnippetSource) -> list[str]:
    return ["--words", "words.csv", "--fixations", "fixations.csv"]


#: The placeholder paths an uploaded dataset's snippet loads its tables from.
UPLOAD_WORDS_PLACEHOLDER = "words.csv"
UPLOAD_FIXATIONS_PLACEHOLDER = "fixations.csv"

#: What an added dataset did on its way in that ``load_scanpath_data`` cannot
#: replay — step code (``source_recipe["steps"]``) → the caveat naming it.
UPLOAD_STEP_NOTES = {
    "aggregate_char_boxes": (
        "Its AOIs were character boxes, which the app joined into word boxes; "
        "the loader in the snippet does not, so join them in your words table "
        "first."
    ),
    "multipleye_preset": (
        "It was added with the MultiplEYE files preset, which builds its tables "
        "from the corpus's own files; the loader in the snippet cannot replay "
        "that, so its mapping is not written out."
    ),
}


def upload_source(
    label: str,
    recipe: dict | None,
    *,
    words: bool,
    fixations: bool,
) -> SnippetSource:
    """The data half for a dataset added through the app (Share → Code).

    ``recipe`` is the dataset's ``source_recipe`` — ``schemas`` (each table's
    mapping in its own files' column names), ``steps`` (what the add did that
    the loader cannot, :data:`UPLOAD_STEP_NOTES`), ``derived`` (columns made
    from the file names) and ``unresolved`` (fields an edit left untraceable).
    ``words`` / ``fixations`` say which tables the dataset has, so an AOI-only
    or fixation-only dataset loads only that one. The files themselves stay
    placeholders: an upload has no path the server could quote.
    """
    recipe = recipe if isinstance(recipe, dict) else {}
    schemas = recipe.get("schemas") if isinstance(recipe.get("schemas"), dict) else {}
    steps = [str(s) for s in recipe.get("steps") or ()]
    notes = [
        "This dataset was added in the app, so the snippet can't name its files: "
        "replace "
        + " and ".join(
            f"`{p}`"
            for p, present in (
                (UPLOAD_WORDS_PLACEHOLDER, words),
                (UPLOAD_FIXATIONS_PLACEHOLDER, fixations),
            )
            if present
        )
        + " with them (a list of files works for one added from several). "
        + (
            "The column mapping it was added with is written out."
            if "multipleye_preset" not in steps
            else ""
        )
    ]
    notes += [UPLOAD_STEP_NOTES[s] for s in steps if s in UPLOAD_STEP_NOTES]
    if derived := [str(c) for c in recipe.get("derived") or ()]:
        notes.append(
            "It maps "
            + ", ".join(f"`{c}`" for c in derived)
            + ", made from the file names when it was added; the loader has no "
            "such step, so add "
            + ("those columns" if len(derived) > 1 else "that column")
            + " to your tables first."
        )
    tables = {"words": "AOI", "fixations": "fixations", "raw_gaze": "raw gaze"}
    unresolved = [
        f"`{field}` ({tables.get(table, table)} table)"
        for table, fields in dict(recipe.get("unresolved") or {}).items()
        for field in fields or ()
    ]
    if unresolved:
        notes.append(
            "Its mapping was edited after it was added, and "
            + ", ".join(unresolved)
            + " could not be traced back to your files' columns — check "
            + ("those fields" if len(unresolved) > 1 else "that field")
            + " before running it."
        )
    if "multipleye_preset" in steps:
        schemas = {}
    options: dict = {
        "words": UPLOAD_WORDS_PLACEHOLDER if words else None,
        "fixations": UPLOAD_FIXATIONS_PLACEHOLDER if fixations else None,
    }
    for table, option in (
        ("words", "word_schema"),
        ("fixations", "fix_schema"),
        ("raw_gaze", "raw_gaze_schema"),
    ):
        schema = schemas.get(table)
        if isinstance(schema, dict) and schema:
            options[option] = _compact_schema(schema)
    return SnippetSource(
        kind=SOURCE_UPLOAD,
        label=label,
        options=options,
        note=" ".join(n.strip() for n in notes if n.strip()),
    )


def _compact_schema(schema: dict) -> dict:
    """A mapping without its unmapped fields, so the snippet stays readable.

    An absent field and an unmapped one load the same — except a reading
    measure, where naming the key with nothing in it means *absent* while
    leaving it out lets a column under its usual name through (AN-32), so a
    cleared measure is kept."""
    return {
        str(key): value
        for key, value in schema.items()
        if value or str(key).startswith("measure_")
    }


def _upload_python(source: SnippetSource) -> list[str]:
    lines = ["words, fixations = sps.load_scanpath_data("]
    for name in ("words", "fixations"):
        if source.options.get(name):
            lines.append(f"    {name}={_py(source.options[name])},")
    for option in ("word_schema", "fix_schema"):
        schema = source.options.get(option)
        if schema:
            lines.append(f"    {option}={{")
            lines += [f"        {_py(k)}: {_py(v)}," for k, v in schema.items()]
            lines.append("    },")
    lines.append(")")
    return lines


def _upload_cli(source: SnippetSource) -> list[str]:
    argv: list[str] = []
    for name, flag, option, schema_flag in (
        ("words", "--words", "word_schema", "--word-schema"),
        ("fixations", "--fixations", "fix_schema", "--fix-schema"),
    ):
        if not source.options.get(name):
            continue
        argv += [flag, str(source.options[name])]
        if schema := source.options.get(option):
            argv += [schema_flag, json.dumps(schema, separators=(",", ":"))]
    return argv


def _raw_gaze_only_python(source: SnippetSource) -> list[str]:
    return [_raw_gaze_python(source), "words, fixations = None, None"]


def _raw_gaze_only_cli(source: SnippetSource) -> list[str]:
    return _raw_gaze_cli(source)


#: kind → (Python loader lines, CLI input flags). A source whose CLI writer is
#: ``None`` has no ``render`` flags at all, and the CLI snippet says so rather
#: than inventing one.
_SOURCE_WRITERS: dict[str, tuple[Any, Any]] = {
    SOURCE_DEMO: (_demo_python, _demo_cli),
    SOURCE_SYNTHETIC: (_synthetic_python, None),
    SOURCE_FILES: (_files_python, _files_cli),
    SOURCE_AUTHOR: (_author_python, _author_cli),
    SOURCE_POTEC: (_potec_python, _potec_cli),
    SOURCE_ONESTOP: (_onestop_python, _onestop_cli),
    SOURCE_MULTIPLEYE: (_multipleye_python, _multipleye_cli),
    SOURCE_BENCHMARK: (_benchmark_python, _benchmark_cli),
    SOURCE_RAW_GAZE: (_raw_gaze_only_python, _raw_gaze_only_cli),
    SOURCE_UPLOAD: (_upload_python, _upload_cli),
    SOURCE_UNKNOWN: (_unknown_python, _unknown_cli),
}


# ---------------------------------------------------------------------------
# The figure half
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CompareTarget:
    """Scanpath B, when the figure on screen is a comparison (CMP-9)."""

    participant: str = ""
    trial: str = ""
    layout: str = "overlay"
    compare_stimulus: str = "both"
    dataset: str = ""
    #: EXP-8 §1. The two trace labels the figure was actually built with —
    #: `friendly_trial_label`'s output, or UX-31's `cmp{idx}_label_pattern`
    #: override. They ride here rather than in ``FigureState.settings`` because
    #: `compare_scanpaths` takes them as a named `labels=` parameter, so
    #: `api._COMPARISON_FIGURE_PARAMS` subtracts them and the
    #: `_amend_snippet_settings` merge structurally cannot see them — the same
    #: reason `layout` and `compare_stimulus` are fields here.
    labels: tuple[str, str] | None = None
    #: EXP-21 — only beside a ``dataset``: B's own screen, when it is known
    #: (``setup_b=`` / ``--compare-canvas``), and the table paths B was read
    #: from, when there are any to name (``render --print-code`` has them; the
    #: app's uploads and corpora do not, so the snippet writes placeholders).
    canvas: tuple[int, int] | None = None
    words: tuple[str, ...] = ()
    fixations: tuple[str, ...] = ()
    #: B's own screen of a multipart trial (``screen_b=`` / ``--compare-screen``),
    #: picked in B's trial independently of A's. ``None``: B is single-screen.
    screen: str | None = None
    #: VIZ-48 — only beside a ``dataset``: B's own raw gaze. ``None`` when B has
    #: none; the paths it was read from (``render --print-code``), or ``()``
    #: when it has samples but no path to name (an upload — a placeholder).
    raw_gaze: tuple[str, ...] | None = None
    #: VIZ-48: whether A's own dataset has raw gaze to load. ``False`` only
    #: when B's dataset alone brings samples, so the recipe loads B's and not a
    #: placeholder for A's.
    primary_raw_gaze: bool = True


@dataclass(frozen=True)
class FigureState:
    """Everything a snippet needs about the figure that is on screen.

    ``settings`` is the ``tabs._build_figure_settings`` dict — the same mapping
    the builders consume — so the snippet is a serializer over the figure's own
    input rather than a second reading of the widgets.
    """

    kind: str = "static"
    settings: dict = field(default_factory=dict)
    participant: str = ""
    trial: str = ""
    screen: str | None = None
    canvas: tuple[int, int] | None = None
    base_font_size: int = 16
    font_family: str = ""
    title: str = ""
    caption: str = ""
    fix_index_range: tuple[int, int] | None = None
    #: CMP-24 — scanpath B's own window (``compare_scanpaths`` /
    #: ``animate_scanpath``'s ``fix_index_range_b``); only beside a ``compare``.
    fix_index_range_b: tuple[int, int] | None = None
    illustration_label: str = "auto"
    drift_correction: str | None = None
    drift_connectors: bool = False
    playback_speed: float = 1.0
    autoplay: bool = True
    compare: CompareTarget | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {self.kind!r}.")


def _comparable(value):
    """Normalize a setting for equality against its default.

    A tuple and a list of the same numbers are the same figure — the rail
    produces one and the builder's signature the other — so a naive ``!=``
    would report half the marker-size ranges in the app as non-default."""
    if isinstance(value, (list, tuple)):
        return tuple(_comparable(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((str(k), _comparable(v)) for k, v in value.items()))
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


#: Figure keywords that are *derived*, not chosen — the app fills them in from
#: something else it already decided, so re-emitting them would be noise at best
#: and wrong at worst. ``connector_y`` is the extreme case: a tuple with one
#: float per fixation, which would bury a snippet in numbers that
#: ``drift_connectors=True`` recomputes anyway.
_DERIVED_SETTINGS = frozenset(
    {
        "connector_y",
        "show_connectors",
        "illustration_reasons",
        # Needs a third frame (`raw_gaze=`), not a keyword: the layer is drawn
        # for the frame it is handed, so both snippets load that table instead
        # (`draws_raw_gaze`) — `show_raw_gaze=True` alone would draw nothing.
        "show_raw_gaze",
    }
)

#: EXP-8 §4. Of the derived settings above, the ones whose *value* scales with
#: the trial rather than being a scalar choice. ``_DERIVED_SETTINGS`` keeps them
#: out of the snippet's text; this keeps them out of the published
#: :class:`FigureState` as well, because `tabs._amend_snippet_settings` merges
#: every builder keyword it recognizes and would otherwise park one float per
#: fixation in session state on every rerun — for a key that is guaranteed
#: never to be emitted. The rest of ``_DERIVED_SETTINGS`` stays in the state:
#: `show_raw_gaze` is read by :func:`state_caveats`, and the others are scalars.
UNPUBLISHED_SETTINGS = frozenset({"connector_y"})

#: A stimulus image the user uploaded lives in the figure as a ``data:`` URI —
#: a megabyte of base64 that would swamp the snippet and mean nothing on
#: another machine. It becomes a placeholder path plus a caveat.
_IMAGE_PLACEHOLDER = "stimulus.png"


def _is_data_uri(value) -> bool:
    return isinstance(value, str) and value.startswith("data:")


def figure_kwargs(
    settings: dict, kind: str = "static", *, explicit: bool = False
) -> dict:
    """The figure keywords a snippet has to pass, in ``api`` vocabulary.

    Keys the chosen builder doesn't accept are dropped (the rail's dict carries
    a few, e.g. ``title_pattern``, that are not figure keywords at all), and so
    are keys already at their effective default — unless ``explicit``, which
    emits the full form. Ordered as ``figure_options`` lists them, so two
    snippets from neighbouring states read as neighbours."""
    from . import api

    defaults = api.figure_options(kind)
    out = {}
    for key, default in defaults.items():
        if key not in settings:
            continue
        if key in _DERIVED_SETTINGS:
            continue
        if key == "heatmap_range" and _heatmap_self_scaled(settings, kind):
            continue  # kept for Word boxes, but it pins nothing here
        value = settings[key]
        if key == "fixation_flags_b" and _same_flags(
            value, settings.get("fixation_flags")
        ):
            continue  # CMP-24: B inheriting A's flags is the builder's default
        if key in _COMPARE_STYLE_SIDES:
            value = _drop_inherited_filters(value, settings)
            # The rail always builds a complete style dict, so the one an
            # untouched Compare carries is not a choice anyone made — only
            # what it changes is (EXP-20).
            value = compare_style_delta(
                value,
                _COMPARE_STYLE_SIDES[key],
                settings.get("marker_size_range", defaults.get("marker_size_range")),
            )
        # A frame-valued option (`words_b`) is data, not a setting: its repr is
        # meaningless in another process. `state_caveats` names it instead.
        if hasattr(value, "to_dict") and hasattr(value, "columns"):
            continue
        if _is_data_uri(value):
            value = _IMAGE_PLACEHOLDER
        if explicit or _comparable(value) != _comparable(default):
            out[key] = value
    return out


def _heatmap_self_scaled(settings: dict, kind: str) -> bool:
    """Whether the figure's heatmap ignores ``heatmap_range``: a smoothed style,
    which scales to its own peak, outside a comparison (always word boxes)."""
    from .constants import SELF_SCALED_HEATMAP_STYLES

    return (
        kind != "comparison"
        and settings.get("heatmap_style") in SELF_SCALED_HEATMAP_STYLES
    )


#: The per-scanpath style options → which scanpath each styles.
_COMPARE_STYLE_SIDES = {"style_a": 0, "style_b": 1}


def _active_flags(flags) -> dict:
    """The part of a fixation-flags dict that draws anything: each category not
    *Off*, with the threshold short/long use. Two dicts with the same active
    part filter identically (CMP-24)."""
    out = {}
    for category, spec in (flags or {}).items():
        if not isinstance(spec, dict) or str(spec.get("mode") or "Off") == "Off":
            continue
        entry = {"mode": spec.get("mode")}
        if category in ("short", "long") and spec.get("threshold_ms") is not None:
            entry["threshold_ms"] = float(spec["threshold_ms"])
        out[category] = entry
    return out


def _same_flags(a, b) -> bool:
    return _active_flags(a) == _active_flags(b)


def _visible_classes(classes) -> frozenset | None:
    from .constants import SACCADE_CLASS_ORDER

    if not classes or set(classes) >= set(SACCADE_CLASS_ORDER):
        return None
    return frozenset(classes)


def _drop_inherited_filters(style, settings: dict):
    """A per-scanpath style without the filters it merely repeats (CMP-24).

    The rail hands B its whole filter set every run; where it equals the
    figure's own ``fixation_flags`` / ``saccade_classes`` the builder draws B the
    same without it, so a snippet should not restate it."""
    if not isinstance(style, dict):
        return style
    style = dict(style)
    if "fixation_flags" in style and _same_flags(
        style["fixation_flags"], settings.get("fixation_flags")
    ):
        style.pop("fixation_flags")
    if "saccade_classes" in style and _visible_classes(
        style["saccade_classes"]
    ) == _visible_classes(settings.get("saccade_classes")):
        style.pop("saccade_classes")
    return style


def compare_style_delta(style, idx: int, marker_size_range) -> dict | None:
    """What a per-scanpath style changes, or ``None`` when it changes nothing.

    Measured against the style the comparison builder would draw *without* it
    (`plots._comparison_scanpath_style`), whose marker range is the figure's own
    ``marker_size_range`` — so a scanpath at the stock range under a changed
    global one still says so. Values the builder drops (``None`` / ``""`` /
    ``False``) are dropped here too, which is what keeps the reduced dict
    drawing exactly the same figure as the full one."""
    if not isinstance(style, dict) or not style:
        return None
    from .plots import _comparison_scanpath_style

    msr = tuple(marker_size_range) if marker_size_range else None
    kwargs = {} if msr is None else {"default_marker_size_range": msr}
    base = _comparison_scanpath_style(idx, None, **kwargs)
    drawn = _comparison_scanpath_style(idx, style, **kwargs)
    delta = {
        key: drawn[key]
        for key in drawn
        if _comparable(drawn[key]) != _comparable(base.get(key))
    }
    return delta or None


# ---------------------------------------------------------------------------
# CLI flag emitters — the `render` subset of the figure keywords
# ---------------------------------------------------------------------------
def _flag_when(flag: str, wanted) -> Any:
    """A bare flag emitted only when the setting equals ``wanted``."""

    def emit(value):
        return [flag] if _comparable(value) == _comparable(wanted) else []

    return emit


def _valued(flag: str) -> Any:
    def emit(value):
        return [] if value is None else [flag, str(value)]

    return emit


def _int_valued(flag: str) -> Any:
    """A ``type=int`` flag: ``12.0`` from a settings dict would be refused."""

    def emit(value):
        return [] if value is None else [flag, str(int(value))]

    return emit


def _optional_valued(flag: str) -> Any:
    """A flag whose ``None`` is a real choice, spelled as an empty value — the
    ``--highlight-column ''`` rule, not the absence of the flag."""

    def emit(value):
        return [flag, "" if value is None else str(value)]

    return emit


def _mapped(flag: str, table: dict) -> Any:
    """A flag whose CLI vocabulary differs from the settings vocabulary."""

    def emit(value):
        token = table.get(value)
        return [] if token is None else [flag, token]

    return emit


def _comma_list(flag: str) -> Any:
    def emit(value):
        if not value:
            return []
        return [flag, ",".join(str(item) for item in value)]

    return emit


def _highlight_column(value):
    """``--highlight-column``. ``None`` is the real request "highlight nothing",
    which the flag spells as an empty string — not the absence of the flag,
    which would leave the default (`is_in_aspan`) in place."""
    return ["--highlight-column", "" if value is None else str(value)]


def _fixation_flags(value, flag: str = "--fixation-flag"):
    """The PRE-2 classification dict → one ``--fixation-flag`` per category.

    Only categories that are actually doing something are written: an *Off*
    category is the default, and the builder reads a missing one the same way.
    ``flag`` is ``--compare-fixation-flag`` for scanpath B's own (CMP-24).
    """
    argv: list[str] = []
    for category, spec in (value or {}).items():
        if not isinstance(spec, dict):
            continue
        mode = str(spec.get("mode") or "Off")
        if mode == "Off":
            continue
        parts = [f"{category}={mode.lower()}"]
        # Only for the two categories that have one — `oob` / `blink` carry a
        # stale default threshold in the app's dict that the CLI would reject.
        if category in ("short", "long") and spec.get("threshold_ms") is not None:
            parts.append(f"threshold_ms={_num(spec['threshold_ms'])}")
        if spec.get("symbol"):
            parts.append(f"symbol={spec['symbol']}")
        if spec.get("color"):
            parts.append(f"color={spec['color']}")
        argv += [flag, ",".join(parts)]
    return argv


def _compare_fixation_flags(value):
    """B's flags (CMP-24). An all-*Off* set still has to be said when A's are
    on, or B would inherit them — so it is spelled as one explicit *off*."""
    argv = _fixation_flags(value, "--compare-fixation-flag")
    return argv or ["--compare-fixation-flag", "short=off"]


def _heatmap_metric(value):
    # The figure level spells "counts" as None (`_build_figure_settings` and
    # `api._figure_kwargs` both translate), so the CLI word has to be put back.
    return ["--heatmap-metric", "counts" if value is None else str(value)]


def _saccade_color_mode(value):
    if value == "By type":
        return ["--saccade-color-by-type"]
    if value == "Forward / regression":
        return ["--saccade-color-by-direction"]
    return []


def _saccade_class_colors(value, baseline: dict | None = None):
    """One ``--saccade-type-color`` per class colour that differs from
    ``baseline`` — the stock classes, or the colours a named ``--palette`` has
    just written (so a stock colour it moved is moved back)."""
    if not isinstance(value, dict):
        return []
    from .constants import SACCADE_CLASS_COLORS, SACCADE_CLASS_EDITABLE

    reference = baseline if isinstance(baseline, dict) else SACCADE_CLASS_COLORS
    argv = []
    for name in SACCADE_CLASS_EDITABLE:
        color = value.get(name)
        if color and str(color).lower() != str(reference.get(name, "")).lower():
            argv += ["--saccade-type-color", f"{name}={color}"]
    return argv


def _effective_color(key: str, value):
    """``saccade_class_colors=None`` means the stock class colours, so compare
    it as those — otherwise the default palette would read as a change."""
    if key == "saccade_class_colors" and value is None:
        from .constants import SACCADE_CLASS_COLORS

        return dict(SACCADE_CLASS_COLORS)
    return value


def _palette_colors(name: str) -> dict:
    """The figure keywords palette ``name`` writes, as `api` expands them."""
    from . import api

    return api._expand_palette({"palette": name})


def _classes_coloured(settings: dict) -> bool:
    """Whether the reading-class colours are drawn at all. In *Uniform* they are
    not, so they can be neither a reason to name a palette nor a flag to emit."""
    return settings.get("saccade_color_mode") in ("By type", "Forward / regression")


def _flag_can_override(key: str, settings: dict) -> bool:
    """Whether ``render`` can restate ``key`` after a ``--palette``.

    `--saccade-type-color` restates class colours in either coloured mode: it
    implies By type on its own, and recolours the two-way fold beside
    `--saccade-color-by-direction` (EXP-20; before that it switched the fold to
    the five-way split, so the fold's colours had no flag at all)."""
    if key == "saccade_class_colors":
        return _classes_coloured(settings)
    return key in _CLI_EMITTERS


def _matching_palette(settings: dict, kind: str) -> tuple[str | None, dict]:
    """The ``--palette`` a CLI snippet can name instead of spelling it out.

    EXP-12. A palette writes eight colours at once. Spelled key by key, three of
    them (`text_color`, `highlight_text_color`, `background_color`) have no
    `render` flag and were named unsupported, and the class colours became five
    ``--saccade-type-color`` flags — which switch saccades to *By type*, so any
    palette choice produced a command drawing a different figure. A palette
    matches when every colour it writes that this kind draws either equals the
    figure's or has a flag to restate it; one that explains none (the default
    palette on a stock figure) is not named at all.

    EXP-20 gave every colour a flag, which turned "can be restated" from rare
    into always — and exposed that a restatement is not free: a colour the
    figure still has at its *default* is one `figure_kwargs` never writes, so
    naming a palette that moves it costs a flag to move it back
    (`_restate_against_palette`). Before this, a figure whose text colour merely
    happened to equal *Print / greyscale*'s was reproduced in greyscale. The
    palette named is the one whose colours save the most flags net of those.

    Returns ``(name, colours)`` — the colours the named palette supplies — or
    ``(None, {})``."""
    from . import api
    from .constants import PALETTES

    defaults = api.figure_options(kind)
    best: tuple[str | None, dict] = (None, {})
    best_score = 0
    for name in PALETTES:
        colors = {k: v for k, v in _palette_colors(name).items() if k in defaults}
        score = 0
        for key, value in colors.items():
            if key == "saccade_class_colors" and not _classes_coloured(settings):
                continue
            current = _effective_color(key, settings.get(key, defaults[key]))
            default = _effective_color(key, defaults[key])
            at_default = _comparable(current) == _comparable(default)
            if _comparable(current) == _comparable(value):
                score += int(not at_default)
            elif not _flag_can_override(key, settings):
                break
            elif at_default:
                score -= 1  # the palette moved it; a flag has to move it back
        else:
            if score > best_score:
                best, best_score = (name, colors), score
    return best


def _restate_against_palette(
    kwargs: dict, settings: dict, kind: str, palette_colors: dict
) -> dict:
    """The figure keywords to write after ``--palette``: the colours it got right
    dropped, and every one it got wrong restated — a colour still at its default
    included, which `figure_kwargs` would not otherwise write (EXP-20)."""
    from . import api

    defaults = api.figure_options(kind)
    out = dict(kwargs)
    for key, value in palette_colors.items():
        current = _effective_color(key, settings.get(key, defaults.get(key)))
        if _comparable(current) == _comparable(value):
            out.pop(key, None)
        else:
            out[key] = current
    return out


def _marker_size_range(value):
    if not value:
        return []
    lo, hi = value
    return ["--marker-size-range", str(int(lo)), str(int(hi))]


def _pair(flag: str, sep: str) -> Any:
    def emit(value):
        if not value:
            return []
        first, second = value
        text = f"{_num(first)}{sep}{_num(second)}"
        # A leading minus reads to argparse as another flag (`-5,3` is not a
        # negative *number*), so a negative origin is glued to its flag.
        return [f"{flag}={text}"] if text.startswith("-") else [flag, text]

    return emit


def _two_numbers(flag: str) -> Any:
    """A ``nargs=2`` flag (`--fixation-color-range LO HI`)."""

    def emit(value):
        if not value:
            return []
        lo, hi = value
        return [flag, _num(lo), _num(hi)]

    return emit


def _lowercase(flag: str) -> Any:
    """A choice the CLI spells in lower case (`--compare-stimulus b`)."""

    def emit(value):
        return [] if value is None else [flag, str(value).lower()]

    return emit


#: The order `--style-a` / `--style-b` write their keys in — `cli._STYLE_KEYS`.
_STYLE_SPEC_KEYS = (
    "fix_color",
    "saccade_color",
    "saccade_style",
    "saccade_width",
    "marker_size_range",
    "opacity",
    "hollow",
)


def _style_spec(flag: str) -> Any:
    """A per-scanpath style (already reduced to what it changes) → one
    ``--style-a KEY=VALUE,…`` — the spec `cli._parse_style_spec` reads back."""

    def emit(value):
        if not isinstance(value, dict) or not value:
            return []
        filters: list[str] = []
        if flag == "--style-b":
            # CMP-24: B's filters have flags of their own, not style keys.
            if "fixation_flags" in value:
                filters += _compare_fixation_flags(value["fixation_flags"])
            if "saccade_classes" in value:
                filters += _comma_list("--compare-saccade-classes")(
                    value["saccade_classes"]
                )
        parts = []
        for key in _STYLE_SPEC_KEYS:
            if key not in value:
                continue
            item = value[key]
            if key == "marker_size_range":
                lo, hi = item
                text = f"{int(lo)}:{int(hi)}"
            elif key == "hollow":
                text = "true" if item else "false"
            elif isinstance(item, (int, float)):
                text = _num(item)
            else:
                text = str(item)
            parts.append(f"{key}={text}")
        return ([flag, ",".join(parts)] if parts else []) + filters

    return emit


def _num(value) -> str:
    """Render a number without a pointless trailing ``.0`` (``1310`` not ``1310.0``)."""
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


#: figure-setting key → the ``render`` argv it becomes. A key **absent** from
#: this table has no CLI flag; :func:`cli_snippet` reports those rather than
#: dropping them, which is what keeps the four-surface rule honest here.
_CLI_EMITTERS: dict[str, Any] = {
    # EXP-8 §1. CMP-11's co-animation names its two trace labels as loose
    # keywords, so the animation half rides the table; the comparison half is
    # written by hand in `cli_snippet`, because `compare_scanpaths` takes them
    # as one `labels=` pair rather than as figure options. Same two flags.
    "label_a": _valued("--label-a"),
    "label_b": _valued("--label-b"),
    "show_words": _flag_when("--no-words", False),
    "show_word_labels": _flag_when("--no-labels", False),
    "show_fixations": _flag_when("--no-fixations", False),
    "show_order": _flag_when("--no-order", False),
    "show_saccades": _flag_when("--no-saccades", False),
    "show_heatmap": _flag_when("--no-heatmap", False),
    "show_saccade_arrows": _flag_when("--saccade-arrows", True),
    "show_coordinate_grid": _flag_when("--coordinate-grid", True),
    "coordinate_grid_spacing": _valued("--coordinate-grid-spacing"),
    "word_hover_fields": _comma_list("--word-hover-fields"),
    "fixation_hover_fields": _comma_list("--fixation-hover-fields"),
    "color_by": _valued("--color-by"),
    "fixation_color": _valued("--fixation-color"),
    "fixation_symbol": _valued("--fixation-symbol"),
    "fixation_colorscale": _valued("--fixation-colorscale"),
    "heatmap_metric": _heatmap_metric,
    "heatmap_colorscale": _valued("--heatmap-colorscale"),
    "heatmap_style": _mapped(
        "--heatmap-style",
        {
            "Word boxes": "word-boxes",
            "Interpolated": "interpolated",
            "Duration mass": "duration-mass",
        },
    ),
    "heatmap_norm": _mapped("--heatmap-norm", {"Linear": "linear", "Log": "log"}),
    "highlight_column": _highlight_column,
    "critical_span_style": _mapped(
        "--critical-span-style",
        {"Mark text": "mark-text", "Mark border": "mark-border", "None": "none"},
    ),
    "fixation_flags": _fixation_flags,
    "duration_mass_sigma_chars": _valued("--duration-mass-sigma"),
    "marker_size_range": _marker_size_range,
    "marker_size_scale": _valued("--marker-size-scale"),
    "marker_duration_range": _two_numbers("--marker-duration-range"),
    "duration_size_legend": _flag_when("--no-duration-size-legend", False),
    "saccade_color": _valued("--saccade-color"),
    "saccade_style": _valued("--saccade-style"),
    "saccade_width": _valued("--saccade-width"),
    "saccade_color_mode": _saccade_color_mode,
    "saccade_class_colors": _saccade_class_colors,
    "saccade_type_legend": _flag_when("--no-saccade-type-legend", False),
    "saccade_classes": _comma_list("--saccade-classes"),
    "saccade_render_mode": _flag_when("--saccade-arcs", "Arc"),
    "fixation_snap_to_word": _flag_when("--snap-fixations", True),
    "background_image": _valued("--stimulus-image"),
    "background_image_size": _pair("--stimulus-image-size", "x"),
    "background_image_origin": _pair("--stimulus-image-origin", ","),
    "background_image_opacity": _valued("--stimulus-image-opacity"),
    "anim_grid_step_ms": _valued("--anim-grid-step-ms"),
    "anim_max_frames": _int_valued("--anim-max-frames"),
    # EXP-20 — every figure option `render` could not say before. Each flag is
    # spelled after its option; `tests/test_code_snippet.py` fails on an option
    # with no row here, so a new one cannot quietly fall back to being "named".
    "fixation_opacity": _valued("--fixation-opacity"),
    "hollow_fixations": _flag_when("--hollow-fixations", True),
    "color_by_line": _flag_when("--color-by-line", True),
    "fixation_color_range": _two_numbers("--fixation-color-range"),
    "heatmap_range": _two_numbers("--heatmap-range"),
    "order_font_size": _int_valued("--order-font-size"),
    "order_font_color": _valued("--order-font-color"),
    "text_color": _valued("--text-color"),
    "highlight_text_color": _valued("--highlight-text-color"),
    "span_border_color": _valued("--span-border-color"),
    "background_color": _valued("--background-color"),
    "line_spacing": _valued("--line-spacing"),
    "scale_text_to_boxes": _flag_when("--no-scale-text-to-boxes", False),
    "word_hover_measure": _optional_valued("--word-hover-measure"),
    "x_field": _valued("--x-field"),
    "y_field": _valued("--y-field"),
    # Was `_CLI_IMPLICIT` ("fitting to the canvas is what `--canvas` means") —
    # true only while the figure *was* fitted; one that wasn't reproduced
    # framed on the monitor anyway.
    "fit_to_monitor": _flag_when("--no-full-monitor", False),
    "show_colorbars": _flag_when("--colorbars", True),
    "colorbar_orientation": _mapped(
        "--colorbar-orientation", {"Vertical": "vertical", "Horizontal": "horizontal"}
    ),
    "colorbar_tickangle": _int_valued("--colorbar-tickangle"),
    "colorbar_tickfont_size": _int_valued("--colorbar-tickfont-size"),
    "raw_gaze_color": _valued("--raw-gaze-color"),
    "raw_gaze_marker_size": _valued("--raw-gaze-marker-size"),
    "raw_gaze_opacity": _valued("--raw-gaze-opacity"),
    "word_heatmap_col": _valued("--word-heatmap-col"),
    "word_heatmap_title": _valued("--word-heatmap-title"),
    # The comparison's (and the co-animation's) own options.
    "show_legend": _flag_when("--compare-legend", True),
    "compare_stimulus": _lowercase("--compare-stimulus"),
    "style_a": _style_spec("--style-a"),
    "style_b": _style_spec("--style-b"),
    # CMP-24 — the co-animation's B flags.
    "fixation_flags_b": _compare_fixation_flags,
    "background_image_b": _valued("--stimulus-image-b"),
    "background_image_size_b": _pair("--stimulus-image-size-b", "x"),
    "background_image_origin_b": _pair("--stimulus-image-origin-b", ","),
}

#: Options that only mean something beside a second scanpath, and whose `render`
#: flag is refused without `--compare-with`. A *single* replay carries them too —
#: the animation builder takes them and ignores them — so there they are left
#: off the command rather than written into one `render` would reject.
_COMPARE_ONLY_SETTINGS = frozenset(
    {"show_legend", "label_a", "label_b", "compare_stimulus", "fixation_flags_b"}
)


# ---------------------------------------------------------------------------
# Emitters
# ---------------------------------------------------------------------------
def _py(value) -> str:
    """A Python literal for a settings value.

    ``repr`` is right for everything the settings dict holds (strings, numbers,
    bools, tuples, lists, dicts of those) — the one thing worth normalizing is a
    tuple, which reads better than a list for a fixed-arity pair."""
    if isinstance(value, tuple):
        inner = ", ".join(_py(item) for item in value)
        return f"({inner})" if len(value) != 1 else f"({inner},)"
    if isinstance(value, list):
        return "[" + ", ".join(_py(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_py(k)}: {_py(v)}" for k, v in value.items()) + "}"
    return repr(value)


def _one_or_list(paths) -> Any:
    """One path stays a string; several stay a list — both are accepted."""
    items = [str(p) for p in paths]
    return items[0] if len(items) == 1 else items


def _names_screen_b(state: FigureState) -> bool:
    """Whether the recipe names B's screen: only beside a B it draws."""
    return (
        state.kind in ("comparison", "animation")
        and state.compare is not None
        and bool(state.compare.screen)
        and bool(state.compare.trial)
    )


def _call_kwargs(state: FigureState, *, explicit: bool) -> list[tuple[str, Any]]:
    """The named (non-figure-keyword) arguments the API call carries.

    These are parameters of ``plot_scanpath`` / ``animate_scanpath`` /
    ``compare_scanpaths`` rather than loose figure keywords, so they are written
    by hand rather than diffed — each one is emitted only when it is doing
    something, which is the same "only the non-defaults" rule by another route.
    """
    out: list[tuple[str, Any]] = []
    # Each scanpath of a comparison or co-animation names its own screen, as the
    # app's two screen navigators pick them.
    if state.screen:
        out.append(("screen", str(state.screen)))
    if _names_screen_b(state):
        out.append(("screen_b", str(state.compare.screen)))
    if state.canvas:
        out.append(("canvas_size", (int(state.canvas[0]), int(state.canvas[1]))))
    if explicit or state.base_font_size != 16:
        out.append(("base_font_size", int(state.base_font_size)))
    if state.font_family and (explicit or _non_default_font(state.font_family)):
        out.append(("font_family", str(state.font_family)))
    if state.kind == "animation":
        if explicit or state.playback_speed != 1.0:
            out.append(("playback_speed", float(state.playback_speed)))
        if explicit or not state.autoplay:
            out.append(("autoplay", bool(state.autoplay)))
    else:
        if state.fix_index_range:
            lo, hi = state.fix_index_range
            out.append(("fix_index_range", (int(lo), int(hi))))
        if state.drift_correction:
            # The rail's own spelling is Title-case ("Warp"). `plot_scanpath`
            # lowercases internally but `compare_scanpaths` hands the string
            # straight to `alignment.correct`, so an un-lowered snippet *raises*
            # there. The CLI validator lowercases too — match it.
            out.append(("drift_correction", str(state.drift_correction).lower()))
            # Connectors are the static builder's alone (the original→corrected
            # layer has no comparison equivalent), so `compare_scanpaths` takes
            # no such keyword — see CLAUDE.md's render-path table.
            if state.drift_connectors and state.kind == "static":
                out.append(("drift_connectors", True))
    # CMP-24 — B's own window, on both builders that draw a B.
    if state.fix_index_range_b and state.compare is not None:
        lo, hi = state.fix_index_range_b
        out.append(("fix_index_range_b", (int(lo), int(hi))))
    # The disclosure is a rail choice, not a derived value: `illustration_reasons`
    # (what the app resolved it to) is in `_DERIVED_SETTINGS`, so without the
    # *label mode* the snippet would silently re-derive at "auto" and disagree
    # with the figure on screen. `compare_scanpaths` has no such parameter —
    # `state_caveats` says so rather than passing a keyword it would reject.
    if state.kind != "comparison" and (
        explicit or str(state.illustration_label).lower() != "auto"
    ):
        out.append(("illustration_label", str(state.illustration_label).lower()))
    if state.title:
        out.append(("title", str(state.title)))
    if state.caption:
        out.append(("caption", str(state.caption)))
    return out


def _non_default_font(name: str) -> bool:
    from .constants import FONT_FAMILY

    return str(name) != FONT_FAMILY


#: What a snippet names for a raw-gaze table it can't name — one that was
#: uploaded into the app, like `_IMAGE_PLACEHOLDER` for an uploaded image.
_RAW_GAZE_PLACEHOLDER = "raw_gaze.csv"


def draws_raw_gaze(state: FigureState) -> bool:
    """Whether the figure on screen draws a raw-gaze layer (EXP-20).

    The single-trial and comparison builders have one (`raw_gaze=` is a frame
    of `plot_scanpath` and, since VIZ-48, `compare_scanpaths`), so a replay that
    carries the switch draws none, and its snippet has nothing to load."""
    return state.kind in {"static", "comparison"} and bool(
        state.settings.get("show_raw_gaze")
    )


def _draws_primary_raw_gaze(state: FigureState) -> bool:
    """Whether A's dataset's samples are loaded — every drawn layer except a
    comparison whose samples all come from B's dataset (VIZ-48)."""
    return draws_raw_gaze(state) and (
        state.kind != "comparison"
        or state.compare is None
        or state.compare.primary_raw_gaze
    )


#: What a snippet names for B's raw gaze when it can't name the file (VIZ-48).
B_RAW_GAZE_PLACEHOLDER = "B_RAW_GAZE"


def _second_raw_gaze(state: FigureState) -> list[str] | None:
    """B's raw-gaze paths when the comparison draws a second dataset's samples
    (VIZ-48), its placeholder when they can't be named, else ``None``."""
    other = second_dataset(state)
    if other is None or other.raw_gaze is None or not draws_raw_gaze(state):
        return None
    return list(other.raw_gaze) or [B_RAW_GAZE_PLACEHOLDER]


def _passes_raw_gaze(source: SnippetSource, state: FigureState) -> bool:
    """Whether the builder call names ``raw_gaze=raw_gaze``.

    Wherever the layer is drawn — and always for a raw-gaze-only source
    (VIZ-45), whose samples are the data the trial is looked up in."""
    return _draws_primary_raw_gaze(state) or (
        source.kind == SOURCE_RAW_GAZE and state.kind == "static"
    )


def _raw_gaze_layer_off(source: SnippetSource, state: FigureState) -> bool:
    """A raw-gaze-only figure with the layer switched off (VIZ-45).

    `plot_scanpath` turns the layer on for the frame it is handed, and on a
    samples-only source the frame is always handed (it is the data), so *off*
    has to be written out — ``show_raw_gaze=False`` / ``--no-raw-gaze`` — or
    the recipe would draw the samples the figure on screen does not."""
    return (
        source.kind == SOURCE_RAW_GAZE
        and state.kind == "static"
        and not state.settings.get("show_raw_gaze", True)
    )


def _raw_gaze_paths(source: SnippetSource) -> list[str] | None:
    paths = source.options.get("raw_gaze")
    if not paths:
        return None
    return [str(paths)] if isinstance(paths, str) else [str(p) for p in paths]


def _raw_gaze_named(source: SnippetSource) -> bool:
    """A table the snippet can name: given as a path, or the demo's own."""
    return _raw_gaze_paths(source) is not None or source.kind == SOURCE_DEMO


def _raw_gaze_python(source: SnippetSource) -> str:
    paths = _raw_gaze_paths(source)
    if paths is None and source.kind == SOURCE_DEMO:
        return "raw_gaze = sps.load_sample_raw_gaze()"
    target = _py(_one_or_list(paths or [_RAW_GAZE_PLACEHOLDER]))
    schema = source.options.get("raw_gaze_schema")
    extra = f", raw_gaze_schema={_py(schema)}" if schema else ""
    return f"raw_gaze = sps.load_raw_gaze({target}{extra})"


def _raw_gaze_cli(source: SnippetSource) -> list[str]:
    paths = _raw_gaze_paths(source)
    if paths is None and source.kind == SOURCE_DEMO:
        return ["--sample-raw-gaze"]
    argv = ["--raw-gaze", *(paths or [_RAW_GAZE_PLACEHOLDER])]
    schema = source.options.get("raw_gaze_schema")
    if schema:
        argv += ["--raw-gaze-schema", json.dumps(schema, separators=(",", ":"))]
    return argv


#: EXP-21 — what a snippet loads scanpath B from when it comes from a second
#: dataset whose files it cannot name (an upload, a corpus the app opened).
B_WORDS_PLACEHOLDER = "B_WORDS"
B_FIXATIONS_PLACEHOLDER = "B_FIXATIONS"
#: `render`'s own default for `--compare-dataset-name` (and `compare_scanpaths`'
#: for `dataset_b=`), so the CLI half writes the flag only when it differs.
_DEFAULT_DATASET_B = "Dataset B"


def second_dataset(state: FigureState) -> CompareTarget | None:
    """Scanpath B's target when it comes from a second dataset, else ``None``.

    EXP-21: B's ids then belong to *that* corpus, so both halves load its
    tables and name B in them — ``words_b=`` / ``fixations_b=`` in Python,
    ``--compare-words`` / ``--compare-fixations`` beside ``--compare-with`` on
    the CLI — rather than looking B's reader up in A's corpus.
    """
    compare = state.compare
    if state.kind == "static" or compare is None:
        return None
    if not (compare.dataset and compare.trial):
        return None
    return compare


def _second_dataset_tables(compare: CompareTarget) -> tuple[list, list]:
    """B's words / fixations paths: the ones it was read from, when there are
    any (either may be absent, as `render` allows), else both placeholders."""
    if compare.words or compare.fixations:
        return list(compare.words), list(compare.fixations)
    return [B_WORDS_PLACEHOLDER], [B_FIXATIONS_PLACEHOLDER]


def _second_dataset_python(compare: CompareTarget) -> list[str]:
    words, fixations = _second_dataset_tables(compare)
    lines = [
        f"# Scanpath B is from a second dataset, {compare.dataset}.",
        "words_b, fixations_b = sps.load_scanpath_data(",
        f"    {_py(_one_or_list(words) if words else None)},",
        f"    {_py(_one_or_list(fixations) if fixations else None)},",
        ")",
    ]
    if compare.canvas:
        # `--compare-canvas`'s own snapshot (`cli._compare_setup_snapshot`): a
        # stated screen is a measured one, which is what the overlay gate reads.
        width, height = (int(v) for v in compare.canvas)
        lines += [
            "setup_b = SetupSnapshot(",
            f"    canvas_width={width},",
            f"    canvas_height={height},",
            "    screen_provenance=Provenance.MEASURED,",
            ")",
        ]
    return lines


def _second_dataset_kwargs(compare: CompareTarget) -> list[str]:
    kwargs = [
        "words_b=words_b",
        "fixations_b=fixations_b",
        f"dataset_b={_py(compare.dataset)}",
    ]
    if compare.canvas:
        kwargs.append("setup_b=setup_b")
    return kwargs


def _second_dataset_cli(compare: CompareTarget, *, explicit: bool) -> list[str]:
    words, fixations = _second_dataset_tables(compare)
    argv = ["--compare-words", *words] if words else []
    if fixations:
        argv += ["--compare-fixations", *fixations]
    if explicit or compare.dataset != _DEFAULT_DATASET_B:
        argv += ["--compare-dataset-name", str(compare.dataset)]
    if compare.canvas:
        width, height = (int(v) for v in compare.canvas)
        argv += ["--compare-canvas", f"{width}x{height}"]
    return argv


def python_snippet(
    source: SnippetSource,
    state: FigureState,
    *,
    explicit: bool = False,
    output: str = "",
    save_kwargs: dict | None = None,
) -> str:
    """The ``scanpath_studio.api`` code that rebuilds ``state``'s figure.

    ``output``, when given, appends the save line for that path — the same
    ``api.save_figure`` the CLI would call, with ``save_kwargs`` carrying any
    non-default raster geometry (``--width`` / ``--height`` / ``--scale``) so a
    translated invocation writes the same-sized file, not just the same
    picture."""
    loader, _ = _SOURCE_WRITERS.get(source.kind, _SOURCE_WRITERS[SOURCE_UNKNOWN])
    other = second_dataset(state)
    lines = ["import scanpath_studio as sps"]
    if other is not None and other.canvas:
        lines.append(
            "from scanpath_studio.experimental_setup import Provenance, SetupSnapshot"
        )
    lines.append("")
    lines += loader(source)
    # A raw-gaze-only source loaded its samples as its data half already.
    if _draws_primary_raw_gaze(state) and source.kind != SOURCE_RAW_GAZE:
        lines.append(_raw_gaze_python(source))
    if other is not None:
        lines += _second_dataset_python(other)
    raw_gaze_b = _second_raw_gaze(state)
    if raw_gaze_b is not None:
        lines.append(f"raw_gaze_b = sps.load_raw_gaze({_py(_one_or_list(raw_gaze_b))})")
    lines.append("")

    func = _API_FUNCTION[state.kind]
    participant, trial = _py(state.participant), _py(state.trial)
    if not (state.participant and state.trial):
        # EXP-14: an unnamed trial is `render`'s "first available" — so the
        # Python half picks that same one rather than quoting `participant=''`,
        # which matches no trial and raised on the snippet's first run.
        lines.append(
            "trials = sps.list_trials(words, fixations, raw_gaze=raw_gaze)"
            if _passes_raw_gaze(source, state)
            else "trials = sps.list_trials(words, fixations)"
        )
        for column, value in (
            ("participant_id", state.participant),
            ("trial_id", state.trial),
        ):
            if value:
                lines.append(f"trials = trials[trials[{column!r}] == {_py(value)}]")
        lines += ["participant, trial = trials.iloc[0]", ""]
        participant, trial = "participant", "trial"
    args = ["words", "fixations"]
    if state.kind == "comparison":
        compare = state.compare or CompareTarget()
        args.append(f"({participant}, {trial})")
        args.append(f"({_py(compare.participant)}, {_py(compare.trial)})")
    else:
        args.append(f"participant={participant}")
        args.append(f"trial={trial}")
        # BUG-85: a co-animation names B the way `compare_scanpaths` does — in
        # B's own frames when it comes from a second dataset (EXP-21), which
        # `trial_b=` alone would look up in this corpus.
        compare = state.compare
        if state.kind == "animation" and compare is not None and compare.trial:
            args.append(f"trial_b=({_py(compare.participant)}, {_py(compare.trial)})")
    if other is not None:
        args += _second_dataset_kwargs(other)
    if _passes_raw_gaze(source, state):
        args.append("raw_gaze=raw_gaze")
    if raw_gaze_b is not None:
        args.append("raw_gaze_b=raw_gaze_b")
    if _raw_gaze_layer_off(source, state):
        args.append("show_raw_gaze=False")

    call = [f"fig = sps.{func}("]
    call += [f"    {arg}," for arg in args]
    if state.kind == "comparison":
        compare = state.compare or CompareTarget()
        if explicit or compare.layout != "overlay":
            call.append(f"    layout={_py(compare.layout)},")
        if explicit or compare.compare_stimulus != "both":
            call.append(f"    compare_stimulus={_py(compare.compare_stimulus)},")
        # Emitted only when set, `explicit` included: the default is `None`,
        # and the labels it stands for are composed by the builder from the
        # trial ids. Writing `labels=None` would be accurate but useless, and
        # writing the auto pair would freeze a derived value into the recipe.
        if compare.labels:
            call.append(f"    labels={_py(tuple(compare.labels))},")
    for name, value in _call_kwargs(state, explicit=explicit):
        call.append(f"    {name}={_py(value)},")
    for name, value in figure_kwargs(
        state.settings, state.kind, explicit=explicit
    ).items():
        call.append(f"    {name}={_py(value)},")
    call.append(")")
    lines += call

    if output:
        extra = "".join(
            f", {name}={_py(value)}" for name, value in (save_kwargs or {}).items()
        )
        lines += ["", f"sps.save_figure(fig, {_py(output)}{extra})"]
    if source.note:
        lines = [f"# {source.note}", ""] + lines
    return "\n".join(lines)


def cli_snippet(
    source: SnippetSource,
    state: FigureState,
    *,
    explicit: bool = False,
    output: str = "scanpath.png",
    save_kwargs: dict | None = None,
) -> tuple[str, list[str]]:
    """The ``scanpath-studio render`` invocation that rebuilds ``state``'s figure.

    Returns ``(command, unsupported)``. ``unsupported`` names the settings this
    figure needs that ``render`` has no flag for — reported, never dropped, so a
    snippet can't quietly promise a figure the CLI won't produce.
    """
    _, source_cli = _SOURCE_WRITERS.get(source.kind, _SOURCE_WRITERS[SOURCE_UNKNOWN])
    other = second_dataset(state)
    argv: list[str] = ["scanpath-studio", "render"]
    if source_cli is None:
        argv += _unknown_cli(source)
    else:
        argv += source_cli(source)

    if state.participant:
        argv += ["-p", str(state.participant)]
    if state.trial:
        argv += ["-t", str(state.trial)]
    if state.screen:
        argv += ["--screen", str(state.screen)]
    if _names_screen_b(state):
        argv += ["--compare-screen", str(state.compare.screen)]
    if state.canvas:
        argv += ["--canvas", f"{int(state.canvas[0])}x{int(state.canvas[1])}"]
    if explicit or state.base_font_size != 16:
        argv += ["--font-size", str(int(state.base_font_size))]
    if state.font_family and (explicit or _non_default_font(state.font_family)):
        argv += ["--font-family", str(state.font_family)]
    # `render`'s compare branch passes neither to `compare_scanpaths` (which has
    # no parameter for either), so emitting them beside a Python form that
    # correctly omits them would be the two flavours contradicting each other.
    if state.kind != "comparison" and (
        explicit or str(state.illustration_label).lower() != "auto"
    ):
        argv += ["--illustration-label", str(state.illustration_label).lower()]
    if state.title:
        argv += ["--title", str(state.title)]
    if state.caption:
        argv += ["--caption", str(state.caption)]

    unsupported: list[str] = []
    env_prefix = ""
    if state.kind == "animation":
        argv.append("--animate")
        if explicit or state.playback_speed != 1.0:
            argv += ["--playback-speed", _num(state.playback_speed)]
        if not state.autoplay:
            argv.append("--no-autoplay")
        # EXP-20: CMP-11's two-reading replay. `render --animate --compare-with`
        # draws it, and the replay's B-side options (`--compare-stimulus`, the
        # labels, the legend) are refused without it. EXP-21: a second
        # dataset's B is named in that dataset's own tables, as in Python.
        if state.compare is not None and state.compare.trial:
            argv += [
                "--compare-with",
                f"{state.compare.participant}:{state.compare.trial}",
            ]
            if other is not None:
                argv += _second_dataset_cli(other, explicit=explicit)
    else:
        if state.drift_correction:
            # PRE-21 gates both flags behind SCANPATH_EXPERIMENTAL=1, so
            # `_render_parser` only grows them when it is set. Checking the gate
            # *here* would be no check at all — `_collect_viz_settings` already
            # forces `align_algorithm` to "Off" unless it is open, so a state
            # that carries a correction can only have come from a process where
            # it was. The command is copied into *another* terminal, though, so
            # it has to carry the variable with it or die on `unrecognized
            # arguments` there.
            env_prefix = "SCANPATH_EXPERIMENTAL=1"
            argv += ["--drift-correction", str(state.drift_correction).lower()]
            # Static-only, exactly as `_call_kwargs` has it: `render`'s compare
            # branch never forwards it, so emitting it here would be the two
            # flavours of one recipe disagreeing.
            if state.drift_connectors and state.kind == "static":
                argv.append("--drift-connectors")
    # VIZ-7's fixation-index window is a `plot_scanpath` / `animate_scanpath`
    # parameter rather than a figure keyword, so it is written by hand like the
    # drift pair above rather than through `_CLI_EMITTERS`. Both builders take
    # it, so it sits outside the static/animation split.
    if state.fix_index_range:
        lo, hi = state.fix_index_range
        argv += ["--fix-index-range", f"{int(lo)}:{int(hi)}"]
    if state.fix_index_range_b and state.compare is not None:
        lo, hi = state.fix_index_range_b
        argv += ["--compare-fix-index-range", f"{int(lo)}:{int(hi)}"]
    # A raw-gaze-only source's input flags *are* its --raw-gaze (VIZ-45).
    if _draws_primary_raw_gaze(state) and source.kind != SOURCE_RAW_GAZE:
        argv += _raw_gaze_cli(source)
    if _raw_gaze_layer_off(source, state):
        argv.append("--no-raw-gaze")
    if state.kind == "comparison":
        compare = state.compare or CompareTarget()
        argv += ["--compare-with", f"{compare.participant}:{compare.trial}"]
        if other is not None:
            argv += _second_dataset_cli(other, explicit=explicit)
        raw_gaze_b = _second_raw_gaze(state)
        if raw_gaze_b is not None:
            argv += ["--compare-raw-gaze", *raw_gaze_b]
        argv += ["--compare-layout", _CLI_COMPARE_LAYOUT.get(compare.layout, "overlay")]
        if explicit or compare.compare_stimulus != "both":
            argv += ["--compare-stimulus", str(compare.compare_stimulus).lower()]
        # Both or neither, matching `render`'s own rule: a lone label would
        # leave the other side to the builder's auto composition, which is not
        # a pair `compare_scanpaths` can be given.
        if compare.labels:
            label_a, label_b = compare.labels
            argv += ["--label-a", str(label_a), "--label-b", str(label_b)]

    palette, palette_colors = _matching_palette(state.settings, state.kind)
    kwargs = figure_kwargs(state.settings, state.kind, explicit=explicit)
    if palette:
        argv += ["--palette", palette]
        kwargs = _restate_against_palette(
            kwargs, state.settings, state.kind, palette_colors
        )
    for key, value in kwargs.items():
        # EXP-12: never emit class colours the figure isn't drawing —
        # `--saccade-type-color` implies By type, so emitting them into a
        # Uniform figure switched its saccades to the five-way split.
        if key == "saccade_class_colors":
            if _classes_coloured(state.settings):
                argv += _saccade_class_colors(
                    value, palette_colors.get("saccade_class_colors")
                )
            continue
        if key in _COMPARE_ONLY_SETTINGS and (
            state.kind == "animation" and state.compare is None
        ):
            continue  # a single replay takes these and draws nothing with them
        emit = _CLI_EMITTERS.get(key)
        if emit is None:
            unsupported.append(key)
            continue
        argv += emit(value)

    # The raster geometry `save_figure` would be given. `render` has the same
    # three flags, so a translated invocation has to carry them or write a
    # differently-sized file than the Python form beside it.
    for name in ("width", "height", "scale"):
        value = (save_kwargs or {}).get(name)
        if value is not None:
            argv += [f"--{name}", _num(value)]

    argv += ["-o", output]
    unsupported.extend(source.cli_unsupported)
    if source_cli is None:
        unsupported.append(f"the {source.label or source.kind} data source")
    return _wrap_command(argv, env_prefix=env_prefix), sorted(
        dict.fromkeys(unsupported)
    )


#: Settings-vocabulary layout → the `--compare-layout` choice.
_CLI_COMPARE_LAYOUT = {
    "overlay": "overlay",
    "side_by_side": "side-by-side",
    "side-by-side": "side-by-side",
    "stacked": "stacked",
}


def _wrap_command(argv: list[str], width: int = 76, *, env_prefix: str = "") -> str:
    """One shell command, wrapped with backslash continuations.

    Wrapped on flag boundaries (a token starting ``-`` opens a new group) so a
    flag never ends up on a different line from its value — that is the one way
    a wrapped command can be pasted and silently mean something else.

    ``env_prefix`` is prepended verbatim (already shell-safe, never user text):
    a flag the parser only grows under an environment variable has to be pasted
    together with it."""
    groups: list[list[str]] = []
    for token in argv:
        if token.startswith("-") or not groups:
            groups.append([token])
        else:
            groups[-1].append(token)
    if env_prefix and groups:
        groups[0].insert(0, env_prefix)
    lines: list[str] = []
    current = ""
    for group in groups:
        # `env_prefix and` matters: without it an *empty* token compares equal to
        # the empty default prefix and is emitted verbatim — so
        # `--highlight-column ''` (mark nothing) printed as a flag with no value,
        # which the parser would then read as taking the next flag as its value.
        piece = " ".join(
            token if (env_prefix and token == env_prefix) else shlex.quote(token)
            for token in group
        )
        if not current:
            current = piece
        elif len(current) + len(piece) + 1 <= width:
            current = f"{current} {piece}"
        else:
            lines.append(current)
            current = f"  {piece}"
    if current:
        lines.append(current)
    return " \\\n".join(lines)


@dataclass(frozen=True)
class ReproductionCode:
    """Both flavours of one figure's recipe, plus what neither can promise.

    ``cli_unsupported`` names settings the ``render`` parser has no flag for;
    ``caveats`` are the human-readable notes that apply to **both** snippets —
    data the code can't name, a layer that needs a frame rather than a keyword.
    """

    python: str
    cli: str
    cli_unsupported: tuple[str, ...] = ()
    caveats: tuple[str, ...] = ()


def state_caveats(source: SnippetSource, state: FigureState) -> list[str]:
    """What the snippets can't promise about ``state``, in the user's terms."""
    notes = []
    if source.note:
        notes.append(source.note)
    if _draws_primary_raw_gaze(state) and not _raw_gaze_named(source):
        notes.append(
            "The raw gaze was loaded into the app, so the snippet can't name the "
            f"file it came from and loads `{_RAW_GAZE_PLACEHOLDER}` instead — "
            "point it at your own table."
        )
    if _second_raw_gaze(state) == [B_RAW_GAZE_PLACEHOLDER]:
        notes.append(
            "Scanpath B's raw gaze was loaded into the app, so the snippet can't "
            f"name its file and loads `{B_RAW_GAZE_PLACEHOLDER}` instead — point "
            "it at your own table."
        )
    if any(
        _is_data_uri(state.settings.get(key))
        for key in ("background_image", "background_image_b")
    ):
        notes.append(
            "The stimulus image was uploaded into the app, so the snippet "
            f"names `{_IMAGE_PLACEHOLDER}` instead — point it at your own file."
        )
    # CMP-8 / EXP-21: scanpath B can come from a *second* dataset, and its
    # participant id is that corpus's own. Both halves load B's tables and name
    # B in them (`words_b=` / `--compare-words`); when the snippet can't name
    # those tables it writes placeholders, and this says whose they are.
    other = second_dataset(state)
    if other is not None:
        note = (
            f"Scanpath B comes from a second dataset (`{other.dataset}`), so "
            f"`{other.participant}` is that corpus's reader, not this one's."
        )
        if not (other.words or other.fixations):
            note += (
                f" The snippet loads it from `{B_WORDS_PLACEHOLDER}` / "
                f"`{B_FIXATIONS_PLACEHOLDER}` (`--compare-words` / "
                "`--compare-fixations` on the CLI): point those at its tables."
            )
        if state.kind == "animation" and other.canvas is None:
            # CMP-21: with `dataset_b=`, `animate_scanpath` checks the two screens
            # as the app did before drawing this — and a screen nobody states is
            # read off that trial's data, which rarely matches, so B's is named.
            note += (
                " A co-animation needs both readings on one screen, so state B's "
                "too, as `setup_b=` (`--compare-canvas` on the CLI): one read off "
                "B's data rarely matches."
            )
        notes.append(note)
    if state.kind == "comparison" and str(state.illustration_label).lower() != "auto":
        notes.append(
            "`compare_scanpaths` has no `illustration_label` parameter, so the "
            "snippet leaves your **"
            f"{str(state.illustration_label).capitalize()}** choice off — the "
            "disclosure is re-derived from the figure."
        )
    return notes


def reproduction_code(
    source: SnippetSource,
    state: FigureState,
    *,
    explicit: bool = False,
    output: str = "scanpath.png",
    save_kwargs: dict | None = None,
    extra_caveats: tuple[str, ...] = (),
) -> ReproductionCode:
    """Both snippets for one figure — the pair the Share subtab shows."""
    command, unsupported = cli_snippet(
        source, state, explicit=explicit, output=output, save_kwargs=save_kwargs
    )
    return ReproductionCode(
        python=python_snippet(
            source,
            state,
            explicit=explicit,
            output=output,
            save_kwargs=save_kwargs,
        ),
        cli=command,
        cli_unsupported=tuple(unsupported),
        caveats=tuple(state_caveats(source, state)) + tuple(extra_caveats),
    )
