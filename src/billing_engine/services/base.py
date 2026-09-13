"""Shared base class for services."""

from __future__ import annotations

from typing import TypeVar

from billing_engine.domain.errors import NotFoundError
from billing_engine.domain.repositories import Repositories
from billing_engine.services.context import AuditService

T = TypeVar("T")


class Service:
    """Common dependencies for service implementations."""

    def __init__(
        self,
        uow: Repositories,
        *,
        default_currency: str = "USD",
        grace_period_days: int = 0,
    ) -> None:
        self.uow = uow
        self.default_currency = default_currency
        self.grace_period_days = grace_period_days
        self.audit = AuditService(uow)


def require(value: T | None, kind: str, identifier: str) -> T:
    """Return ``value`` or raise :class:`NotFoundError` naming the entity."""
    if value is None:
        raise NotFoundError(f"{kind} {identifier!r} was not found")
    return value
