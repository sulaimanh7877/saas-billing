"""Scenario: entitlement resolution and overrides.

Run with::

    python examples/scenario_entitlements.py

Shows how a plan grants a feature with both a value and a separate limit, how
``can()`` and ``limit()`` read it, and how customer and subscription overrides
take precedence (customer first), including expiring overrides.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from billing_engine import BillingEngine, EngineConfig
from billing_engine.domain.value_objects import utcnow


def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    billing = BillingEngine(EngineConfig(engine=engine, table_prefix="scenario_"))
    billing.migrate()

    with billing.transaction() as services:
        plan = services.catalog.create_plan("team", "Team")
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 9900, "currency": "USD", "interval": "month"}],
            entitlements=[{"feature_key": "seats", "value": 1, "limit_value": 5}],
        )
        customer = services.customers.create("ent-user")
        subscription = services.subscriptions.create(customer.id, version.id)

        resolved = services.entitlements.resolve(customer.id, "seats")
        print(
            f"plan        source={resolved.source} value={resolved.value} "
            f"limit={resolved.limit_value} can={services.entitlements.can(customer.id, 'seats')}"
        )

        # A customer-level override replaces the plan grant.
        customer_override = services.entitlements.set_customer_override(
            customer.id, "seats", value=3, reason="sales deal"
        )
        print(f"overridden  limit={services.entitlements.limit(customer.id, 'seats')}")

        # A subscription override is shadowed by the customer override.
        services.entitlements.set_subscription_override(subscription.id, "seats", value=9)
        print(f"shadowed    limit={services.entitlements.limit(customer.id, 'seats')}")

        # Removing the customer override lets the subscription override apply.
        services.entitlements.remove_override(customer_override.id)
        print(f"fallback    limit={services.entitlements.limit(customer.id, 'seats')}")

        # An expired override is ignored, so resolution falls back again.
        services.entitlements.set_customer_override(
            customer.id, "seats", value=0, expires_at=utcnow() - timedelta(days=1)
        )
        print(
            f"expired     limit={services.entitlements.limit(customer.id, 'seats')} "
            f"can={services.entitlements.can(customer.id, 'seats')}"
        )


if __name__ == "__main__":
    main()
