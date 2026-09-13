---
title: FAQ
description: Answers to common questions about databases, prefixes, money, renewals, entitlements, and partner licensing.
---

## Does it need its own database?

No. The engine connects to **your** database and creates only its own prefixed
tables beside yours. With PostgreSQL you can also point it at a separate
database or schema if you prefer.

## Why is a table prefix required?

So the engine can never collide with your schema. It is applied to every table,
index, and constraint — not just table names — because constraint/index scoping
differs across PostgreSQL, MySQL, and SQLite. See
[Prefix strategy](/saas-billing/architecture/prefix-strategy/).

## Why can't I use two prefixes in one process?

v0.2 resolves the prefix once per process and rejects a second, different prefix
with `ConfigurationError` instead of clobbering the first engine's tables. Use
one process (or one service instance) per deployment. For tests, call
`BillingEngine.reset_process_state()`.

## Can I use floats for money?

No. All money is **integer minor units** plus an ISO 4217 currency code.
Multiply by 100 at the edge and keep integers internally. `2900 USD` is `$29.00`.

## Is there a live payment gateway?

Not in v0.2. Billing is manual/invoice only — you create invoices and record
offline payments (transfer, cash, other). The provider seam is reserved for a
future Stripe adapter.

## How do renewals happen?

Explicitly. Call `services.subscriptions.process_due()` from a scheduler or cron
job at least daily. Nothing renews on its own. Trials convert, periods roll, and
cancellations take effect during that run.

## How do trials and grace periods work?

A subscription's effective trial is the explicit `trial_days` on creation, then
the plan version's `trial_days`, then `EngineConfig.trial_days`. If the effective
trial is greater than zero, the subscription starts `trialing`. With
`grace_period_days > 0`, a lapsed subscription first enters `past_due` (still
granting access) before it expires.

## How do entitlements resolve?

**Customer override → subscription override → plan entitlement → feature
default**, skipping expired overrides. Use `can()` for a boolean decision and
`limit()` for a ceiling. See [Entitlements](/saas-billing/guides/entitlements/).

## Are the timestamps UTC?

Yes, always timezone-aware UTC. `EngineConfig` accepts only `timezone="UTC"`.

## Can I edit a plan after customers subscribe?

Not in place. Plan versions are immutable — publish a new version instead. Live
subscriptions keep pointing at the version they started on. Use
`change_plan()` to move a specific subscription to a new version.

## Does `change_plan` prorate?

No, not in this version. The switch is immediate and the next renewal uses the
new plan's interval. Proration is on the roadmap.

## What happens when I revoke a partner license?

The license stops counting toward channel revenue, but ledger entries are **not**
automatically reversed. Record an offsetting entry or a partner payment. See
[Partners](/saas-billing/guides/partners/).

## How do I know my database won't be altered?

The engine creates and migrates only its own prefixed tables. It never issues
DDL against other tables. You can confirm the ownership boundary by reviewing
the prefix-aware migrations in `migrations/`.

## Which databases are supported?

PostgreSQL, MySQL/MariaDB, and SQLite. Report queries and migrations are tested
across all three. Install the driver for your database separately — the core
package does not bundle one.

## Can my coding agent use it?

Yes — there is a ready-made agent skill published to npm. See
[Use with a coding agent](/saas-billing/guides/agent-skill/).

## Where do I report bugs or request features?

Open an issue at
[github.com/sulaimanh7877/saas-billing/issues](https://github.com/sulaimanh7877/saas-billing/issues).
