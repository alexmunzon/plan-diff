"""Command line entry point for plan-diff. More commands arrive in later PRs."""

import json
import os
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from plan_diff import __version__
from plan_diff import fetch as fetching
from plan_diff import run as running
from plan_diff.advisory_cli import app as advisory_app
from plan_diff.audit.evidence import AuditRefused
from plan_diff.audit.runner import AuditOptions, audit
from plan_diff.cms import CmsFileError
from plan_diff.cms.unzip import UnzipRefused, unzip_cms
from plan_diff.integration_cli import app as integration_app
from plan_diff.models import TOP_LEVEL_MODELS

app = typer.Typer(help="plan-diff. Public data only.", no_args_is_help=True)
app.add_typer(integration_app, name="integration")
app.add_typer(advisory_app, name="advisory")
schema_app = typer.Typer(help="The canonical plan schema.", no_args_is_help=True)
app.add_typer(schema_app, name="schema")


@app.callback()
def main() -> None:
    """Keep the app a command group so subcommands arrive cleanly in later PRs."""


@app.command()
def version() -> None:
    """Print the engine version."""
    typer.echo(__version__)


@schema_app.command("export")
def schema_export(
    out: Annotated[Path, typer.Option("--out", help="Folder for one JSON Schema file per model.")],
) -> None:
    """Write a JSON Schema file for each top-level model."""
    out.mkdir(parents=True, exist_ok=True)
    for model in TOP_LEVEL_MODELS:
        path = out / f"{model.__name__}.schema.json"
        path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
        typer.echo(f"wrote {path}")


@app.command()
def fetch(
    manifest: Annotated[Path, typer.Option(help="The sources manifest.")] = Path(
        "sources/manifest.json"
    ),
    out: Annotated[Path, typer.Option(help="Folder for downloads (git-ignored).")] = Path(
        "data/raw"
    ),
    only: Annotated[str | None, typer.Option(help="Fetch just this document_id.")] = None,
    pin: Annotated[
        bool, typer.Option(help="Record the hash of files that have none yet (trust on first use).")
    ] = False,
) -> None:
    """Download the public documents in the manifest, slowly, refusing any hash mismatch."""
    if os.environ.get("CI"):
        typer.echo("refused: fetch never runs in CI. Tests use a fake transport instead.")
        raise typer.Exit(2)
    with fetching.make_client() as client:
        code = fetching.fetch_manifest(
            manifest, out, only=only, pin=pin, client=client, echo=typer.echo
        )
    raise typer.Exit(code)


class DataKindChoice(StrEnum):
    """PR 13: no default, so a run never labels itself by guessing."""

    SYNTHETIC = "synthetic"
    PUBLIC = "public"


def _csv(text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in text.split(",") if part.strip())


@app.command("run")
def run_command(
    docs: Annotated[Path, typer.Option(help="Folder of carrier PDFs (read recursively).")],
    cms: Annotated[Path, typer.Option(help="Folder of CMS files, named as in fixtures/cms.")],
    plans: Annotated[str, typer.Option(help="Plan ids, comma separated: H9999-001,H9999-002.")],
    years: Annotated[str, typer.Option(help="One year, or two in a row: 2026,2027.")],
    data_kind: Annotated[
        DataKindChoice,
        typer.Option("--data-kind", help="synthetic (test fixtures) or public (carrier files)."),
    ],
    out: Annotated[Path, typer.Option(help="Folder that holds run folders.")] = Path("runs"),
    run_id: Annotated[str, typer.Option("--run-id", help="Name of this run's folder.")] = "",
    overwrite: Annotated[bool, typer.Option(help="Replace an existing run folder.")] = False,
    sources: Annotated[
        Path | None,
        typer.Option(help="sources/manifest.json, to record each fetched PDF's https URL."),
    ] = None,
    now: Annotated[
        str | None, typer.Option(help="Freeze the clock (ISO time with zone) for a repeatable run.")
    ] = None,
) -> None:
    """Classify, extract, validate against CMS, and diff; write one immutable run folder."""
    frozen = datetime.fromisoformat(now) if now else None
    if frozen is not None and frozen.tzinfo is None:
        typer.echo("refused: --now needs a time zone, for example 2026-10-05T12:00:00+00:00")
        raise typer.Exit(2)
    clock = (lambda: frozen) if frozen is not None else (lambda: datetime.now(UTC))
    try:
        year_numbers = tuple(int(y) for y in _csv(years))
    except ValueError:
        typer.echo(f"refused: years must be numbers, got {years!r}")
        raise typer.Exit(2) from None
    options = running.RunOptions(
        docs=docs,
        cms=cms,
        plans=_csv(plans),
        years=year_numbers,
        out=out,
        run_id=run_id or (frozen or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ"),
        data_kind="synthetic" if data_kind is DataKindChoice.SYNTHETIC else "public",
        overwrite=overwrite,
        sources=sources,
    )
    try:
        folder = running.run(options, clock)
    except (running.RunRefused, CmsFileError) as err:  # anything else is a bug: fail loudly
        typer.echo(f"refused: {err}")
        raise typer.Exit(1) from None
    typer.echo(f"wrote {folder}")
    for line in running.summary(folder):
        typer.echo(line)


@app.command("audit")
def audit_command(
    claims: Annotated[Path, typer.Option(help="Claims file (citation-claims-v1 JSON).")],
    run: Annotated[Path, typer.Option(help="Run folder; its manifest names each PDF and hash.")],
    docs: Annotated[Path, typer.Option(help="Folder of the PDFs that run read.")],
    out: Annotated[Path, typer.Option(help="Folder that holds audit folders.")] = Path("audits"),
    audit_id: Annotated[str, typer.Option("--audit-id", help="Name of this audit's folder.")] = "",
    meta: Annotated[
        Path | None, typer.Option(help="Evidence metadata: effective dates, supersession.")
    ] = None,
    now: Annotated[
        str | None, typer.Option(help="Freeze the clock (ISO time with zone) for a repeatable run.")
    ] = None,
) -> None:
    """Check whether each claim's cited evidence supports it. Offline; no model is called."""
    frozen = datetime.fromisoformat(now) if now else None
    if frozen is not None and frozen.tzinfo is None:
        typer.echo("refused: --now needs a time zone, for example 2026-10-05T12:00:00+00:00")
        raise typer.Exit(2)
    clock = (lambda: frozen) if frozen is not None else (lambda: datetime.now(UTC))
    options = AuditOptions(
        claims=claims,
        docs=docs,
        out=out,
        audit_id=audit_id or (frozen or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ"),
        run=run,
        meta=meta,
    )
    try:
        command = ["plan-diff", "audit", "--claims", str(claims), "--run", str(run)]
        command += ["--docs", str(docs), "--out", str(out), "--audit-id", options.audit_id]
        command += [*(["--meta", str(meta)] if meta else []), *(["--now", now] if now else [])]
        folder = audit(options, clock, command=command)
    except AuditRefused as err:  # anything else is a bug: fail loudly
        typer.echo(f"refused: {err}")
        raise typer.Exit(1) from None
    typer.echo(f"wrote {folder}")
    verdicts = json.loads((folder / "audit_manifest.json").read_text())["verdicts"]
    typer.echo(", ".join(f"{k} {v}" for k, v in verdicts.items() if v))


@app.command("unzip-cms")
def unzip_cms_command(
    raw: Annotated[Path, typer.Option(help="Folder holding fetched CMS zips.")] = Path("data/raw"),
) -> None:
    """Unzip every fetched CMS zip into a folder next to it, safely; skip unchanged zips."""
    failed = False
    for zipped in sorted(raw.glob("*.zip")):
        try:
            folder, changed = unzip_cms(zipped)
        except (UnzipRefused, OSError, ValueError) as err:
            typer.echo(f"refused {zipped.name}: {err}")
            failed = True
            continue
        typer.echo(f"{'unzipped' if changed else 'unchanged'} {zipped.name} into {folder}")
    raise typer.Exit(1 if failed else 0)
