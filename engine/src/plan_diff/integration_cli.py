"""Freeze explicit coverage and plan evidence, then consume only the saved snapshot."""

import os
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

import typer

from plan_diff.adapters.contract import (
    Artifact,
    ContractModel,
    CoverageFile,
    Packet,
    Text,
    canonical_json,
    pin,
    read_pinned,
)
from plan_diff.adapters.worklist import build_worklist, pin_plan_run
from plan_diff.models.diff import PlanDiff
from plan_diff.models.plan import PlanRecord
from plan_diff.models.review import ReviewItem
from plan_diff.models.run import RunManifest

app = typer.Typer(
    help="Build synthetic review worklists from pinned evidence.", no_args_is_help=True
)


class DataKind(StrEnum):
    SYNTHETIC = "synthetic"


class SnapshotPins(ContractModel):
    schema_version: Literal["1.0.0"] = "1.0.0"
    agency_id: Text
    plan_run_id: Text
    data_kind: Literal["synthetic"]
    coverage_artifact: Artifact
    coverage_evidence: tuple[Artifact, ...]
    plan_artifacts: tuple[Artifact, ...]


def _required(value: str) -> None:
    if not value.strip():
        raise ValueError("an explicit nonempty ID is required")


def _unused(out: Path) -> None:
    if out.exists() or out.is_symlink():
        raise FileExistsError("output already exists")


def _write_new(out: Path, content: str) -> None:
    """Stage complete bytes, then publish without replacing any concurrent winner."""
    _unused(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".integration-", dir=out.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, out)
    finally:
        os.unlink(temporary)


def _plan_manifest(root: Path, artifacts: tuple[Artifact, ...]) -> RunManifest:
    manifest = next(a for a in artifacts if a.path == "manifest.json")
    result = RunManifest.model_validate_json(read_pinned(root, manifest))
    if result.data_kind != "synthetic":
        raise ValueError("expected synthetic plan inputs")
    return result


@app.command("pin")
def pin_command(
    coverage_root: Annotated[
        Path, typer.Option(help="Root containing explicit enrollment evidence.")
    ],
    coverage: Annotated[
        str, typer.Option(help="CoverageFile JSON path relative to coverage root.")
    ],
    plan_root: Annotated[Path, typer.Option(help="Saved synthetic Plan Diff run directory.")],
    agency_id: Annotated[str, typer.Option(help="Explicit synthetic agency ID.")],
    plan_run_id: Annotated[str, typer.Option(help="Expected Plan Diff manifest run ID.")],
    data_kind: Annotated[DataKind, typer.Option(help="Explicit synthetic input attestation.")],
    out: Annotated[Path, typer.Option(help="New immutable snapshot pins JSON.")],
) -> None:
    """Freeze coverage bytes, their source evidence, and the complete plan artifact inventory."""
    try:
        _unused(out)
        _required(agency_id)
        _required(plan_run_id)
        coverage_pin = pin(coverage_root, coverage)
        claims = CoverageFile.model_validate_json(read_pinned(coverage_root, coverage_pin))
        paths = {a.path for a in claims.artifacts}
        if len(paths) != len(claims.artifacts):
            raise ValueError("duplicate coverage evidence paths")
        for artifact in claims.artifacts:
            read_pinned(coverage_root, artifact)
        for row in claims.rows:
            if row.provenance.artifact not in paths:
                raise ValueError("coverage source evidence is not pinned")
        plans = pin_plan_run(plan_root)
        if _plan_manifest(plan_root, plans).run_id != plan_run_id:
            raise ValueError("plan run ID mismatch")
        for artifact in plans:
            blob = read_pinned(plan_root, artifact)
            if artifact.path.startswith("plans/"):
                PlanRecord.model_validate_json(blob)
            elif artifact.path.startswith("diff/"):
                PlanDiff.model_validate_json(blob)
            elif artifact.path == "review_queue.jsonl":
                for line in blob.splitlines():
                    if line.strip():
                        ReviewItem.model_validate_json(line)
        snapshot = SnapshotPins(
            agency_id=agency_id,
            plan_run_id=plan_run_id,
            data_kind="synthetic",
            coverage_artifact=coverage_pin,
            coverage_evidence=tuple(sorted(claims.artifacts, key=lambda a: a.path)),
            plan_artifacts=plans,
        )
        _write_new(out, canonical_json(snapshot))
    except (OSError, ValueError):
        typer.echo("Integration pin refused: invalid evidence, IDs, or existing output.", err=True)
        raise typer.Exit(2) from None
    typer.echo(f"wrote {out}")


@app.command("worklist")
def worklist_command(
    packet: Annotated[Path, typer.Option(help="Resolved Bob integration packet JSON.")],
    pins: Annotated[Path, typer.Option(help="Previously saved integration pin output.")],
    intake_root: Annotated[Path, typer.Option(help="Original Intake output directory.")],
    coverage_root: Annotated[Path, typer.Option(help="Root of the pinned coverage evidence.")],
    plan_root: Annotated[Path, typer.Option(help="Root of the pinned Plan Diff run.")],
    agency_id: Annotated[str, typer.Option(help="Expected explicit synthetic agency ID.")],
    bob_run_id: Annotated[str, typer.Option(help="Expected Bob producer run ID.")],
    run_id: Annotated[str, typer.Option(help="Explicit new worklist producer run ID.")],
    data_kind: Annotated[DataKind, typer.Option(help="Explicit synthetic input attestation.")],
    out: Annotated[Path, typer.Option(help="New immutable review worklist JSON.")],
) -> None:
    """Build a review worklist without inferring enrollment, plan year, or county."""
    try:
        _unused(out)
        for value in (agency_id, bob_run_id, run_id):
            _required(value)
        source = Packet.model_validate_json(packet.read_bytes())
        snapshot = SnapshotPins.model_validate_json(pins.read_bytes())
        if (source.agency_id, source.run_id) != (agency_id, bob_run_id):
            raise ValueError("Bob packet identity mismatch")
        if snapshot.agency_id != agency_id:
            raise ValueError("snapshot agency mismatch")
        for artifact in snapshot.coverage_evidence:
            read_pinned(coverage_root, artifact)
        if _plan_manifest(plan_root, snapshot.plan_artifacts).run_id != snapshot.plan_run_id:
            raise ValueError("plan snapshot identity mismatch")
        result = build_worklist(
            source,
            intake_root,
            coverage_root=coverage_root,
            coverage_artifact=snapshot.coverage_artifact,
            plan_root=plan_root,
            plan_artifacts=snapshot.plan_artifacts,
            run_id=run_id,
        )
        _write_new(out, canonical_json(result))
    except (OSError, ValueError, StopIteration, KeyError):
        typer.echo(
            "Integration worklist refused: invalid or stale evidence, IDs, or output.", err=True
        )
        raise typer.Exit(2) from None
    typer.echo(f"wrote {out}")
