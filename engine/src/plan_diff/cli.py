"""Command line entry point for plan-diff. More commands arrive in later PRs."""

import typer

from plan_diff import __version__

app = typer.Typer(help="plan-diff. Public data only.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Keep the app a command group so subcommands arrive cleanly in later PRs."""


@app.command()
def version() -> None:
    """Print the engine version."""
    typer.echo(__version__)
