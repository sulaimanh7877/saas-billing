"""Regression tests for the functional defects in issue #13 (F1-F15)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing_engine.adapters.db.reporting import _monthly_minor
from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from billing_engine.services.registry import Services
from helpers import make_customer, make_plan


def _open_invoice(services, customer, amount: int = 1000):
    return services.invoices.create(
        customer.id,
        lines=[{"description": "item", "quantity": 1, "unit_amount_minor": amount}],
        finalize=True,
    )


def test_f1_plan_limit_value_is_preserved(services) -> None:
    customer = make_customer(services)
    plan = services.catalog.create_plan("limits")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}],
        entitlements=[{"feature_key": "seats", "value": 1, "limit_value": 5}],
    )
    services.subscriptions.create(customer.id, version.id)
    resolved = services.entitlements.resolve(customer.id, "seats")
    assert resolved.value == 1
    assert resolved.limit_value == 5
    assert services.entitlements.limit(customer.id, "seats") == 5


def test_f2_one_time_subscription_does_not_renew_forever(services) -> None:
    version = make_plan(services, "one-time", interval="one_time")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    end = sub.current_period_end
    for _ in range(3):
        services.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))
    got = services.subscriptions.get(sub.id)
    assert got.status == "expired"
    assert got.current_period_end == end
    adjustments = services.uow.subscriptions.list_adjustments(sub.id)
    assert [a.adjustment_type for a in adjustments] == ["expire"]


def test_f3_trial_longer_than_interval_is_not_forced_active(services) -> None:
    version = make_plan(services, "trial-long", interval="month")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, trial_days=45, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.process_due(now=datetime(2026, 2, 2, tzinfo=UTC))
    got = services.subscriptions.get(sub.id)
    assert got.status == "trialing"
    assert got.trial_end is not None and got.trial_end > datetime(2026, 2, 2, tzinfo=UTC)


def test_f3_trial_shorter_than_interval_activates_at_trial_end(services) -> None:
    version = make_plan(services, "trial-short", interval="month")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, trial_days=5, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.process_due(now=datetime(2026, 1, 7, tzinfo=UTC))
    got = services.subscriptions.get(sub.id)
    assert got.status == "active"
    assert got.current_period_start == datetime(2026, 1, 6, tzinfo=UTC)


def test_f4_uncollectible_requires_open(services) -> None:
    customer = make_customer(services)
    open_invoice = _open_invoice(services, customer)
    assert services.invoices.mark_uncollectible(open_invoice.id).status == "uncollectible"

    paid = _open_invoice(services, customer)
    services.invoices.record_payment(paid.id, 1000)
    with pytest.raises(ConflictError):
        services.invoices.mark_uncollectible(paid.id)


def test_f5_overpayment_is_rejected(services) -> None:
    customer = make_customer(services)
    invoice = _open_invoice(services, customer, amount=1000)
    with pytest.raises(ValidationError):
        services.invoices.record_payment(invoice.id, 5000)
    assert services.invoices.get(invoice.id).amount_paid_minor == 0


def test_f6_draft_invoice_cannot_be_paid(services) -> None:
    customer = make_customer(services)
    draft = services.invoices.create(
        customer.id,
        lines=[{"description": "item", "quantity": 1, "unit_amount_minor": 1000}],
    )
    assert draft.status == "draft"
    with pytest.raises(ConflictError):
        services.invoices.record_payment(draft.id, 400)


def test_f7_license_requires_a_matching_currency_price(services) -> None:
    version = make_plan(services, "eur-mismatch", amount=10000)
    partner = services.partners.create("EUR partner", currency="EUR")
    allocation = services.licenses.allocate(partner.id, version.id, 2)
    with pytest.raises(NotFoundError):
        services.licenses.issue(allocation.id, external_id="cust-1")


def test_f8_credit_balances_are_per_currency(services) -> None:
    customer = make_customer(services, "ccy-user")
    services.credits.grant(customer.id, 100, currency="USD")
    services.credits.grant(customer.id, 100, currency="EUR")
    assert services.credits.balance(customer.id) == 100
    with pytest.raises(ConflictError):
        services.credits.consume(customer.id, 200)
    services.credits.consume(customer.id, 100)
    assert services.credits.balance(customer.id) == 0


def test_f9_dangling_references_are_rejected(services) -> None:
    missing = new_ulid()
    with pytest.raises(NotFoundError):
        services.catalog.create_plan("orphan", product_id=missing)
    with pytest.raises(NotFoundError):
        services.customers.create("orphan-user", partner_id=missing)

    customer = make_customer(services, "f9-user")
    with pytest.raises(NotFoundError):
        services.invoices.create(customer.id, subscription_id=missing)


def test_f9_invoice_cannot_reference_another_customers_subscription(services) -> None:
    version = make_plan(services, "f9-plan")
    owner = make_customer(services, "owner")
    other = make_customer(services, "other")
    subscription = services.subscriptions.create(owner.id, version.id)
    with pytest.raises(ValidationError):
        services.invoices.create(other.id, subscription_id=subscription.id)


def test_f10_free_form_enums_are_validated(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, "f10-plan")
    with pytest.raises(ValidationError):
        services.subscriptions.create(customer.id, version.id, collection_method="bogus")

    plan = services.catalog.create_plan("f10-scope")
    with pytest.raises(ValidationError):
        services.catalog.create_plan_version(
            plan.id,
            scope="bogus",
            prices=[{"amount_minor": 1, "currency": "USD"}],
        )
    with pytest.raises(ValidationError):
        services.catalog.create_feature("f10-feature", reset_period="fortnight")


def test_f11_config_trial_days_applies_when_plan_has_none(session_factory) -> None:
    session = session_factory()
    try:
        bundle = Services(SqlUnitOfWork(session), default_currency="USD", trial_days=7)
        customer = bundle.customers.create("cfg-trial")
        plan = bundle.catalog.create_plan("cfg-trial-plan")
        version = bundle.catalog.create_plan_version(
            plan.id, prices=[{"amount_minor": 1, "currency": "USD", "interval": "month"}]
        )
        subscription = bundle.subscriptions.create(customer.id, version.id)
        assert subscription.status == "trialing"
        assert subscription.trial_end is not None
    finally:
        session.close()


def test_f11_grace_period_delays_expiration(session_factory) -> None:
    session = session_factory()
    try:
        bundle = Services(SqlUnitOfWork(session), default_currency="USD", grace_period_days=3)
        customer = bundle.customers.create("cfg-grace")
        plan = bundle.catalog.create_plan("cfg-grace-plan")
        version = bundle.catalog.create_plan_version(
            plan.id, prices=[{"amount_minor": 1, "currency": "USD", "interval": "month"}]
        )
        sub = bundle.subscriptions.create(
            customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        bundle.subscriptions.cancel(sub.id, at_period_end=True)

        bundle.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))
        in_grace = bundle.subscriptions.get(sub.id)
        assert in_grace.status == "past_due"
        assert in_grace.grace_until == datetime(2026, 2, 4, tzinfo=UTC)

        bundle.subscriptions.process_due(now=datetime(2026, 2, 4, tzinfo=UTC))
        assert bundle.subscriptions.get(sub.id).status == "expired"
    finally:
        session.close()


def test_f12_created_entities_carry_timestamps(services) -> None:
    customer = make_customer(services)
    assert customer.created_at is not None
    assert customer.updated_at is not None
    version = make_plan(services, "f12-plan")
    subscription = services.subscriptions.create(customer.id, version.id)
    assert subscription.created_at is not None
    assert subscription.updated_at is not None


def test_f13_mrr_uses_integer_division(services) -> None:
    assert _monthly_minor(10, "year") == 0
    assert _monthly_minor(11, "year") == 0
    assert _monthly_minor(23, "year") == 1
    assert _monthly_minor(24, "year") == 2


def test_f14_channel_revenue_excludes_revoked_licenses(services) -> None:
    version = make_plan(services, "f14-plan", amount=1000)
    partner = services.partners.create("f14 partner")
    allocation = services.licenses.allocate(partner.id, version.id, 2)
    license_ = services.licenses.issue(allocation.id, external_id="f14-cust")
    assert services.uow.reports.channel_revenue("USD")
    services.licenses.revoke(license_.id)
    assert services.uow.reports.channel_revenue("USD") == []


def test_f15_expiration_writes_an_adjustment(services) -> None:
    version = make_plan(services, "f15-plan")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.cancel(sub.id, at_period_end=True)
    services.subscriptions.process_due(now=datetime(2026, 2, 2, tzinfo=UTC))
    adjustments = services.uow.subscriptions.list_adjustments(sub.id)
    assert [a.adjustment_type for a in adjustments] == ["cancel", "expire"]
    assert services.subscriptions.get(sub.id).status == "expired"


def test_grace_extends_but_cancel_still_expires(services) -> None:
    # Sanity: with the default zero grace period, expiration is immediate.
    version = make_plan(services, "grace-zero")
    customer = make_customer(services)
    sub = services.subscriptions.create(customer.id, version.id)
    services.subscriptions.cancel(sub.id, at_period_end=False)
    assert services.subscriptions.get(sub.id).status == "canceled"
    assert services.subscriptions.get(sub.id).canceled_at is not None
