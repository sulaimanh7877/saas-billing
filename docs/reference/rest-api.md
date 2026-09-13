# REST endpoints

The full HTTP surface. When an API key is configured, every request must send
`X-API-Key`. Errors use `{"detail": "..."}` with the status codes in
[Errors](errors.md).

## Conventions

- **Money** is always integer minor units plus an ISO currency.
- **Timestamps** are ISO 8601 UTC.
- List endpoints accept `limit` (1–500, default 100) and `offset` (default 0).

## Customers

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/customers` | Create a customer (`external_id` required) |
| `GET` | `/customers` | List customers |
| `GET` | `/customers/{customer_id}` | Get one customer |
| `PATCH` | `/customers/{customer_id}` | Update `email`, `name`, `attributes` |

```json
POST /customers
{"external_id": "user-42", "email": "ada@example.com", "currency": "USD",
 "attributes": {"plan_tier": "self-serve"}}
```

## Catalog

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/features` | Create a feature |
| `GET` | `/features` | List features |
| `POST` | `/plans` | Create a plan |
| `GET` | `/plans` | List plans |
| `POST` | `/plans/{plan_id}/versions` | Create a plan version (prices + entitlements) |
| `GET` | `/plans/{plan_id}/versions` | List a plan's versions |
| `POST` | `/custom-plans` | Create a per-customer custom plan version |
| `GET` | `/plan-versions/{version_id}/prices` | List prices |
| `POST` | `/plan-versions/{version_id}/entitlements` | Replace entitlements |

```json
POST /plans/{plan_id}/versions
{
  "prices": [{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
  "trial_days": 14,
  "entitlements": [{"feature_key": "reports", "limit_value": 1}]
}
```

## Subscriptions

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/subscriptions` | Create a subscription |
| `GET` | `/subscriptions/{subscription_id}` | Get one |
| `GET` | `/customers/{customer_id}/subscriptions` | List for a customer |
| `POST` | `/subscriptions/{id}/extend` | Extend by days/months/until |
| `POST` | `/subscriptions/{id}/extend-trial` | Push out a trial |
| `POST` | `/subscriptions/{id}/pause` | Pause (optionally `until`) |
| `POST` | `/subscriptions/{id}/resume` | Resume |
| `POST` | `/subscriptions/{id}/cancel` | Cancel (`at_period_end`, default true) |
| `POST` | `/subscriptions/{id}/reactivate` | Reactivate |
| `POST` | `/subscriptions/{id}/change-plan` | Switch plan version |
| `POST` | `/subscriptions/{id}/renew` | Renew one subscription |
| `POST` | `/subscriptions/process-due` | Renew/expire everything due |

```json
POST /subscriptions/{id}/extend
{"days": 14, "reason": "goodwill"}
```

## Entitlements

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/customers/{customer_id}/entitlements` | Resolve every feature |
| `POST` | `/entitlements/check` | `can()` plus resolution detail |
| `POST` | `/customers/{customer_id}/overrides` | Set a customer override |
| `POST` | `/subscriptions/{subscription_id}/overrides` | Set a subscription override |

```json
POST /entitlements/check
{"customer_id": "01H...", "feature_key": "reports"}
→ {"allowed": true, "value": 1, "limit_value": 1, "source": "plan"}
```

## Invoices & credits

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/invoices` | Create an invoice |
| `GET` | `/invoices/{invoice_id}` | Get one |
| `GET` | `/customers/{customer_id}/invoices` | List for a customer |
| `POST` | `/invoices/{id}/finalize` | Draft → open |
| `POST` | `/invoices/{id}/void` | Void |
| `POST` | `/invoices/{id}/payments` | Record an offline payment |
| `POST` | `/customers/{customer_id}/credits` | Grant credit |
| `GET` | `/customers/{customer_id}/credits` | Balance and entries |

```json
POST /invoices/{id}/payments
{"amount_minor": 2900, "method": "transfer", "reference": "WIRE-9931"}
```

## Reports

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/reports/overview?currency=USD` | MRR/ARR and headline counts |
| `GET` | `/reports/revenue?currency=USD` | Revenue by plan |
| `GET` | `/reports/subscriptions` | Counts by status |
| `GET` | `/reports/entitlements` | Feature adoption |
| `GET` | `/reports/payments` | Outstanding invoices |
| `GET` | `/reports/channel?currency=USD` | Channel revenue by partner |

## Audit & events

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/audit-logs` | Query logs (`entity_type`, `entity_id`, `action`, `actor_id`) |
| `GET` | `/events` | Pending outbox events |

## Partners & channel

### Partners

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/partners` | Create a partner |
| `GET` | `/partners` | List partners |
| `GET` | `/partners/{partner_id}` | Get one |
| `POST` | `/commission-rules` | Create a commission rule |
| `GET` | `/commission-rules` | List rules |
| `POST` | `/partners/{partner_id}/agreements` | Create an agreement |
| `GET` | `/partners/{partner_id}/agreements` | List agreements |

### Licenses

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/partners/{partner_id}/allocations` | Allocate licenses |
| `GET` | `/partners/{partner_id}/allocations` | List allocations |
| `POST` | `/allocations/{allocation_id}/licenses` | Issue a license |
| `GET` | `/partners/{partner_id}/licenses` | List issued licenses |
| `POST` | `/licenses/{license_id}/revoke` | Revoke a license |

```json
POST /allocations/{allocation_id}/licenses
{"external_id": "end-customer-7", "email": "sam@example.com"}
```

### Accounts & settlement

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/partners/{partner_id}/prefund` | Prepay a prepaid account |
| `POST` | `/partners/{partner_id}/payments` | Record money received |
| `GET` | `/partners/{partner_id}/accounts` | List accounts |
| `GET` | `/partners/{partner_id}/ledger` | Ledger entries |
| `POST` | `/partners/{partner_id}/statements` | Generate a statement |
| `GET` | `/partners/{partner_id}/statements` | List statements |
| `POST` | `/partners/{partner_id}/invoices` | Create a partner invoice |
| `POST` | `/partner-invoices/{invoice_id}/payments` | Pay a partner invoice |
| `POST` | `/partners/{partner_id}/payouts` | Create a payout |
| `POST` | `/payouts/{payout_id}/pay` | Mark a payout paid |

## OpenAPI

The running server exposes machine-readable schemas at `/openapi.json` and
interactive docs at `/docs`.
