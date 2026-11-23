"""An advisory lock shared by independent processes publishing local files."""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(path: Path, *, reading: bool = False) -> Iterator[None]:
    """Hold a stable sidecar open through one read or publish transaction.

    Readers can open an existing lock without write access. A read-only
    cache created before sidecar locks existed still opens.
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
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(
                handle.fileno(), msvcrt.LK_RLCK if reading else msvcrt.LK_LOCK, 1
            )
        else:
            import fcntl

            fcntl.flock(handle, fcntl.LOCK_SH if reading else fcntl.LOCK_EX)
        # Closing the handle releases the lock, including after an exception.
        yield
