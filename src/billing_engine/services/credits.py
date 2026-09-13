"""Customer credit ledger."""

from __future__ import annotations

from billing_engine.domain.entities import CreditEntry
from billing_engine.domain.enums import CreditEntryType
from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor


class CreditService(Service):
    def _record(
        self,
        customer_id: str,
        entry_type: str,
        amount_minor: int,
        *,
        currency: str,
        reason: str | None,
        reference_type: str | None,
        reference_id: str | None,
        actor: Actor | None,
    ) -> CreditEntry:
        previous = self.uow.credits.balance(customer_id, currency)
        entry = CreditEntry(
            id=new_ulid(),
            customer_id=customer_id,
            entry_type=entry_type,
            amount_minor=amount_minor,
            currency=currency,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            balance_after_minor=previous + amount_minor,
        )
        self.uow.credits.add_entry(entry)
        self.uow.flush()
        self.audit.record(
            f"credit.{entry_type}", "customer", customer_id, actor, after=entry, reason=reason
        )
        return entry

    def grant(
        self,
        customer_id: str,
        amount_minor: int,
        *,
        currency: str | None = None,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        actor: Actor | None = None,
    ) -> CreditEntry:
        """Add credit to a customer's balance."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        if amount_minor <= 0:
            raise ValidationError("credit amount must be positive")
        return self._record(
            customer.id,
            CreditEntryType.GRANT.value,
            amount_minor,
            currency=(currency or customer.currency).upper(),
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            actor=actor,
        )

    def refund(
        self,
        customer_id: str,
        amount_minor: int,
        *,
        currency: str | None = None,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        actor: Actor | None = None,
    ) -> CreditEntry:
        """Return credit to a customer's balance."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        if amount_minor <= 0:
            raise ValidationError("refund amount must be positive")
        return self._record(
            customer.id,
            CreditEntryType.REFUND.value,
            amount_minor,
            currency=(currency or customer.currency).upper(),
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            actor=actor,
        )

    def consume(
        self,
        customer_id: str,
        amount_minor: int,
        *,
        reason: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        actor: Actor | None = None,
    ) -> CreditEntry:
        """Spend credit from a customer's balance."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        if amount_minor <= 0:
            raise ValidationError("consume amount must be positive")
        if self.uow.credits.balance_for_update(customer.id, customer.currency) < amount_minor:
            raise ConflictError("insufficient credit balance")
        return self._record(
            customer.id,
            CreditEntryType.CONSUME.value,
            -amount_minor,
            currency=customer.currency,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            actor=actor,
        )

    def balance(self, customer_id: str) -> int:
        """Return a customer's current credit balance in minor units."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        return self.uow.credits.balance(customer_id, customer.currency)

    def list_entries(self, customer_id: str) -> list[CreditEntry]:
        return self.uow.credits.list_entries(customer_id)
