"""Regression tests for the behavioral/audit defects in issue #13 (B1-B15)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from billing_engine.adapters.db import models as m
from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from billing_engine.events.dispatcher import EventDispatcher
from billing_engine.services.context import AuditService
from billing_engine.services.registry import Services
from helpers import make_customer, make_plan


def test_b1_audit_before_snapshot_is_not_mutated(services) -> None:
    partner = services.partners.create("Audit partner")
    services.partners.set_status(partner.id, "inactive")
    logs = services.uow.audit.list(
        entity_type="partner", entity_id=partner.id, action="partner.update_status"
    )
    assert logs[0].before is not None and logs[0].after is not None
    assert logs[0].before["status"] == "active"
    assert logs[0].after["status"] == "inactive"


def test_b2_default_agreement_is_deterministic_and_recent(services) -> None:
    partner = services.partners.create("Agreement partner")
    older = services.partners.create_agreement(
        partner.id, effective_from=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = services.partners.create_agreement(
        partner.id, effective_from=datetime(2026, 3, 1, tzinfo=UTC)
    )
    assert services.partners.default_agreement(partner.id).id == newer.id
    assert services.partners.default_agreement(partner.id).id != older.id


def test_b2_default_agreement_prefers_plan_match(services) -> None:
    plan = services.catalog.create_plan("b2-plan")
    version = services.catalog.create_plan_version(
        plan.id, prices=[{"amount_minor": 1, "currency": "USD", "interval": "month"}]
    )
    partner = services.partners.create("Plan partner")
    services.partners.create_agreement(partner.id)
    targeted = services.partners.create_agreement(partner.id, plan_id=version.plan_id)
    assert services.partners.default_agreement(partner.id, version.plan_id).id == targeted.id


def test_b3_account_currency_lookup_is_normalized(services) -> None:
    partner = services.partners.create("Currency partner")
    first = services.partner_accounts.get_or_create_account(partner.id, "USD", "receivable")
    second = services.partner_accounts.get_or_create_account(partner.id, "usd", "receivable")
    assert first.id == second.id
    assert len(services.partner_accounts.accounts(partner.id)) == 1


def test_b4_statement_accepts_naive_periods(services) -> None:
    partner = services.partners.create("Statement partner")
    services.partner_accounts.post(partner.id, "USD", "receivable", "charge", 100)
    now = datetime.now(UTC).replace(tzinfo=None)
    statement = services.partner_accounts.generate_statement(
        partner.id, now - timedelta(days=1), now + timedelta(days=1)
    )
    assert statement.period_start.tzinfo is not None
    assert statement.charges_minor == 100


def test_b5_partner_invoice_draft_is_not_payable(services) -> None:
    partner = services.partners.create("Invoice partner")
    draft = services.partner_accounts.create_invoice(
        partner.id, lines=[{"description": "x", "quantity": 1, "unit_amount_minor": 1000}]
    )
    with pytest.raises(ConflictError):
        services.partner_accounts.record_invoice_payment(draft.id, 1000)

    open_invoice = services.partner_accounts.create_invoice(
        partner.id,
        lines=[{"description": "y", "quantity": 1, "unit_amount_minor": 1000}],
        finalize=True,
    )
    services.partner_accounts.record_invoice_payment(open_invoice.id, 400)
    assert services.uow.partner_accounts.get_invoice(open_invoice.id).status == "open"


def test_b6_partner_invoice_and_payout_reject_negatives(services) -> None:
    partner = services.partners.create("Negative partner")
    with pytest.raises(ValidationError):
        services.partner_accounts.create_invoice(
            partner.id, lines=[{"description": "x", "quantity": -1, "unit_amount_minor": 100}]
        )
    with pytest.raises(ValidationError):
        services.partner_accounts.create_invoice(
            partner.id, lines=[{"description": "x", "quantity": 1, "unit_amount_minor": -5}]
        )
    with pytest.raises(ValidationError):
        services.partner_accounts.create_payout(partner.id, lines=[{"amount_minor": -500}])


def test_b7_adjustment_types_are_specific(services) -> None:
    version = make_plan(services, "b7-plan")
    customer = make_customer(services)
    sub = services.subscriptions.create(customer.id, version.id)

    services.subscriptions.cancel(sub.id, at_period_end=True)
    assert services.uow.subscriptions.list_adjustments(sub.id)[-1].adjustment_type == "cancel"

    services.subscriptions.renew(sub.id)
    assert services.uow.subscriptions.list_adjustments(sub.id)[-1].adjustment_type == "renew"

    services.subscriptions.cancel(sub.id, at_period_end=False)
    services.subscriptions.reactivate(sub.id)
    assert services.uow.subscriptions.list_adjustments(sub.id)[-1].adjustment_type == "reactivate"


def test_b8_expiration_sets_canceled_at_and_clears_cancel_at(services) -> None:
    version = make_plan(services, "b8-plan")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.cancel(sub.id, at_period_end=True)
    services.subscriptions.process_due(now=datetime(2026, 2, 2, tzinfo=UTC))
    got = services.subscriptions.get(sub.id)
    assert got.status == "expired"
    assert got.canceled_at is not None
    assert got.cancel_at is None


def test_b9_overview_counts_past_due(services) -> None:
    version = make_plan(services, "b9-plan", amount=1000)
    first = make_customer(services, "b9-1")
    second = make_customer(services, "b9-2")
    services.subscriptions.create(first.id, version.id)
    sub = services.subscriptions.create(second.id, version.id)
    sub.status = "past_due"
    services.uow.subscriptions.update(sub)
    services.uow.flush()
    overview = services.reports.overview("USD")
    assert overview["active_subscriptions"] == 2
    assert overview["mrr_minor"] == 2000


def test_b10_feature_adoption_includes_override_only_features(services) -> None:
    version = make_plan(services, "b10-plan", feature_keys=("base",))
    services.catalog.create_feature("extra")
    customer = make_customer(services)
    services.subscriptions.create(customer.id, version.id)
    services.entitlements.set_customer_override(customer.id, "extra")
    adoption = {row["feature_key"]: row for row in services.reports.feature_adoption()}
    assert "extra" in adoption
    assert adoption["extra"]["plans"] == 0
    assert adoption["extra"]["overrides"] == 1


def test_b11_open_invoice_is_not_editable(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(
        customer.id,
        lines=[{"description": "x", "quantity": 1, "unit_amount_minor": 1000}],
        finalize=True,
    )
    with pytest.raises(ConflictError):
        services.invoices.add_line(invoice.id, "extra", quantity=1, unit_amount_minor=500)
    assert services.invoices.get(invoice.id).total_minor == 1000


def test_b12_unpublished_plan_version_cannot_start_subscription(services) -> None:
    plan = services.catalog.create_plan("b12-plan")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 1, "currency": "USD", "interval": "month"}],
        is_published=False,
    )
    customer = make_customer(services)
    with pytest.raises(ConflictError):
        services.subscriptions.create(customer.id, version.id)


def test_b14_remove_unknown_override_is_not_silent(services) -> None:
    with pytest.raises(NotFoundError):
        services.entitlements.remove_override(new_ulid())


def test_b15_outbox_event_eventually_marked_failed(session_factory) -> None:
    session = session_factory()
    try:
        bundle = Services(SqlUnitOfWork(session))
        AuditService(bundle.uow).emit("test.event", {"x": 1})
        session.commit()
    finally:
        session.close()

    def boom(event) -> None:
        raise RuntimeError("webhook down")

    dispatcher = EventDispatcher(session_factory, boom, backoff_seconds=0, max_attempts=2)
    assert dispatcher.dispatch_pending() == 0
    assert dispatcher.dispatch_pending() == 0

    session = session_factory()
    try:
        row = session.scalar(select(m.Event).where(m.Event.event_type == "test.event"))
        assert row is not None
        assert row.status == "failed"
        assert row.attempts == 2
        assert row.last_error == "webhook down"
    finally:
        session.close()


def test_b15_retry_below_max_stays_pending(session_factory) -> None:
    session = session_factory()
    try:
        bundle = Services(SqlUnitOfWork(session))
        AuditService(bundle.uow).emit("test.retry", {"x": 1})
        session.commit()
    finally:
        session.close()

    def boom(event) -> None:
        raise RuntimeError("down")

    dispatcher = EventDispatcher(session_factory, boom, backoff_seconds=0, max_attempts=5)
    dispatcher.dispatch_pending()
    session = session_factory()
    try:
        row = session.scalar(select(m.Event).where(m.Event.event_type == "test.retry"))
        assert row is not None
        assert row.status == "pending"
        assert row.attempts == 1
    finally:
        session.close()


def test_b13_commission_rules_are_global(services) -> None:
    rule = services.partners.create_commission_rule(basis="flat", rate_bps=1500)
    rules = services.partners.list_commission_rules()
    assert [item.id for item in rules] == [rule.id]


def test_quiet_period_behavior_without_grace(services) -> None:
    # A canceled subscription with zero grace expires on its period end.
    version = make_plan(services, "nograce-plan")
    customer = make_customer(services)
    sub = services.subscriptions.create(
        customer.id, version.id, start_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    services.subscriptions.cancel(sub.id, at_period_end=True)
    services.subscriptions.process_due(now=datetime(2026, 2, 1, tzinfo=UTC))
    assert services.subscriptions.get(sub.id).status == "expired"
