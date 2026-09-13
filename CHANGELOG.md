# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Channel & partner management (v0.2.0): partners, agreements, license
  allocation, partner accounts/ledger, invoices, payouts, and statements.

## [0.1.0] - 2026-09-13

The first release: a self-hostable billing, subscription, entitlement, audit,
and analytics engine for any SaaS, running on the host database with a required
table prefix.

### Added
- **Configuration**: `EngineConfig` with required `table_prefix`, DSN or live
  SQLAlchemy engine, ISO 4217 currency, and UTC-only timestamps.
- **Prefix strategy**: every table, index, and constraint is stamped with the
  configured prefix; `PrefixNamer` is the single source of truth.
- **Domain**: entities, `Money` (integer minor units), ULID identifiers, period
  arithmetic, subscription lifecycle state machine, and typed errors.
- **Schema & migrations**: SQLAlchemy 2.0 models for customers, catalog,
  subscriptions, entitlements, invoices, payments, credits, events, audit logs,
  and a prefix-aware migration runner.
- **Services**: customer and catalog management (immutable plan versions, custom
  plans, prices, features), subscription lifecycle (create, extend, extend
  trial, pause, resume, cancel, reactivate, change plan, renew, process due),
  entitlement resolution with overrides, manual invoicing and offline payments,
  a credit ledger, reporting, and full entity-level auditing.
- **Events**: transactional outbox with a dispatcher (retry/backoff) and an
  HMAC-signed webhook sender.
- **Interfaces**: embeddable `BillingEngine` SDK, Typer CLI
  (`version`, `migrate`, `seed`, `report`, `audit`), and a FastAPI HTTP adapter
  with a mountable router, standalone app, and API-key auth.
- **Deployment**: Dockerfile, `docker-compose.yml` with PostgreSQL/MySQL, and a
  standalone ASGI entry point.
- **CI**: GitHub Actions matrix over Python 3.11-3.13 running ruff, mypy, and
  pytest.

[Unreleased]: https://github.com/sulaimanh7877/saas-billing/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sulaimanh7877/saas-billing/releases/tag/v0.1.0
