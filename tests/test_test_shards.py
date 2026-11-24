"""CI splits the suite over machines by `SCANPATH_TEST_SHARD` (tests/conftest.py).

The shares must never overlap and must add up to the whole suite: a test in no
share would never run on a PR, and one in two would run twice.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests import conftest


class _Config:
    def __init__(self):
        self.deselected: list = []
        self.hook = SimpleNamespace(pytest_deselected=self._deselect)

    def _deselect(self, items):
        self.deselected.extend(items)


def _share(nodeids: list[str], spec: str, monkeypatch) -> tuple[list, list]:
    monkeypatch.setenv(conftest.SHARD_ENV, spec)
    items = [SimpleNamespace(nodeid=nodeid) for nodeid in nodeids]
    config = _Config()
    conftest.pytest_collection_modifyitems(config, items)
    return [i.nodeid for i in items], [i.nodeid for i in config.deselected]


@given(
    nodeids=st.lists(st.text(min_size=1), unique=True, max_size=50),
    total=st.integers(min_value=1, max_value=8),
)
def test_the_shares_are_the_whole_suite_once(nodeids, total):
    with pytest.MonkeyPatch.context() as monkeypatch:
        shares = [
            _share(nodeids, f"{k}/{total}", monkeypatch) for k in range(1, total + 1)
        ]
    run = [nodeid for kept, _ in shares for nodeid in kept]
    assert sorted(run) == sorted(nodeids)
    for kept, deselected in shares:
        assert sorted(kept + deselected) == sorted(nodeids)


def test_no_share_set_runs_everything(monkeypatch):
    monkeypatch.delenv(conftest.SHARD_ENV, raising=False)
    items = [SimpleNamespace(nodeid=f"tests/test_x.py::t{i}") for i in range(5)]
    conftest.pytest_collection_modifyitems(_Config(), items)
    assert len(items) == 5


@pytest.mark.parametrize("spec", ["0/4", "5/4"])
def test_a_share_outside_its_range_is_refused(spec, monkeypatch):
    with pytest.raises(pytest.UsageError):
        _share(["tests/test_x.py::t"], spec, monkeypatch)
