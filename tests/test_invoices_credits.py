import pytest

from billing_engine.domain.errors import ConflictError, ValidationError
from helpers import make_customer, make_plan


def test_create_and_finalize_invoice(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(
        customer.id,
        lines=[
            {"description": "Setup", "quantity": 1, "unit_amount_minor": 5000},
            {"description": "Seats", "quantity": 3, "unit_amount_minor": 1000},
        ],
    )
    assert invoice.status == "draft"
    assert invoice.total_minor == 8000
    finalized = services.invoices.finalize(invoice.id)
    assert finalized.status == "open"
    assert finalized.issue_date is not None


def test_partial_then_full_payment(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(
        customer.id,
        lines=[{"description": "Plan", "quantity": 1, "unit_amount_minor": 2000}],
        finalize=True,
    )
    services.invoices.record_payment(invoice.id, 500, method="transfer")
    assert services.invoices.get(invoice.id).status == "open"
    services.invoices.record_payment(invoice.id, 1500, method="cash")
    paid = services.invoices.get(invoice.id)
    assert paid.status == "paid"
    assert paid.amount_paid_minor == 2000


def test_invoice_from_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, amount=2900)
    subscription = services.subscriptions.create(customer.id, version.id)
    invoice = services.invoices.create_from_subscription(subscription.id)
    assert invoice.status == "open"
    assert invoice.total_minor == 2900
    assert invoice.subscription_id == subscription.id


def test_cannot_void_paid_invoice(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(
        customer.id,
        lines=[{"description": "Plan", "quantity": 1, "unit_amount_minor": 1000}],
        finalize=True,
    )
    services.invoices.record_payment(invoice.id, 1000)
    with pytest.raises(ConflictError):
        services.invoices.void(invoice.id)


def test_payment_must_be_positive(services) -> None:
    customer = make_customer(services)
    invoice = services.invoices.create(customer.id, finalize=True)
    with pytest.raises(ValidationError):
        services.invoices.record_payment(invoice.id, 0)


def test_credit_grant_consume_and_refund(services) -> None:
    customer = make_customer(services)
    services.credits.grant(customer.id, 5000, reason="goodwill")
    assert services.credits.balance(customer.id) == 5000
    services.credits.consume(customer.id, 2000, reason="top-up")
    assert services.credits.balance(customer.id) == 3000
    services.credits.refund(customer.id, 1000, reason="overcharge")
    assert services.credits.balance(customer.id) == 4000


def test_credit_consume_cannot_overdraw(services) -> None:
    customer = make_customer(services)
    with pytest.raises(ConflictError):
        services.credits.consume(customer.id, 100)
