# Configuration

All runtime settings flow through a single immutable `EngineConfig`. There is no
global state and no module-level database connection.

```python
from billing_engine import EngineConfig

config = EngineConfig(
    table_prefix="acme_",
    dsn="postgresql+psycopg://user:pass@localhost/mysaas",
)
```

## Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `table_prefix` | `str` | **required** | Normalized to end with exactly one `_` |
| `dsn` | `str \| None` | `None` | Exactly one of `dsn` / `engine` |
| `engine` | `Engine \| None` | `None` | A live SQLAlchemy engine to reuse |
| `default_currency` | `str` | `"USD"` | Uppercased; must match `^[A-Z]{3}$` |
| `grace_period_days` | `int` | `0` | Non-negative; access window after a period ends |
| `trial_days` | `int` | `0` | Non-negative; fallback trial when a plan sets none |
| `timezone` | `str` | `"UTC"` | v0.2 supports UTC only |

## Validation rules

- **Exactly one** of `dsn` or `engine` must be provided.
- `table_prefix` is stripped and normalized: `"acme"` and `"acme_"` both become
  `"acme_"`. It must be a safe identifier fragment — lowercase letters, digits,
  and underscores, not starting with a digit.
- `default_currency` is uppercased and must be a three-letter ISO 4217 code.
- `grace_period_days` and `trial_days` must be non-negative integers (booleans
  are rejected).
- `timezone` must be `UTC`; anything else raises `ConfigurationError`.

Violations raise `ConfigurationError` at construction time — fail fast, before
any database work.

## Helpers

```python
config.namer          # PrefixNamer bound to this prefix
config.build_engine() # returns the provided engine or creates one from the DSN
```

## Environment variables (standalone server & CLI)

| Variable | Used by | Required | Default |
|---|---|---|---|
| `BILLING_DSN` | server, CLI | ✅ server | — |
| `BILLING_TABLE_PREFIX` | server, CLI | ✅ server | — |
| `BILLING_API_KEY` | server | — | none |
| `BILLING_DEFAULT_CURRENCY` | server | — | `USD` |
| `BILLING_TRIAL_DAYS` | server | — | `0` |
| `BILLING_GRACE_PERIOD_DAYS` | server | — | `0` |

The CLI reads only `BILLING_DSN` and `BILLING_TABLE_PREFIX` (or `--dsn` /
`--prefix`).

## Defaults in practice

- **`trial_days`**: a subscription's effective trial is the explicit
  `trial_days` on `subscriptions.create()`, else the plan version's `trial_days`,
  else this config default.
- **`grace_period_days`**: with a value greater than zero, a subscription whose
  period lapses first enters `past_due` with access, then expires when grace
  ends.

## Next

- [Errors](errors.md)
- [Prefix strategy](../architecture/prefix-strategy.md)
