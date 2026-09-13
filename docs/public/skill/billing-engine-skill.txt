---
name: billing-engine
description: >
  Integrate and operate billing-engine (the billing_engine Python package) for
  subscriptions, entitlements/feature gating, manual invoices, credits, audit,
  reporting, and channel/partner license sales. Use this skill whenever a task
  involves adding billing, plans/pricing, trials, feature access checks,
  subscription lifecycle (extend/cancel/pause), invoices/payments, credits, or
  partner/reseller distribution to a Python SaaS.
license: MIT
metadata:
  package: billing-engine
  language: python
  docs: https://sulaimanh7877.github.io/saas-billing/
  repository: https://github.com/sulaimanh7877/saas-billing
---

# billing-engine

A self-hostable Python engine that provides billing, subscriptions,
entitlements, audit, analytics, and channel/partner sales for any SaaS. It runs
**on the host app's existing SQL database** and manages only its own
**prefixed** tables. Ships as an embedded library, a standalone FastAPI service,
and a Typer CLI.

<!-- --8<-- [start:docs] -->

## When to use this skill

Load this skill when the task is to:

- add plans, prices, trials, or subscriptions to a Python app;
- gate a feature/module or enforce a seat/quota limit;
- manage the subscription lifecycle (extend, pause, cancel, change plan);
- create manual invoices, record offline payments, or manage credits;
- sell licenses through distributors, agents, or resellers;
- build reports, audit trails, or webhooks for billing events.

## Golden rules (do not break these)

1. **Money is integer minor units + ISO currency.** `2900` = `$29.00`. Never
   introduce floats for money.
2. **All timestamps are UTC and timezone-aware.** Use `datetime(..., tzinfo=UTC)`.
3. **`table_prefix` is required and has no default.** It is normalized to end
   with one underscore (`acme` → `acme_`).
4. **All mutations go through `billing.transaction()`.** The block commits on
   success and rolls back on error; audit + outbox rows are written in the same
   transaction.
5. **Never edit a published plan version.** Create a new version instead; live
   subscriptions keep pointing at theirs.
6. **Renewals are explicit.** Call `services.subscriptions.process_due()` from a
   scheduler. Nothing renews itself.
7. **One prefix per process.** A second `BillingEngine` with a different prefix
   raises `ConfigurationError`.
8. **v0.2 has no live payment gateway.** Billing is manual/invoice only.
9. **Do not hand-write SQL or touch prefixed tables directly.** Use services.

## Install and configure

```bash
pip install billing-engine
# then the driver for the target DB:
pip install "psycopg[binary]"   # PostgreSQL
pip install "pymysql"           # MySQL/MariaDB
# SQLite is built into Python
```

```python
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(
        dsn="postgresql+psycopg://user:pass@localhost/mysaas",  # or engine=<Engine>
        table_prefix="acme_",
        default_currency="USD",
        trial_days=14,          # fallback when a plan sets none
        grace_period_days=3,    # access window after a period ends
    )
)
billing.migrate()   # creates ONLY the acme_* tables; idempotent
```

Provide exactly one of `dsn` or `engine`. Reuse an existing SQLAlchemy engine by
passing `engine=...`.

## Minimal embedded flow

```python
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
    allowed = services.entitlements.can(customer.id, "reports")
```

The `Services` bundle exposes: `customers`, `catalog`, `subscriptions`,
`entitlements`, `invoices`, `credits`, `reports`, `partners`, `licenses`,
`partner_accounts`, and `uow` (repositories, including `uow.audit` and
`uow.events`).

## API cheatsheet

### Customers

```python
services.customers.create(external_id, email=..., name=..., currency=..., attributes=..., partner_id=...)
services.customers.get(customer_id)
services.customers.get_by_external_id(external_id)   # -> Customer | None
services.customers.update(customer_id, email=..., name=..., attributes=...)
services.customers.list(limit=100, offset=0)
```

### Catalog

```python
services.catalog.create_feature(key, name=..., value_type="boolean|limit|meter", default_value=0)
services.catalog.create_plan(key, name=..., product_id=...)
services.catalog.create_plan_version(plan_id, prices=[...], trial_days=0, entitlements=[...], is_published=True)
services.catalog.create_custom_plan(customer_id, name=..., prices=[...], entitlements=[...])
services.catalog.set_entitlements(plan_version_id, [{"feature_key": ..., "value": 1, "limit_value": ...}])
services.catalog.get_plan_by_key(key)
services.catalog.list_prices(plan_version_id)
```

Price entry: `{"amount_minor": int, "currency": "USD", "interval": "month"|"year"|"one_time"}`.

### Subscriptions

```python
services.subscriptions.create(customer_id, plan_version_id, price_id=None, currency=None, trial_days=None, quantity=1, collection_method="manual", start_at=None)
services.subscriptions.get(sub_id)
services.subscriptions.list_for_customer(customer_id)

# lifecycle
services.subscriptions.extend(sub_id, days=14, reason="goodwill")   # or months=/until=
services.subscriptions.extend_trial(sub_id, days=7, reason=...)
services.subscriptions.pause(sub_id, until=None, reason=...)
services.subscriptions.resume(sub_id, reason=...)
services.subscriptions.cancel(sub_id, at_period_end=True, reason=...)  # at_period_end=False for immediate
services.subscriptions.reactivate(sub_id, reason=...)
services.subscriptions.change_plan(sub_id, plan_version_id, reason=...)  # no proration
services.subscriptions.renew(sub_id)
services.subscriptions.process_due()          # scheduler: renew/expire everything due
services.subscriptions.list_adjustments(sub_id)  # via uow: services.uow.subscriptions.list_adjustments
```

Statuses: `trialing`, `active`, `past_due`, `paused`, `canceled`, `expired`.
Access is granted for `trialing`, `active`, and `past_due`.

### Entitlements

```python
services.entitlements.can(customer_id, feature_key)     # -> bool
services.entitlements.limit(customer_id, feature_key)   # -> int | None
services.entitlements.value(customer_id, feature_key)   # -> int
services.entitlements.resolve(customer_id, feature_key)
services.entitlements.list_for_customer(customer_id)
services.entitlements.set_customer_override(customer_id, feature_key, value=1, limit_value=None, expires_at=None, reason=...)
services.entitlements.set_subscription_override(subscription_id, feature_key, ...)
services.entitlements.remove_override(override_id)
```

Resolution order: **customer override → subscription override → plan entitlement
→ feature default** (expired overrides skipped).

### Invoices, payments, credits

```python
services.invoices.create(customer_id, lines=[{"description":..., "quantity":..., "unit_amount_minor":...}], currency=None, due_date=None, subscription_id=None, notes=None, finalize=False)
services.invoices.create_from_subscription(subscription_id, quantity=None, due_date=None, description=None)
services.invoices.add_line(invoice_id, description, quantity=1, unit_amount_minor=0)   # draft only
services.invoices.finalize(invoice_id)
services.invoices.void(invoice_id, reason=...)
services.invoices.mark_uncollectible(invoice_id)
services.invoices.record_payment(invoice_id, amount_minor, method="cash|transfer|other", reference=None)
services.invoices.list_for_customer(customer_id)

services.credits.grant(customer_id, amount_minor, reason=...)
services.credits.consume(customer_id, amount_minor, reason=..., reference_type=..., reference_id=...)
services.credits.refund(customer_id, amount_minor, reason=...)
services.credits.balance(customer_id)
services.credits.list_entries(customer_id)
```

Invoice statuses: `draft → open → paid | void | uncollectible`. Only `open`
invoices are payable; overpayment is rejected.

### Partners & channel

```python
partner = services.partners.create(name, type="distributor|agent|reseller", external_id=None, currency=None, parent_partner_id=None)
rule = services.partners.create_commission_rule(basis="flat|tiered|multi_level", rate_bps=2000, tiers=None, levels=None)
agreement = services.partners.create_agreement(partner.id, money_model="wholesale_prepaid|consignment|agency_commission", currency=None, discount_bps=0, plan_id=None, commission_rule_id=None)

allocation = services.licenses.allocate(partner.id, plan_version_id, quantity, agreement_id=None, parent_allocation_id=None)
services.licenses.available(allocation)
license_ = services.licenses.issue(allocation_id, customer_id=None, external_id=None, email=None, name=None)  # creates customer + subscription
services.licenses.revoke(license_id, reason=...)
services.licenses.expire(license_id)

services.partner_accounts.balances(partner.id)     # {'receivable': 2900}
services.partner_accounts.prefund(partner.id, amount_minor, reason=...)
services.partner_accounts.record_payment(partner.id, amount_minor, method=...)
services.partner_accounts.generate_statement(partner.id, period_start, period_end, currency=None)
services.partner_accounts.create_invoice(partner.id, lines=[...], finalize=False)
services.partner_accounts.create_payout(partner.id, lines=[{"description":..., "amount_minor":...}])
services.partner_accounts.pay_payout(payout_id, reference=...)
```

Money models: `wholesale_prepaid` (prepaid drawn down), `consignment`
(receivable grows), `agency_commission` (gross receivable minus commission).
The wholesale amount is `gross * (10000 - discount_bps) / 10000`.

### Reporting, audit, events

```python
services.reports.overview("USD")
services.reports.subscription_counts()
services.reports.revenue_by_plan("USD")
services.reports.outstanding_invoices()
services.reports.feature_adoption()
services.uow.reports.channel_revenue("USD")

services.uow.audit.list(entity_type=None, entity_id=None, action=None, actor_id=None, limit=100, offset=0)
services.uow.events.list_pending(utcnow(), limit=100)
```

## Transactions and actors

```python
from billing_engine.services.context import Actor

actor = Actor(type="user", id=str(user.id), source="embedded", ip=None)
with billing.transaction() as services:
    services.subscriptions.cancel(sub_id, reason="churn", actor=actor)
```

Keep transactions tight; do not perform network I/O inside a transaction.

## Background job (required)

```python
def run_due() -> None:
    with billing.transaction() as services:
        services.subscriptions.process_due()
```

Register with cron/Celery/APScheduler. Run it at least daily.

## Errors

Catch `BillingError`; specific types map to HTTP status in the REST adapter.

| Error | HTTP | Meaning |
|---|---|---|
| `ValidationError` | 400 | Bad input / business rule |
| `NotFoundError` | 404 | Missing entity |
| `EntitlementError` | 403 | Feature/limit denial |
| `ConflictError` | 409 | State conflict (unpublished version, overpay, insufficient credit) |
| `AllocationExhaustedError` | 409 | No licenses left |
| `ConfigurationError` | 500 | Bad engine wiring |

## Testing pattern

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from billing_engine import BillingEngine, EngineConfig

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
billing = BillingEngine(EngineConfig(engine=engine, table_prefix="test_"))
billing.migrate()
```

Call `BillingEngine.reset_process_state()` between tests that build engines with
different prefixes. Use real PostgreSQL/MySQL for migration, aggregate-report,
and allocation-concurrency tests.

## Common pitfalls

- Forgetting `billing.migrate()` → tables missing.
- Reusing one transaction across many unrelated operations → long locks.
- Expecting auto-renewal → schedule `process_due()`.
- Mutating a plan version to change price → create a new version.
- Assuming `change_plan` prorates → it does not.
- Using floats or non-integer minor units for money.
- Using naive datetimes instead of UTC-aware ones.
- Revoking a license and expecting ledger reversal → post an offsetting entry.
- Constructing two engines with different prefixes in one process.

## Reference

- Docs: https://sulaimanh7877.github.io/saas-billing/
- Repository: https://github.com/sulaimanh7877/saas-billing
- Runnable examples: https://github.com/sulaimanh7877/saas-billing/tree/main/examples

<!-- --8<-- [end:docs] -->
