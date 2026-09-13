# Installation

## Requirements

- **Python 3.11+**
- A supported database:
    - PostgreSQL 12+
    - MySQL 8+ / MariaDB 10.5+
    - SQLite 3.35+
- A **table prefix** you choose (for example `acme_`). It is required and has no
  default.

## Install the library

=== "pip"

    ```bash
    pip install billing-engine
    ```

=== "uv"

    ```bash
    uv add billing-engine
    ```

=== "Poetry"

    ```bash
    poetry add billing-engine
    ```

The core package depends only on SQLAlchemy 2.0, Pydantic v2, FastAPI, and Typer.
Database drivers are **not** bundled — install the one for your database:

=== "PostgreSQL"

    ```bash
    pip install "psycopg[binary]"
    ```

=== "MySQL / MariaDB"

    ```bash
    pip install "pymysql"
    ```

=== "SQLite"

    ```bash
    # Built into the Python standard library.
    ```

## Verify the install

```bash
billing version
```

You should see the installed version (for example `0.2.0`). The same value is
exported as `billing_engine.__version__`.

## Configuration at a glance

Everything flows through a single `EngineConfig`. The only required field is
`table_prefix`; provide exactly one of `dsn` or an existing SQLAlchemy `engine`.

```python
from sqlalchemy import create_engine

from billing_engine import BillingEngine, EngineConfig

# Option A: a DSN string (the engine creates the connection pool for you).
config = EngineConfig(
    dsn="postgresql+psycopg://user:pass@localhost/mysaas",
    table_prefix="acme_",
    default_currency="USD",
    trial_days=14,
    grace_period_days=3,
)

# Option B: reuse an engine you already manage (connection pooling, IAM auth, etc.).
config = EngineConfig(
    engine=create_engine("postgresql+psycopg://user:pass@localhost/mysaas"),
    table_prefix="acme_",
)
```

See [Configuration](../reference/configuration.md) for every option and the
[prefix strategy](../architecture/prefix-strategy.md) for naming rules.

## Create the schema

The engine creates **only its own prefixed tables**. It never touches your
existing schema.

```python
billing = BillingEngine(config)
billing.migrate()
```

Or from the command line:

```bash
billing migrate --dsn "postgresql+psycopg://user:pass@localhost/mysaas" --prefix acme_
```

!!! warning "One prefix per process"

    In v0.2 a process serves **one** prefix. Constructing a second
    `BillingEngine` with a different prefix raises `ConfigurationError` instead
    of silently renaming the first engine's tables. This matches the embedded
    and standalone deployment models. See
    [ADR 0001](https://github.com/sulaimanh7877/saas-billing/blob/main/docs/adr/0001-prefix-strategy.md).

## Next steps

- [Quick start](quickstart.md) — a minimal end-to-end example.
- [Tutorial](tutorial.md) — build a feature-gated SaaS step by step.
- [Use with a coding agent](../guides/agent-skill.md) — install the npm skill.
