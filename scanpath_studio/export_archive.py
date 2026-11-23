"""Disk-backed bulk downloads. Each request serves at most one piece of a ZIP."""

from __future__ import annotations

import io
import os
import secrets
import shutil
import zipfile
from contextlib import ExitStack, closing
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from urllib.parse import urlencode

_PART_BYTES = 8 * 1024**2
_SMALL_ZIP = 32 * 1024**2
_ROOT_LOCK = Lock()
_root: TemporaryDirectory | None = None


def _download_root() -> TemporaryDirectory:
    global _root
    with _ROOT_LOCK:
        if _root is None:
            root = TemporaryDirectory(prefix="scanpath-downloads-")
            assets = Path(__file__).parent / "assets" / "bundle_download"
            for name in ("index.html", "worker.js"):
                shutil.copyfile(assets / name, Path(root.name) / name)
            _root = root
        return _root


class DiskBundle:
    """One ZIP in numbered pieces, owned by the session that built it."""

    def __init__(self) -> None:
        self._directory = TemporaryDirectory(
            prefix=secrets.token_urlsafe(32) + "-", dir=_download_root().name
        )
        self.folder = Path(self._directory.name)
        self.part_size = _PART_BYTES
        self.size = 0
        self.parts = 0

    def __len__(self) -> int:
        return self.size

    def part(self, index: int) -> Path:
        return self.folder / f"{index}.part"

    def open(self) -> io.BufferedReader:
        """Seekable input for zipfile when retrying a partial bundle."""
        return io.BufferedReader(_PartReader(self))

    def close(self) -> None:
        self._directory.cleanup()

    def download_url(self, filename: str) -> str:
        """A same-origin download page under the app's own URL prefix."""
        from streamlit.components.v1 import declare_component

        component = declare_component("bulk_download", path=str(self.folder.parent))
        params = urlencode(
            dict(
                id=self.folder.name, name=filename, size=self.size, part=self.part_size
            )
        )
        return f"component/{component.name}/index.html#{params}"


class _PartReader(io.RawIOBase):
    def __init__(self, bundle: DiskBundle):
        super().__init__()
        self.bundle = bundle
        self.pos = 0
        self.index = None
        self.file = None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        origins = {os.SEEK_SET: 0, os.SEEK_CUR: self.pos, os.SEEK_END: self.bundle.size}
        if whence not in origins or origins[whence] + offset < 0:
            raise OSError("Invalid ZIP seek")
        self.pos = origins[whence] + offset
        return self.pos

    def readinto(self, target):
        if self.pos >= self.bundle.size:
            return 0
        index, offset = divmod(self.pos, self.bundle.part_size)
        if index != self.index:
            if self.file is not None:
                self.file.close()
            self.file = self.bundle.part(index).open("rb")
            self.index = index
        self.file.seek(offset)
        count = self.file.readinto(target)
        self.pos += count
        return count

    def close(self):
        if self.file is not None:
            self.file.close()
        super().close()


class _PartWriter:
    """An append-only ZIP destination. zipfile writes its sizes in data descriptors."""

    def __init__(self, bundle):
        self.bundle = bundle
        self.file = None

    def write(self, data):
        view = memoryview(data)
        while view:
            offset = self.bundle.size % self.bundle.part_size
            if offset == 0:
                self.close()
                self.file = self.bundle.part(self.bundle.parts).open("wb")
                self.bundle.parts += 1
            count = self.file.write(view[: self.bundle.part_size - offset])
            self.bundle.size += count
            view = view[count:]
        return len(data)

    def flush(self):
        if self.file is not None:
            self.file.flush()

    def close(self):
        if self.file is not None:
            file = self.file
            self.file = None
            file.close()


def open_bundle(data):
    return data.open() if isinstance(data, DiskBundle) else io.BytesIO(data)


def build_download(build, *args, **kwargs):
    """Build into private temporary files and keep only small downloads as bytes."""
    bundle = DiskBundle()
    with ExitStack() as cleanup:
        cleanup.callback(bundle.close)
        with (
            closing(_PartWriter(bundle)) as writer,
            zipfile.ZipFile(writer, "w", zipfile.ZIP_DEFLATED) as archive,
        ):
            result, progress = build(*args, _archive=archive, **kwargs)
        if result is not None:  # A retry with no failures keeps its existing bundle.
            return result, progress
        if bundle.size <= _SMALL_ZIP:
            with bundle.open() as source:
                return source.read(), progress
        # The session now owns these files through the returned DiskBundle.
        cleanup.pop_all()
        return bundle, progress
