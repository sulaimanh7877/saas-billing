"""Scenario: a subscription's trial, renewal, and cancellation lifecycle.

Run with::

    python examples/scenario_subscription_lifecycle.py

The engine drives a monthly plan through a trial, converts it to active when
the trial ends, renews it, then expires it at the end of the period after a
cancel-at-period-end request. Every transition is recorded as an adjustment.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from billing_engine import BillingEngine, EngineConfig


def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    billing = BillingEngine(EngineConfig(engine=engine, table_prefix="scenario_"))
    billing.migrate()

    with billing.transaction() as services:
        plan = services.catalog.create_plan("starter", "Starter")
        services.catalog.create_feature("reports", name="Reports")
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
            trial_days=14,
            entitlements=[{"feature_key": "reports", "limit_value": 1}],
        )
        customer = services.customers.create("trial-user", email="trial@example.com")
        sub = services.subscriptions.create(
            customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        print(f"created      status={sub.status} trial_end={sub.trial_end:%Y-%m-%d}")

        # A due run on the day after the trial ends converts trial -> active.
        services.subscriptions.process_due(now=sub.trial_end + timedelta(days=1))
        sub = services.subscriptions.get(sub.id)
        print(
            f"trial ended  status={sub.status} "
            f"period={sub.current_period_start:%Y-%m-%d}..{sub.current_period_end:%Y-%m-%d}"
        )

        # The next due run renews the monthly period.
        services.subscriptions.process_due(now=sub.current_period_end + timedelta(days=1))
        sub = services.subscriptions.get(sub.id)
        print(f"renewed      period_end={sub.current_period_end:%Y-%m-%d}")

        # Cancel at period end, then let the period roll past.
        services.subscriptions.cancel(sub.id, reason="customer churn")
        services.subscriptions.process_due(now=sub.current_period_end + timedelta(days=1))
        sub = services.subscriptions.get(sub.id)
        print(f"canceled     status={sub.status} canceled_at={sub.canceled_at:%Y-%m-%d}")

        adjustments = services.uow.subscriptions.list_adjustments(sub.id)
        print("adjustments ", [item.adjustment_type for item in adjustments])
        print("access?      ", services.entitlements.can(customer.id, "reports"))


if __name__ == "__main__":
    main()
