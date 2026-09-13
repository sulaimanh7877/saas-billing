"""Command line interface for the billing engine."""

from __future__ import annotations

import typer

from billing_engine import __version__

app = typer.Typer(
    help="Billing engine command line interface.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed billing-engine version."""
    typer.echo(__version__)


if __name__ == "__main__":  # pragma: no cover
    app()
