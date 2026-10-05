"""PR 14: the run manifest names each document's carrier URL and the config values the run used."""

import json
from pathlib import Path

from demo_run import CMS, NOW, write_demo_docs
from pypdf import PdfReader

from plan_diff import config
from plan_diff.run import RunOptions, run
from plan_diff.run.documents import sha256_file

URL = "https://example.com/plans/H9999-001_2026_SB.pdf"


def _entry(doc_id: str, url: str, sha: str) -> dict[str, object]:
    return {
        "document_id": doc_id,
        "url": url,
        "sha256": sha,
        "size_bytes": 1,
        "retrieved_at": "2026-10-01T00:00:00Z",
        "carrier": "Example Health Plan",
        "plan_id": "H9999-001",
        "year": 2026,
        "document_type": "SB",
    }


def _run(tmp_path: Path, sources: Path | None) -> dict[str, object]:
    docs = tmp_path / "docs"
    if not docs.exists():
        write_demo_docs(docs)
    options = RunOptions(
        docs=docs, cms=CMS, plans=("H9999-001",), years=(2026, 2027), out=tmp_path / "runs",
        run_id="r", data_kind="public", overwrite=True, sources=sources,
    )  # fmt: skip
    folder = run(options, lambda: NOW)
    loaded: dict[str, object] = json.loads((folder / "manifest.json").read_text())
    return loaded


def _inputs(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    inputs = manifest["inputs"]
    assert isinstance(inputs, list)
    return {i["path"]: i for i in inputs}


def test_fetched_document_gets_its_https_url_and_others_stay_null(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    gold = tmp_path / "docs" / "H9999-001_2026_SB.pdf"
    silver = tmp_path / "docs" / "H9999-002_2026_SB.pdf"
    sources = tmp_path / "sources.json"
    entries = [
        _entry("gold", URL, sha256_file(gold)),
        _entry("silver", "http://example.com/silver.pdf", sha256_file(silver)),  # not https
    ]
    sources.write_text(json.dumps({"schema_version": 1, "documents": entries}))
    inputs = _inputs(_run(tmp_path, sources))
    assert inputs["H9999-001_2026_SB.pdf"]["source_url"] == URL
    assert inputs["H9999-002_2026_SB.pdf"]["source_url"] is None
    assert inputs["H9999-001_2027_SB.pdf"]["source_url"] is None
    assert all(i["source_url"] is None for i in inputs.values() if i["kind"] == "cms")


def test_without_sources_every_url_is_null_and_page_counts_are_known(tmp_path: Path) -> None:
    inputs = _inputs(_run(tmp_path, None))
    assert {i["source_url"] for i in inputs.values()} == {None}
    gold = inputs["H9999-001_2026_SB.pdf"]
    pages = len(PdfReader(tmp_path / "docs" / "H9999-001_2026_SB.pdf").pages)
    assert gold["page_count"] == pages >= 2
    assert all(i["page_count"] is None for i in inputs.values() if i["kind"] == "cms")


def test_manifest_records_the_config_values_it_used(tmp_path: Path) -> None:
    used = _run(tmp_path, None)["config"]
    assert used == {
        "confidence_floor": config.SHOP_AGAIN_CONFIDENCE_FLOOR,
        "premium_up": str(config.SHOP_AGAIN_PREMIUM_UP),
        "moop_up": str(config.SHOP_AGAIN_MOOP_UP),
        "drug_deductible_up": str(config.SHOP_AGAIN_DRUG_DEDUCTIBLE_UP),
    }
