"""The recovery cache's sidecar lock on Windows, where ``msvcrt.locking``'s
own blocking mode gives up after about ten seconds: the lock waits out
another process's long save instead, up to a ceiling. Windows cannot run here,
so ``msvcrt`` and the clock are stood in for."""

from __future__ import annotations

import errno
import sys

import pytest

from scanpath_studio import file_lock as lock_module
from scanpath_studio.file_lock import file_lock


class FakeMsvcrt:
    """``msvcrt.locking`` for a lock another process holds for ``busy`` tries."""

    LK_UNLCK, LK_LOCK, LK_NBLCK, LK_RLCK, LK_NBRLCK = range(5)

    def __init__(self, busy: float = 0, error: int = errno.EACCES):
        self.busy = busy
        self.error = error
        self.calls: list[int] = []

    def locking(self, fd: int, mode: int, nbytes: int) -> None:
        assert nbytes == 1
        self.calls.append(mode)
        if mode != self.LK_UNLCK and self.busy:
            self.busy -= 1
            raise OSError(self.error, "Permission denied")


@pytest.fixture
def windows(monkeypatch):
    """Lock as on Windows, with a fake clock that each sleep moves on."""
    now = [0.0]
    slept: list[float] = []

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(lock_module, "_ON_WINDOWS", True)
    monkeypatch.setattr(lock_module, "_clock", lambda: now[0])
    monkeypatch.setattr(lock_module, "_sleep", sleep)

    def install(fake: FakeMsvcrt) -> list[float]:
        monkeypatch.setitem(sys.modules, "msvcrt", fake)
        return slept

    return install


@pytest.mark.parametrize("reading", [False, True])
def test_a_lock_another_process_holds_is_waited_for(tmp_path, windows, reading):
    fake = FakeMsvcrt(busy=40)
    slept = windows(fake)
    with file_lock(tmp_path / ".lock", reading=reading):
        entered = list(fake.calls)
    # Never the blocking modes, which give up; readers lock alone too.
    assert entered == [fake.LK_NBLCK] * 41
    assert slept == [lock_module.WINDOWS_RETRY_S] * 40
    assert fake.calls[-1] == fake.LK_UNLCK


def test_a_save_that_outlasts_the_ceiling_is_given_up_on(tmp_path, windows):
    fake = FakeMsvcrt(busy=float("inf"))
    slept = windows(fake)
    with pytest.raises(OSError):
        with file_lock(tmp_path / ".lock"):
            pytest.fail("entered a lock another process holds")
    assert sum(slept) == pytest.approx(lock_module.WINDOWS_WAIT_S, abs=0.1)
    assert fake.LK_UNLCK not in fake.calls


def test_a_failure_that_is_not_contention_is_not_waited_out(tmp_path, windows):
    fake = FakeMsvcrt(busy=1, error=errno.EBADF)
    slept = windows(fake)
    with pytest.raises(OSError):
        with file_lock(tmp_path / ".lock"):
            pass
    assert slept == []


def test_the_lock_is_released_when_the_transaction_fails(tmp_path, windows):
    fake = FakeMsvcrt()
    windows(fake)
    with pytest.raises(RuntimeError):
        with file_lock(tmp_path / ".lock"):
            raise RuntimeError("the save failed")
    assert fake.calls == [fake.LK_NBLCK, fake.LK_UNLCK]
