"""Customer management."""

from __future__ import annotations

from typing import Any

from billing_engine.domain.entities import Customer
from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor


class CustomerService(Service):
    def create(
        self,
        external_id: str,
        *,
        email: str | None = None,
        name: str | None = None,
        currency: str | None = None,
        attributes: dict[str, Any] | None = None,
        partner_id: str | None = None,
        actor: Actor | None = None,
    ) -> Customer:
        """Create a customer linked to the host app's identifier."""
        cleaned = external_id.strip() if isinstance(external_id, str) else ""
        if not cleaned:
            raise ValidationError("external_id is required")
        if self.uow.customers.get_by_external_id(cleaned) is not None:
            raise ConflictError(f"customer with external_id {cleaned!r} already exists")
        if partner_id is not None:
            require(self.uow.partners.get_partner(partner_id), "partner", partner_id)

        customer = Customer(
            id=new_ulid(),
            external_id=cleaned,
            email=email,
            name=name,
            currency=(currency or self.default_currency).upper(),
            partner_id=partner_id,
            attributes=attributes or {},
        )
        self.uow.customers.add(customer)
        self.uow.flush()
        self.audit.record("customer.create", "customer", customer.id, actor, after=customer)
        self.audit.emit("customer.created", {"customer_id": customer.id})
        return customer

    def get(self, customer_id: str) -> Customer:
        return require(self.uow.customers.get(customer_id), "customer", customer_id)

    def get_by_external_id(self, external_id: str) -> Customer | None:
        return self.uow.customers.get_by_external_id(external_id)

    def update(
        self,
        customer_id: str,
        *,
        email: str | None = None,
        name: str | None = None,
        attributes: dict[str, Any] | None = None,
        actor: Actor | None = None,
    ) -> Customer:
        """Update mutable customer fields."""
        before = self.get(customer_id)
        after = Customer(
            id=before.id,
            external_id=before.external_id,
            email=email if email is not None else before.email,
            name=name if name is not None else before.name,
            currency=before.currency,
            partner_id=before.partner_id,
            attributes=attributes if attributes is not None else before.attributes,
        )
        self.uow.customers.update(after)
        self.uow.flush()
        self.audit.record("customer.update", "customer", customer_id, actor, before, after)
        return after

    def list(self, limit: int = 100, offset: int = 0) -> list[Customer]:
        return self.uow.customers.list(limit=limit, offset=offset)
