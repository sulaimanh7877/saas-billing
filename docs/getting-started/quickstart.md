# Quick start

Five minutes from `pip install` to a feature-gated subscription.

## 1. Install

```bash
pip install billing-engine
```

SQLite is built into Python, so it is the fastest way to try the engine. For
production you will usually point it at PostgreSQL or MySQL — see
[Installation](installation.md).

## 2. Start the engine

```python title="quickstart.py"
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(dsn="sqlite:///billing.db", table_prefix="acme_")
)
billing.migrate()
```

`migrate()` creates **only** the `acme_*` tables. Your own tables are untouched.

## 3. Define features, a plan, and a price

```python
with billing.transaction() as services:
    # A feature you will gate in your app.
    services.catalog.create_feature("reports", name="Reports")

    plan = services.catalog.create_plan("pro", "Pro")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
        trial_days=14,
        entitlements=[{"feature_key": "reports", "limit_value": 1}],
    )
```

`amount_minor=2900` is **29.00 USD** — money is always integer minor units.

## 4. Create a customer and a subscription

```python
with billing.transaction() as services:
    customer = services.customers.create("user-42", email="ada@example.com")
    subscription = services.subscriptions.create(customer.id, version.id)
    print(subscription.status)  # "trialing" (14-day trial from the plan)
```

`"user-42"` is your app's user/tenant id. It is the only link the engine needs.

## 5. Gate a feature

```python
with billing.transaction() as services:
    if not services.entitlements.can(customer.id, "reports"):
        raise PermissionError("Upgrade required")

    seats = services.entitlements.limit(customer.id, "seats")  # None if unlimited
```

Call `can()` / `limit()` wherever your application checks access.

## 6. Extend, invoice, and pay

```python
with billing.transaction() as services:
    services.subscriptions.extend(subscription.id, days=14, reason="goodwill")

    invoice = services.invoices.create_from_subscription(subscription.id)
    services.invoices.record_payment(invoice.id, 2900, method="transfer")
    print(invoice.status)  # "paid"
```

## 7. Run your first report

```python
with billing.transaction() as services:
    print(services.reports.overview("USD"))
    # {'customers': 1, 'mrr_minor': 2900, 'subscriptions': 1, ...}
```

## Full script

```python title="quickstart.py"
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(EngineConfig(dsn="sqlite:///billing.db", table_prefix="acme_"))
billing.migrate()

with billing.transaction() as services:
    services.catalog.create_feature("reports", name="Reports")
    plan = services.catalog.create_plan("pro", "Pro")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
        trial_days=14,
        entitlements=[{"feature_key": "reports", "limit_value": 1}],
    )

with billing.transaction() as services:
    customer = services.customers.create("user-42", email="ada@example.com")
    subscription = services.subscriptions.create(customer.id, version.id)

with billing.transaction() as services:
    if not services.entitlements.can(customer.id, "reports"):
        raise PermissionError("Upgrade required")
    print("reports allowed:", services.entitlements.can(customer.id, "reports"))
    print("overview:", services.reports.overview("USD"))
```

Run it:

```bash
python quickstart.py
```

!!! tip "Everything in one transaction"

    `billing.transaction()` commits on success and rolls back on error. Every
    mutation also writes an append-only audit row and an outbox event **inside
    the same transaction**, so the trail can never drift from the data.

## Where to go next

- [Tutorial](tutorial.md) — build a complete feature-gated SaaS.
- [Subscriptions](../guides/subscriptions.md) — the full lifecycle and extensions.
- [Entitlements](../guides/entitlements.md) — overrides and resolution order.
- [Use with a coding agent](../guides/agent-skill.md) — let an agent write this for you.
