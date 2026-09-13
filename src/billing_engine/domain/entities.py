"""Framework-free domain entities.

Field names mirror the persistence attributes so adapters can map models to
entities generically. Enum-typed columns are held as plain strings, which is
compatible with the ``StrEnum`` members defined in :mod:`.enums`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Customer:
    id: str
    external_id: str
    email: str | None = None
    name: str | None = None
    currency: str = "USD"
    partner_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class Product:
    id: str
    key: str
    name: str | None = None
    is_active: bool = True
    created_at: datetime | None = None


@dataclass(slots=True)
class Plan:
    id: str
    key: str
    name: str | None = None
    product_id: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class PlanVersion:
    id: str
    plan_id: str
    version: int = 1
    name: str | None = None
    scope: str = "catalog"
    customer_id: str | None = None
    trial_days: int = 0
    is_published: bool = True
    created_at: datetime | None = None


@dataclass(slots=True)
class Price:
    id: str
    plan_version_id: str
    currency: str = "USD"
    amount_minor: int = 0
    interval: str = "month"
    created_at: datetime | None = None


@dataclass(slots=True)
class Feature:
    id: str
    key: str
    name: str | None = None
    value_type: str = "boolean"
    default_value: int = 0
    reset_period: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PlanEntitlement:
    id: str
    plan_version_id: str
    feature_id: str
    value: int = 0
    limit_value: int | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class EntitlementOverride:
    id: str
    scope: str
    feature_id: str
    customer_id: str | None = None
    subscription_id: str | None = None
    value: int = 0
    limit_value: int | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class Subscription:
    id: str
    customer_id: str
    plan_version_id: str
    price_id: str | None = None
    status: str = "trialing"
    quantity: int = 1
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_end: datetime | None = None
    cancel_at: datetime | None = None
    canceled_at: datetime | None = None
    paused_until: datetime | None = None
    grace_until: datetime | None = None
    collection_method: str = "manual"
    partner_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SubscriptionAdjustment:
    id: str
    subscription_id: str
    adjustment_type: str
    delta_days: int | None = None
    previous_period_end: datetime | None = None
    new_period_end: datetime | None = None
    reason: str | None = None
    actor_type: str = "system"
    actor_id: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class Invoice:
    id: str
    customer_id: str
    subscription_id: str | None = None
    status: str = "draft"
    currency: str = "USD"
    subtotal_minor: int = 0
    total_minor: int = 0
    amount_paid_minor: int = 0
    issue_date: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    voided_at: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class InvoiceLine:
    id: str
    invoice_id: str
    description: str
    quantity: int = 1
    unit_amount_minor: int = 0
    amount_minor: int = 0
    created_at: datetime | None = None


@dataclass(slots=True)
class Payment:
    id: str
    customer_id: str
    invoice_id: str | None = None
    amount_minor: int = 0
    currency: str = "USD"
    method: str = "other"
    reference: str | None = None
    received_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class CreditEntry:
    id: str
    customer_id: str
    entry_type: str
    amount_minor: int = 0
    currency: str = "USD"
    reason: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    balance_after_minor: int = 0
    created_at: datetime | None = None


@dataclass(slots=True)
class Event:
    id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    attempts: int = 0
    available_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class AuditLog:
    id: str
    action: str
    entity_type: str
    entity_id: str
    actor_type: str = "system"
    actor_id: str | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    source: str = "embedded"
    ip: str | None = None
    created_at: datetime | None = None
