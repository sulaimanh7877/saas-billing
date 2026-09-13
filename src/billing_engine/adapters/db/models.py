"""SQLAlchemy 2.0 models for the core billing schema.

Table names are logical; :func:`billing_engine.adapters.db.base.configure_metadata`
applies the configured prefix to every table and index before DDL or use.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from billing_engine.adapters.db.base import Base
from billing_engine.domain.value_objects import new_ulid, utcnow


class IdMixin:
    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    name: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    partner_id: Mapped[str | None] = mapped_column(String(26), index=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Product(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "products"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Plan(IdMixin, TimestampMixin, Base):
    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlanVersion(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "plan_versions"

    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(32), default="catalog", nullable=False)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Price(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "prices"

    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("plan_versions.id"), index=True, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    interval: Mapped[str] = mapped_column(String(16), default="month", nullable=False)


class Feature(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "features"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    value_type: Mapped[str] = mapped_column(String(16), default="boolean", nullable=False)
    default_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reset_period: Mapped[str | None] = mapped_column(String(16))


class PlanEntitlement(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "plan_entitlements"

    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("plan_versions.id"), index=True, nullable=False
    )
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id"), index=True, nullable=False)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer)


class Subscription(IdMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("plan_versions.id"), index=True, nullable=False
    )
    price_id: Mapped[str | None] = mapped_column(ForeignKey("prices.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="trialing", nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_method: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    partner_id: Mapped[str | None] = mapped_column(String(26), index=True)


class EntitlementOverride(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "entitlement_overrides"

    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id"), index=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    limit_value: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubscriptionAdjustment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "subscription_adjustments"

    subscription_id: Mapped[str] = mapped_column(
        ForeignKey("subscriptions.id"), index=True, nullable=False
    )
    adjustment_type: Mapped[str] = mapped_column(String(32), nullable=False)
    delta_days: Mapped[int | None] = mapped_column(Integer)
    previous_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    new_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(String(16), default="system", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_paid_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class InvoiceLine(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Payment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "payments"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="other", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditEntry(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "credit_ledger"

    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(26))
    balance_after_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Event(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "events"

    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class AuditLog(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    entity_id: Mapped[str] = mapped_column(String(26), index=True, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), default="system", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="embedded", nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45))


class MigrationRecord(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "migrations"

    version: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))


class Partner(IdMixin, TimestampMixin, Base):
    __tablename__ = "partners"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), default="agent", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    parent_partner_id: Mapped[str | None] = mapped_column(ForeignKey("partners.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class CommissionRule(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "commission_rules"

    basis: Mapped[str] = mapped_column(String(16), default="flat", nullable=False)
    rate_bps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tiers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    levels: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)


class PartnerAgreement(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_agreements"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    money_model: Mapped[str] = mapped_column(String(32), default="consignment", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    discount_bps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("plans.id"), index=True)
    commission_rule_id: Mapped[str | None] = mapped_column(ForeignKey("commission_rules.id"))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)


class LicenseAllocation(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "license_allocations"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("plan_versions.id"), index=True, nullable=False
    )
    quantity_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_issued: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agreement_id: Mapped[str | None] = mapped_column(ForeignKey("partner_agreements.id"))
    parent_allocation_id: Mapped[str | None] = mapped_column(
        ForeignKey("license_allocations.id"), index=True
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)


class License(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "licenses"

    allocation_id: Mapped[str] = mapped_column(
        ForeignKey("license_allocations.id"), index=True, nullable=False
    )
    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    plan_version_id: Mapped[str] = mapped_column(
        ForeignKey("plan_versions.id"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), default="issued", nullable=False)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerAccount(IdMixin, TimestampMixin, Base):
    __tablename__ = "partner_accounts"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    balance_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PartnerLedgerEntry(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_ledger"

    account_id: Mapped[str] = mapped_column(
        ForeignKey("partner_accounts.id"), index=True, nullable=False
    )
    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(32), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reference_id: Mapped[str | None] = mapped_column(String(26))
    actor_type: Mapped[str] = mapped_column(String(16), default="system", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))


class PartnerInvoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "partner_invoices"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_paid_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PartnerInvoiceLine(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_invoice_lines"

    partner_invoice_id: Mapped[str] = mapped_column(
        ForeignKey("partner_invoices.id"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PartnerPayment(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_payments"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    partner_invoice_id: Mapped[str | None] = mapped_column(
        ForeignKey("partner_invoices.id"), index=True
    )
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    method: Mapped[str] = mapped_column(String(16), default="other", nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerPayout(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_payouts"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    total_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference: Mapped[str | None] = mapped_column(String(255))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PartnerPayoutLine(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_payout_lines"

    payout_id: Mapped[str] = mapped_column(
        ForeignKey("partner_payouts.id"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PartnerStatement(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "partner_statements"

    partner_id: Mapped[str] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opening_balance_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    charges_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payments_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    commission_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    closing_balance_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
