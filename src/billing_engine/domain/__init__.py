"""Pure domain layer: entities, value objects, lifecycle, and business rules.

Nothing in this package may import SQLAlchemy, FastAPI, or perform I/O.
"""

from billing_engine.domain.errors import (
    AllocationExhaustedError,
    BillingError,
    ConfigurationError,
    ConflictError,
    EntitlementError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "AllocationExhaustedError",
    "BillingError",
    "ConfigurationError",
    "ConflictError",
    "EntitlementError",
    "NotFoundError",
    "ValidationError",
]
