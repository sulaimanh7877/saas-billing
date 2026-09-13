"""Scenario: channel sales through a reseller partner.

Run with::

    python examples/scenario_partner_channel.py

Allocates a pool of licenses to a reseller, issues two, shows the partner
receivable ledger, generates a settlement statement, then revokes one license
and confirms channel revenue stops counting it.
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
        services.catalog.create_feature("reports", name="Reports")
        plan = services.catalog.create_plan("channel-pro", "Channel Pro")
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 10000, "currency": "USD", "interval": "month"}],
            entitlements=[{"feature_key": "reports", "limit_value": 1}],
        )

        partner = services.partners.create("Acme Reseller", type="reseller")
        rule = services.partners.create_commission_rule(basis="flat", rate_bps=2000)
        agreement = services.partners.create_agreement(
            partner.id, money_model="consignment", commission_rule_id=rule.id
        )
        allocation = services.licenses.allocate(
            partner.id, version.id, quantity=2, agreement_id=agreement.id
        )
        print(f"allocated   available={services.licenses.available(allocation)}")

        first = services.licenses.issue(
            allocation.id, external_id="end-customer-1", email="one@example.com"
        )
        second = services.licenses.issue(
            allocation.id, external_id="end-customer-2", email="two@example.com"
        )
        print(f"issued      status={first.status} customer={first.customer_id[:8]}...")
        print(
            f"available   {services.licenses.available(services.licenses.get_allocation(allocation.id))}"
        )

        print(f"balances    {services.partner_accounts.balances(partner.id)}")

        statement = services.partner_accounts.generate_statement(
            partner.id, utcnow() - timedelta(days=1), utcnow() + timedelta(days=1)
        )
        print(
            f"statement   charges={statement.charges_minor} closing={statement.closing_balance_minor}"
        )

        before = services.uow.reports.channel_revenue("USD")
        print(f"channel     {before[0]['licenses']} licenses, {before[0]['value_minor']} minor")

        services.licenses.revoke(second.id, reason="chargeback")
        after = services.uow.reports.channel_revenue("USD")
        print(f"after revoke {after[0]['licenses']} licenses, {after[0]['value_minor']} minor")
        print(f"rules       {[item.basis for item in services.partners.list_commission_rules()]}")


if __name__ == "__main__":
    main()
