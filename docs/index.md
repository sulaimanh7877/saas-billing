# Billing & Channel Engine

A self-hostable, MIT-licensed Python engine that gives any SaaS app
**billing, subscriptions, module/feature access, audit, analytics, and
channel/partner sales** — without taking over the host app's database.

Run it **embedded** in your app or as a **standalone REST service**. It connects
to your existing PostgreSQL, MySQL/MariaDB, or SQLite database and manages only
its own **prefixed** tables beside yours.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Quick start**

    ---

    Install the package, point it at a database, run one migration, and gate a
    feature in under five minutes.

    [:octicons-arrow-right-24: Quick start](getting-started/quickstart.md)

-   :material-school:{ .lg .middle } **Tutorial**

    ---

    Build a feature-gated SaaS step by step: catalog, trials, entitlements,
    invoices, credits, and reporting.

    [:octicons-arrow-right-24: Follow the tutorial](getting-started/tutorial.md)

-   :material-robot:{ .lg .middle } **Use with an agent**

    ---

    Install the ready-made agent skill from npm so your coding agent knows the
    API, the rules, and the pitfalls.

    [:octicons-arrow-right-24: Agent skill](guides/agent-skill.md)

-   :material-sitemap:{ .lg .middle } **Architecture**

    ---

    Pure Python domain, service layer, and pluggable adapters. One schema, a
    required table prefix, integer money, UTC everywhere.

    [:octicons-arrow-right-24: Design](architecture/design.md)

</div>

## Why this engine

Most billing tools either lock you into a hosted platform, hide their data
model, or force a separate database. This project instead:

- Runs **on your database**, beside your tables, with a **required table
  prefix** so nothing collides.
- Ships as a **library or a service** — same core, same schema, same behavior.
- Handles the awkward real-world cases: manual/custom plans, subscription
  **extensions**, offline invoices, credits, and **partner distribution**.
- Keeps a **full entity-level audit trail** and built-in **analytics**.
- Uses **integer minor units** for all money and **UTC** for all timestamps.

## Two integration paths, one core

=== "Embedded SDK"

    ```python
    from billing_engine import BillingEngine, EngineConfig

    billing = BillingEngine(
        EngineConfig(dsn="postgresql://user:pass@localhost/mysaas", table_prefix="acme_")
    )
    billing.migrate()

    with billing.transaction() as services:
        customer = services.customers.create("user-42", email="ada@example.com")
        print(services.entitlements.can(customer.id, "api_access"))
    ```

=== "Standalone REST"

    ```bash
    export BILLING_DSN="postgresql://user:pass@localhost/mysaas"
    export BILLING_TABLE_PREFIX="acme_"
    export BILLING_API_KEY="a-long-random-secret"
    uvicorn billing_engine.server:create_server --factory --port 8000
    ```

=== "CLI"

    ```bash
    billing migrate --dsn "sqlite:///billing.db" --prefix acme_
    billing seed    --dsn "sqlite:///billing.db" --prefix acme_
    billing report  --dsn "sqlite:///billing.db" --prefix acme_
    ```

## What's inside

| Area | Capabilities |
|---|---|
| **Catalog** | Products, plans, immutable plan versions, multi-currency prices, features, plan entitlements |
| **Subscriptions** | Trials, activate, renew, extend (days/months/until), extend trial, pause, resume, cancel-now/at-period-end, reactivate, change plan, process-due |
| **Entitlements** | `can()`, `limit()`, resolution chain, customer/subscription overrides, expiring overrides |
| **Billing** | Manual invoices, line items, offline payments, credit ledger |
| **Channel** | Partners, agreements, three money models, commission rules, license allocation & issuance, accounts, ledger, invoices, payouts, statements |
| **Governance** | Append-only audit log, transactional outbox, webhooks with retries |
| **Analytics** | MRR/ARR, subscription counts, revenue by plan, feature adoption, outstanding invoices, channel revenue |

## Project status

!!! info "Stable baseline: v0.2.0"

    Core billing (v0.1.0) and channel/partner management (v0.2.0) are complete
    and covered by unit, integration, and cross-dialect tests. The next work is
    a live payment-gateway adapter behind the reserved Stripe seam, proration,
    usage-based pricing, and a partner portal.

## License

MIT — see [LICENSE](https://github.com/sulaimanh7877/saas-billing/blob/main/LICENSE).
