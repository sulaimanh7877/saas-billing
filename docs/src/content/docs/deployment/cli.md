---
title: Command line
description: Use the billing CLI for migrations, demo seeding, reports, and audits.
---

The `billing` command covers migrations, demo seeding, reports, and audits. It
reads `BILLING_DSN` and `BILLING_TABLE_PREFIX` from the environment, or accepts
`--dsn` and `--prefix`.

```bash
billing --help
```

## Commands

### `version`

```bash
billing version
```

### `migrate`

Applies pending migrations. Idempotent.

```bash
billing migrate --dsn "postgresql+psycopg://user:pass@localhost/mysaas" --prefix acme_
# applied migrations: 0001_initial
```

A table prefix is **required**; omitting it exits with a parameter error.

### `seed`

Creates demo data — a feature, a plan and version, a customer, and a
subscription. Migrations run first.

```bash
billing seed --dsn "sqlite:///demo.db" --prefix acme_
# plan_version=01H...
# customer=01H...
# subscription=01H... status=trialing
```

### `report`

Prints headline metrics.

```bash
billing report --dsn "sqlite:///demo.db" --prefix acme_ --currency USD
# customers: 1
# mrr_minor: 2900
# subscriptions: 1
```

### `audit`

Prints recent audit-log entries, optionally filtered.

```bash
billing audit --dsn "sqlite:///demo.db" --prefix acme_ --entity-type subscription --limit 20
```

## Environment variables

```bash
export BILLING_DSN="postgresql+psycopg://user:pass@localhost/mysaas"
export BILLING_TABLE_PREFIX="acme_"

billing migrate
billing seed
billing report
```

:::note[CLI vs server config]

The CLI builds a minimal `EngineConfig` from `--dsn`/`--prefix` only. The
standalone server additionally reads `BILLING_DEFAULT_CURRENCY`,
`BILLING_TRIAL_DAYS`, and `BILLING_GRACE_PERIOD_DAYS`.

:::

## Exit codes

- `0` — success
- `1` — a `BillingError` (most commonly a missing prefix/DSN)
- `2` — invalid CLI usage (Typer/Click)

## Next

- [Docker](/saas-billing/deployment/docker/)
- [Embedded library](/saas-billing/deployment/embedded/)
