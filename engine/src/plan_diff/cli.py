"""Command line entry point for plan-diff. More commands arrive in later PRs."""

import json
import os
from pathlib import Path
from typing import Annotated

import typer

from plan_diff import __version__
from plan_diff import fetch as fetching
from plan_diff.models import TOP_LEVEL_MODELS

app = typer.Typer(help="plan-diff. Public data only.", no_args_is_help=True)
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
