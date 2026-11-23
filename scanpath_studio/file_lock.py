"""An advisory lock shared by independent processes publishing local files."""

from __future__ import annotations

import errno
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: Whether locks go through ``msvcrt`` (Windows) rather than ``fcntl``.
_ON_WINDOWS = os.name == "nt"
#: How long a Windows lock waits for another process to let go. On POSIX
#: ``flock`` waits as long as it takes; ``msvcrt.locking``'s own blocking mode
#: gives up after about ten seconds, which a save or a restore of large tables
#: outlasts. Ten minutes is the age at which the cache treats an unnamed file
#: as no save's work in progress (``persistence._STALE_AFTER_S``).
WINDOWS_WAIT_S = 600.0
#: The pause between two tries of a Windows lock.
WINDOWS_RETRY_S = 0.05
#: The errors ``msvcrt.locking`` reports a lock another process holds with.
_CONTENDED = frozenset(
    {errno.EACCES, errno.EDEADLK, getattr(errno, "EDEADLOCK", errno.EDEADLK)}
)
# The wait's clock and sleep: module attributes, so a test can replace them.
_clock = time.monotonic
_sleep = time.sleep


@contextmanager
def file_lock(path: Path, *, reading: bool = False) -> Iterator[None]:
    """Hold a stable sidecar open through one read or publish transaction.

    Readers can open an existing lock without write access. A read-only
    cache created before sidecar locks existed still opens.

    On POSIX readers share the lock and a writer holds it alone. ``msvcrt``
    has no shared lock, so on Windows a reader holds it alone too: two
    restores take turns, as a restore and a save do.
    """
    try:
        handle = path.open("a+b")
    except OSError as exc:
        if not reading or exc.errno not in (errno.EACCES, errno.EPERM, errno.EROFS):
            raise
        try:
            handle = path.open("rb")
        except FileNotFoundError:
            yield
            return
    with handle:
        if _ON_WINDOWS:
            import msvcrt

            _lock_windows(handle, msvcrt)
            try:
                yield
            finally:
                _unlock_windows(handle, msvcrt)
            return
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_SH if reading else fcntl.LOCK_EX)
        # Closing the handle releases the lock, including after an exception.
        yield


def _lock_windows(handle, msvcrt) -> None:
    """Lock the sidecar's first byte, waiting up to `WINDOWS_WAIT_S` for
    another process's transaction to end; the ``OSError`` after that, or at
    once for any other failure."""
    deadline = _clock() + WINDOWS_WAIT_S
    while True:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError as exc:
            if exc.errno not in _CONTENDED or _clock() >= deadline:
                raise
        _sleep(WINDOWS_RETRY_S)


def _unlock_windows(handle, msvcrt) -> None:
    """Release the lock now: Windows frees a closed file's locks only when
    its resources allow."""
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass  # closing the handle releases it all the same
