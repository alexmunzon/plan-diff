"""SPEC example 7: carrier PDFs are never committed. Only generated test fixtures under tests/."""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def pdfs_outside_tests(paths: list[str]) -> list[str]:
    return [p for p in paths if p.lower().endswith(".pdf") and "tests" not in Path(p).parts]


def test_the_guard_catches_a_pdf_outside_tests() -> None:
    paths = ["data/raw/eoc.pdf", "engine/tests/fixtures/sb.pdf", "docs/a.PDF", "README.md"]
    assert pdfs_outside_tests(paths) == ["data/raw/eoc.pdf", "docs/a.PDF"]


def test_no_pdf_is_tracked_by_git_outside_tests() -> None:
    tracked = git("ls-files", "-z").stdout.split("\0")
    assert pdfs_outside_tests(tracked) == []


def test_data_raw_is_git_ignored() -> None:
    assert git("check-ignore", "-q", "data/raw/H0028030000EOC27.pdf").returncode == 0
    assert git("check-ignore", "-q", "data/raw/pbp-benefits-2027.zip").returncode == 0
