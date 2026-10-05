"""PR 13: every run says whether its documents are synthetic or public. Never guessed."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from demo_run import CMS, write_demo_docs
from pydantic import ValidationError
from typer.testing import CliRunner

from plan_diff.cli import app
from plan_diff.models import RunManifest
from plan_diff.models.run import ApiUsage

NOW = "2026-10-05T12:00:00+00:00"


def invoke(docs: Path, out: Path, *kind: str) -> tuple[int, str]:
    args = ["run", "--docs", str(docs), "--cms", str(CMS), "--plans", "H9999-001"]
    args += ["--years", "2026,2027", "--out", str(out), "--run-id", "k", "--now", NOW, *kind]
    result = CliRunner().invoke(app, args)
    return result.exit_code, result.output


def test_run_refuses_without_a_data_kind(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    code, output = invoke(tmp_path / "docs", tmp_path / "runs")
    assert code == 2 and "--data-kind" in output
    assert not (tmp_path / "runs" / "k").exists()


def test_run_refuses_an_unknown_data_kind(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    assert invoke(tmp_path / "docs", tmp_path / "runs", "--data-kind", "real")[0] == 2


@pytest.mark.parametrize("kind", ["synthetic", "public"])
def test_the_manifest_records_the_data_kind(tmp_path: Path, kind: str) -> None:
    write_demo_docs(tmp_path / "docs")
    code, output = invoke(tmp_path / "docs", tmp_path / "runs", "--data-kind", kind)
    assert code == 0, output
    manifest = json.loads((tmp_path / "runs" / "k" / "manifest.json").read_text())
    assert manifest["data_kind"] == kind


def test_the_model_has_no_default_data_kind() -> None:
    usage = ApiUsage(mode="off", calls=0, cost_usd=Decimal("0"))
    base = {
        "run_id": "k", "started_at": datetime.now(UTC), "finished_at": datetime.now(UTC),
        "versions": {}, "plans": (), "years": (), "inputs": (), "modes": {},
        "jev": usage, "llm": usage, "timings": (), "counts": {},
        "config": {"confidence_floor": 0.7, "premium_up": "20", "moop_up": "1000",
                   "drug_deductible_up": "0.01"},
    }  # fmt: skip
    with pytest.raises(ValidationError, match="data_kind"):
        RunManifest.model_validate(base)
    with pytest.raises(ValidationError, match="data_kind"):
        RunManifest.model_validate(base | {"data_kind": "real"})
    assert RunManifest.model_validate(base | {"data_kind": "public"}).data_kind == "public"


def test_the_demo_is_labeled_synthetic() -> None:
    demo = CMS.parents[1] / "dashboard" / "public" / "demo-run" / "manifest.json"
    assert json.loads(demo.read_text())["data_kind"] == "synthetic"
