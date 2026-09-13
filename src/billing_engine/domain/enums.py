"""Enumerations shared across the domain, services, and adapters."""

from __future__ import annotations

from enum import StrEnum


class BillingInterval(StrEnum):
    """How often a price recurs."""

    MONTH = "month"
    YEAR = "year"
    ONE_TIME = "one_time"


class PlanScope(StrEnum):
    """Whether a plan version lives in the catalog or is customer-specific."""

    CATALOG = "catalog"
    CUSTOMER_CUSTOM = "customer_custom"


class SubscriptionStatus(StrEnum):
    """Lifecycle states for a subscription."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELED = "canceled"
    EXPIRED = "expired"


class AdjustmentType(StrEnum):
    """Kinds of manual subscription adjustments."""

    EXTEND = "extend"
    SHORTEN = "shorten"
    TRIAL_EXTEND = "trial_extend"
    PAUSE = "pause"
    RESUME = "resume"
    SET_PERIOD_END = "set_period_end"
    PLAN_CHANGE = "plan_change"


class EntitlementValueType(StrEnum):
    """How an entitlement value should be interpreted."""

    BOOLEAN = "boolean"
    LIMIT = "limit"
    METER = "meter"


class OverrideScope(StrEnum):
    """What an entitlement override applies to."""

    CUSTOMER = "customer"
    SUBSCRIPTION = "subscription"


class InvoiceStatus(StrEnum):
    """Invoice lifecycle states."""

    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentMethod(StrEnum):
    """Manually recorded payment methods."""

    CASH = "cash"
    TRANSFER = "transfer"
    OTHER = "other"


class CreditEntryType(StrEnum):
    """Customer credit ledger entry kinds."""

    GRANT = "grant"
    CONSUME = "consume"
    REFUND = "refund"


class ActorType(StrEnum):
    """Who performed an audit-logged action."""

    USER = "user"
    API_KEY = "api_key"
    SYSTEM = "system"


class Source(StrEnum):
    """Where a change originated."""

    EMBEDDED = "embedded"
    REST = "rest"
    WEBHOOK = "webhook"
    JOB = "job"


class EventStatus(StrEnum):
    """Outbox event delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
