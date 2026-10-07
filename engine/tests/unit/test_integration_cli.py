"""Plan integration consumes saved pins rather than silently refreshing them."""

import json
import os
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from plan_diff.cli import app
from plan_diff.integration_cli import _write_new

FIXTURE = Path(__file__).resolve().parents[3] / "fixtures/integration-v1"
RUNNER = CliRunner()


def freeze(root: Path, out: Path, *extra: str):
    return RUNNER.invoke(
        app,
        [
            "integration",
            "pin",
            "--coverage-root",
            str(root),
            "--coverage",
            "coverage.json",
            "--plan-root",
            str(root / "plan-run"),
            "--agency-id",
            "synthetic-agency-a",
            "--plan-run-id",
            "plan-synthetic-v1",
            "--data-kind",
            "synthetic",
            "--out",
            str(out),
            *extra,
        ],
    )


def worklist(root: Path, pins: Path, out: Path, *extra: str):
    return RUNNER.invoke(
        app,
        [
            "integration",
            "worklist",
            "--packet",
            str(root / "bob-packet.json"),
            "--pins",
            str(pins),
            "--intake-root",
            str(root / "intake-run"),
            "--coverage-root",
            str(root),
            "--plan-root",
            str(root / "plan-run"),
            "--agency-id",
            "synthetic-agency-a",
            "--bob-run-id",
            "bob-synthetic-v1",
            "--run-id",
            "worklist-cli-v1",
            "--data-kind",
            "synthetic",
            "--out",
            str(out),
            *extra,
        ],
    )


@pytest.fixture
def inputs(tmp_path: Path) -> Path:
    root = tmp_path / "inputs"
    shutil.copytree(FIXTURE, root)
    return root


def test_saved_pins_worklist_determinism_and_no_overwrite(inputs: Path, tmp_path: Path) -> None:
    pins, pins2 = tmp_path / "pins.json", tmp_path / "pins2.json"
    result = freeze(inputs, pins)
    assert result.exit_code == 0, result.output
    assert freeze(inputs, pins2).exit_code == 0
    assert pins.read_bytes() == pins2.read_bytes()
    assert freeze(inputs, pins).exit_code == 2
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    result = worklist(inputs, pins, a)
    assert result.exit_code == 0, result.output
    assert worklist(inputs, pins, b).exit_code == 0
    original = a.read_bytes()
    assert original == b.read_bytes()
    assert worklist(inputs, pins, a).exit_code == 2
    assert a.read_bytes() == original
    result_data = json.loads(original)
    assert any("MISSING_COVERAGE" in item["reasons"] for item in result_data["items"])
    assert all(item["review_state"] == "needs_review" for item in result_data["items"])


@pytest.mark.parametrize(
    "relative",
    [
        "coverage.json",
        "synthetic-enrollment.csv",
        "plan-run/manifest.json",
        "plan-run/diff/H8433-008.json",
        "intake-run/clean/clients.csv",
    ],
)
def test_stale_pins_refused(inputs: Path, tmp_path: Path, relative: str) -> None:
    pins, out = tmp_path / "pins.json", tmp_path / "out.json"
    result = freeze(inputs, pins)
    assert result.exit_code == 0, result.output
    path = inputs / relative
    assert path.exists(), relative
    with path.open("a") as stream:
        stream.write("\n")
    assert worklist(inputs, pins, out).exit_code == 2
    assert not out.exists()


def test_new_plan_file_malformed_pins_and_metadata_refused(inputs: Path, tmp_path: Path) -> None:
    pins, out = tmp_path / "pins.json", tmp_path / "out.json"
    assert freeze(inputs, pins).exit_code == 0
    assert worklist(inputs, pins, out, "--agency-id", "other").exit_code == 2
    assert worklist(inputs, pins, out, "--bob-run-id", "other").exit_code == 2
    assert worklist(inputs, pins, out, "--run-id", " ").exit_code == 2
    shutil.copy(inputs / "plan-run/diff/H8433-008.json", inputs / "plan-run/diff/new.json")
    assert worklist(inputs, pins, out).exit_code == 2
    pins.write_text('{"secret-value":42}')
    result = worklist(inputs, pins, out)
    assert result.exit_code == 2
    assert "secret-value" not in result.output
    assert not out.exists()


def test_pin_rejects_path_escape_wrong_manifest_and_malformed_coverage(
    inputs: Path,
    tmp_path: Path,
) -> None:
    out = tmp_path / "pins.json"
    assert freeze(inputs, out, "--coverage", "../coverage.json").exit_code == 2
    assert freeze(inputs, out, "--plan-run-id", "wrong").exit_code == 2
    (inputs / "coverage.json").write_text("bad secret-value")
    result = freeze(inputs, out)
    assert result.exit_code == 2
    assert "secret-value" not in result.output
    assert not out.exists()


def test_pin_rejects_malformed_native_plan(inputs: Path, tmp_path: Path) -> None:
    (inputs / "plan-run/diff/H8433-008.json").write_text('{"secret-value":42}')
    out = tmp_path / "pins.json"
    result = freeze(inputs, out)
    assert result.exit_code == 2
    assert "secret-value" not in result.output
    assert not out.exists()


def test_atomic_race_preserves_winner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out.json"
    link = os.link

    def competing_link(source: str, target: Path) -> None:
        target.write_text("successful concurrent output")
        link(source, target)

    monkeypatch.setattr(os, "link", competing_link)
    with pytest.raises(FileExistsError):
        _write_new(out, "loser")
    assert out.read_text() == "successful concurrent output"
    assert list(tmp_path.iterdir()) == [out]


def test_failed_publish_cleans_staging_and_retry_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "out.json"
    with monkeypatch.context() as patch:

        def fail(*args: object) -> None:
            raise OSError("disk failure")

        patch.setattr(os, "link", fail)
        with pytest.raises(OSError):
            _write_new(out, "complete\n")
    assert not list(tmp_path.iterdir())
    _write_new(out, "complete\n")
    assert out.read_text() == "complete\n"
