"""PR 9: SPEC section 9 examples 1 to 8, end to end through `plan-diff run` (6 through fetch)."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
from demo_run import CMS, GOLD, REPO, write_demo_docs
from pdf_factory import make_plan_pdf
from typer.testing import CliRunner

from plan_diff.cli import app
from plan_diff.fetch import FetchSettings, fetch_manifest
from plan_diff.models import FieldName

NOW = "2026-10-05T12:00:00+00:00"


def run(
    docs: Path, out: Path, cms: Path = CMS, plans: str = "H9999-001,H9999-002,H9999-003"
) -> Path:
    args = ["run", "--docs", str(docs), "--cms", str(cms), "--plans", plans, "--years"]
    args += ["2026,2027", "--out", str(out), "--run-id", "e2e", "--now", NOW]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return out / "e2e"


def load(path: Path) -> Any:
    return json.loads(path.read_text())


def queue(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (folder / "review_queue.jsonl").read_text().splitlines()]


@pytest.fixture(scope="module")
def demo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp = tmp_path_factory.mktemp("demo")
    write_demo_docs(tmp / "docs")
    return run(tmp / "docs", tmp / "runs")


def test_example_1_happy_path(demo: Path, tmp_path: Path) -> None:
    pages = make_plan_pdf(tmp_path).field_pages  # same layout as the demo SBs
    for year in (2026, 2027):
        record = load(demo / "plans" / f"H9999-001_{year}.json")
        assert set(record["fields"]) == {f.value for f in FieldName}
        for name, field in record["fields"].items():
            assert field["citation"]["page"] == pages[FieldName(name)]
            assert field["citation"]["document_id"] == f"H9999-001_{year}_SB"
    diff = load(demo / "diff" / "H9999-001.json")
    premium = next(c for c in diff["changes"] if c["field"] == "monthly_premium")
    assert premium["direction"] == "up"
    assert (premium["old"]["value"]["amount"], premium["new"]["value"]["amount"]) == (
        "0.00",
        "25.00",
    )
    assert diff["shop_again"] is True and diff["reasons"] == ["premium up $25 a month"]


def test_example_2_consolidated_is_not_terminated(demo: Path) -> None:
    diff = load(demo / "diff" / "H9999-002.json")
    assert diff["crosswalk_status"] == "consolidated" and diff["new_plan_id"] == "H9999-001"
    assert diff["reasons"][0] == "plan consolidated into H9999-001"
    assert "plan terminated" not in diff["reasons"]
    assert diff["changes"]  # compared with the plan it merged into


def test_example_3_real_termination_cites_the_cms_row(demo: Path) -> None:
    diff = load(demo / "diff" / "H9999-003.json")
    assert diff["shop_again"] is True and diff["reasons"] == ["plan terminated"]
    assert diff["evidence"] == [
        {"document_id": "crosswalk_2027.csv", "page": 3, "method": "cms",
         "text": "Terminated/Non-renewed Plan"}
    ]  # fmt: skip


def test_example_4_flag_not_pick(demo: Path) -> None:
    spec = next(
        r
        for r in load(demo / "validation.json")
        if (r["plan_id"], r["year"], r["field"]) == ("H9999-001", 2026, "specialist_copay")
    )
    assert spec["verdict"] == "mismatch"
    assert (spec["pdf_value"]["amount"], spec["cms_value"]["amount"]) == ("45.00", "40.00")
    item = next(i for i in queue(demo) if i["field"] == "specialist_copay")
    assert item["kind"] == "pdf_cms_mismatch" and item["confidence"] <= 0.3
    rows = load(demo / "accuracy.json")["rows"]
    assert next(r for r in rows if r["field"] == "specialist_copay")["mismatched"] == 1


def test_example_5_below_threshold_no_flag(tmp_path: Path) -> None:
    cms = tmp_path / "cms"
    shutil.copytree(CMS, cms)
    section_d = cms / "pbp_2027" / "pbp_Section_D.txt"  # CMS agrees with the new MOOP
    section_d.write_text(section_d.read_text().replace("4900", "5400"))
    landscape = cms / "landscape_2027.csv"
    landscape.write_text(landscape.read_text().replace("$25.00", "$0.00"))
    docs = tmp_path / "docs"
    docs.mkdir()
    make_plan_pdf(docs, year=2026, values=GOLD)
    make_plan_pdf(docs, year=2027, values=GOLD | {FieldName.MOOP_IN_NETWORK: "$5,400 per year"})
    diff = load(run(docs, tmp_path / "runs", cms, plans="H9999-001") / "diff" / "H9999-001.json")
    moop = next(c for c in diff["changes"] if c["field"] == "moop_in_network")
    assert moop["direction"] == "up"
    assert [c["field"] for c in diff["changes"] if c["direction"] != "same"] == ["moop_in_network"]
    assert diff["shop_again"] is False and diff["reasons"] == []


def test_example_6_fetch_refuses_a_hash_mismatch(tmp_path: Path) -> None:
    expected = hashlib.sha256(b"the real file").hexdigest()
    received = hashlib.sha256(b"%PDF-1.4 something else").hexdigest()
    entry = {
        "document_id": "h9999-001-2026-sb",
        "url": "https://example.test/sb.pdf",
        "sha256": expected,
        "size_bytes": 13,
        "retrieved_at": "2026-10-01T00:00:00Z",
        "carrier": "Example Health Plan",
        "plan_id": "H9999-001",
        "year": 2026,
        "document_type": "SB",
    }
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "documents": [entry]}))
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, content=b"%PDF-1.4 something else")
    )
    lines: list[str] = []
    with httpx.Client(transport=transport) as client:
        code = fetch_manifest(
            manifest, tmp_path / "raw", client=client, settings=FetchSettings(delay_s=0),
            sleep=lambda _: None, echo=lines.append,
        )  # fmt: skip
    assert code != 0
    assert list((tmp_path / "raw").iterdir()) == []
    assert any(expected in line and received in line for line in lines)


def test_example_7_no_pdf_is_tracked_and_the_demo_has_none() -> None:
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"], capture_output=True, text=True
    )
    tracked = [p for p in listed.stdout.split("\0") if p]
    assert listed.returncode == 0 and "SPEC.md" in tracked
    assert [p for p in tracked if p.lower().endswith(".pdf")] == []
    demo_out = REPO / "dashboard" / "public" / "demo-run"
    assert [p for p in demo_out.rglob("*") if p.suffix.lower() not in (".json", ".jsonl", "")] == []


def test_example_8_jev_and_llm_off(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    write_demo_docs(docs)  # includes one SB with no plan id
    (docs / "H9999-003_2026_SB.pdf").unlink()
    make_plan_pdf(docs, year=2026, plan_ids=("H9999-003",), omit=[FieldName.DENTAL_ALLOWANCE])
    folder = run(docs, tmp_path / "runs")
    kinds = {(i["kind"], i["plan_id"], i["field"]) for i in queue(folder)}
    assert ("unclassified_document", None, None) in kinds
    assert ("not_extracted", "H9999-003", "dental_allowance") in kinds
    manifest = load(folder / "manifest.json")
    for tier in ("jev", "llm"):
        assert manifest[tier] == {"mode": "off", "calls": 0, "cost_usd": "0.00"}
    assert manifest["modes"]["extract_llm"] == manifest["modes"]["classify_jev"] == "off"
