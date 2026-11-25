"""The caching conventions, checked on every cached function in the package.

`@st.cache_data` (and `@st.cache_resource`) hashes each argument on every
call. A DataFrame argument is hashed in full on every rerun unless its name
starts with `_`, which leaves it out of the key; its identity then travels as
an explicit `data.frame_fingerprint(...)` argument. And a cached function must
not draw: Streamlit replays what a cached call drew, so an element made inside
one reappears wherever the result is next used, and the caller's layout is no
longer its own. REVIEW.md's Performance items state both rules; this reads
every cached function for them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import scanpath_studio

PACKAGE = Path(scanpath_studio.__file__).parent

#: Cached functions that draw, each with why that is right.
_DRAWS_ON_PURPOSE = {
    ("data.py", "load_sample_data"): (
        "draws only the missing-installation error and returns no data; the "
        "replay keeps the error on screen while that is the result"
    ),
    ("data.py", "load_onestop_server_bundle"): (
        "draws only the server's missing-files errors: a participant without "
        "files stops the run, so nothing is cached; missing full exports return "
        "no data, and the replay keeps that error on screen beside it"
    ),
}

#: The decorators that cache, as attributes (`st.cache_data`) or imported names.
_CACHING = ("cache_data", "cache_resource")

#: Parameter names that hold a table, for the many cached helpers whose
#: parameters carry no annotation (`def _c_word_rate(_words, …)`).
_TABLE_NAME = re.compile(
    r"^(words|fixations|raw_gaze|gaze|samples|combos|df|frame|table)$"
    r"|_(df|frame|words|fixations|raw_gaze|combos|table)$"
)


def _cached_functions():
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in fn.decorator_list:
                target = (
                    decorator.func if isinstance(decorator, ast.Call) else decorator
                )
                name = (
                    target.attr
                    if isinstance(target, ast.Attribute)
                    else getattr(target, "id", None)
                )
                if name in _CACHING:
                    yield path.name, fn
                    break


def _holds_a_table(arg: ast.arg) -> bool:
    if arg.annotation is not None:
        return "DataFrame" in ast.unparse(arg.annotation)
    return bool(_TABLE_NAME.search(arg.arg))


def test_there_are_cached_functions_to_check():
    assert len(list(_cached_functions())) > 50


def test_no_cached_function_hashes_a_dataframe():
    offenders = [
        f"{module}:{fn.lineno} {fn.name}({arg.arg})"
        for module, fn in _cached_functions()
        for arg in (*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs)
        if _holds_a_table(arg) and not arg.arg.startswith("_")
    ]
    assert not offenders, (
        "a cached function hashes a whole DataFrame on every call; prefix the "
        "parameter with `_` and pass `data.frame_fingerprint(df)` as its key: "
        f"{offenders}"
    )


def test_no_cached_function_draws():
    offenders = []
    for module, fn in _cached_functions():
        if (module, fn.name) in _DRAWS_ON_PURPOSE:
            continue
        for node in ast.walk(fn):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "st"
                and node.attr not in _CACHING
            ):
                offenders.append(f"{module}:{node.lineno} {fn.name}: st.{node.attr}")
    assert not offenders, (
        "a cached function draws or reads the session (Streamlit replays what it "
        "drew, and the cache key does not see the session); draw in the caller: "
        f"{offenders}"
    )


def test_every_exception_still_names_a_cached_function():
    cached = {(module, fn.name) for module, fn in _cached_functions()}
    assert set(_DRAWS_ON_PURPOSE) <= cached, set(_DRAWS_ON_PURPOSE) - cached
