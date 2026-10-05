"""PR 9: the run command. Immutable folder, determinism, unreadable PDFs, Decimal money."""

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest
from demo_run import CMS, write_demo_docs
from pypdf import PdfReader, PdfWriter
from typer.testing import CliRunner

from plan_diff import run as running
from plan_diff.cli import app

NOW = "2026-10-05T12:00:00+00:00"
PLANS = "H9999-001,H9999-002,H9999-003"


def run_cli(docs: Path, out: Path, *extra: str, run_id: str = "r1") -> tuple[int, str]:
    args = ["run", "--docs", str(docs), "--cms", str(CMS), "--plans", PLANS]
    args += ["--years", "2026,2027", "--out", str(out), "--run-id", run_id, "--now", NOW]
    args += ["--data-kind", "synthetic", *extra]
    result = CliRunner().invoke(app, args)
    return result.exit_code, result.output


def files(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    }


def test_same_inputs_and_clock_give_byte_identical_folders(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    assert run_cli(tmp_path / "docs", tmp_path / "a")[0] == 0
    assert run_cli(tmp_path / "docs", tmp_path / "b")[0] == 0
    a, b = files(tmp_path / "a" / "r1"), files(tmp_path / "b" / "r1")
    assert a == b
    assert {"manifest.json", "plans.parquet", "validation.json", "accuracy.json"} <= set(a)
    assert {"review_queue.jsonl", "plans/H9999-001_2026.json", "diff/H9999-001.json"} <= set(a)
    assert [p for p in (tmp_path / "a").iterdir()] == [tmp_path / "a" / "r1"]  # no temp left


def test_a_run_folder_is_immutable_without_overwrite(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    assert run_cli(tmp_path / "docs", tmp_path / "runs")[0] == 0
    marker = tmp_path / "runs" / "r1" / "manifest.json"
    before = marker.read_bytes()
    code, output = run_cli(tmp_path / "docs", tmp_path / "runs")
    assert code == 1 and "immutable" in output
    assert marker.read_bytes() == before
    assert run_cli(tmp_path / "docs", tmp_path / "runs", "--overwrite")[0] == 0


def test_money_in_plans_parquet_is_decimal(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    run_cli(tmp_path / "docs", tmp_path / "runs")
    frame = pl.read_parquet(tmp_path / "runs" / "r1" / "plans.parquet")
    assert frame.schema["amount"] == pl.Decimal(12, 2)
    assert frame.schema["percent"] == pl.Decimal(5, 2)
    premium = frame.filter((pl.col("plan_id") == "H9999-001") & (pl.col("year") == 2027))
    premium = premium.filter(pl.col("field") == "monthly_premium")
    assert str(premium["amount"][0]) == "25.00"


def test_corrupt_and_password_protected_pdfs_go_to_review(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    write_demo_docs(docs)
    (docs / "corrupt.pdf").write_bytes(b"%PDF-1.4 this is not really a PDF")
    writer = PdfWriter(clone_from=PdfReader(docs / "H9999-003_2026_SB.pdf"))
    writer.encrypt(user_password="secret", algorithm="AES-128")
    with (docs / "locked.pdf").open("wb") as fh:
        writer.write(fh)
    code, output = run_cli(docs, tmp_path / "runs")
    assert code == 0, output
    folder = tmp_path / "runs" / "r1"
    items = [json.loads(line) for line in (folder / "review_queue.jsonl").read_text().splitlines()]
    unreadable = {i["evidence"][0]["document_id"] for i in items if "could not open" in i["reason"]}
    assert unreadable == {"corrupt", "locked"}
    inputs = json.loads((folder / "manifest.json").read_text())["inputs"]
    assert {i["path"]: i["status"] for i in inputs}["locked.pdf"] == "unreadable"


def test_bad_options_are_refused_before_anything_is_written(tmp_path: Path) -> None:
    write_demo_docs(tmp_path / "docs")
    assert run_cli(tmp_path / "docs", tmp_path / "runs", run_id="../escape")[0] == 1
    code, output = run_cli(tmp_path / "docs", tmp_path / "runs", "--years", "2026,2028")
    assert code == 1 and "two years in a row" in output
    args = ["run", "--docs", str(tmp_path), "--cms", str(CMS), "--plans", PLANS, "--years"]
    result = CliRunner().invoke(
        app, [*args, "2026", "--data-kind", "synthetic", "--now", "2026-10-05T12:00:00"]
    )
    assert result.exit_code == 2 and "time zone" in result.output
    assert not (tmp_path / "runs").exists() and not (tmp_path / "escape").exists()


def test_unzip_cms_command(tmp_path: Path) -> None:
    with zipfile.ZipFile(tmp_path / "pbp.zip", "w") as archive:
        archive.writestr("pbp_mrx.txt", "x")
    first = CliRunner().invoke(app, ["unzip-cms", "--raw", str(tmp_path)])
    again = CliRunner().invoke(app, ["unzip-cms", "--raw", str(tmp_path)])
    assert first.exit_code == again.exit_code == 0
    assert "unzipped pbp.zip" in first.output and "unchanged pbp.zip" in again.output


def test_a_threshold_field_that_disagrees_with_cms_leaves_the_flag_undecided(
    tmp_path: Path,
) -> None:
    cms = tmp_path / "cms"
    shutil.copytree(CMS, cms)
    landscape = cms / "landscape_2027.csv"  # CMS says $30, the 2027 SB says $25
    landscape.write_text(landscape.read_text().replace("$25.00", "$30.00"))
    write_demo_docs(tmp_path / "docs")
    args = ["run", "--docs", str(tmp_path / "docs"), "--cms", str(cms), "--plans", "H9999-001"]
    args += ["--years", "2026,2027", "--out", str(tmp_path / "runs"), "--run-id", "r", "--now", NOW]
    args += ["--data-kind", "synthetic"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    diff = json.loads((tmp_path / "runs" / "r" / "diff" / "H9999-001.json").read_text())
    assert diff["shop_again"] is None and diff["reasons"] == []
    assert "H9999-001: shop again undecided, needs review" in result.output


def test_a_bug_in_our_own_code_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> None:
        raise ValueError("bug in extraction")

    monkeypatch.setattr("plan_diff.run.documents.extract_document", broken)
    write_demo_docs(tmp_path / "docs")
    with pytest.raises(ValueError, match="bug in extraction"):
        running.run(
            running.RunOptions(
                docs=tmp_path / "docs", cms=CMS, plans=tuple(PLANS.split(",")),
                years=(2026, 2027), out=tmp_path / "runs", run_id="r", data_kind="synthetic",
            ),
            lambda: datetime.fromisoformat(NOW),
        )  # fmt: skip
    assert not (tmp_path / "runs" / "r").exists()
