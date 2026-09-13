"""Partner accounts, ledger, invoices, payouts, and statements."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from billing_engine.domain.entities import (
    PartnerAccount,
    PartnerInvoice,
    PartnerInvoiceLine,
    PartnerLedgerEntry,
    PartnerPayment,
    PartnerPayout,
    PartnerPayoutLine,
    PartnerStatement,
)
from billing_engine.domain.enums import (
    AccountType,
    InvoiceStatus,
    PartnerLedgerEntryType,
    PayoutStatus,
)
from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import as_utc, new_ulid, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor

_ACCOUNT_FOR_MODEL = {
    "wholesale_prepaid": AccountType.PREPAID.value,
    "consignment": AccountType.RECEIVABLE.value,
    "agency_commission": AccountType.RECEIVABLE.value,
}


class PartnerAccountService(Service):
    def account_type_for(self, money_model: str) -> str:
        return _ACCOUNT_FOR_MODEL.get(money_model, AccountType.RECEIVABLE.value)

    def get_or_create_account(
        self, partner_id: str, currency: str, account_type: str
    ) -> PartnerAccount:
        account = self.uow.partner_accounts.get_account(partner_id, currency, account_type)
        if account is None:
            account = PartnerAccount(
                id=new_ulid(),
                partner_id=partner_id,
                currency=currency.upper(),
                account_type=account_type,
                balance_minor=0,
            )
            self.uow.partner_accounts.add_account(account)
            self.uow.flush()
        return account

    def post(
        self,
        partner_id: str,
        currency: str,
        account_type: str,
        entry_type: str,
        amount_minor: int,
        *,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerLedgerEntry:
        """Append a signed ledger entry and update the account balance."""
        account = self.get_or_create_account(partner_id, currency, account_type)
        account.balance_minor += amount_minor
        self.uow.partner_accounts.update_account(account)
        entry = PartnerLedgerEntry(
            id=new_ulid(),
            account_id=account.id,
            partner_id=partner_id,
            entry_type=entry_type,
            amount_minor=amount_minor,
            balance_after_minor=account.balance_minor,
            currency=currency.upper(),
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_type=actor.type if actor else "system",
            actor_id=actor.id if actor else None,
        )
        self.uow.partner_accounts.add_entry(entry)
        self.uow.flush()
        self.audit.record(
            f"partner_ledger.{entry_type}",
            "partner",
            partner_id,
            actor,
            after=entry,
            reason=reason,
        )
        return entry

    def prefund(
        self,
        partner_id: str,
        amount_minor: int,
        *,
        currency: str | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerLedgerEntry:
        """Record money the partner has paid up front for a prepaid account."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        if amount_minor <= 0:
            raise ValidationError("prefund amount must be positive")
        return self.post(
            partner.id,
            currency or partner.currency,
            AccountType.PREPAID.value,
            PartnerLedgerEntryType.PAYMENT_RECEIVED.value,
            amount_minor,
            reason=reason or "prepayment",
            actor=actor,
        )

    def record_payment(
        self,
        partner_id: str,
        amount_minor: int,
        *,
        currency: str | None = None,
        method: str = "other",
        reference: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerPayment:
        """Record money received from a partner against their receivable."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        if amount_minor <= 0:
            raise ValidationError("payment amount must be positive")
        payment = PartnerPayment(
            id=new_ulid(),
            partner_id=partner.id,
            amount_minor=amount_minor,
            currency=(currency or partner.currency).upper(),
            method=method,
            reference=reference,
            received_at=utcnow(),
        )
        self.uow.partner_accounts.add_payment(payment)
        self.post(
            partner.id,
            payment.currency,
            AccountType.RECEIVABLE.value,
            PartnerLedgerEntryType.PAYMENT_RECEIVED.value,
            -amount_minor,
            reason="partner payment",
            reference_type="partner_payment",
            reference_id=payment.id,
            actor=actor,
        )
        return payment

    def balances(self, partner_id: str, currency: str | None = None) -> dict[str, int]:
        require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        result: dict[str, int] = {}
        for account in self.uow.partner_accounts.list_accounts(partner_id):
            if currency is not None and account.currency != currency.upper():
                continue
            result[account.account_type] = (
                result.get(account.account_type, 0) + account.balance_minor
            )
        return result

    def accounts(self, partner_id: str) -> list[PartnerAccount]:
        return self.uow.partner_accounts.list_accounts(partner_id)

    def entries(
        self,
        partner_id: str,
        *,
        currency: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[PartnerLedgerEntry]:
        return self.uow.partner_accounts.list_entries(
            partner_id, currency=currency, since=since, until=until
        )

    def generate_statement(
        self,
        partner_id: str,
        period_start: datetime,
        period_end: datetime,
        *,
        currency: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerStatement:
        """Summarize ledger activity for a settlement period."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        target_currency = (currency or partner.currency).upper()
        start = as_utc(period_start)
        end = as_utc(period_end)
        if end < start:
            raise ValidationError("period_end must not precede period_start")

        entries = self.uow.partner_accounts.list_entries(partner.id, currency=target_currency)
        opening = 0
        charges = 0
        payments = 0
        commission = 0
        closing = 0
        for entry in entries:
            moment = entry.created_at or start
            if moment < start:
                opening += entry.amount_minor
                continue
            if moment > end:
                continue
            if entry.entry_type == PartnerLedgerEntryType.CHARGE.value:
                charges += entry.amount_minor
            elif entry.entry_type == PartnerLedgerEntryType.PAYMENT_RECEIVED.value:
                payments += -entry.amount_minor
            elif entry.entry_type == PartnerLedgerEntryType.COMMISSION_EARNED.value:
                commission += -entry.amount_minor
            closing += entry.amount_minor

        statement = PartnerStatement(
            id=new_ulid(),
            partner_id=partner.id,
            currency=target_currency,
            period_start=start,
            period_end=end,
            opening_balance_minor=opening,
            charges_minor=charges,
            payments_minor=payments,
            commission_minor=commission,
            closing_balance_minor=opening + closing,
        )
        self.uow.partner_accounts.add_statement(statement)
        self.uow.flush()
        self.audit.record("partner_statement.create", "partner", partner.id, actor, after=statement)
        return statement

    def list_statements(self, partner_id: str) -> list[PartnerStatement]:
        return self.uow.partner_accounts.list_statements(partner_id)

    def create_invoice(
        self,
        partner_id: str,
        *,
        lines: list[dict[str, Any]] | None = None,
        currency: str | None = None,
        due_date: datetime | None = None,
        notes: str | None = None,
        finalize: bool = False,
        actor: Actor | None = None,
    ) -> PartnerInvoice:
        """Create an invoice billed to a partner at the agreed price."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        invoice = PartnerInvoice(
            id=new_ulid(),
            partner_id=partner.id,
            currency=(currency or partner.currency).upper(),
            due_date=due_date,
            notes=notes,
        )
        self.uow.partner_accounts.add_invoice(invoice)
        self.uow.flush()
        total = 0
        for entry in lines or []:
            quantity = int(entry.get("quantity", 1))
            unit = int(entry.get("unit_amount_minor", 0))
            if quantity < 1:
                raise ValidationError("invoice line quantity must be at least 1")
            if unit < 0:
                raise ValidationError("invoice line unit_amount_minor must be non-negative")
            line = PartnerInvoiceLine(
                id=new_ulid(),
                partner_invoice_id=invoice.id,
                description=str(entry.get("description", "item")),
                quantity=quantity,
                unit_amount_minor=unit,
                amount_minor=quantity * unit,
            )
            self.uow.partner_accounts.add_invoice_line(line)
            total += line.amount_minor
        invoice.subtotal_minor = total
        invoice.total_minor = total
        if finalize:
            invoice.status = InvoiceStatus.OPEN.value
            invoice.issue_date = utcnow()
        self.uow.partner_accounts.update_invoice(invoice)
        self.uow.flush()
        self.audit.record(
            "partner_invoice.create", "partner_invoice", invoice.id, actor, after=invoice
        )
        return invoice

    def list_invoices(self, partner_id: str) -> list[PartnerInvoice]:
        return self.uow.partner_accounts.list_invoices(partner_id)

    def record_invoice_payment(
        self,
        invoice_id: str,
        amount_minor: int,
        *,
        method: str = "other",
        reference: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerPayment:
        invoice = require(
            self.uow.partner_accounts.get_invoice(invoice_id), "partner_invoice", invoice_id
        )
        if amount_minor <= 0:
            raise ValidationError("payment amount must be positive")
        if invoice.status != InvoiceStatus.OPEN.value:
            raise ConflictError(
                f"cannot pay a {invoice.status!r} invoice; only open invoices are payable"
            )
        payment = PartnerPayment(
            id=new_ulid(),
            partner_id=invoice.partner_id,
            partner_invoice_id=invoice.id,
            amount_minor=amount_minor,
            currency=invoice.currency,
            method=method,
            reference=reference,
            received_at=utcnow(),
        )
        self.uow.partner_accounts.add_payment(payment)
        invoice.amount_paid_minor += amount_minor
        if invoice.amount_paid_minor >= invoice.total_minor:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_at = utcnow()
        self.uow.partner_accounts.update_invoice(invoice)
        self.post(
            invoice.partner_id,
            invoice.currency,
            AccountType.RECEIVABLE.value,
            PartnerLedgerEntryType.PAYMENT_RECEIVED.value,
            -amount_minor,
            reason="partner invoice payment",
            reference_type="partner_invoice",
            reference_id=invoice.id,
            actor=actor,
        )
        self.uow.flush()
        self.audit.record(
            "partner_invoice.payment", "partner_invoice", invoice.id, actor, after=payment
        )
        return payment

    def create_payout(
        self,
        partner_id: str,
        *,
        lines: list[dict[str, Any]] | None = None,
        currency: str | None = None,
        reference: str | None = None,
        actor: Actor | None = None,
    ) -> PartnerPayout:
        """Create a draft payout (e.g. commission) to a partner."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        payout = PartnerPayout(
            id=new_ulid(),
            partner_id=partner.id,
            currency=(currency or partner.currency).upper(),
            reference=reference,
        )
        self.uow.partner_accounts.add_payout(payout)
        self.uow.flush()
        total = 0
        for entry in lines or []:
            amount = int(entry.get("amount_minor", 0))
            if amount < 0:
                raise ValidationError("payout line amount_minor must be non-negative")
            line = PartnerPayoutLine(
                id=new_ulid(),
                payout_id=payout.id,
                description=str(entry.get("description", "payout")),
                amount_minor=amount,
            )
            self.uow.partner_accounts.add_payout_line(line)
            total += amount
        payout.total_minor = total
        self.uow.partner_accounts.update_payout(payout)
        self.uow.flush()
        self.audit.record("partner_payout.create", "partner_payout", payout.id, actor, after=payout)
        return payout

    def pay_payout(
        self, payout_id: str, *, reference: str | None = None, actor: Actor | None = None
    ) -> PartnerPayout:
        payout = require(
            self.uow.partner_accounts.get_payout(payout_id), "partner_payout", payout_id
        )
        if payout.status == PayoutStatus.PAID.value:
            raise ConflictError("payout already paid")
        payout.status = PayoutStatus.PAID.value
        payout.paid_at = utcnow()
        payout.reference = reference or payout.reference
        self.uow.partner_accounts.update_payout(payout)
        self.post(
            payout.partner_id,
            payout.currency,
            AccountType.PAYABLE.value,
            PartnerLedgerEntryType.PAYOUT.value,
            -payout.total_minor,
            reason="payout to partner",
            reference_type="partner_payout",
            reference_id=payout.id,
            actor=actor,
        )
        self.audit.record("partner_payout.paid", "partner_payout", payout.id, actor, after=payout)
        return payout
