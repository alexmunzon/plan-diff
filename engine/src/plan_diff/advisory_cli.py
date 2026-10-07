"""Explicit offline sidecar command. Never alters canonical extraction artifacts."""

import hashlib
import io
import os
import stat
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import pdfplumber
import typer

from plan_diff.advisory import Request, evaluate
from plan_diff.models.plan import PlanRecord
from plan_diff.models.run import RunManifest

app = typer.Typer(help="Offline, synthetic advisory sidecars. No model calls.")


class Mode(StrEnum):
    OFF = "off"
    REPLAY = "replay"


def bound_request(request: Path, document: Path, manifest: Path, plan: Path) -> Request:
    """Verify bytes, identities, pages and deterministic values before evaluating replay."""
    req = Request.model_validate_json(request.read_bytes())
    run_bytes = manifest.read_bytes()
    run = RunManifest.model_validate_json(run_bytes)
    record = PlanRecord.model_validate_json(plan.read_bytes())
    document_bytes = document.read_bytes()
    digest = hashlib.sha256(document_bytes).hexdigest()
    if req.data_kind != "synthetic" or run.data_kind != "synthetic":
        raise ValueError("only explicitly synthetic artifacts are supported")
    if req.run_hash != hashlib.sha256(run_bytes).hexdigest() or req.document_hash != digest:
        raise ValueError("source or run hash mismatch")
    if (record.plan_id, record.year) != (req.plan_id, req.year):
        raise ValueError("plan identity mismatch")
    if req.document_id not in record.documents:
        raise ValueError("source document absent from canonical plan")
    if req.plan_id not in run.plans or req.year not in run.years:
        raise ValueError("plan absent from run")
    sources = [
        i
        for i in run.inputs
        if i.sha256 == digest
        and i.document_id == req.document_id
        and i.plan_id == req.plan_id
        and i.year == req.year
        and i.kind == "pdf"
    ]
    if len(sources) != 1:
        raise ValueError("source not uniquely bound to run")
    # County names never imply FIPS. This command cannot verify that extra binding.
    if req.county_fips is not None:
        raise ValueError("county FIPS binding is not supported by this command")
    with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
        for page in req.pages:
            if page.page > len(pdf.pages):
                raise ValueError("page outside source")
            text = " ".join((pdf.pages[page.page - 1].extract_text() or "").split())
            if " ".join(page.text.split()) not in text:
                raise ValueError("excerpt absent from source page")
    existing = record.fields.get(req.field)
    return req.model_copy(update={"deterministic_value": existing.value if existing else None})


def read_response(path: Path) -> bytes:
    """Read bounded regular fixture bytes without following a final symlink or blocking."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("response fixture must be a regular file")
        # Preserve evaluate's pending-review outcome for oversized responses.
        return stream.read(8193)


@app.command("evaluate")
def evaluate_sidecar(
    request: Path,
    document: Path,
    manifest: Path,
    plan: Path,
    mode: Annotated[Mode, typer.Option()] = Mode.OFF,
    response: Annotated[Path | None, typer.Option()] = None,
) -> None:
    """Emit one JSON sidecar to stdout; handwritten replay remains pending broker review."""
    try:
        req = bound_request(request, document, manifest, plan)
        blob = None
        if mode == Mode.REPLAY and response:
            try:
                blob = read_response(response)
            except FileNotFoundError:
                pass
        result = evaluate(req, mode=mode.value, response=blob)
    except (ValueError, OSError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(result.model_dump_json())
