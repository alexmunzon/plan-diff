"""SPEC example 7: no PDF is ever tracked by git. Test PDFs are generated into tmp_path."""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def tracked_pdfs(paths: list[str]) -> list[str]:
    return [p for p in paths if p.lower().endswith(".pdf")]


def test_the_guard_catches_a_pdf_anywhere() -> None:
    paths = ["data/raw/eoc.pdf", "engine/tests/fixtures/sb.pdf", "docs/a.PDF", "README.md"]
    assert tracked_pdfs(paths) == ["data/raw/eoc.pdf", "engine/tests/fixtures/sb.pdf", "docs/a.PDF"]


def test_no_pdf_is_tracked_by_git() -> None:
    result = git("ls-files", "-z")
    assert result.returncode == 0, result.stderr
    tracked = [p for p in result.stdout.split("\0") if p]
    assert "SPEC.md" in tracked  # git really listed this repo, so an empty list cannot pass
    assert tracked_pdfs(tracked) == []


def test_data_raw_is_git_ignored() -> None:
    assert git("check-ignore", "-q", "data/raw/H0028030000EOC27.pdf").returncode == 0
    assert git("check-ignore", "-q", "data/raw/pbp-benefits-2027.zip").returncode == 0
