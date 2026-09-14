"""Command line interface for the billing engine."""

from __future__ import annotations

import typer

from billing_engine import __version__
from billing_engine.config import EngineConfig
from billing_engine.domain.errors import BillingError
from billing_engine.sdk import BillingEngine

app = typer.Typer(
    help="Billing engine command line interface.",
    no_args_is_help=True,
    add_completion=False,
)

DsnOption = typer.Option(None, "--dsn", envvar="BILLING_DSN", help="SQLAlchemy database URL.")
PrefixOption = typer.Option(
    None, "--prefix", envvar="BILLING_TABLE_PREFIX", help="Required table prefix."
)


def _build_engine(dsn: str | None, prefix: str | None) -> BillingEngine:
    if not prefix:
        raise typer.BadParameter(
            "a table prefix is required (pass --prefix or set BILLING_TABLE_PREFIX)"
        )
    if not dsn:
        raise typer.BadParameter("a database URL is required (pass --dsn or set BILLING_DSN)")
    return BillingEngine(EngineConfig(table_prefix=prefix, dsn=dsn))


@app.command()
def version() -> None:
    """Print the installed billing-engine version."""
    typer.echo(__version__)


@app.command()
def migrate(
    dsn: str | None = DsnOption,
    prefix: str | None = PrefixOption,
) -> None:
    """Apply pending database migrations."""
    try:
        engine = _build_engine(dsn, prefix)
        applied = engine.migrate()
    except BillingError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    if applied:
        typer.echo(f"applied migrations: {', '.join(applied)}")
    else:
        typer.echo("already up to date")


@app.command()
def seed(
    dsn: str | None = DsnOption,
    prefix: str | None = PrefixOption,
) -> None:
    """Seed demo data (a feature, plan, customer, and subscription)."""
    try:
        engine = _build_engine(dsn, prefix)
        engine.migrate()
        with engine.transaction() as services:
            services.catalog.create_feature("reports", name="Reports")
            plan = services.catalog.create_plan("pro", "Pro")
            version = services.catalog.create_plan_version(
                plan.id,
                prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
                trial_days=14,
                entitlements=[{"feature_key": "reports", "limit_value": 1}],
            )
            customer = services.customers.create("demo-user", email="demo@example.com")
            subscription = services.subscriptions.create(customer.id, version.id)
    except BillingError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"plan_version={version.id}")
    typer.echo(f"customer={customer.id}")
    typer.echo(f"subscription={subscription.id} status={subscription.status}")


@app.command()
def report(
    dsn: str | None = DsnOption,
    prefix: str | None = PrefixOption,
    currency: str = typer.Option("USD", help="Reporting currency."),
) -> None:
    """Print headline billing metrics."""
    try:
        engine = _build_engine(dsn, prefix)
        with engine.transaction() as services:
            overview = services.reports.overview(currency)
    except BillingError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"customers: {overview['customers']}")
    typer.echo(f"mrr_minor: {overview['mrr_minor']}")
    typer.echo(f"subscriptions: {overview['subscriptions']}")


@app.command()
def audit(
    dsn: str | None = DsnOption,
    prefix: str | None = PrefixOption,
    entity_type: str | None = typer.Option(None, help="Filter by entity type."),
    limit: int = typer.Option(20, help="Maximum entries to show."),
) -> None:
    """Print recent audit-log entries."""
    try:
        engine = _build_engine(dsn, prefix)
        with engine.transaction() as services:
            entries = services.uow.audit.list(entity_type=entity_type, limit=limit)
    except BillingError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    for entry in entries:
        typer.echo(f"{entry.created_at} {entry.action} {entry.entity_type}:{entry.entity_id}")


if __name__ == "__main__":  # pragma: no cover
    app()
