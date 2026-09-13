# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Documentation site** (MkDocs Material) with a quick start, a step-by-step
  tutorial, guides for every subsystem, deployment and reference pages, and an
  FAQ.
- **Agent skill** shipped as the `billing-engine-skill` npm package: a
  `SKILL.md` with the API cheatsheet, locked rules, and pitfalls, plus a
  dependency-free installer (`npx billing-engine-skill`). A byte-for-byte copy
  is served on the docs site with one-click copy/download.
- `scripts/sync_skill.py` and an integrity test to keep the npm skill and its
  docs mirror in sync.
- GitHub Actions workflows to build/deploy the docs to GitHub Pages and to
  publish the skill to npm.

## [0.2.0] - 2026-09-13

Channel & partner management: sell and manage licenses through distributors,
agents, and resellers, and track the money you owe each other.

### Added
- **Partners**: distributors, agents, and resellers, hierarchy-ready via
  `parent_partner_id`.
- **Agreements** with three money models: `wholesale_prepaid`, `consignment`,
  and `agency_commission`, plus optional wholesale discounts.
- **Commission engine** (pure): flat, tiered/volume, and multi-level bases,
  expressed in basis points.
- **License allocation & issuance**: authorize a partner with N licenses for a
  plan version; issuing creates/attributes the end customer, starts their
  subscription, consumes allocation capacity, and posts ledger entries.
- **Partner accounts & ledger**: prepaid, receivable, and payable balances with
  an append-only ledger (charges, payments, commissions, adjustments, refunds,
  write-offs, payouts).
- **Partner invoices, payments, payouts, and statements** for settlement.
- **Channel reporting**: licenses and value grouped by partner.
- **REST endpoints** for partners, allocations, licenses, accounts, ledger,
  statements, invoices, payouts, and `/reports/channel`.

### Changed
- Foreign-key naming convention now derives the referred table from the target
  name, supporting self-referential keys (partner hierarchy).

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

[Unreleased]: https://github.com/sulaimanh7877/saas-billing/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sulaimanh7877/saas-billing/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sulaimanh7877/saas-billing/releases/tag/v0.1.0
