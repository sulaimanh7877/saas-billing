"""Regression tests for the consolidated audit in issue #22.

Covers the functional (F*) and behavioural (B*) defects listed there.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect

from billing_engine import BillingEngine, EngineConfig
from billing_engine.adapters.api.app import router
from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from conftest import TEST_PREFIX
from helpers import make_customer, make_plan

# --- F1 / F2: timestamp coherence -------------------------------------------


def test_f1_updated_at_advances_on_subscription_change(services) -> None:
    version = make_plan(services, "f1-plan")
    customer = make_customer(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    created = subscription.updated_at

    time.sleep(0.01)
    services.subscriptions.extend(subscription.id, days=5)

    reloaded = services.subscriptions.get(subscription.id)
    assert reloaded.updated_at is not None
    assert created is not None
    assert reloaded.updated_at > created


def test_f1_updated_at_advances_on_partner_status(services) -> None:
    partner = services.partners.create("F1 partner")
    created = partner.updated_at
    time.sleep(0.01)
    services.partners.set_status(partner.id, "inactive")
    reloaded = services.partners.get(partner.id)
    assert created is not None and reloaded.updated_at > created


def test_f2_update_returns_created_at_and_audits_it(services) -> None:
    customer = make_customer(services, "f2-user")
    updated = services.customers.update(customer.id, name="Ada")
    assert updated.created_at == customer.created_at

    entries = services.uow.audit.list(
        entity_type="customer", entity_id=customer.id, action="customer.update"
    )
    assert entries[0].after is not None
    assert entries[0].after["created_at"] is not None


# --- F3: cancel-at-period-end during a trial --------------------------------


def test_f3_cancel_at_period_end_uses_trial_end(services) -> None:
    version = make_plan(services, "f3-plan", trial_days=14)
    customer = make_customer(services)
    subscription = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert subscription.trial_end == datetime(2026, 1, 15, tzinfo=UTC)

    canceled = services.subscriptions.cancel(subscription.id, at_period_end=True)
    assert canceled.cancel_at == subscription.trial_end

    services.subscriptions.process_due(now=datetime(2026, 1, 15, tzinfo=UTC))
    assert services.subscriptions.get(subscription.id).status == "expired"


# --- F4 / F6: plan-version scoping and publication --------------------------


def test_f4_cannot_subscribe_another_customers_custom_plan(services) -> None:
    owner = make_customer(services, "f4-owner")
    other = make_customer(services, "f4-other")
    custom = services.catalog.create_custom_plan(
        owner.id,
        name="Private",
        prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
    )
    with pytest.raises(ValidationError):
        services.subscriptions.create(other.id, custom.id)

    version = make_plan(services, "f4-plan")
    subscription = services.subscriptions.create(other.id, version.id)
    with pytest.raises(ValidationError):
        services.subscriptions.change_plan(subscription.id, custom.id)


def test_f6_change_plan_rejects_unpublished_version(services) -> None:
    customer = make_customer(services)
    current = make_plan(services, "f6-current")
    subscription = services.subscriptions.create(customer.id, current.id)

    plan = services.catalog.create_plan("f6-draft")
    draft = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
        is_published=False,
    )
    with pytest.raises(ConflictError):
        services.subscriptions.change_plan(subscription.id, draft.id)


# --- F5: catalog does not list custom-only plans ----------------------------


def test_f5_custom_plans_do_not_pollute_catalog(services) -> None:
    customer = make_customer(services)
    make_plan(services, "f5-catalog")
    services.catalog.create_custom_plan(
        customer.id,
        name="Deal",
        prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
    )
    keys = {plan.key for plan in services.catalog.list_plans()}
    assert "f5-catalog" in keys
    assert not any(key.startswith("custom-") for key in keys)


# --- F7 / B6: price uniqueness and channel revenue --------------------------


def test_f7_duplicate_price_currency_and_interval_rejected(services) -> None:
    plan = services.catalog.create_plan("f7")
    with pytest.raises(ValidationError):
        services.catalog.create_plan_version(
            plan.id,
            prices=[
                {"amount_minor": 100, "currency": "USD", "interval": "month"},
                {"amount_minor": 200, "currency": "USD", "interval": "month"},
            ],
        )


def test_f7_distinct_intervals_are_allowed(services) -> None:
    plan = services.catalog.create_plan("f7-ok")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[
            {"amount_minor": 100, "currency": "USD", "interval": "month"},
            {"amount_minor": 1000, "currency": "USD", "interval": "year"},
        ],
    )
    assert len(services.catalog.list_prices(version.id)) == 2


def test_b6_channel_revenue_counts_each_license_once_and_applies_discount(
    services,
) -> None:
    plan = services.catalog.create_plan("f7-chan")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[
            {"amount_minor": 10000, "currency": "USD", "interval": "month"},
            {"amount_minor": 100000, "currency": "USD", "interval": "year"},
        ],
    )
    partner = services.partners.create("Channel partner")
    agreement = services.partners.create_agreement(
        partner.id, money_model="consignment", discount_bps=2500
    )
    allocation = services.licenses.allocate(partner.id, version.id, 1, agreement_id=agreement.id)
    services.licenses.issue(allocation.id, external_id="f7-cust")

    rows = services.uow.reports.channel_revenue("USD")
    assert len(rows) == 1
    assert rows[0]["licenses"] == 1
    assert rows[0]["value_minor"] == 7500


# --- F8: customer-scoped versions validate their customer -------------------


def test_f8_custom_version_requires_existing_customer(services) -> None:
    plan = services.catalog.create_plan("f8")
    with pytest.raises(NotFoundError):
        services.catalog.create_plan_version(
            plan.id,
            scope="customer_custom",
            customer_id=new_ulid(),
            prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
        )


# --- F9: ISO currency validation --------------------------------------------


@pytest.mark.parametrize("bad", ["us", "EURO", "12", "U$D"])
def test_f9_invalid_currency_is_rejected(services, bad) -> None:
    with pytest.raises(ValidationError):
        services.customers.create("f9-user", currency=bad)
    with pytest.raises(ValidationError):
        services.partners.create("f9-partner", currency=bad)


# --- F10: the bare router works when mounted directly -----------------------


def test_f10_bare_router_is_self_contained(tmp_path) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    BillingEngine.reset_process_state()
    try:
        engine = BillingEngine(
            EngineConfig(dsn=f"sqlite:///{tmp_path / 'mount.sqlite3'}", table_prefix=TEST_PREFIX)
        )
        engine.create_all()
        app = FastAPI()
        app.include_router(router, prefix="/billing")
        app.state.engine = engine
        app.state.api_key = "secret"

        client = TestClient(app)
        headers = {"X-API-Key": "secret"}
        assert client.get("/billing/customers", headers=headers).status_code == 200
        created = client.post("/billing/customers", json={"external_id": "f10"}, headers=headers)
        assert created.status_code == 200
        assert client.get("/billing/customers", headers=headers).json()[0]["external_id"] == "f10"
    finally:
        BillingEngine.reset_process_state()


# --- B1: plan version immutability ------------------------------------------


def test_b1_published_version_entitlements_are_immutable(services) -> None:
    version = make_plan(services, "b1-plan")
    with pytest.raises(ConflictError):
        services.catalog.set_entitlements(
            version.id, [{"feature_key": "reports", "limit_value": 5}]
        )


def test_b1_unpublished_version_entitlements_can_change(services) -> None:
    plan = services.catalog.create_plan("b1-draft")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
        is_published=False,
    )
    services.catalog.set_entitlements(version.id, [{"feature_key": "reports", "limit_value": 5}])
    resolved = services.catalog.list_plan_entitlements(version.id)
    assert len(resolved) == 1


# --- B2: past_due grace transition is recorded ------------------------------


def test_b2_grace_transition_records_adjustment(services) -> None:
    services.subscriptions.grace_period_days = 3
    version = make_plan(services, "b2-plan")
    customer = make_customer(services)
    subscription = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.cancel(subscription.id, at_period_end=True)
    services.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))

    types = [
        item.adjustment_type
        for item in services.uow.subscriptions.list_adjustments(subscription.id)
    ]
    assert types == ["cancel", "past_due"]
    assert services.subscriptions.get(subscription.id).status == "past_due"


# --- B3: pause-until auto-resumes -------------------------------------------


def test_b3_pause_until_resumes_on_process_due(services) -> None:
    version = make_plan(services, "b3-plan")
    customer = make_customer(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    services.subscriptions.pause(subscription.id, until=datetime(2026, 1, 1, tzinfo=UTC))
    assert services.subscriptions.get(subscription.id).status == "paused"

    services.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))
    assert services.subscriptions.get(subscription.id).status == "active"


# --- B4: partner account uniqueness -----------------------------------------


def test_b4_partner_account_columns_are_unique(engine) -> None:
    constraints = inspect(engine).get_unique_constraints("test_partner_accounts")
    indexes = [
        item for item in inspect(engine).get_indexes("test_partner_accounts") if item["unique"]
    ]
    target = {"partner_id", "currency", "account_type"}
    assert any(set(item["column_names"]) == target for item in constraints) or any(
        set(item["column_names"]) == target for item in indexes
    )


def test_b4_get_or_create_account_is_idempotent(services) -> None:
    partner = services.partners.create("B4 partner")
    first = services.partner_accounts.get_or_create_account(partner.id, "USD", "receivable")
    second = services.partner_accounts.get_or_create_account(partner.id, "usd", "receivable")
    assert first.id == second.id
    assert len(services.partner_accounts.accounts(partner.id)) == 1


# --- B5: finalized partner invoices post a backing charge -------------------


def test_b5_finalized_partner_invoice_posts_charge(services) -> None:
    partner = services.partners.create("B5 partner")
    invoice = services.partner_accounts.create_invoice(
        partner.id,
        lines=[{"description": "licenses", "quantity": 2, "unit_amount_minor": 1000}],
        finalize=True,
    )
    assert services.partner_accounts.balances(partner.id)["receivable"] == 2000

    services.partner_accounts.record_invoice_payment(invoice.id, 2000)
    assert services.partner_accounts.balances(partner.id)["receivable"] == 0


# --- Minor: set_period_end is implemented -----------------------------------


def test_set_period_end_records_adjustment(services) -> None:
    version = make_plan(services, "spe-plan")
    customer = make_customer(services)
    subscription = services.subscriptions.create(customer.id, version.id)

    target = datetime(2026, 6, 30, tzinfo=UTC)
    updated = services.subscriptions.set_period_end(subscription.id, target, reason="custom")
    assert updated.current_period_end == target
    adjustment = services.uow.subscriptions.list_adjustments(subscription.id)[-1]
    assert adjustment.adjustment_type == "set_period_end"
    assert adjustment.reason == "custom"
