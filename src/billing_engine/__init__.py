"""billing_engine — self-hostable billing, subscriptions, and entitlements.

The public entry point is :class:`billing_engine.config.EngineConfig`; the
``BillingEngine`` facade is introduced in a later milestone.
"""

from billing_engine.config import EngineConfig
from billing_engine.domain.enums import (
    BillingInterval,
    InvoiceStatus,
    PlanScope,
    SubscriptionStatus,
)
from billing_engine.domain.errors import (
    AllocationExhaustedError,
    BillingError,
    ConfigurationError,
    ConflictError,
    EntitlementError,
    NotFoundError,
    ValidationError,
)
from billing_engine.domain.value_objects import Money, new_ulid
from billing_engine.naming import PrefixNamer
from billing_engine.sdk import BillingEngine

__version__ = "0.1.0"

__all__ = [
    "AllocationExhaustedError",
    "BillingEngine",
    "BillingError",
    "BillingInterval",
    "ConfigurationError",
    "ConflictError",
    "EngineConfig",
    "EntitlementError",
    "InvoiceStatus",
    "Money",
    "NotFoundError",
    "PlanScope",
    "PrefixNamer",
    "SubscriptionStatus",
    "ValidationError",
    "__version__",
    "new_ulid",
]
