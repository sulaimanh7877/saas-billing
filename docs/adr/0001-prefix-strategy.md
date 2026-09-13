# ADR 0001 — Table prefix strategy

- Status: Accepted
- Date: 2026-09-13
- Milestone: M0

## Context

The billing engine runs **on the host application's database**, alongside the
host's own tables. It must never collide with existing schema objects, and it
must remain portable across PostgreSQL, MySQL/MariaDB, and SQLite.

The engine owns many objects: roughly twenty tables plus their primary keys,
foreign keys, unique constraints, check constraints, and indexes. Constraint and
index names are not always scoped the way table names are — PostgreSQL scopes
constraint names per table but index names per schema, and MySQL requires
foreign-key names to be unique per database — so a naive approach that only
prefixes table names can still collide.

## Decision

Every object the engine creates is prefixed with a single required,
configurable `table_prefix`:

- The prefix is **required** and has **no default**; the engine refuses to start
  without one (`billing migrate` errors out).
- The prefix is **normalized** to end with exactly one underscore, so both
  `acme` and `acme_` yield `acme_subscriptions`.
- The prefix must be a safe SQL identifier fragment: lowercase letters, digits,
  and underscores, not starting with a digit.
- Naming follows the project convention:
  - tables: `{prefix}{snake_case_plural}` → `acme_subscriptions`
  - indexes: `{prefix}ix_<table>_<cols>` → `acme_ix_subscriptions_customer_id`
  - unique: `{prefix}uq_<table>_<cols>`
  - check: `{prefix}ck_<table>_<name>`
  - foreign keys: `{prefix}fk_<table>_<cols>_<reftable>`
  - primary keys: `{prefix}pk_<table>`
- The prefix is applied to **all** identifier kinds, not only tables.

`billing_engine.naming.PrefixNamer` is the single source of truth for building
these names. It validates every component to prevent malformed or injected
identifiers. It also exposes `logical()` and `is_prefixed()` to translate
between physical and logical names.

The prefix is resolved **once per process** at engine construction (v0.1). When
SQLAlchemy models are introduced (M1), table objects will carry the prefixed
name, and the `MetaData` naming convention will use callables that strip the
prefix from `table.name` before composing constraint names, so the prefix
appears exactly once.

## Consequences

- Host schemas cannot be clobbered by the engine's DDL.
- Multiple logical deployments can share one database with distinct prefixes.
- Constraint and index names remain deterministic and collision-free.
- One prefix per process in v0.1: constructing two engines with different
  prefixes in a single process is not supported. `BillingEngine` tracks the
  process prefix and raises `ConfigurationError` on a second, different prefix
  instead of silently renaming the first engine's tables. This is acceptable for
  the embedded and standalone deployment models, where a process serves one
  deployment.
- Migrations must interpolate the prefix everywhere; hard-coded table names are
  forbidden.

## Alternatives considered

- **Separate database or schema.** Rejected: the design goal is to run on the
  host's database with a direct SQL connection. PostgreSQL schemas do not exist
  in SQLite and behave differently in MySQL.
- **Random or hashed prefixes.** Rejected: unreadable during debugging and
  support.
- **Alembic with runtime-variable prefixes.** Deferred: Alembic's version
  scripts and naming are awkward with a runtime prefix. A small prefix-aware
  runner is planned for M1; Alembic may be reconsidered later.
- **Prefix only table names.** Rejected: index and FK name collisions are a real
  risk across dialects.
