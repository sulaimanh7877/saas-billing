"""Manual invoicing and offline payments."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from billing_engine.domain.entities import Invoice, InvoiceLine, Payment
from billing_engine.domain.enums import InvoiceStatus, PaymentMethod
from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import new_ulid, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor

_EDITABLE = {InvoiceStatus.DRAFT.value}
_PAYABLE = {InvoiceStatus.OPEN.value}


class InvoiceService(Service):
    def _recalculate(self, invoice: Invoice) -> Invoice:
        lines = self.uow.invoices.list_lines(invoice.id)
        subtotal = sum(line.amount_minor for line in lines)
        invoice.subtotal_minor = subtotal
        invoice.total_minor = subtotal
        return invoice

    def create(
        self,
        customer_id: str,
        *,
        lines: list[dict[str, Any]] | None = None,
        currency: str | None = None,
        due_date: datetime | None = None,
        subscription_id: str | None = None,
        notes: str | None = None,
        finalize: bool = False,
        actor: Actor | None = None,
    ) -> Invoice:
        """Create a manual invoice for a customer."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        if subscription_id is not None:
            subscription = require(
                self.uow.subscriptions.get(subscription_id), "subscription", subscription_id
            )
            if subscription.customer_id != customer.id:
                raise ValidationError(
                    f"subscription {subscription_id!r} does not belong to customer {customer_id!r}"
                )
        invoice = Invoice(
            id=new_ulid(),
            customer_id=customer.id,
            subscription_id=subscription_id,
            status=InvoiceStatus.DRAFT.value,
            currency=(currency or customer.currency).upper(),
            due_date=due_date,
            notes=notes,
        )
        self.uow.invoices.add_invoice(invoice)
        self.uow.flush()
        for entry in lines or []:
            self.add_line(
                invoice.id,
                str(entry.get("description", "item")),
                quantity=int(entry.get("quantity", 1)),
                unit_amount_minor=int(entry.get("unit_amount_minor", 0)),
                actor=actor,
            )
        invoice = self._recalculate(invoice)
        if finalize:
            invoice.status = InvoiceStatus.OPEN.value
            invoice.issue_date = utcnow()
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record("invoice.create", "invoice", invoice.id, actor, after=invoice)
        self.audit.emit("invoice.created", {"invoice_id": invoice.id, "customer_id": customer.id})
        if finalize:
            self.audit.emit("invoice.finalized", {"invoice_id": invoice.id})
        return invoice

    def create_from_subscription(
        self,
        subscription_id: str,
        *,
        quantity: int | None = None,
        due_date: datetime | None = None,
        description: str | None = None,
        actor: Actor | None = None,
    ) -> Invoice:
        """Create an invoice from a subscription's current plan and price."""
        subscription = require(
            self.uow.subscriptions.get(subscription_id), "subscription", subscription_id
        )
        price = (
            self.uow.catalog.get_price(subscription.price_id)
            if subscription.price_id is not None
            else None
        )
        if price is None:
            prices = self.uow.catalog.list_prices(subscription.plan_version_id)
            price = prices[0] if prices else None
        if price is None:
            raise ValidationError("subscription has no price to invoice")
        line_quantity = quantity if quantity is not None else subscription.quantity
        return self.create(
            subscription.customer_id,
            lines=[
                {
                    "description": description or f"Subscription {subscription.id}",
                    "quantity": line_quantity,
                    "unit_amount_minor": price.amount_minor,
                }
            ],
            currency=price.currency,
            due_date=due_date,
            subscription_id=subscription.id,
            finalize=True,
            actor=actor,
        )

    def add_line(
        self,
        invoice_id: str,
        description: str,
        *,
        quantity: int = 1,
        unit_amount_minor: int = 0,
        actor: Actor | None = None,
    ) -> InvoiceLine:
        """Append a line item to a draft invoice."""
        invoice = self.get(invoice_id)
        if invoice.status not in _EDITABLE:
            raise ConflictError(f"cannot add lines to a {invoice.status!r} invoice")
        if quantity < 1:
            raise ValidationError("quantity must be at least 1")
        if unit_amount_minor < 0:
            raise ValidationError("unit_amount_minor must be non-negative")
        line = InvoiceLine(
            id=new_ulid(),
            invoice_id=invoice_id,
            description=description,
            quantity=quantity,
            unit_amount_minor=unit_amount_minor,
            amount_minor=quantity * unit_amount_minor,
        )
        self.uow.invoices.add_line(line)
        self._recalculate(invoice)
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record("invoice.line.add", "invoice", invoice_id, actor, after=line)
        return line

    def get(self, invoice_id: str) -> Invoice:
        return require(self.uow.invoices.get_invoice(invoice_id), "invoice", invoice_id)

    def list_for_customer(self, customer_id: str) -> list[Invoice]:
        return self.uow.invoices.list_invoices(customer_id)

    def finalize(self, invoice_id: str, *, actor: Actor | None = None) -> Invoice:
        """Move a draft invoice to open."""
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.DRAFT.value:
            raise ConflictError(f"invoice is {invoice.status!r}, expected draft")
        invoice.status = InvoiceStatus.OPEN.value
        invoice.issue_date = utcnow()
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record("invoice.finalize", "invoice", invoice_id, actor, after=invoice)
        self.audit.emit("invoice.finalized", {"invoice_id": invoice_id})
        return invoice

    def void(
        self, invoice_id: str, *, reason: str | None = None, actor: Actor | None = None
    ) -> Invoice:
        """Void an invoice."""
        invoice = self.get(invoice_id)
        if invoice.status in {InvoiceStatus.PAID.value, InvoiceStatus.UNCOLLECTIBLE.value}:
            raise ConflictError(f"cannot void a {invoice.status!r} invoice")
        invoice.status = InvoiceStatus.VOID.value
        invoice.voided_at = utcnow()
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record(
            "invoice.void", "invoice", invoice_id, actor, after=invoice, reason=reason
        )
        self.audit.emit("invoice.voided", {"invoice_id": invoice_id})
        return invoice

    def mark_uncollectible(self, invoice_id: str, *, actor: Actor | None = None) -> Invoice:
        """Mark an open invoice as uncollectible."""
        invoice = self.get(invoice_id)
        if invoice.status != InvoiceStatus.OPEN.value:
            raise ConflictError(
                f"cannot mark a {invoice.status!r} invoice uncollectible; expected open"
            )
        invoice.status = InvoiceStatus.UNCOLLECTIBLE.value
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record("invoice.mark_uncollectible", "invoice", invoice_id, actor, after=invoice)
        return invoice

    def record_payment(
        self,
        invoice_id: str,
        amount_minor: int,
        *,
        method: str = PaymentMethod.OTHER.value,
        reference: str | None = None,
        received_at: datetime | None = None,
        actor: Actor | None = None,
    ) -> Payment:
        """Record an offline payment and update the invoice balance."""
        invoice = self.get(invoice_id)
        if invoice.status not in _PAYABLE:
            raise ConflictError(
                f"cannot pay a {invoice.status!r} invoice; only open invoices are payable"
            )
        if amount_minor <= 0:
            raise ValidationError("payment amount must be positive")
        remaining = invoice.total_minor - invoice.amount_paid_minor
        if amount_minor > remaining:
            raise ValidationError(
                f"payment {amount_minor} exceeds the remaining balance {remaining}"
            )
        payment = Payment(
            id=new_ulid(),
            customer_id=invoice.customer_id,
            invoice_id=invoice.id,
            amount_minor=amount_minor,
            currency=invoice.currency,
            method=method,
            reference=reference,
            received_at=received_at or utcnow(),
        )
        self.uow.invoices.add_payment(payment)
        invoice.amount_paid_minor += amount_minor
        if invoice.amount_paid_minor >= invoice.total_minor:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_at = utcnow()
        else:
            invoice.status = InvoiceStatus.OPEN.value
        self.uow.invoices.update_invoice(invoice)
        self.uow.flush()
        self.audit.record("invoice.payment.record", "invoice", invoice.id, actor, after=payment)
        self.audit.emit(
            "invoice.paid"
            if invoice.status == InvoiceStatus.PAID.value
            else "invoice.partially_paid",
            {"invoice_id": invoice.id, "amount_minor": amount_minor},
        )
        return payment

    def list_lines(self, invoice_id: str) -> list[InvoiceLine]:
        return self.uow.invoices.list_lines(invoice_id)

    def list_payments(self, invoice_id: str) -> list[Payment]:
        return self.uow.invoices.list_payments(invoice_id)
