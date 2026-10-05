"""Download the public source documents listed in sources/manifest.json, slowly and hash-checked.

A file whose SHA-256 differs from the manifest is refused and nothing is written. A file with no
hash yet is only downloaded with --pin, which records its hash (trust on first use).
"""

import hashlib
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from plan_diff import __version__, config
from plan_diff.models import SourceDocument, SourcesManifest

USER_AGENT = f"plan-diff/{__version__} (public plan document research; one slow download per file)"


@dataclass(frozen=True)
class FetchSettings:
    delay_s: float = config.FETCH_DELAY_S
    max_bytes: int = config.FETCH_MAX_BYTES


class FetchRefused(Exception):
    """One document was refused. The message says why in plain words."""


def make_client() -> httpx.Client:
    return httpx.Client(timeout=config.FETCH_TIMEOUT_S, follow_redirects=True)


def file_name(doc: SourceDocument) -> str:
    return doc.document_id + (".zip" if doc.document_type.startswith("CMS_") else ".pdf")


def _expected_magic(doc: SourceDocument) -> tuple[bytes, str]:
    """The first bytes a real file of this type starts with, and a plain name for the type."""
    if doc.document_type.startswith("CMS_"):
        return b"PK\x03\x04", "ZIP"
    return b"%PDF-", "PDF"


def _check_content(doc: SourceDocument, path: Path) -> None:
    magic, kind = _expected_magic(doc)
    with path.open("rb") as fh:
        head = fh.read(len(magic))
    if head != magic:
        raise FetchRefused(
            f"{doc.document_id}: the server sent something that is not a {kind} "
            f"(it starts with {head!r}). Nothing was written."
        )


def _quarantine(path: Path, out: Path) -> Path:
    """Move a bad file out of the way so no later step reads it."""
    rejected = out / ".rejected"
    rejected.mkdir(exist_ok=True)
    target = rejected / path.name
    os.replace(path, target)
    return target


def _download(client: httpx.Client, doc: SourceDocument, out: Path, max_bytes: int) -> Path:
    """Stream to a temp file in `out` and return its path. The caller moves or deletes it."""
    fd, tmp_name = tempfile.mkstemp(dir=out, prefix=f".{doc.document_id}.", suffix=".part")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            ua = {"User-Agent": USER_AGENT}
            with client.stream("GET", str(doc.url), headers=ua) as response:
                asked, landed = httpx.URL(str(doc.url)).host, response.url.host
                if landed != asked:
                    raise FetchRefused(
                        f"{doc.document_id}: redirected from {asked} to {landed}, another host"
                    )
                response.raise_for_status()
                declared = int(response.headers.get("Content-Length") or 0)
                if declared > max_bytes:
                    raise FetchRefused(f"{doc.document_id}: too large ({declared} bytes declared)")
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchRefused(f"{doc.document_id}: too large (over {max_bytes} bytes)")
                    fh.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_manifest(
    manifest_path: Path,
    out: Path,
    *,
    only: str | None = None,
    pin: bool = False,
    client: httpx.Client,
    settings: FetchSettings | None = None,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    echo: Callable[[str], None] = print,
) -> int:
    """Fetch every document (or just `only`). Returns 0 when nothing was refused, else 1."""
    settings = settings or FetchSettings()
    manifest = SourcesManifest.model_validate_json(manifest_path.read_text())
    docs = [d for d in manifest.documents if only is None or d.document_id == only]
    if only is not None and not docs:
        echo(f"refused: no document with id {only} in {manifest_path}")
        return 1
    out.mkdir(parents=True, exist_ok=True)
    updated = {d.document_id: d for d in manifest.documents}
    failed = False
    first_request = True
    for doc in docs:
        if doc.url is None:
            echo(f"skipped {doc.document_id}: no URL yet ({doc.note})")
            continue
        if doc.sha256 is None and not pin:
            echo(
                f"refused {doc.document_id}: no hash in the manifest. Rerun with --pin to trust it."
            )
            failed = True
            continue
        dest = out / file_name(doc)
        if dest.exists():
            if doc.sha256 is not None and _sha256(dest) == doc.sha256:
                echo(f"already have {doc.document_id}")
                continue
            moved = _quarantine(dest, out)
            echo(
                f"quarantined {doc.document_id}: the file already in {out} does not match the "
                f"manifest hash. Moved to {moved}."
            )
        if not first_request:
            sleep(settings.delay_s)
        first_request = False
        tmp: Path | None = None
        try:
            tmp = _download(client, doc, out, settings.max_bytes)
            _check_content(doc, tmp)
            received = _sha256(tmp)
            if doc.sha256 is not None and received != doc.sha256:
                raise FetchRefused(
                    f"{doc.document_id}: hash mismatch. "
                    f"expected {doc.sha256}, received {received}. Nothing was written."
                )
            size = tmp.stat().st_size
            os.replace(tmp, dest)
        except FetchRefused as exc:
            echo(f"refused {exc}")
            failed = True
            continue
        except httpx.HTTPError as exc:
            echo(f"failed {doc.document_id}: {exc}")
            failed = True
            continue
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)  # a no-op once the file was moved into place
        if doc.sha256 is None:
            updated[doc.document_id] = doc.model_copy(
                update={"sha256": received, "size_bytes": size, "retrieved_at": now()}
            )
            echo(f"pinned {doc.document_id}: sha256 {received}, {size} bytes")
        else:
            echo(f"fetched {doc.document_id}: hash matches")
    if pin and any(updated[d.document_id] is not d for d in manifest.documents):
        new = manifest.model_copy(update={"documents": tuple(updated.values())})
        _write_atomically(manifest_path, new.model_dump_json(indent=2) + "\n")
    return 1 if failed else 0


def _write_atomically(path: Path, text: str) -> None:
    """Write to a temp file next to `path`, then swap it in, so a crash never leaves half a file."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)
