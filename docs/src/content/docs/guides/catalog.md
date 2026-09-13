---
title: Catalog & plans
description: "The catalog: features you gate and plans made of immutable versions with prices and entitlements."
---

The catalog is your product structure: **features** you gate, and **plans** made
of immutable **versions** with prices and entitlements.

## Features

A feature is anything you want to gate — a module, a boolean switch, or a quota.
Features are global to the deployment and looked up by `key`.

```python
with billing.transaction() as services:
    services.catalog.create_feature("reports", name="Reports")                    # boolean
    services.catalog.create_feature(
        "seats", name="Seats", value_type="limit", default_value=1
    )
```

| `value_type` | Meaning |
|---|---|
| `boolean` | On/off; `can()` returns true when the effective value is positive |
| `limit` | A numeric ceiling read with `limit()` |
| `meter` | A usage counter (reserved for usage-based pricing) |

`default_value` is used when no plan entitlement or override applies. An optional
`reset_period` (`day`, `week`, `month`, `year`) tags how a limit is meant to
reset.

:::tip[Auto-created features]
When you attach an entitlement whose `feature_key` does not exist yet, the
engine creates it for you — as a `limit` feature if you pass `limit_value`,
otherwise as a `boolean`. Explicit features are clearer, so prefer
`create_feature()` first.
:::

## Plans and versions

A **plan** is a stable identity. A **plan version** is the immutable snapshot
that subscriptions actually point at.

```python
with billing.transaction() as services:
    plan = services.catalog.create_plan("pro", "Pro")

    v1 = services.catalog.create_plan_version(
        plan.id,
        name="Pro (2026-01)",
        prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
        trial_days=14,
        entitlements=[
            {"feature_key": "reports"},                       # boolean grant
            {"feature_key": "seats", "value": 1, "limit_value": 5},
        ],
    )
```

Versions are numbered automatically (`v1.version == 1`). To change a published
plan, create a **new** version. Existing subscriptions are unaffected.

### Prices

A version can carry multiple prices, one per currency (multi-currency ready):

```python
prices=[
    {"amount_minor": 2900, "currency": "USD", "interval": "month"},
    {"amount_minor": 2700, "currency": "EUR", "interval": "month"},
]
```

| `interval` | Meaning |
|---|---|
| `month` | Recurring monthly |
| `year` | Recurring yearly |
| `one_time` | No renewal; the period simply ends |

### Entitlement entries

Each entry names a `feature_key` and may set `value` (default `1`) and
`limit_value` (default `None`):

| Field | Purpose |
|---|---|
| `feature_key` | Which feature to grant |
| `value` | Effective value when `limit_value` is absent (boolean on/off, or a quota) |
| `limit_value` | An explicit numeric ceiling, separate from `value` |

`set_entitlements(version_id, [...])` **replaces** all entitlements on a version
and is itself audited.

## Custom, per-customer plans

Sometimes a deal does not fit the catalog. A custom plan version is tied to one
customer and never pollutes the shared catalog.

```python
with billing.transaction() as services:
    custom = services.catalog.create_custom_plan(
        customer.id,
        name="Enterprise (Acme)",
        prices=[{"amount_minor": 250000, "currency": "USD", "interval": "year"}],
        trial_days=0,
        entitlements=[{"feature_key": "reports"}, {"feature_key": "seats", "limit_value": 250}],
    )
    services.subscriptions.create(customer.id, custom.id)
```

Behind the scenes the version gets `scope="customer_custom"` and a generated
`custom-<customer>-<id>` plan key.

## Reading the catalog

```python
services.catalog.list_features()
services.catalog.list_plans(limit=100, offset=0)
services.catalog.get_plan_by_key("pro")
services.catalog.get_plan_version(version_id)
services.catalog.list_prices(version_id)
services.catalog.list_plan_entitlements(version_id)
services.catalog.find_price(version_id, currency="USD")   # or price_id=...
```

## Gotchas

- **Keys are unique.** Creating a duplicate plan or feature key raises
  `ValidationError`.
- **At least one price is required** per version.
- **Unpublished versions cannot be subscribed to** — `create(..., is_published=False)`
  is for staging; a subscription attempt raises `ConflictError`.
- **Amounts are non-negative integers** in minor units. A free plan can use `0`.

## Next

- [Subscriptions](/saas-billing/guides/subscriptions/) — start, extend, and cancel.
- [Entitlements](/saas-billing/guides/entitlements/) — read and override what a plan grants.
