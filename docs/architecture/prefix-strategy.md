# Prefix strategy

The engine runs **on the host application's database**, alongside the host's own
tables. Every object it creates is stamped with a single required, configurable
`table_prefix`.

The canonical decision record is
[ADR 0001](https://github.com/sulaimanh7877/saas-billing/blob/main/docs/adr/0001-prefix-strategy.md).
This page is the practical summary.

## Rules

- The prefix is **required** and has **no default**. `billing migrate` errors
  without one.
- It is normalized to end with exactly one underscore: `acme` and `acme_` both
  produce `acme_subscriptions`.
- It must be a safe SQL identifier fragment: lowercase letters, digits, and
  underscores, not starting with a digit.
- It is applied to **all** identifier kinds — tables, primary keys, foreign
  keys, unique constraints, check constraints, and indexes — not just tables.
- The prefix is resolved **once per process** at engine construction.

## Naming

| Object | Pattern | Example |
|---|---|---|
| Table | `{prefix}{snake_case_plural}` | `acme_subscriptions` |
| Index | `{prefix}ix_<table>_<cols>` | `acme_ix_subscriptions_customer_id` |
| Unique | `{prefix}uq_<table>_<cols>` | `acme_uq_customers_external_id` |
| Check | `{prefix}ck_<table>_<name>` | `acme_ck_...` |
| Foreign key | `{prefix}fk_<table>_<cols>_<reftable>` | `acme_fk_subscriptions_customer_id_customers` |
| Primary key | `{prefix}pk_<table>` | `acme_pk_subscriptions` |

`billing_engine.naming.PrefixNamer` is the single source of truth. It validates
every component to prevent malformed or injected identifiers, and exposes
`logical()` / `is_prefixed()` to translate between physical and logical names.

## Why prefix constraints and indexes too

Constraint and index names are not scoped uniformly:

- PostgreSQL scopes constraint names per table but **index names per schema**.
- MySQL requires **foreign-key names to be unique per database**.

Prefixing only tables would still allow collisions. Prefixing every object makes
them deterministic and collision-free on all three dialects.

## One prefix per process

In v0.2 a process serves one deployment (one prefix). Constructing a second
`BillingEngine` with a different prefix raises `ConfigurationError` rather than
silently renaming the first engine's tables.

This fits both deployment models:

- **Embedded**: one app process serves one tenant database.
- **Standalone**: one service instance serves one deployment.

Multiple prefixes in one process, and multiple logical deployments sharing one
database, are deferred.

## Migrations

Migrations interpolate the prefix everywhere; hard-coded table names are
forbidden. Applied versions are tracked in the prefixed `{prefix}migrations`
table, and `billing migrate` is idempotent.

## Next

- [Configuration](../reference/configuration.md)
- [Design](design.md)
