# Reporting

The reporting module is **read-only** and deliberately kept out of the write
path. It exposes dialect-aware aggregate queries for the metrics most SaaS apps
need.

```python
services.reports.overview("USD")
services.reports.subscription_counts()
services.reports.revenue_by_plan("USD")
services.reports.outstanding_invoices()
services.reports.feature_adoption()
services.uow.reports.channel_revenue("USD")
```

## Headline metrics

```python
services.reports.overview("USD")
# {
#   'customers': 120,
#   'subscriptions': 98,
#   'mrr_minor': 284200,
#   'arr_minor': 3410400,
#   ...
# }
```

| Key | Meaning |
|---|---|
| `customers` | Total customers |
| `subscriptions` | Subscriptions granting access (trialing/active/past_due) |
| `mrr_minor` | Monthly recurring revenue, normalized to one month |
| `arr_minor` | Annual run rate (`mrr * 12`) |

Yearly prices are normalized to a monthly figure so mixed intervals sum
correctly. Amounts are minor units in the requested currency.

## Subscriptions

```python
services.reports.subscription_counts()
# {'trialing': 12, 'active': 80, 'past_due': 4, 'paused': 2, 'canceled': 0, 'expired': 9}
```

## Revenue by plan

```python
services.reports.revenue_by_plan("USD")
# [{'plan_id': '01H...', 'mrr_minor': 232000, 'subscriptions': 80}, ...]
```

## Outstanding invoices

```python
services.reports.outstanding_invoices()
# {'count': 6, 'total_minor': 43500}
```

Open invoices and their unpaid amount — useful for receivables aging when
combined with `due_date`.

## Feature adoption

```python
services.reports.feature_adoption()
# [{'feature_key': 'reports', 'plans': 3, 'overrides': 5}, ...]
```

How often each feature appears in plan entitlements and overrides.

## Channel revenue

Grouped by partner, excluding revoked licenses:

```python
services.uow.reports.channel_revenue("USD")
# [{'partner_id': '01H...', 'licenses': 14, 'value_minor': 140000}, ...]
```

## CLI

```bash
billing report --dsn "postgresql+psycopg://..." --prefix acme_ --currency USD
```

## HTTP

```
GET /reports/overview?currency=USD
GET /reports/subscriptions
GET /reports/revenue?currency=USD
GET /reports/payments
GET /reports/entitlements
GET /reports/channel?currency=USD
```

## Next

- [Audit & events](audit-events.md) — the compliance side of the same data.
