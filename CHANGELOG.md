# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Timestamps**: `updated_at` now advances on every persisted mutation (it was
  frozen because stale entity values suppressed `onupdate`), and updates return
  the persisted `created_at` instead of `None` (#22).
- **Trial cancellation**: `cancel(at_period_end=True)` on a trialing
  subscription now cancels at `trial_end` rather than a full interval later
  (#22).
- **Custom plans**: `customer_custom` plan versions are enforced as
  customer-scoped on both `create` and `change_plan`, require an existing
  customer, and no longer appear in the catalog listing (`list_plans` /
  `GET /plans`) (#22).
- **Catalog**: `change_plan` rejects unpublished plan versions, and
  `create_plan_version` rejects duplicate `(currency, interval)` prices (#22).
- **Currency**: customer/partner/agreement/credit/invoice currencies are
  validated as three-letter ISO 4217 codes instead of being silently uppercased
  (#22).
- **Mountable router**: mounting `billing_engine.adapters.api.app.router`
  directly now opens its own session/transaction per request instead of
  returning 500, matching the documented deployment guide (#22).
- **Plan version immutability**: `set_entitlements` now refuses to mutate a
  published plan version (create a new version instead) (#22).
- **Lifecycle audit**: entering the `past_due` grace window now writes a
  `subscription_adjustments` row, and `pause(until=...)` is honored by
  `process_due`, which auto-resumes the subscription when the window ends (#22).
- **Partner accounts**: `(partner_id, currency, account_type)` is unique and
  posting takes a row lock, so concurrent ledger posts cannot create duplicate
  accounts or lose balance updates (#22).
- **Partner invoicing**: finalizing a partner invoice posts a backing `charge`
  to the receivable, so payments net the balance to zero instead of driving it
  negative (#22).
- **Channel reporting**: `channel_revenue` counts each license once (joining the
  actual subscription price) and applies the agreement `discount_bps` (#22).
- **License issuance currency mismatch**: issuing now passes the
  agreement-currency price into the subscription, so the subscription and any
  invoice derived from it use the same currency/amount that was charged (#20).
- **Deterministic price selection**: `list_prices` is ordered, removing the
  dialect-dependent `prices[0]` fallback (#20).
- **Reference validation**: agreements reject a dangling `plan_id` and reversed
  effective windows; allocations reject a dangling `agreement_id` or an
  agreement/parent allocation belonging to another partner (#20).
- **Partner invoicing**: overpayments are rejected, and void payouts can no
  longer be paid (#20).
- **Subscription lifecycle**: `resume` now requires a paused subscription, and
  extending an expired subscription clears `canceled_at`; entering the grace
  window writes an audit row (#20).
- **Attribution**: issuing a license to an existing customer now records the
  partner on both the customer and the subscription (#20).
- **Invoicing**: voiding an uncollectible invoice is rejected, and
  `finalize=True` emits an `invoice.finalized` outbox event (#20).
- **API transactions**: the request transaction now commits (or rolls back)
  before the response is sent, so a failed commit is no longer reported as
  success (#20).
- **Outbox**: the dispatcher rolls the session back when delivery raises an
  unexpected error (#20).
- **CLI**: `seed`/`report`/`audit` report configuration errors cleanly instead
  of raising a traceback (#20).

### Added
- **Documentation site** built with **Astro + Starlight** (the stack behind
  `docs.astro.build`): a quick start, a step-by-step tutorial, guides for every
  subsystem, deployment and reference pages, an architecture section, and an
  FAQ.
- **Agent skill** shipped as the `billing-engine-skill` npm package: a
  `SKILL.md` with the API cheatsheet, locked rules, and pitfalls, plus a
  dependency-free installer (`npx billing-engine-skill`). A byte-for-byte copy
  is served on the docs site with one-click copy/download.
- `scripts/sync_skill.py` and an integrity test to keep the npm skill and its
  docs copies in sync.
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
