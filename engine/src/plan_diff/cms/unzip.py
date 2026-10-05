"""Unzip a fetched CMS file into a sibling folder under data/raw/ (review 1 finding 6).

Refuses a member with an absolute path, a drive letter, a `..` part, or a symlink (zip slip), too
many members, or too many uncompressed bytes. Extraction goes to a temp folder that is swapped in
only when every member is written, and is skipped when the zip's hash has not changed.
"""

import hashlib
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from plan_diff import config

MARKER = ".source-sha256"  # inside the folder: the hash of the zip it came from


class UnzipRefused(Exception):
    """The zip was refused. Nothing was written. The message says why."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _check_member(zip_path: Path, info: zipfile.ZipInfo) -> None:
    name = info.filename.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if name.startswith("/") or (len(name) > 1 and name[1] == ":") or ".." in parts:
        raise UnzipRefused(
            f"{zip_path.name}: member {info.filename!r} would land outside the folder"
        )
    if stat.S_ISLNK(info.external_attr >> 16):
        raise UnzipRefused(f"{zip_path.name}: member {info.filename!r} is a symlink")


def unzip_cms(
    zip_path: Path,
    *,
    max_members: int = config.UNZIP_MAX_MEMBERS,
    max_bytes: int = config.UNZIP_MAX_BYTES,
) -> tuple[Path, bool]:
    """Extract `zip_path` into `<same folder>/<zip name without .zip>/`. Returns the folder and
    whether it was (re)extracted; False means the folder already came from this exact zip."""
    dest = zip_path.with_suffix("")
    digest = _sha256(zip_path)
    marker = dest / MARKER
    if dest.exists():
        if not marker.is_file():
            raise UnzipRefused(f"{dest} exists but was not made by unzip; move it away first")
        if marker.read_text().strip() == digest:
            return dest, False
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        if len(infos) > max_members:
            raise UnzipRefused(f"{zip_path.name}: {len(infos)} members, over {max_members}")
        for info in infos:
            _check_member(zip_path, info)
        if sum(i.file_size for i in infos) > max_bytes:
            raise UnzipRefused(f"{zip_path.name}: declares over {max_bytes} uncompressed bytes")
        tmp = Path(tempfile.mkdtemp(dir=zip_path.parent, prefix=f".{dest.name}.", suffix=".part"))
        try:
            written = 0
            for info in infos:
                target = tmp / info.filename.replace("\\", "/")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, target.open("wb") as out:
                    for chunk in iter(lambda: src.read(1024 * 1024), b""):
                        written += len(chunk)
                        if written > max_bytes:
                            raise UnzipRefused(
                                f"{zip_path.name}: over {max_bytes} bytes once uncompressed"
                            )
                        out.write(chunk)
            (tmp / MARKER).write_text(digest + "\n")
            if dest.exists():
                shutil.rmtree(dest)  # our own earlier extraction of an older zip (marker checked)
            os.replace(tmp, dest)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)  # a no-op once it was moved into place
    return dest, True
