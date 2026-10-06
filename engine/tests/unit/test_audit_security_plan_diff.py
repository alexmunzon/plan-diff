"""Bounded synthetic fetch/ZIP checks, with all HTTP requests handled by a mock."""

import zipfile
from types import SimpleNamespace

import httpx
import pytest

from plan_diff.cms.unzip import UnzipRefused, unzip_cms
from plan_diff.fetch import FetchRefused, _download


def test_redirect_target_is_rejected_before_request(tmp_path):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "public.example":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1/internal"})
        return httpx.Response(200, content=b"%PDF-synthetic")

    doc = SimpleNamespace(document_id="synthetic", url="https://public.example/document.pdf")
    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        try:
            _download(client, doc, tmp_path, 1024)
        except FetchRefused:
            pass
    print("OBSERVED redirect request destinations:", seen)
    assert len(seen) == 1, "cross-host redirect was contacted before refusal"


@pytest.mark.parametrize(
    "member", ["../escape.txt", "/escape.txt", "C:/escape.txt", "..\\escape.txt"]
)
def test_zip_traversal_is_refused_without_output(tmp_path, member):
    archive = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(member, "synthetic")
    with pytest.raises(UnzipRefused):
        unzip_cms(archive)
    assert not archive.with_suffix("").exists()
