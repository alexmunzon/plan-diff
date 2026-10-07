"""Sidecar wiring uses real synthetic PDF bytes and never changes the plan."""

import hashlib
import json
from pathlib import Path

import pytest
from reportlab.pdfgen.canvas import Canvas
from typer.testing import CliRunner

from plan_diff.advisory import Request, evaluate
from plan_diff.advisory_cli import bound_request
from plan_diff.cli import app


def setup(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "dashboard/public/demo-run/manifest.json").read_text())
    plan = json.loads((root / "dashboard/public/demo-run/plans/H9999-001_2026.json").read_text())
    pdf = tmp_path / "source.pdf"
    canvas = Canvas(str(pdf))
    canvas.drawString(30, 700, "Monthly premium: $12 per month")
    canvas.save()
    doc = "handwritten_synthetic"
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    manifest["inputs"] = [
        {
            "kind": "pdf",
            "path": "source.pdf",
            "sha256": digest,
            "size_bytes": pdf.stat().st_size,
            "document_id": doc,
            "plan_id": plan["plan_id"],
            "year": plan["year"],
        }
    ]
    run_path = tmp_path / "manifest.json"
    run_path.write_text(json.dumps(manifest))
    plan_path = tmp_path / "plan.json"
    plan["documents"].append(doc)
    plan_path.write_text(json.dumps(plan))
    request = Request(
        run_hash=hashlib.sha256(run_path.read_bytes()).hexdigest(),
        document_hash=digest,
        document_id=doc,
        plan_id=plan["plan_id"],
        year=plan["year"],
        field="monthly_premium",
        pages=({"page": 1, "text": "Monthly premium: $12 per month"},),
    )
    request_path = tmp_path / "request.json"
    request_path.write_text(request.model_dump_json())
    return request_path, pdf, run_path, plan_path


def test_preserves_existing_value_and_inputs(tmp_path: Path) -> None:
    paths = setup(tmp_path)
    before = [p.read_bytes() for p in paths]
    req = bound_request(*paths)
    assert req.deterministic_value is not None
    assert evaluate(req, mode="replay").reason == "deterministic_value_preserved"
    assert [p.read_bytes() for p in paths] == before
    result = CliRunner().invoke(app, ["advisory", "evaluate", *map(str, paths)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "off"


@pytest.mark.parametrize("change", ["hash", "page", "plan", "county", "membership"])
def test_rejects_unbound_evidence(tmp_path: Path, change: str) -> None:
    paths = setup(tmp_path)
    req = json.loads(paths[0].read_text())
    if change == "hash":
        req["document_hash"] = "0" * 64
    if change == "page":
        req["pages"][0]["page"] = 999
    if change == "plan":
        req["plan_id"] = "H9999-002"
    if change == "county":
        req["county_fips"] = "12345"
    if change == "membership":
        plan = json.loads(paths[3].read_text())
        plan["documents"].remove("handwritten_synthetic")
        paths[3].write_text(json.dumps(plan))
    paths[0].write_text(json.dumps(req))
    with pytest.raises(ValueError):
        bound_request(*paths)


def test_missing_or_rejected_replay_stays_pending(tmp_path: Path) -> None:
    paths = setup(tmp_path)
    plan = json.loads(paths[3].read_text())
    del plan["fields"]["monthly_premium"]
    paths[3].write_text(json.dumps(plan))
    req = bound_request(*paths)
    assert evaluate(req, mode="replay").status == "pending"
    assert evaluate(req, mode="replay", response=b"{}").status == "pending"
    result = CliRunner().invoke(
        app,
        [
            "advisory",
            "evaluate",
            *map(str, paths),
            "--mode",
            "replay",
            "--response",
            str(tmp_path / "absent.json"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "pending"


def test_handwritten_replay_sidecar(tmp_path: Path) -> None:
    paths = setup(tmp_path)
    plan = json.loads(paths[3].read_text())
    del plan["fields"]["monthly_premium"]
    paths[3].write_text(json.dumps(plan))
    req = bound_request(*paths)
    response = {
        "version": "plan-fallback-v1",
        "origin": "hand_written_synthetic_fixture",
        "request_key": req.key,
        "value": {"kind": "money", "amount": "12.00"},
        "unit": "per_month",
        "document_id": req.document_id,
        "page": 1,
        "quote": req.pages[0].text,
    }
    response_path = tmp_path / "response.json"
    response_path.write_text(json.dumps(response))
    result = CliRunner().invoke(
        app,
        [
            "advisory",
            "evaluate",
            *map(str, paths),
            "--mode",
            "replay",
            "--response",
            str(response_path),
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "replayed"
    assert data["review_state"] == "needs_review"
    assert data["calls"] == 0
