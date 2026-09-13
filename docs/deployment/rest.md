# Standalone & REST

Run the engine as its own HTTP service and talk to it over REST. Useful when
your app is not Python, or you want billing isolated behind a network boundary.

## Configure with environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `BILLING_DSN` | ✅ | — | SQLAlchemy database URL |
| `BILLING_TABLE_PREFIX` | ✅ | — | Required table prefix |
| `BILLING_API_KEY` | — | none | If set, all requests must present it |
| `BILLING_DEFAULT_CURRENCY` | — | `USD` | Default ISO 4217 currency |
| `BILLING_TRIAL_DAYS` | — | `0` | Fallback trial length |
| `BILLING_GRACE_PERIOD_DAYS` | — | `0` | Access window after a period ends |

The server runs migrations on startup.

## Run

```bash
export BILLING_DSN="postgresql+psycopg://user:pass@localhost/mysaas"
export BILLING_TABLE_PREFIX="acme_"
export BILLING_API_KEY="a-long-random-secret"

uvicorn billing_engine.server:create_server --factory --host 0.0.0.0 --port 8000
```

Interactive API docs are served at `/docs` (OpenAPI at `/openapi.json`).

## Build your own app

Use `create_app()` to control options or mount the router:

```python
from billing_engine import BillingEngine, EngineConfig
from billing_engine.adapters.api.app import create_app

engine = BillingEngine(EngineConfig(dsn="...", table_prefix="acme_"))
engine.migrate()

app = create_app(engine, api_key="a-long-random-secret", title="Acme Billing")
```

## Authentication

When `api_key` is set, every request must send it:

```bash
curl -H "X-API-Key: a-long-random-secret" \
     -H "Content-Type: application/json" \
     -d '{"external_id": "user-42", "email": "ada@example.com"}' \
     http://localhost:8000/customers
```

Comparison is constant-time. The REST adapter derives the audit `actor` type as
`api_key` (or `system` when no key is configured) and reads an optional
`X-Actor-Id` header to attribute the action to a specific operator.

## A typical flow

```bash
BASE=http://localhost:8000
KEY="a-long-random-secret"

# 1. Create a feature, plan, and version
curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"key":"reports","name":"Reports"}' $BASE/features

curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"key":"pro","name":"Pro"}' $BASE/plans

curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
        "prices": [{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
        "trial_days": 14,
        "entitlements": [{"feature_key": "reports", "limit_value": 1}]
      }' \
  "$BASE/plans/<plan_id>/versions"

# 2. Create a customer and subscription
curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"external_id":"user-42","email":"ada@example.com"}' $BASE/customers

curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"customer_id":"<customer_id>","plan_version_id":"<version_id>"}' \
  $BASE/subscriptions

# 3. Check an entitlement
curl -s -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"customer_id":"<customer_id>","feature_key":"reports"}' \
  $BASE/entitlements/check
```

See the full [REST endpoints reference](../reference/rest-api.md).

## Errors

Engine errors map to HTTP status codes with a `{"detail": "..."}` body:

| Error | Status |
|---|---|
| `ValidationError` | 400 |
| `EntitlementError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError`, `AllocationExhaustedError` | 409 |
| `ConfigurationError` | 500 |

## Keep it fast

The REST adapter opens one transaction per request and commits on success, so
audit and outbox writes stay atomic with the change. Front it with your usual
proxy, timeout, and rate-limit layers.

## Next

- [Docker](docker.md)
- [REST endpoints](../reference/rest-api.md)
