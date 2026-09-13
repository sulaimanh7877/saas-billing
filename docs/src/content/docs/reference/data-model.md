---
title: Data model
description: The prefixed tables owned by the billing engine, their portability guarantees, naming conventions, and key relationships.
---

The engine owns roughly twenty tables, all prefixed with your `table_prefix`
(shown here as `{prefix}`). It never creates or alters tables it does not own.

:::note[Portability]

All identifiers are prefixed, all keys are ULID strings, all money is integer
minor units, and all timestamps are UTC. The schema works unchanged on
PostgreSQL, MySQL/MariaDB, and SQLite.

:::

## Core (v0.1)

| Table | Purpose |
|---|---|
| `{prefix}customers` | `external_id` (unique link to your app), email, name, currency, attributes, `partner_id` |
| `{prefix}products` | Optional grouping for plans |
| `{prefix}plans` | Stable catalog identity (`key`, `name`, `is_active`) |
| `{prefix}plan_versions` | Immutable snapshot: trial, scope (`catalog`/`customer_custom`), `customer_id`, published flag, version number |
| `{prefix}prices` | One or more per version: currency, `amount_minor`, interval |
| `{prefix}features` | Gateable feature: `key`, `value_type`, `default_value`, `reset_period` |
| `{prefix}plan_entitlements` | Version ↔ feature with `value` / `limit_value` |
| `{prefix}entitlement_overrides` | Customer- or subscription-scoped grant with optional `expires_at` |
| `{prefix}subscriptions` | Plan version + status + period dates + trial/pause/cancel/grace fields |
| `{prefix}subscription_adjustments` | Immutable audit of extensions, pauses, renewals, plan changes |
| `{prefix}invoices` / `{prefix}invoice_lines` | Manual invoices (`draft → open → paid/void/uncollectible`) |
| `{prefix}payments` | Manually recorded offline payments |
| `{prefix}credit_ledger` | Customer credit entries with `balance_after_minor` |
| `{prefix}events` | Transactional outbox (`type`, `payload`, `status`, `attempts`) |
| `{prefix}audit_logs` | Append-only: actor, action, entity, before/after, reason, source, ip |
| `{prefix}migrations` | Applied migration versions |

## Channel & partners (v0.2)

| Table | Purpose |
|---|---|
| `{prefix}partners` | Type, `parent_partner_id` (hierarchy), contact, currency, status |
| `{prefix}partner_agreements` | Partner ↔ plan, `money_model`, discount, commission rule, effective window |
| `{prefix}commission_rules` | `basis` + params (`rate_bps`, `tiers`, `levels`) |
| `{prefix}license_allocations` | Partner + plan version + `quantity_allocated` / `quantity_issued` |
| `{prefix}licenses` | One row per issued unit: status, customer, subscription, dates |
| `{prefix}partner_accounts` | Per partner + currency: `prepaid` / `receivable` / `payable`, balance |
| `{prefix}partner_ledger_entries` | Append-only charges, payments, commissions, adjustments, payouts |
| `{prefix}partner_invoices` (+ lines) | Invoices billed to a partner |
| `{prefix}partner_payments` | Money received from a partner |
| `{prefix}partner_payouts` (+ lines) | Money paid out to a partner |
| `{prefix}partner_statements` | Settlement period with opening/closing balances |

## Naming conventions

| Object | Pattern | Example |
|---|---|---|
| Table | `{prefix}{snake_case_plural}` | `acme_subscriptions` |
| Index | `{prefix}ix_<table>_<cols>` | `acme_ix_subscriptions_customer_id` |
| Unique | `{prefix}uq_<table>_<cols>` | `acme_uq_customers_external_id` |
| Check | `{prefix}ck_<table>_<name>` | `acme_ck_...` |
| Foreign key | `{prefix}fk_<table>_<cols>_<reftable>` | `acme_fk_subscriptions_customer_id_customers` |
| Primary key | `{prefix}pk_<table>` | `acme_pk_subscriptions` |

## Key relationships

```
customer ──< subscription >── plan_version ──< price
   │             │                  │
   │             │                  └──< plan_entitlement >── feature
   │             └──< subscription_adjustment
   ├──< invoice ──< invoice_line
   ├──< payment
   ├──< credit_entry
   └──< entitlement_override (customer-scoped)

partner ──< agreement >── commission_rule
   ├──< allocation >── license >── customer / subscription
   ├──< account >── ledger_entry
   ├──< invoice / payment / payout / statement
   └──< customer (attribution via customers.partner_id)
```

## Next

- [Prefix strategy](/saas-billing/architecture/prefix-strategy/) — how identifiers are built.
- [Design](/saas-billing/architecture/design/) — the layer boundaries.
