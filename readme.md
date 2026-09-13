# Billing & Channel Engine

A self-hostable, MIT-licensed Python engine that gives any SaaS app
**billing, subscriptions, module/feature access, audit, analytics, and
channel/partner (distributor & agent) sales** — without taking over the host
app's database.

Connect it **directly to your existing SQL database** (PostgreSQL, MySQL, or
SQLite) and it manages its own **prefixed** tables alongside yours.

- **Embedded** — `pip install`, call it in-process against your DB connection.
- **Standalone** — run the Docker image and talk REST; or mount the FastAPI
  router inside your own app.

> Status: **pre-release / planning.** See [`plan.md`](./plan.md) for the full
> design and roadmap. The package has not been published yet.

---

## Why

Most billing tools either lock you into a hosted platform, hide their data
model, or force a separate database. This project instead:

- Runs **on your database**, beside your tables, with a required table prefix.
- Ships as a **library or a service**, same core, same schema.
- Handles the awkward real-world cases: manual/custom plans, subscription
  **extensions**, offline invoices, credits, and **partner distribution**.
- Keeps a **full entity-level audit trail** and built-in **analytics**.

## Features

### Core (v0.1)
- Products, plans, and **immutable plan versions** (editing a plan never breaks
  live subscriptions).
- Subscriptions lifecycle: trials, activate, renew, pause, resume, cancel-now,
  cancel-at-period-end, reactivate.
- **Subscription extensions** by days, months, or a target date — logged with
  reason and actor.
- **Custom per-customer plans** with arbitrary price and entitlements.
- **Entitlements / module access** with limits, quotas, and per-customer or
  per-subscription overrides.
- **Manual billing:** invoices, line items, offline payments (transfer/cash),
  and a customer credit ledger.
- **Full audit log** (append-only, before/after, actor/why).
- **Reporting:** MRR/ARR, churn, conversion, revenue by plan, feature adoption,
  receivables.
- **Events outbox + webhooks** so your app can react to changes.

### Channel & Partners (v0.2)
- Distributors/agents with agreements (hierarchy-ready, single-level first).
- **License allocation** — approved quantities with `available = allocated − issued`.
- Issue licenses to end customers; each issue starts a subscription and updates
  the partner ledger.
- Three money models per agreement: **wholesale/prepaid**, **consignment**, and
  **agency/commission**.
- Commission bases: **flat %**, **tiered/volume**, **multi-level split**.
- Partner **accounts, ledger, invoices, payments, payouts, and statements**.
- Channel revenue and partner receivable reporting.

## How It Integrates

```python
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(
        dsn="postgresql://user:pass@localhost/mysaas",
        table_prefix="acme_",  # required, no default
        default_currency="USD",
        grace_period_days=3,
    )
)
```

```bash
billing migrate        # creates ONLY its prefixed tables
```

```python
customer = billing.customers.create(external_id=str(user.id), email=user.email)

if not billing.entitlements.can(customer.id, "api_access"):
    raise PermissionError("Upgrade required")

seats = billing.entitlements.limit(customer.id, "seats")
```

That's the seam: one `external_id` link per customer plus `can()`/`limit()`
calls where you gate features. Adopt modules incrementally — start with
entitlements, add billing, add partners later.

## Tech Stack

Python 3.11+ · SQLAlchemy 2.0 (sync-first) · PostgreSQL / MySQL / SQLite ·
FastAPI + Pydantic v2 · Typer CLI · ULID keys · integer minor-unit money.
Quality: ruff, mypy, pytest, GitHub Actions.

## Installation

Not yet published. When available:

```bash
pip install billing-engine
```

## Documentation

- [`plan.md`](./plan.md) — full design, data model, business rules, roadmap.
- [`AGENTS.md`](./AGENTS.md) — contributor and coding-agent conventions.

## Roadmap

- **v0.1.0** — core billing, entitlements, audit, reporting, REST + SDK + CLI.
- **v0.2.0** — channel & partner management.

## Contributing

See [`AGENTS.md`](./AGENTS.md) for architecture rules, conventions, and the
definition of done. Conventional Commits are used for history.

## License

MIT — see [LICENSE](./LICENSE).
