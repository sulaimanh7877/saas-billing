"""Pydantic request schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    external_id: str
    email: str | None = None
    name: str | None = None
    currency: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    partner_id: str | None = None


class CustomerUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    attributes: dict[str, Any] | None = None


class FeatureCreate(BaseModel):
    key: str
    name: str | None = None
    value_type: str = "boolean"
    default_value: int = 0
    reset_period: str | None = None


class PlanCreate(BaseModel):
    key: str
    name: str | None = None
    product_id: str | None = None


class PriceIn(BaseModel):
    amount_minor: int
    currency: str = "USD"
    interval: str = "month"


class EntitlementIn(BaseModel):
    feature_key: str
    value: int = 1
    limit_value: int | None = None


class PlanVersionCreate(BaseModel):
    name: str | None = None
    prices: list[PriceIn]
    trial_days: int = 0
    entitlements: list[EntitlementIn] = Field(default_factory=list)


class CustomPlanCreate(BaseModel):
    customer_id: str
    name: str
    prices: list[PriceIn]
    trial_days: int = 0
    entitlements: list[EntitlementIn] = Field(default_factory=list)


class EntitlementsUpdate(BaseModel):
    entitlements: list[EntitlementIn]


class SubscriptionCreate(BaseModel):
    customer_id: str
    plan_version_id: str
    price_id: str | None = None
    currency: str | None = None
    trial_days: int | None = None
    quantity: int = 1
    start_at: datetime | None = None


class ExtendRequest(BaseModel):
    days: int | None = None
    months: int | None = None
    until: datetime | None = None
    reason: str | None = None


class ExtendTrialRequest(BaseModel):
    days: int
    reason: str | None = None


class PauseRequest(BaseModel):
    until: datetime | None = None
    reason: str | None = None


class ReasonRequest(BaseModel):
    reason: str | None = None


class CancelRequest(BaseModel):
    at_period_end: bool = True
    reason: str | None = None


class ChangePlanRequest(BaseModel):
    plan_version_id: str
    price_id: str | None = None
    currency: str | None = None
    reason: str | None = None


class OverrideRequest(BaseModel):
    feature_key: str
    value: int = 1
    limit_value: int | None = None
    expires_at: datetime | None = None
    reason: str | None = None


class CheckRequest(BaseModel):
    customer_id: str
    feature_key: str


class InvoiceLineIn(BaseModel):
    description: str
    quantity: int = 1
    unit_amount_minor: int


class InvoiceCreate(BaseModel):
    customer_id: str
    lines: list[InvoiceLineIn] = Field(default_factory=list)
    currency: str | None = None
    due_date: datetime | None = None
    subscription_id: str | None = None
    notes: str | None = None
    finalize: bool = False


class PaymentCreate(BaseModel):
    amount_minor: int
    method: str = "other"
    reference: str | None = None


class CreditCreate(BaseModel):
    amount_minor: int
    reason: str | None = None


class PartnerCreate(BaseModel):
    name: str
    type: str = "agent"
    external_id: str | None = None
    email: str | None = None
    phone: str | None = None
    currency: str | None = None
    parent_partner_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class CommissionRuleCreate(BaseModel):
    basis: str = "flat"
    rate_bps: int = 0
    tiers: list[dict[str, Any]] | None = None
    levels: list[dict[str, Any]] | None = None


class AgreementCreate(BaseModel):
    money_model: str = "consignment"
    currency: str | None = None
    discount_bps: int = 0
    plan_id: str | None = None
    commission_rule_id: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class AllocationCreate(BaseModel):
    plan_version_id: str
    quantity: int
    agreement_id: str | None = None
    parent_allocation_id: str | None = None


class LicenseIssue(BaseModel):
    customer_id: str | None = None
    external_id: str | None = None
    email: str | None = None
    name: str | None = None


class PrefundRequest(BaseModel):
    amount_minor: int
    currency: str | None = None
    reason: str | None = None


class PartnerPaymentRequest(BaseModel):
    amount_minor: int
    currency: str | None = None
    method: str = "other"
    reference: str | None = None


class PartnerInvoiceCreate(BaseModel):
    lines: list[InvoiceLineIn] = Field(default_factory=list)
    currency: str | None = None
    due_date: datetime | None = None
    notes: str | None = None
    finalize: bool = False


class PayoutCreate(BaseModel):
    lines: list[dict[str, Any]] = Field(default_factory=list)
    currency: str | None = None
    reference: str | None = None


class StatementCreate(BaseModel):
    period_start: datetime
    period_end: datetime
    currency: str | None = None
