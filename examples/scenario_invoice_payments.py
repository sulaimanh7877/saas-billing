"""Scenario: manual invoicing and offline payments.

Run with::

    python examples/scenario_invoice_payments.py

Builds a draft invoice, finalizes it, records a partial and then a full
payment, and shows the guardrails: overpayment, paying a draft, and marking a
paid invoice uncollectible are all rejected.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from billing_engine import BillingEngine, EngineConfig
from billing_engine.domain.errors import BillingError


def _attempt(label: str, action) -> None:
    try:
        action()
    except BillingError as exc:
        print(f"{label:<22} rejected: {exc}")
    else:
        print(f"{label:<22} accepted")


def main() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    billing = BillingEngine(EngineConfig(engine=engine, table_prefix="scenario_"))
    billing.migrate()

    with billing.transaction() as services:
        customer = services.customers.create("billing-contact")
        draft = services.invoices.create(
            customer.id,
            lines=[{"description": "Setup", "quantity": 1, "unit_amount_minor": 2000}],
        )
        services.invoices.add_line(draft.id, "Extra seat", quantity=2, unit_amount_minor=500)
        draft = services.invoices.get(draft.id)
        print(f"draft total {draft.total_minor}")

        _attempt("pay draft", lambda: services.invoices.record_payment(draft.id, 100))

        invoice = services.invoices.finalize(draft.id)
        print(f"finalized status={invoice.status} total={invoice.total_minor}")

        _attempt("overpay", lambda: services.invoices.record_payment(invoice.id, 50_000))

        services.invoices.record_payment(invoice.id, 1000, method="transfer")
        paid = services.invoices.get(invoice.id)
        print(f"partial      status={paid.status} paid={paid.amount_paid_minor}")

        services.invoices.record_payment(invoice.id, 2000, method="cash")
        paid = services.invoices.get(invoice.id)
        print(f"settled      status={paid.status} paid={paid.amount_paid_minor}")

        _attempt("mark uncollectible", lambda: services.invoices.mark_uncollectible(invoice.id))

        open_invoice = services.invoices.create(
            customer.id,
            lines=[{"description": "Retainer", "quantity": 1, "unit_amount_minor": 500}],
            finalize=True,
        )
        services.invoices.mark_uncollectible(open_invoice.id)
        print(f"write-off    status={services.invoices.get(open_invoice.id).status}")


if __name__ == "__main__":
    main()
