"""Regression tests for the post-v0.2.0 audit (issue #20)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from billing_engine.domain.value_objects import new_ulid, utcnow
from billing_engine.services.registry import Services
from helpers import make_customer, make_plan


def _two_currency_version(
    services: Services, key: str = "two-ccy", amount_usd: int = 1000, amount_eur: int = 1200
):
    plan = services.catalog.create_plan(key)
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[
            {"amount_minor": amount_usd, "currency": "USD", "interval": "month"},
            {"amount_minor": amount_eur, "currency": "EUR", "interval": "month"},
        ],
    )
    prices = {price.currency: price for price in services.catalog.list_prices(version.id)}
    return version, prices


def test_f1_license_issue_uses_agreement_currency_price(services) -> None:
    version, prices = _two_currency_version(services)
    partner = services.partners.create("EUR partner", currency="EUR")
    allocation = services.licenses.allocate(partner.id, version.id, 1)

    license_ = services.licenses.issue(allocation.id, external_id="eur-cust")

    subscription = services.subscriptions.get(license_.subscription_id)
    assert subscription.price_id == prices["EUR"].id
    invoice = services.invoices.create_from_subscription(subscription.id)
    assert invoice.currency == "EUR"
    assert services.invoices.list_lines(invoice.id)[0].unit_amount_minor == 1200


def test_f2_price_listing_is_stable(services) -> None:
    version, prices = _two_currency_version(services, "stable-ccy")
    first = [price.id for price in services.catalog.list_prices(version.id)]
    second = [price.id for price in services.catalog.list_prices(version.id)]
    assert first == second
    assert set(first) == {prices["USD"].id, prices["EUR"].id}


def test_f3_agreement_rejects_dangling_plan(services) -> None:
    partner = services.partners.create("P")
    with pytest.raises(NotFoundError):
        services.partners.create_agreement(partner.id, plan_id=new_ulid())


def test_f4_allocation_rejects_dangling_agreement(services) -> None:
    version = make_plan(services, "f4a")
    partner = services.partners.create("P")
    with pytest.raises(NotFoundError):
        services.licenses.allocate(partner.id, version.id, 1, agreement_id=new_ulid())


def test_f4_allocation_rejects_cross_partner_parent(services) -> None:
    version = make_plan(services, "f4b")
    owner = services.partners.create("Owner")
    other = services.partners.create("Other")
    parent = services.licenses.allocate(owner.id, version.id, 5)
    with pytest.raises(ValidationError):
        services.licenses.allocate(other.id, version.id, 1, parent_allocation_id=parent.id)


def test_f4_allocation_rejects_cross_partner_agreement(services) -> None:
    version = make_plan(services, "f4c")
    owner = services.partners.create("Owner")
    other = services.partners.create("Other")
    agreement = services.partners.create_agreement(owner.id)
    with pytest.raises(ValidationError):
        services.licenses.allocate(other.id, version.id, 1, agreement_id=agreement.id)


def test_f5_partner_invoice_overpayment_rejected(services) -> None:
    partner = services.partners.create("P")
    invoice = services.partner_accounts.create_invoice(
        partner.id,
        lines=[{"description": "x", "quantity": 1, "unit_amount_minor": 1000}],
        finalize=True,
    )
    with pytest.raises(ValidationError):
        services.partner_accounts.record_invoice_payment(invoice.id, 5000)
    assert services.uow.partner_accounts.get_invoice(invoice.id).amount_paid_minor == 0


def test_f6_void_payout_cannot_be_paid(services) -> None:
    partner = services.partners.create("P")
    payout = services.partner_accounts.create_payout(
        partner.id, lines=[{"description": "x", "amount_minor": 100}]
    )
    payout.status = "void"
    services.uow.partner_accounts.update_payout(payout)
    services.uow.flush()
    with pytest.raises(ConflictError):
        services.partner_accounts.pay_payout(payout.id)


def test_f10_resume_requires_paused(services) -> None:
    version = make_plan(services, "f10")
    customer = make_customer(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    with pytest.raises(ConflictError):
        services.subscriptions.resume(subscription.id)
    services.subscriptions.pause(subscription.id)
    assert services.subscriptions.resume(subscription.id).status == "active"


def test_f11_extend_expired_clears_canceled_at(services) -> None:
    version = make_plan(services, "f11")
    customer = make_customer(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    services.subscriptions.cancel(subscription.id, at_period_end=False)
    expired = services.subscriptions.get(subscription.id)
    expired.status = "expired"
    services.uow.subscriptions.update(expired)
    services.uow.flush()

    extended = services.subscriptions.extend(subscription.id, days=30, reason="goodwill")
    assert extended.status == "active"
    assert extended.canceled_at is None


def test_b3_default_agreement_ignores_future_and_expired(services) -> None:
    partner = services.partners.create("P")
    services.partners.create_agreement(partner.id, effective_from=datetime(2099, 1, 1, tzinfo=UTC))
    assert services.partners.default_agreement(partner.id) is None

    other = services.partners.create("Q")
    services.partners.create_agreement(other.id, effective_to=datetime(2000, 1, 1, tzinfo=UTC))
    assert services.partners.default_agreement(other.id) is None


def test_b5_grace_entry_is_audited(services) -> None:
    services.subscriptions.grace_period_days = 3
    version = make_plan(services, "b5")
    customer = make_customer(services)
    subscription = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.cancel(subscription.id, at_period_end=True)
    services.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))
    logs = services.uow.audit.list(
        entity_type="subscription", entity_id=subscription.id, action="subscription.past_due"
    )
    assert len(logs) == 1
    assert logs[0].after is not None and logs[0].after["status"] == "past_due"


def test_b6_existing_customer_gets_attributed(services) -> None:
    version = make_plan(services, "b6")
    partner = services.partners.create("P")
    customer = make_customer(services, "b6-user")
    allocation = services.licenses.allocate(partner.id, version.id, 1)

    license_ = services.licenses.issue(allocation.id, customer_id=customer.id)

    assert services.customers.get(customer.id).partner_id == partner.id
    assert services.subscriptions.get(license_.subscription_id).partner_id == partner.id


def test_b9_uncollectible_invoice_cannot_be_voided(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(
        customer.id,
        lines=[{"description": "x", "quantity": 1, "unit_amount_minor": 100}],
        finalize=True,
    )
    services.invoices.mark_uncollectible(invoice.id)
    with pytest.raises(ConflictError):
        services.invoices.void(invoice.id)


def test_b10_agreement_rejects_reversed_window(services) -> None:
    partner = services.partners.create("P")
    with pytest.raises(ValidationError):
        services.partners.create_agreement(
            partner.id,
            effective_from=datetime(2030, 1, 1, tzinfo=UTC),
            effective_to=datetime(2020, 1, 1, tzinfo=UTC),
        )


def test_b13_finalize_create_emits_event(services) -> None:
    customer = make_customer(services)
    services.invoices.create(
        customer.id,
        lines=[{"description": "x", "quantity": 1, "unit_amount_minor": 100}],
        finalize=True,
    )
    pending = {event.event_type for event in services.uow.events.list_pending(utcnow())}
    assert "invoice.finalized" in pending


def _api_client(tmp_path):
    from fastapi.testclient import TestClient

    from billing_engine import BillingEngine, EngineConfig
    from billing_engine.adapters.api.app import create_app
    from conftest import TEST_PREFIX

    engine = BillingEngine(
        EngineConfig(dsn=f"sqlite:///{tmp_path / 'audit20.sqlite3'}", table_prefix=TEST_PREFIX)
    )
    engine.create_all()
    return TestClient(create_app(engine, api_key="secret"))


def test_b1_api_rolls_back_when_route_rejects(tmp_path) -> None:
    client = _api_client(tmp_path)
    headers = {"X-API-Key": "secret"}
    customer = client.post("/customers", json={"external_id": "b1"}, headers=headers).json()

    response = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "lines": [
                {"description": "ok", "quantity": 1, "unit_amount_minor": 500},
                {"description": "bad", "quantity": 0, "unit_amount_minor": 500},
            ],
        },
        headers=headers,
    )
    assert response.status_code == 400
    invoices = client.get(f"/customers/{customer['id']}/invoices", headers=headers).json()
    assert invoices == []


def test_b16_cli_reports_configuration_error_cleanly() -> None:
    from typer.testing import CliRunner

    from billing_engine.cli import app

    result = CliRunner().invoke(app, ["report", "--dsn", "sqlite://", "--prefix", "1bad"])
    assert result.exit_code == 1
    assert "table_prefix" in result.output.lower() or "prefix" in result.output.lower()
