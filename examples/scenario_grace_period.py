"""Scenario: configured trial and grace period.

Run with::

    python examples/scenario_grace_period.py

``EngineConfig.trial_days`` supplies a default trial when the plan version has
none, and ``grace_period_days`` keeps a past-due subscription accessible for a
few days after its period ends before it finally expires.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from billing_engine import BillingEngine, EngineConfig


def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    billing = BillingEngine(
        EngineConfig(
            engine=engine,
            table_prefix="scenario_",
            trial_days=7,
            grace_period_days=3,
        )
    )
    billing.migrate()

    with billing.transaction() as services:
        plan = services.catalog.create_plan("pro", "Pro")
        # No plan-level trial: the engine falls back to config.trial_days.
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 4900, "currency": "USD", "interval": "month"}],
        )
        customer = services.customers.create("grace-user")
        sub = services.subscriptions.create(
            customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        print(f"created     trial_end={sub.trial_end:%Y-%m-%d} (from config.trial_days=7)")

        services.subscriptions.cancel(sub.id, reason="non-payment")
        # First due run after the trial period ends enters the grace window.
        services.subscriptions.process_due(now=sub.current_period_end)
        sub = services.subscriptions.get(sub.id)
        print(f"in grace    status={sub.status} grace_until={sub.grace_until:%Y-%m-%d}")

        # A run on the grace deadline expires the subscription.
        services.subscriptions.process_due(now=sub.grace_until)
        sub = services.subscriptions.get(sub.id)
        print(f"expired     status={sub.status} canceled_at={sub.canceled_at:%Y-%m-%d}")


if __name__ == "__main__":
    main()
