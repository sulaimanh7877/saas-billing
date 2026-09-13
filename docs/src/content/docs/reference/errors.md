---
title: Errors
description: The engine's typed error hierarchy, when each error is raised, and how adapters map them to HTTP responses.
---

The engine raises a small, typed hierarchy. Adapters translate these into HTTP
responses or CLI output, so callers never see raw database or framework errors.

```
BillingError
├── ConfigurationError
├── ValidationError
├── NotFoundError
├── ConflictError
├── EntitlementError
└── AllocationExhaustedError
```

All are importable from the top-level package:

```python
from billing_engine import (
    BillingError,
    ConfigurationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    EntitlementError,
    AllocationExhaustedError,
)
```

## When each is raised

| Error | Raised when | Examples |
|---|---|---|
| `ConfigurationError` | Engine wiring is invalid | Missing `table_prefix`; both or neither of `dsn`/`engine`; bad currency; a second prefix in one process |
| `ValidationError` | Input breaks a business rule | Empty `external_id`; `quantity < 1`; negative or non-integer money; unknown enum value |
| `NotFoundError` | A referenced entity does not exist | Unknown customer, plan version, invoice, allocation, feature |
| `ConflictError` | The change conflicts with current state | Subscribing to an unpublished version; paying a non-open invoice; overpaying; insufficient credit; inactive allocation |
| `EntitlementError` | A feature or limit check fails | Explicit entitlement denial at the adapter boundary |
| `AllocationExhaustedError` | A partner allocation has no capacity | Issuing the 501st license from a 500-unit allocation |

## Handling in embedded code

```python
from billing_engine import BillingError, ConflictError

try:
    with billing.transaction() as services:
        services.invoices.record_payment(invoice.id, amount)
except ConflictError as exc:
    # Business-state problem the caller can act on.
    show_message(str(exc))
except BillingError as exc:
    # Any other engine error.
    log.error("billing failed: %s", exc)
```

Because the transaction rolls back on exception, a failure leaves no partial
state.

## HTTP mapping (REST adapter)

| Error | Status |
|---|---|
| `ValidationError` | `400 Bad Request` |
| `NotFoundError` | `404 Not Found` |
| `EntitlementError` | `403 Forbidden` |
| `ConflictError` | `409 Conflict` |
| `AllocationExhaustedError` | `409 Conflict` |
| `ConfigurationError` | `500 Internal Server Error` |

Responses use `{"detail": "<message>"}`.

## Next

- [Configuration](/saas-billing/reference/configuration/)
- [REST endpoints](/saas-billing/reference/rest-api/)
