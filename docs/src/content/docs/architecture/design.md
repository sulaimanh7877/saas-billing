---
title: Design
description: Map of the billing engine's layers, dependency rule, request flows, locked decisions, and extension points.
---

The engine is a sync-first, framework-free core with thin adapters. If you are
extending it, this page is the map; the authoritative source of truth is
[`plan.md`](https://github.com/sulaimanh7877/saas-billing/blob/main/plan.md).

## Layers

```
src/billing_engine/
├─ config.py            EngineConfig: dsn/engine, table_prefix, currency, trial, grace
├─ naming.py            PrefixNamer — builds every prefixed identifier
├─ domain/              pure business logic — no ORM, no HTTP, no I/O
│  ├─ entities/         Customer, Plan, PlanVersion, Subscription, Invoice, Partner, License, ...
│  ├─ value_objects/    Money (minor units), ULID, period arithmetic, UTC helpers
│  ├─ lifecycle.py      SubscriptionStateMachine + access grants
│  ├─ commission.py     flat / tiered / multi-level commission
│  ├─ repositories.py   repository interfaces (the ports)
│  └─ errors.py         typed error hierarchy
├─ services/            orchestration: customers, catalog, subscriptions,
│                       entitlements, invoices, credits, audit, reporting,
│                       partners, licenses, partner accounts
├─ adapters/
│  ├─ db/               SQLAlchemy models, repositories (SqlUnitOfWork), migrations
│  └─ api/              FastAPI routers, Pydantic DTOs, API-key auth
├─ events/              transactional outbox + webhook dispatcher
├─ sdk.py               BillingEngine facade
├─ server.py            standalone ASGI entry point
└─ cli.py               Typer commands
```

## The dependency rule

- `domain` depends on **nothing**.
- `services` depend on `domain` and on repository **interfaces**.
- `adapters` implement those interfaces and translate errors to HTTP/CLI.

Enforced consequences:

- Business rules live in `domain` and `services`, never in routers or ORM models.
- API routers are thin: validate → call a service → serialize.
- The same core powers the embedded SDK and the REST service with identical
  behavior.
- `domain` tests need no database; service tests run against in-memory SQLite.

## Request/data flow (embedded)

```
caller
  └─ BillingEngine.transaction()
       ├─ Session + SqlUnitOfWork        (one DB transaction)
       ├─ Services(...)                  (services share the unit of work)
       └─ service method
            ├─ reads/writes via repositories
            ├─ audit.record(...)         append-only audit row
            └─ audit.emit(...)           transactional outbox row
       └─ commit on success / rollback on error
```

Because the audit row, outbox event, and domain change share one transaction,
the trail cannot diverge from the data.

## Request flow (REST)

```
request
  └─ require_api_key dependency
  └─ get_services dependency  (opens a transaction for the request)
  └─ router: validate -> service call -> snapshot()
  └─ commit on success; BillingError -> HTTP status
```

## Locked decisions

| Concern | Decision |
|---|---|
| Language | Python 3.11+ |
| ORM | SQLAlchemy 2.0, **sync-first** |
| Databases | PostgreSQL, MySQL/MariaDB, SQLite |
| Keys | ULID strings |
| Money | Integer minor units + ISO currency (never float) |
| API | FastAPI + Pydantic v2 |
| CLI | Typer |
| Prefix | Required, configurable, no default |
| Billing (v0.2) | Manual/invoice only; Stripe seam reserved |
| Audit | Append-only, entity-level |
| Timezone | UTC everywhere |
| License | MIT |

## Extending the engine

1. Put pure rules in `domain/` (with unit tests, no DB).
2. Define any new persistence need as a repository interface in
   `domain/repositories.py`.
3. Implement it in `adapters/db`, and orchestrate from a `services/` class.
4. Write an audit row in the same transaction for every mutation.
5. If it changes behavior, update `plan.md`.

See [`AGENTS.md`](https://github.com/sulaimanh7877/saas-billing/blob/main/AGENTS.md)
for the full contributor workflow and definition of done.

## Next

- [Prefix strategy](/saas-billing/architecture/prefix-strategy/)
- [Data model](/saas-billing/reference/data-model/)
