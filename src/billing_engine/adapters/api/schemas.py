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
