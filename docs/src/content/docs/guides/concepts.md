---
title: Core concepts
description: A short tour of the core ideas behind the billing engine, from integration and architecture to money, time, and entitlements.
---

A short tour of the ideas you need before using the engine. Everything else in
these docs builds on them.

## The integration model

The engine keeps **its own** data and links back to your app with a single
`external_id` per customer. That is the whole seam:

```python
customer = services.customers.create(external_id=str(user.id), email=user.email)
```

Then, wherever your application gates a feature:

```python
if not services.entitlements.can(customer.id, "api_access"):
    raise PermissionError("Upgrade required")
```

You adopt modules incrementally — start with entitlements, add billing, add
partners later. Nothing else in your app has to change.

## Architecture

The codebase is split into three layers with a strict dependency direction:

```
domain/    pure logic — no SQLAlchemy, no FastAPI, no I/O
services/  orchestration + business rules; depend on domain + repo interfaces
adapters/  db/ (SQLAlchemy models, repositories, migrations)
           api/ (FastAPI routers, DTOs, auth)
```

`domain` depends on nothing. `services` depend on `domain` and on repository
*interfaces*; the concrete SQLAlchemy implementations live in `adapters/db`. This
keeps the business rules testable without a database and lets the same core
power both the embedded SDK and the REST service.

:::note[Consequence for contributors]
Business rules belong in `domain` and `services`, never in routers or ORM
models. Routers validate → call a service → serialize. Anything that mutates
data goes through a service and writes an audit row in the same transaction.
:::

## Money

All money is an **integer number of minor units** plus an ISO 4217 currency
code. `2900` with `USD` means **$29.00**. There are no floats anywhere in the
money path, so you never lose cents to binary rounding.

```python
{"amount_minor": 2900, "currency": "USD", "interval": "month"}
```

:::danger[Never use floats for money]
This is a locked decision. Convert at the edges (for example, Stripe's
`amount` field is already minor units) and keep integers internally.
:::

## Time

All timestamps are **UTC and timezone-aware**. `EngineConfig` accepts only
`timezone="UTC"`. Period arithmetic uses calendar-aware helpers, so a monthly
subscription started on Jan 31 advances to the last day of February as you would
expect.

## Identifiers

Primary keys are **ULID strings** — lexicographically sortable, portable across
all three dialects, and safe to expose in URLs. Generate one with:

```python
from billing_engine import new_ulid

new_ulid()  # '01J8Z...'
```

## Table prefixing

The engine runs **on your database** and owns about twenty tables plus their
indexes and constraints. Every object it creates is stamped with the required
`table_prefix`, so it can never collide with your schema.

```python
EngineConfig(table_prefix="acme_")  # -> acme_customers, acme_subscriptions, ...
```

The prefix is normalized to end in exactly one underscore, so `acme` and
`acme_` are equivalent. See [Prefix strategy](/saas-billing/architecture/prefix-strategy/).

## Transactions, audit, and events

`billing.transaction()` yields a bundle of services bound to one database
transaction. It commits when the block exits cleanly and rolls back on any
exception.

```python
with billing.transaction() as services:
    customer = services.customers.create("user-1")
    # commit happens here
```

Inside that transaction, **every mutation also writes**:

1. an append-only **audit row** (`before`, `after`, actor, source, reason), and
2. a **transactional outbox event** for anything you want to dispatch.

Because they share the transaction, the audit trail and the outbox can never
drift from the data.

## Catalog immutability

A **plan** is a stable identity (`key`, `name`). What customers subscribe to is a
**plan version** — an immutable snapshot of prices, trial length, and
entitlements.

Need to raise a price? Create a new version. Existing subscriptions keep pointing
at the version they signed up for, so you never break live customers.

```python
version = services.catalog.create_plan_version(plan.id, prices=[...])
# -> version.version == 1, 2, 3, ...
```

## Subscription state machine

```
trialing ──▶ active ──▶ past_due ──▶ paused
    │           │            │          │
    └───────────┴────────────┴──▶ canceled ──▶ expired
```

Transitions are exposed as explicit service calls — `renew`, `extend`, `pause`,
`resume`, `cancel`, `reactivate`, `change_plan` — plus a batch `process_due` for
your scheduler. Every transition writes a `subscription_adjustment`, an audit
row, and an outbox event. See [Subscriptions](/saas-billing/guides/subscriptions/).

## Entitlement resolution order

When you ask whether a customer can use a feature, the engine checks, in order:

1. a **customer override**
2. a **subscription override**
3. the **plan entitlement** on their current version
4. the **feature default**

The first hit wins (expired overrides are skipped). See [Entitlements](/saas-billing/guides/entitlements/).

## Next

- [Catalog & plans](/saas-billing/guides/catalog/)
- [Subscriptions](/saas-billing/guides/subscriptions/)
- [Entitlements](/saas-billing/guides/entitlements/)
