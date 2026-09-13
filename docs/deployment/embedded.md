# Embedded library

Run the engine in-process, sharing your application's database connection. This
is the most direct integration and needs no extra service.

## Create once, reuse

Construct a single `BillingEngine` at process start — it holds the SQLAlchemy
engine and connection pool.

```python title="billing.py"
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(
        dsn="postgresql+psycopg://user:pass@localhost/mysaas",
        table_prefix="acme_",
        default_currency="USD",
        trial_days=14,
        grace_period_days=3,
    )
)
```

!!! warning "One prefix per process"

    A process serves one prefix. A second `BillingEngine` with a different
    prefix raises `ConfigurationError`. For tests, call
    `BillingEngine.reset_process_state()` between cases, or build a fresh engine
    with the same prefix.

## Reuse an existing engine

If your app already manages a SQLAlchemy `Engine` (custom pool, IAM auth,
proxies), hand it over instead of a DSN:

```python
from sqlalchemy import create_engine

config = EngineConfig(engine=create_engine("postgresql+psycopg://..."), table_prefix="acme_")
billing = BillingEngine(config)
```

## Migrate

```python
billing.migrate()          # apply pending migrations, idempotent
```

`billing.create_all()` / `billing.drop_all()` exist for tests and throwaway
databases; prefer `migrate()` everywhere else.

## Transactions

Every mutation happens inside a transaction, which also carries the audit and
outbox rows.

```python
with billing.transaction() as services:
    customer = services.customers.create(str(user.id), email=user.email)
    services.subscriptions.create(customer.id, version.id)
    # commit on exit; rollback on any exception
```

Do not hold a transaction open across slow I/O (HTTP calls, file uploads). Keep
the block tight so row locks are released quickly.

## Recording the actor

```python
from billing_engine.services.context import Actor

actor = Actor(type="user", id=str(user.id), source="embedded", ip=request.client.host)

with billing.transaction() as services:
    services.subscriptions.cancel(sub_id, reason="churn", actor=actor)
```

## Mount the REST router in your own app

You can have both: embedded calls for internal code, and HTTP for other
services. Mount the router into your existing FastAPI app.

```python
from fastapi import FastAPI

from billing_engine.adapters.api.app import create_app, router

app = FastAPI()
# Option A: build a sub-app with the engine and auth wired up.
app.mount("/billing", create_app(billing, api_key="secret"))

# Option B: include the bare router (you provide app.state.engine / app.state.api_key).
app.state.engine = billing
app.state.api_key = "secret"
app.include_router(router, prefix="/billing")
```

## Nightly job

```python
def run_billing_job() -> None:
    with billing.transaction() as services:
        services.subscriptions.process_due()
```

Register it with your scheduler (APScheduler, Celery beat, cron, a worker
process). Never call it inside a request handler.

## Testing

Use an in-memory SQLite engine with a static pool:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
billing = BillingEngine(EngineConfig(engine=engine, table_prefix="test_"))
billing.migrate()
```

For dialect-sensitive behavior (migrations, aggregate reports, allocation
concurrency), run against real PostgreSQL and MySQL — see the project's
integration tests.

## Next

- [Command line](cli.md)
- [Standalone & REST](rest.md)
