"""plan-diff fetch, with a fake HTTP transport. These tests never touch the network."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from plan_diff.cli import app
from plan_diff.fetch import FetchSettings, fetch_manifest
from plan_diff.models import SourceDocument, SourcesManifest

BODY = b"%PDF-1.4 synthetic test body"
GOOD = hashlib.sha256(BODY).hexdigest()
NOW = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)


def doc(document_id: str, **over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "document_id": document_id,
        "url": f"https://example.test/{document_id}.pdf",
        "sha256": None,
        "size_bytes": None,
        "retrieved_at": None,
        "carrier": "Humana",
        "plan_id": "H9999-001",
        "year": 2026,
        "document_type": "SB",
    }
    return base | over


def pinned(document_id: str, sha: str = GOOD) -> dict[str, Any]:
    return doc(document_id, sha256=sha, size_bytes=len(BODY), retrieved_at="2026-10-01T00:00:00Z")


def write_manifest(tmp_path: Path, *docs: dict[str, Any]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "documents": list(docs)}))
    return path


class Run:
    def __init__(self, body: bytes = BODY, headers: dict[str, str] | None = None) -> None:
        self.requests: list[str] = []
        self.sleeps: list[float] = []
        self.lines: list[str] = []
        self.body = body
        self.headers = headers or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        return httpx.Response(200, content=self.body, headers=self.headers)

    def __call__(self, manifest: Path, out: Path, **kw: Any) -> int:
        settings = kw.pop("settings", FetchSettings(delay_s=5, max_bytes=1_000_000))
        client = httpx.Client(transport=httpx.MockTransport(self.handler), follow_redirects=True)
        return fetch_manifest(
            manifest,
            out,
            client=client,
            settings=settings,
            sleep=self.sleeps.append,
            now=lambda: NOW,
            echo=self.lines.append,
            **kw,
        )


def test_hash_match_writes_the_file(tmp_path: Path) -> None:
    run = Run()
    code = run(write_manifest(tmp_path, pinned("sb-a")), tmp_path / "raw")
    assert code == 0
    assert (tmp_path / "raw" / "sb-a.pdf").read_bytes() == BODY
    assert run.requests == ["https://example.test/sb-a.pdf"]


def test_hash_mismatch_writes_nothing_and_names_both_hashes(tmp_path: Path) -> None:
    run = Run()
    expected = "0" * 64
    code = run(write_manifest(tmp_path, pinned("sb-a", sha=expected)), tmp_path / "raw")
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []
    message = "\n".join(run.lines)
    assert expected in message and GOOD in message


def test_pin_records_hash_size_and_date(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, doc("sb-a"))
    assert Run()(manifest, tmp_path / "raw", pin=True) == 0
    saved = SourcesManifest.model_validate_json(manifest.read_text()).documents[0]
    assert saved.sha256 == GOOD
    assert saved.size_bytes == len(BODY)
    assert saved.retrieved_at == NOW
    assert (tmp_path / "raw" / "sb-a.pdf").exists()


def test_no_hash_and_no_pin_refuses_without_a_request(tmp_path: Path) -> None:
    run = Run()
    code = run(write_manifest(tmp_path, doc("sb-a")), tmp_path / "raw")
    assert code != 0
    assert run.requests == []
    assert "--pin" in "\n".join(run.lines)


def test_size_guard_refuses_a_large_body(tmp_path: Path) -> None:
    run = Run(body=b"x" * 2000)
    settings = FetchSettings(delay_s=0, max_bytes=1000)
    code = run(write_manifest(tmp_path, doc("sb-a")), tmp_path / "raw", pin=True, settings=settings)
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []
    assert "too large" in "\n".join(run.lines)


def test_size_guard_trusts_content_length_first(tmp_path: Path) -> None:
    run = Run(headers={"Content-Length": "999999999"})
    settings = FetchSettings(delay_s=0, max_bytes=1000)
    code = run(write_manifest(tmp_path, doc("sb-a")), tmp_path / "raw", pin=True, settings=settings)
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []


def test_null_url_is_skipped_with_a_message(tmp_path: Path) -> None:
    run = Run()
    missing = doc("eoc-b", url=None, note="find by hand")
    code = run(write_manifest(tmp_path, missing, pinned("sb-a")), tmp_path / "raw")
    assert code == 0
    assert run.requests == ["https://example.test/sb-a.pdf"]
    assert any("eoc-b" in line and "find by hand" in line for line in run.lines)


def test_delay_between_requests_and_user_agent(tmp_path: Path) -> None:
    run = Run()
    seen: list[str] = []
    original = run.handler

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return original(request)

    run.handler = handler  # type: ignore[method-assign]
    manifest = write_manifest(tmp_path, pinned("a"), pinned("b"), pinned("c"))
    assert run(manifest, tmp_path / "raw") == 0
    assert run.sleeps == [5, 5]  # a fixed pause before every request but the first
    assert len(seen) == 3 and all(ua.startswith("plan-diff/") for ua in seen)


def test_only_fetches_one_document(tmp_path: Path) -> None:
    run = Run()
    manifest = write_manifest(tmp_path, pinned("a"), pinned("b"))
    assert run(manifest, tmp_path / "raw", only="b") == 0
    assert run.requests == ["https://example.test/b.pdf"]
    assert run(manifest, tmp_path / "raw", only="nope") != 0


def test_cli_refuses_to_run_in_ci(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CI", "true")
    manifest = write_manifest(tmp_path, pinned("a"))
    result = CliRunner().invoke(app, ["fetch", "--manifest", str(manifest), "--out", str(tmp_path)])
    assert result.exit_code != 0
    assert "CI" in result.output


def test_committed_manifest_is_valid_and_pinned() -> None:
    # PR 15: Alex approved the 17 files and they were pinned on the first download, so every
    # entry now has an https URL, a SHA-256, a size, and a retrieved date.
    path = Path(__file__).resolve().parents[3] / "sources" / "manifest.json"
    manifest = SourcesManifest.model_validate_json(path.read_text())
    assert len(manifest.documents) == 17
    for d in manifest.documents:
        assert d.url is not None and d.url.scheme == "https"
        assert d.sha256 and d.size_bytes and d.retrieved_at


def test_redirect_to_another_host_is_refused(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"Location": "https://evil.test/sb-a.pdf"})
        return httpx.Response(200, content=BODY)

    run = Run()
    run.handler = handler  # type: ignore[method-assign]
    manifest = write_manifest(tmp_path, doc("sb-a"))
    code = run(manifest, tmp_path / "raw", pin=True)
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []
    assert "evil.test" in "\n".join(run.lines)
    assert SourcesManifest.model_validate_json(manifest.read_text()).documents[0].sha256 is None


def test_redirect_on_the_same_host_is_allowed(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sb-a.pdf":
            return httpx.Response(302, headers={"Location": "https://example.test/files/sb-a.pdf"})
        return httpx.Response(200, content=BODY)

    run = Run()
    run.handler = handler  # type: ignore[method-assign]
    assert run(write_manifest(tmp_path, pinned("sb-a")), tmp_path / "raw") == 0
    assert (tmp_path / "raw" / "sb-a.pdf").read_bytes() == BODY


def test_html_body_with_pin_is_refused_and_nothing_pinned(tmp_path: Path) -> None:
    run = Run(body=b"<!doctype html><html>landing page</html>")
    manifest = write_manifest(tmp_path, doc("sb-a"))
    code = run(manifest, tmp_path / "raw", pin=True)
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []
    assert "not a PDF" in "\n".join(run.lines)
    assert SourcesManifest.model_validate_json(manifest.read_text()).documents[0].sha256 is None


def test_cms_zip_must_start_with_zip_bytes(tmp_path: Path) -> None:
    cms = doc(
        "cms-pbp-2026", plan_id=None, document_type="CMS_PBP", url="https://example.test/p.zip"
    )
    assert Run(body=BODY)(write_manifest(tmp_path, cms), tmp_path / "raw", pin=True) != 0
    assert list((tmp_path / "raw").iterdir()) == []
    zipped = b"PK\x03\x04 synthetic zip"
    assert Run(body=zipped)(write_manifest(tmp_path, cms), tmp_path / "raw", pin=True) == 0
    assert (tmp_path / "raw" / "cms-pbp-2026.zip").read_bytes() == zipped


def test_existing_file_with_wrong_hash_is_quarantined_and_refetched(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sb-a.pdf").write_bytes(b"%PDF-tampered")
    run = Run()
    assert run(write_manifest(tmp_path, pinned("sb-a")), raw) == 0
    assert (raw / "sb-a.pdf").read_bytes() == BODY
    assert (raw / ".rejected" / "sb-a.pdf").read_bytes() == b"%PDF-tampered"
    assert any("sb-a" in line and "quarantined" in line for line in run.lines)


def test_existing_bad_file_is_not_left_when_the_refetch_fails(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "sb-a.pdf").write_bytes(b"%PDF-tampered")
    run = Run(body=b"<html>gone</html>")
    assert run(write_manifest(tmp_path, pinned("sb-a")), raw) != 0
    assert not (raw / "sb-a.pdf").exists()
    assert sorted(p.name for p in raw.iterdir()) == [".rejected"]


def test_size_guard_counts_a_streamed_body_with_no_content_length(tmp_path: Path) -> None:
    seen: list[httpx.Headers] = []

    def chunks() -> Any:
        for _ in range(10):
            yield b"%PDF-" + b"x" * 200

    def handler(request: httpx.Request) -> httpx.Response:
        response = httpx.Response(200, content=chunks())
        seen.append(response.headers)
        return response

    run = Run()
    run.handler = handler  # type: ignore[method-assign]
    settings = FetchSettings(delay_s=0, max_bytes=1000)
    code = run(write_manifest(tmp_path, doc("sb-a")), tmp_path / "raw", pin=True, settings=settings)
    assert code != 0
    assert "content-length" not in seen[0]
    assert list((tmp_path / "raw").iterdir()) == []
    assert "too large" in "\n".join(run.lines)


def test_no_part_file_is_left_after_any_failure(tmp_path: Path) -> None:
    raw = tmp_path / "raw"

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    for handler_body in (b"<html>", b"%PDF-wrong"):
        run = Run(body=handler_body)
        run(write_manifest(tmp_path, pinned("sb-a", sha="0" * 64)), raw)
    run = Run()
    run.handler = broken  # type: ignore[method-assign]
    assert run(write_manifest(tmp_path, pinned("sb-a")), raw) != 0
    assert [p.name for p in raw.iterdir() if p.name.endswith(".part")] == []


def test_pin_rewrites_the_manifest_atomically(tmp_path: Path) -> None:
    manifest = write_manifest(tmp_path, doc("sb-a"))
    assert Run()(manifest, tmp_path / "raw", pin=True) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["manifest.json", "raw"]


@pytest.mark.parametrize("bad", ["../x", "a/b", "A-B", "a_b", "", "a.pdf"])
def test_document_id_must_be_lowercase_letters_digits_and_dashes(bad: str) -> None:
    with pytest.raises(ValueError):
        SourceDocument.model_validate(doc(bad))


def test_path_traversal_id_is_refused_by_fetch(tmp_path: Path) -> None:
    run = Run()
    with pytest.raises(ValueError):
        run(write_manifest(tmp_path, doc("../x")), tmp_path / "raw", pin=True)
    assert run.requests == []
    assert not (tmp_path / "x.pdf").exists()
