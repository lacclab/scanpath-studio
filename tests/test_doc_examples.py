"""ENG-53 — the documented examples run as written.

The pre-beta audit found a dozen examples in the docs that failed when pasted:
demo ids that do not exist (``-p 1 -t 1``, ``p2:t5``, ``l7_101``), a
``--heatmap-style`` spelling the parser rejects, keyword names no function
takes. Each was a doc drifting from the code with nothing to notice. These
tests run every ``render --sample`` command in the CLI-facing pages and the
Python examples that name demo ids, so the next drift fails here instead."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from scanpath_studio import api, cli

DOCS = Path(__file__).resolve().parents[1] / "docs"
#: The pages whose shell examples use the bundled demo.
PAGES = ("cli.md", "automation.md", "agents.md")


def _sample_commands(page: str) -> list[str]:
    """Every ``scanpath-studio render --sample …`` command in a page's bash
    blocks, backslash continuations joined and trailing comments dropped."""
    text = (DOCS / page).read_text(encoding="utf-8")
    commands = []
    for block in re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL):
        joined = re.sub(r"\\\n\s*", " ", block)
        for line in joined.splitlines():
            line = line.split("  #")[0].strip()
            if line.startswith("scanpath-studio render --sample"):
                commands.append(line)
    return commands


CASES = [(page, command) for page in PAGES for command in _sample_commands(page)]


def test_the_pages_still_have_sample_commands():
    """Guard the extractor: an empty parametrization would pass vacuously."""
    assert len(CASES) >= 8


@pytest.mark.parametrize(("page", "command"), CASES)
def test_a_documented_sample_command_runs(tmp_path, monkeypatch, page, command):
    argv = shlex.split(command)[1:]
    # The output is rewritten to HTML in a temp dir: the example is about its
    # flags, and a static format would need Chrome on the test machine.
    if "-o" in argv:
        index = argv.index("-o") + 1
        argv[index] = str(tmp_path / (Path(argv[index]).stem + ".html"))
    monkeypatch.chdir(tmp_path)
    cli.main(argv)


def test_the_documented_figure_code_call_builds_its_figure(monkeypatch):
    """docs/api.md, docs/automation.md and the `figure_code` docstring name
    this trial; the snippet it prints has to run against the demo."""
    import scanpath_studio as sps

    code = sps.figure_code(
        participant="l7_1090", trial="l7_1090_2_1_1_Ele_r0", show_heatmap=False
    )
    monkeypatch.setattr(api, "save_figure", lambda fig, path, **kwargs: path)
    namespace: dict = {}
    exec(compile(code, "<figure_code>", "exec"), namespace)  # noqa: S102
    assert namespace["fig"].data


def test_the_documented_examples_name_real_demo_ids():
    """The ids the Python examples quote exist in the bundled demo."""
    combos = api.list_trials(*api.load_sample_data())
    pairs = set(combos.itertuples(index=False, name=None))
    for pair in (
        ("l37_1129", "l37_1129_2_1_1_Ele_r0"),
        ("l7_1090", "l7_1090_2_1_1_Ele_r0"),
    ):
        assert pair in pairs
    for page in ("api.md", "automation.md"):
        text = (DOCS / page).read_text(encoding="utf-8")
        assert "l7_101" not in text and "1_Adv_1" not in text


def test_the_api_docstrings_use_names_the_package_root_has():
    """`sps.api.…` raises AttributeError on a fresh `import scanpath_studio as
    sps` — the package root resolves its exports lazily and `api` is not one."""
    source = (Path(api.__file__)).read_text(encoding="utf-8")
    assert "sps.api." not in source


def test_the_documented_duration_mass_spelling_parses():
    """docs/cli.md spelled it `'Duration mass'` — the settings vocabulary, not
    the flag's — which argparse rejects."""
    text = (DOCS / "cli.md").read_text(encoding="utf-8")
    fragment = re.search(r"`(--heatmap-style [^`]+)`", text).group(1)
    args = cli._render_parser().parse_args(["--sample", *shlex.split(fragment)])
    assert args.heatmap_style == "duration-mass"
