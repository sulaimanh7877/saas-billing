"""Typed, framework-free error hierarchy for the billing engine.

Adapters translate these into HTTP responses or CLI output; callers should
never see raw database or framework errors.
"""

from __future__ import annotations


class BillingError(Exception):
    """Base class for all errors raised by the billing engine."""


class ConfigurationError(BillingError):
    """Raised when ``EngineConfig`` or engine wiring is invalid."""


class ValidationError(BillingError):
    """Raised when input fails a business validation rule."""


class NotFoundError(BillingError):
    """Raised when a referenced entity does not exist."""


class ConflictError(BillingError):
    """Raised when a change conflicts with current state."""


class EntitlementError(BillingError):
    """Raised when a feature or limit check fails."""


class AllocationExhaustedError(BillingError):
    """Raised when a partner license allocation has no capacity left."""
