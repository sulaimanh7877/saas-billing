"""Embedded billing engine demo.

Run with::

    python examples/embedded_demo.py

Uses a throwaway SQLite database and the required ``demo_`` table prefix.
"""

from __future__ import annotations

from billing_engine import BillingEngine, EngineConfig


def main() -> None:
    billing = BillingEngine(EngineConfig(dsn="sqlite:///demo.sqlite3", table_prefix="demo_"))
    billing.migrate()

    with billing.transaction() as services:
        feature = services.catalog.create_feature("reports", name="Reports")
        plan = services.catalog.create_plan("pro", "Pro")
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
            trial_days=14,
            entitlements=[{"feature_key": feature.key, "limit_value": 1}],
        )
        customer = services.customers.create("user-1", email="user@example.com")
        subscription = services.subscriptions.create(customer.id, version.id)
        print(f"subscription {subscription.id} -> {subscription.status}")

        services.subscriptions.extend(subscription.id, days=14, reason="goodwill")
        print(f"extended to {services.subscriptions.get(subscription.id).current_period_end}")

        print("reports access:", services.entitlements.can(customer.id, "reports"))
        print("overview:", services.reports.overview("USD"))


if __name__ == "__main__":
    main()
