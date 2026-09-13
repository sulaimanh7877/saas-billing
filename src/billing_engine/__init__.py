"""billing_engine — self-hostable billing, subscriptions, and entitlements.

The public entry point is :class:`billing_engine.config.EngineConfig`; the
``BillingEngine`` facade is introduced in a later milestone.
"""

from billing_engine.config import EngineConfig
from billing_engine.domain.errors import (
    AllocationExhaustedError,
    BillingError,
    ConfigurationError,
    ConflictError,
    EntitlementError,
    NotFoundError,
    ValidationError,
)
from billing_engine.naming import PrefixNamer

__version__ = "0.1.0.dev0"

__all__ = [
    "AllocationExhaustedError",
    "BillingError",
    "ConfigurationError",
    "ConflictError",
    "EngineConfig",
    "EntitlementError",
    "NotFoundError",
    "PrefixNamer",
    "ValidationError",
    "__version__",
]
