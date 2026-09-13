# Billing & Channel Engine — Project Plan

A self-hostable, MIT-licensed engine that owns **billing, subscriptions,
entitlements, audit, analytics, and channel/partner sales** for any SaaS.

One core, two integration paths (embedded library + standalone REST), one
schema with a **required configurable table prefix**.

> Working package name: `billing_engine` (renameable). Repo: `saas-billing`.

---

## 1. Vision

Give any SaaS app a drop-in billing and access-control layer that:

- Manages **billing, subscriptions, and module/feature access**.
- Supports a **wider range of scenarios**: manual/custom plans, subscription
  extensions, offline invoices, credits, and channel/partner distribution.
- Connects **directly to the host app's SQL database** without taking it over.
- Uses **prefixed table names** so it never collides with existing schema.

Integration is deliberately thin: one `external_id` link per customer, plus
`can()` / `limit()` calls wherever the host gates features. Everything else is
opt-in per module.

---

## 2. Locked Decisions

| Concern | Decision |
|---|---|
| Language / runtime | Python 3.11+ |
| ORM / DB access | SQLAlchemy 2.0, **sync-first** |
| Databases (first-class) | PostgreSQL, MySQL/MariaDB, SQLite |
| Primary keys | ULID strings (sortable, portable) |
| Money | Integer minor units + ISO currency code (never float) |
| API | FastAPI + Pydantic v2 (mountable router + standalone app) |
| CLI | Typer |
| Packaging | `pyproject.toml` (hatchling), published to PyPI |
| Container | Dockerfile + docker-compose |
| Integration | Embedded library **and** standalone service, same core |
| Table prefix | **Required, configurable, no default** |
| Billing scope (v0.1) | Manual/invoice only — no live gateway, Stripe seam reserved |
| Audit | Full entity-level, append-only |
| Analytics | Reporting module in scope for v0.1 |
| Partner money models | Support all three, configured per agreement |
| License model | Counted units only (no exposed keys) |
| Partner hierarchy | Hierarchy-ready, single-level first |
| Partner invoicing | Invoice partner at wholesale/net only (end-customer prices private) |
| Commission | All bases supported: flat %, tiered/volume, multi-level split |
| Partner access (v0.1) | Admin API + CLI only (no partner portal) |
| Release shape | **v0.1.0 = core**, **v0.2.0 = partners** |
| License | MIT |
| Timezone | UTC everywhere |

---

## 3. Architecture

```
src/billing_engine/
├─ config.py            EngineConfig: dsn/engine, table_prefix, currency,
│                       grace_period_days, trial_days, timezone
├─ domain/              pure business logic — no ORM, no HTTP
│  ├─ entities/         Customer, Plan, PlanVersion, Subscription, Invoice,
│  │                    Partner, LicenseAllocation, License, ...
│  ├─ value_objects/    Money(minor units), BillingInterval, EntitlementValue
│  ├─ lifecycle.py      SubscriptionStateMachine
│  ├─ commission.py     flat / tiered / multi-level commission rules
│  └─ errors.py
├─ services/            customer, catalog, subscription, entitlement,
│                       invoice, credit, audit, reporting,
│                       partner, license, ledger
├─ adapters/
│  ├─ db/               SQLAlchemy models, repositories, prefix-aware migrations
│  └─ api/              FastAPI routers, DTOs, API-key/HMAC auth
├─ events/              transactional outbox + webhook dispatcher
├─ sdk.py               BillingEngine facade
└─ cli.py               migrate | seed | report | audit | partner | license
```

**Dependency rule:** `domain` depends on nothing; `services` depend on domain +
repository interfaces; `adapters` implement those interfaces. This keeps the
core testable and gateway-agnostic.

### Prefix strategy

- Every table, index, constraint, and foreign key name is prefixed
  (e.g. `acme_subscriptions`, `acme_ix_subscriptions_customer_id`).
- Prefix is resolved at engine init and is **required**; `billing migrate`
  errors without it.
- v0.1 uses a **process-level prefix** (one prefix per process). Supporting
  multiple prefixes in one process is deferred.
- Migrations use a small **prefix-aware runner** with its own prefixed history
  table (Alembic struggles with runtime-variable prefixes).

---

## 4. Data Model (all tables prefixed)

### Core

- `customers` — `id`, `external_id` (host app user/tenant id, unique), `email`,
  `name`, `currency`, metadata, `partner_id` (attribution), timestamps.
- `products` — optional grouping of plans.
- `plans` — stable catalog identity (`key`, `name`, `is_active`).
- `plan_versions` — **immutable** snapshot: price, interval
  (`month` | `year` | `one_time`), trial days, scope (`catalog` |
  `customer_custom`), `customer_id` (nullable for custom plans), published flag.
- `prices` — one or more per plan version (currency, amount in minor units,
  interval). Multi-currency ready.
- `features` — `key`, `name`, `default_value`, `value_type`
  (`boolean` | `limit` | `meter`).
- `plan_entitlements` — plan_version ↔ feature, with `value`/`limit` and
  `reset_period`.
- `entitlement_overrides` — scoped to `customer` or `subscription`, to
  grant/raise/lower a feature without changing the plan.
- `subscriptions` — `customer_id`, `plan_version_id`, `status`,
  `current_period_start`, `current_period_end`, `trial_end`, `cancel_at`,
  `canceled_at`, `paused_until`, `grace_until`, `quantity`,
  `collection_method`, `partner_id`, timestamps.
- `subscription_adjustments` — immutable audit of extensions, pauses, manual
  date edits (who/why/when).
- `invoices` + `invoice_lines` — manual invoices,
  `draft → open → paid / void / uncollectible`.
- `payments` — manually recorded payments (cash, transfer, other), applied to
  invoices.
- `credit_ledger` — customer credit balance entries (grant/consume/refund).
- `events` — transactional outbox (`type`, `payload`, `status`, `attempts`).
- `audit_logs` — append-only, one row per mutation: `actor_type`, `actor_id`,
  `action`, `entity_type`, `entity_id`, `before`, `after`, `reason`,
  `source` (embedded | rest | webhook | job), `ip`, `created_at`.
- `<prefix>migrations` — applied-version tracking.

### Channel & Partners (v0.2)

- `partners` — `type` (distributor | agent | reseller), `parent_partner_id`,
  name, contact, currency, status, portal credentials.
- `partner_agreements` — partner ↔ plan, `money_model`, price/discount,
  `commission_rule_id`, currency, effective period, status.
- `commission_rules` — `basis` (`flat` | `tiered` | `multi_level`) + params.
- `license_allocations` — partner, plan_version, `quantity_allocated`,
  `quantity_issued`, effective window, status, `parent_allocation_id`.
- `licenses` — one row per issued unit (`status`, `customer_id`,
  `subscription_id`, `issued_at`, `expires_at`). No exposed keys.
- `partner_accounts` — per partner + currency, `account_type`
  (`prepaid` | `receivable` | `payable`), balance.
- `partner_ledger_entries` — append-only: `charge`, `payment_received`,
  `commission_earned`, `adjustment`, `refund`, `write_off`; each with
  reference, `balance_after`, actor, reason.
- `partner_invoices` (+ lines), `partner_payments`, `partner_payouts` (+ lines).
- `partner_statements` — settlement period, opening/closing balance, charges,
  payments, commission, status (`draft | sent | settled`).

---

## 5. Business Rules

### Subscription state machine

`trialing → active → past_due → paused → canceled → expired`

Transitions: `renew`, `extend`, `pause`, `resume`, `cancel_at_period_end`,
`cancel_now`, `reactivate`. Every transition writes `subscription_adjustments`,
`audit_logs`, and an `events` outbox row.

### Entitlement resolution order

`customer override → subscription override → plan entitlement → feature default`

Cached per customer; invalidated on writes.

### Subscription extension

`extend(days=, months=, until=, reason=)` adjusts `current_period_end` and is
logged. Also: extend trial, pause-until, set custom next billing date.

### Custom plans

`plan_versions` with `scope = customer_custom`, tied to one customer, with
arbitrary price + entitlements, published without polluting the catalog.

### Partner money models (per agreement)

- **`wholesale_prepaid`** — partner prepays a block; issuing draws down a
  prepaid balance.
- **`consignment`** — licenses on credit; issuing creates a receivable; partner
  settles later.
- **`agency_commission`** — partner sells at list, collects, keeps a commission;
  invoice net or track remittance.

### Commission bases (per agreement)

- **`flat`** — fixed % on the agreed amount.
- **`tiered`** — rate table by volume threshold.
- **`multi_level`** — rate per partner level (distributor + agent).

Computed at license issue/activation, posted to the ledger, reflected in
statements/payouts.

### Issue-license flow

Validate allocation capacity → create/link end customer (attributed) →
create subscription on agreed plan version → post ledger entry per money model
→ mark license `active`, increment counters, compute commission.

---

## 6. Interfaces

### Embedded SDK

```python
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(
        dsn="postgresql://user:pass@localhost/mysaas",
        table_prefix="acme_",
        default_currency="USD",
        grace_period_days=3,
    )
)

billing.customers.create(external_id=str(user.id), email=user.email)
billing.subscriptions.create(customer_id, plan_version_id, trial_days=14)
billing.subscriptions.extend(sub_id, days=14, reason="goodwill")
billing.entitlements.can(customer_id, "reports")
billing.entitlements.limit(customer_id, "seats")
billing.invoices.create_from_subscription(sub_id)
```

### REST (FastAPI)

```
POST   /customers                    GET/POST /plans, /plans/{id}/versions
GET    /customers/{id}/entitlements  POST     /subscriptions
POST   /entitlements/check           POST     /subscriptions/{id}/actions
POST   /overrides                    GET      /customers/{id}/subscriptions
POST   /invoices, /invoices/{id}/payments, /credits
GET    /reports/*                    GET      /audit-logs
GET    /events
# v0.2
POST   /partners /allocations /licenses
GET    /partner-accounts /statements
```

Auth: API key + HMAC signature for the service; no auth in embedded mode.

### CLI

```
billing migrate        billing seed
billing report <name>  billing audit
billing partner ...    billing license ...
```

---

## 7. Milestones

### v0.1.0 — Core

| ID | Deliverable |
|---|---|
| M0 | Repo, packaging, CI (ruff/mypy/pytest), `EngineConfig`, prefix strategy, license, first ADR |
| M1 | Core domain + schema + prefix-aware migration runner |
| M2 | Core services (customers, catalog, subscriptions/lifecycle/extension, entitlements + cache, invoices/payments/credits); audit writes built in |
| M3 | Embedded `BillingEngine` SDK + CLI |
| M4 | REST API + API-key/HMAC auth (mountable router) |
| M5 | Events outbox + webhook dispatcher with retries |
| M6 | Audit query layer + `/audit-logs` |
| M7 | Reporting/analytics module + `/reports/*` |
| M8 | Hardening: 3-dialect integration tests, concurrency, docs, examples, Stripe seam, Docker + compose, PyPI v0.1.0 |

### v0.2.0 — Channel & Partners

| ID | Deliverable |
|---|---|
| P1 | Partners, agreements, commission rules, allocations, licenses, issue flow |
| P2 | Partner accounts/ledger, invoices, payments, payouts, statements |
| P3 | Attribution + channel reports + CLI/admin API |
| P4 | Partner tests across dialects, docs, examples |

---

## 8. Reporting / Analytics

- **Revenue:** MRR, ARR, ARPU, revenue by plan/currency, credits issued,
  outstanding invoices.
- **Subscriptions:** active/trialing/past_due/paused counts, new vs churned,
  trial→paid conversion, churn rate, upcoming renewals.
- **Entitlements:** feature adoption, limit utilization.
- **Payments:** collected vs failed, aging receivables.
- **Channel (v0.2):** licenses allocated/issued/available per partner, channel
  revenue, commission payable, partner receivables aging.

Exposed via SQL (dialect-aware view/aggregate queries), `/reports/*`, and
`billing report ...`. Kept out of the write path.

---

## 9. Deferred (post-v0.1/v0.2)

Proration, usage-based pricing, live gateways beyond the Stripe seam, partner
self-service portal, multi-prefix in one process, async DB backend, i18n.

---

## 10. Risks

- Dynamic-prefix DDL mechanics (process-level prefix in v0.1).
- Dialect-safe aggregate SQL for reports.
- Concurrency on allocation counters (row locking).
- Audit atomicity under long transactions.

## 11. Status

- **v0.1.0 released** — M0-M8 complete: core billing, subscriptions,
  entitlements, audit, reporting, events, embedded SDK, CLI, and REST API.
- **v0.2.0 released** — P1-P4 complete: channel & partner management (partners,
  agreements, commission rules, license allocation/issuance, partner
  accounts/ledger, invoices, payments, payouts, statements, channel reporting).
- Known limitation: one table prefix per process (see ADR 0001). Multi-prefix
  support is deferred. `BillingEngine` now rejects a second differing prefix
  with a clear `ConfigurationError` rather than clobbering the first engine.
- `EngineConfig.trial_days` is the fallback trial length when a plan version
  defines none; `grace_period_days` keeps a past-due subscription accessible
  after its period ends before it expires.
- Next: payment gateway adapter (Stripe seam), proration, usage-based pricing,
  partner portal.

