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


@dataclass(slots=True)
class Partner:
    id: str
    name: str
    type: str = "agent"
    external_id: str | None = None
    email: str | None = None
    phone: str | None = None
    currency: str = "USD"
    parent_partner_id: str | None = None
    status: str = "active"
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class CommissionRule:
    id: str
    basis: str = "flat"
    rate_bps: int = 0
    tiers: list[dict[str, Any]] | None = None
    levels: list[dict[str, Any]] | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerAgreement:
    id: str
    partner_id: str
    money_model: str = "consignment"
    currency: str = "USD"
    discount_bps: int = 0
    plan_id: str | None = None
    commission_rule_id: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    status: str = "active"
    created_at: datetime | None = None


@dataclass(slots=True)
class LicenseAllocation:
    id: str
    partner_id: str
    plan_version_id: str
    quantity_allocated: int
    quantity_issued: int = 0
    agreement_id: str | None = None
    parent_allocation_id: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    status: str = "active"
    created_at: datetime | None = None


@dataclass(slots=True)
class License:
    id: str
    allocation_id: str
    partner_id: str
    plan_version_id: str
    status: str = "issued"
    customer_id: str | None = None
    subscription_id: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerAccount:
    id: str
    partner_id: str
    currency: str
    account_type: str
    balance_minor: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class PartnerLedgerEntry:
    id: str
    account_id: str
    partner_id: str
    entry_type: str
    amount_minor: int
    balance_after_minor: int = 0
    currency: str = "USD"
    reason: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    actor_type: str = "system"
    actor_id: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerInvoice:
    id: str
    partner_id: str
    status: str = "draft"
    currency: str = "USD"
    subtotal_minor: int = 0
    total_minor: int = 0
    amount_paid_minor: int = 0
    issue_date: datetime | None = None
    due_date: datetime | None = None
    paid_at: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class PartnerInvoiceLine:
    id: str
    partner_invoice_id: str
    description: str
    quantity: int = 1
    unit_amount_minor: int = 0
    amount_minor: int = 0
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerPayment:
    id: str
    partner_id: str
    amount_minor: int
    currency: str = "USD"
    partner_invoice_id: str | None = None
    method: str = "other"
    reference: str | None = None
    received_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerPayout:
    id: str
    partner_id: str
    status: str = "draft"
    currency: str = "USD"
    total_minor: int = 0
    reference: str | None = None
    paid_at: datetime | None = None
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerPayoutLine:
    id: str
    payout_id: str
    description: str
    amount_minor: int = 0
    created_at: datetime | None = None


@dataclass(slots=True)
class PartnerStatement:
    id: str
    partner_id: str
    currency: str
    period_start: datetime
    period_end: datetime
    opening_balance_minor: int = 0
    charges_minor: int = 0
    payments_minor: int = 0
    commission_minor: int = 0
    closing_balance_minor: int = 0
    status: str = "draft"
    created_at: datetime | None = None
