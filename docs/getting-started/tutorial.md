# Tutorial: build a feature-gated SaaS

This tutorial builds **Acme Notes**, a tiny note-taking SaaS, and adds billing
and access control with the engine. By the end you will have:

- A catalog with plans, prices, and features.
- Signups that start a free trial.
- Feature gating in a FastAPI endpoint.
- Subscription lifecycle — extensions, cancellations, and a nightly job.
- Manual invoicing, offline payments, and credits.
- Reporting and an audit trail.
- *(Optional)* selling through a reseller partner.

The whole tutorial runs on SQLite so you can copy-paste it. The API is identical
on PostgreSQL and MySQL.

!!! note "Prerequisites"

    ```bash
    pip install billing-engine
    ```

    If you get stuck, the runnable [`examples/`](https://github.com/sulaimanh7877/saas-billing/tree/main/examples)
    directory contains small scripts for each scenario.

---

## Part 0 — Set up the engine

Create `acme_notes/engine.py`:

```python title="acme_notes/engine.py"
from billing_engine import BillingEngine, EngineConfig

billing = BillingEngine(
    EngineConfig(
        dsn="sqlite:///acme_notes.db",
        table_prefix="acme_",   # required, no default
        default_currency="USD",
        trial_days=14,          # fallback trial when a plan has none
        grace_period_days=3,    # access window after a period ends
    )
)
```

Create the tables once at startup (or run `billing migrate` in your deploy step):

```python
billing.migrate()
```

!!! tip "Why the prefix?"

    The engine lives in **your** database, beside **your** tables. Every table,
    index, and constraint it creates is named with `acme_`, so it can never
    collide with your schema. You can rename it to anything (for example
    `billing_`) as long as it is stable.

---

## Part 1 — Model your product

Think in engine terms: a **feature** is something you gate, and a **plan
version** is an immutable snapshot of a plan's price and entitlements. You never
edit a published version — you publish a new one, which keeps live
subscriptions stable.

```python title="acme_notes/setup_catalog.py"
from acme_notes.engine import billing

with billing.transaction() as services:
    # Features you gate in the app.
    services.catalog.create_feature("notes", name="Notes")
    services.catalog.create_feature("reports", name="Reports")
    services.catalog.create_feature("seats", name="Seats", value_type="limit", default_value=1)

    free = services.catalog.create_plan("free", "Free")
    pro = services.catalog.create_plan("pro", "Pro")

    services.catalog.create_plan_version(
        free.id,
        prices=[{"amount_minor": 0, "currency": "USD", "interval": "month"}],
        entitlements=[
            {"feature_key": "notes", "limit_value": None},   # boolean grant
        ],
    )

    services.catalog.create_plan_version(
        pro.id,
        prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
        trial_days=14,
        entitlements=[
            {"feature_key": "notes", "limit_value": 1},
            {"feature_key": "reports", "limit_value": 1},
            {"feature_key": "seats", "value": 1, "limit_value": 5},
        ],
    )
    print("catalog ready")
```

- `boolean` features use `value` / `limit_value` as an on/off switch.
- `limit` features carry a numeric ceiling you read with `limit()`.

---

## Part 2 — Sign up a customer and start a trial

A **customer** is linked to your app by a single `external_id` (your user or
tenant id). Creating a subscription with a plan that has `trial_days` starts it
in `trialing`.

```python title="acme_notes/signup.py"
from acme_notes.engine import billing

def signup(user_id: str, email: str) -> str:
    """Create the customer + a Pro trial. Returns the subscription id."""
    with billing.transaction() as services:
        try:
            customer = services.customers.create(user_id, email=email)
        except Exception:
            # Already signed up: reuse the existing customer.
            customer = services.customers.get_by_external_id(user_id)
            assert customer is not None

        pro = services.catalog.get_plan_by_key("pro")
        versions = services.uow.catalog.list_plan_versions(pro.id)
        latest = versions[-1]

        subscription = services.subscriptions.create(customer.id, latest.id)
        print(f"{email}: {subscription.status} until {subscription.current_period_end:%Y-%m-%d}")
        return subscription.id
```

Call it from your signup flow:

```python
signup("user-42", "ada@example.com")
```

---

## Part 3 — Gate features in your app

The engine is not in your request path's critical logic — you call it for a
decision. Wrap access checks in a small helper and use it everywhere you gate.

```python title="acme_notes/access.py"
from acme_notes.engine import billing

class UpgradeRequired(Exception):
    """Raised when the customer's plan does not include a feature."""

def _customer_id(external_id: str) -> str | None:
    with billing.transaction() as services:
        customer = services.customers.get_by_external_id(external_id)
        return customer.id if customer else None

def can(external_id: str, feature: str) -> bool:
    customer_id = _customer_id(external_id)
    if customer_id is None:
        return False
    with billing.transaction() as services:
        return services.entitlements.can(customer_id, feature)

def limit(external_id: str, feature: str) -> int | None:
    customer_id = _customer_id(external_id)
    if customer_id is None:
        return 0
    with billing.transaction() as services:
        return services.entitlements.limit(customer_id, feature)

def require(external_id: str, feature: str) -> None:
    if not can(external_id, feature):
        raise UpgradeRequired(feature)
```

Now use it in a FastAPI endpoint:

```python title="acme_notes/api.py"
from fastapi import FastAPI, HTTPException

from acme_notes.access import UpgradeRequired, require

app = FastAPI()

@app.get("/reports")
def reports(user_id: str):
    try:
        require(user_id, "reports")
    except UpgradeRequired:
        raise HTTPException(status_code=402, detail="Upgrade to Pro for reports")
    return {"report": "..."}
```

!!! tip "Resolution order"

    `can()` and `limit()` resolve in a fixed order:
    **customer override → subscription override → plan entitlement → feature
    default**. See [Entitlements](../guides/entitlements.md) for the details and
    how to grant a one-off override.

---

## Part 4 — Run the lifecycle

### Extend a subscription (goodwill, outage, migration)

```python
with billing.transaction() as services:
    customer = services.customers.get_by_external_id("user-42")
    subscription = services.subscriptions.list_for_customer(customer.id)[0]
    services.subscriptions.extend(
        subscription.id, days=30, reason="service outage credit"
    )
```

You can also extend with `months=1`, `until=datetime(...)`, or push out a trial
with `extend_trial(subscription.id, days=7)`.

### Cancel at period end

```python
with billing.transaction() as services:
    services.subscriptions.cancel(subscription.id, at_period_end=True, reason="churn")
```

### The nightly job

Renewals and expirations are explicit. Call `process_due()` from a scheduler or
cron job; it renews everything due and expires what fell past its grace window.

```python title="acme_notes/nightly.py"
from acme_notes.engine import billing

def run_due() -> None:
    with billing.transaction() as services:
        renewed = services.subscriptions.process_due()
        print(f"renewed {len(renewed)} subscriptions")

if __name__ == "__main__":
    run_due()
```

!!! warning "Schedule it"

    Nothing renews itself. Run `process_due()` at least daily (hourly is fine
    too) so trials convert, periods roll, and cancellations take effect.

---

## Part 5 — Get paid

### Invoice from a subscription

```python
with billing.transaction() as services:
    invoice = services.invoices.create_from_subscription(subscription.id)
    print(invoice.total_minor, invoice.currency)  # 2900 USD
```

New invoices are created **open** by `create_from_subscription`. For custom
charges, build a draft and finalize it:

```python
with billing.transaction() as services:
    draft = services.invoices.create(
        customer.id,
        lines=[{"description": "Onboarding", "quantity": 1, "unit_amount_minor": 15000}],
        due_date=...,  # optional datetime
    )
    services.invoices.add_line(draft.id, "Extra seat", quantity=2, unit_amount_minor=500)
    services.invoices.finalize(draft.id)
```

### Record an offline payment

Only **open** invoices are payable, and you cannot overpay:

```python
with billing.transaction() as services:
    services.invoices.record_payment(invoice.id, 2900, method="transfer", reference="WIRE-9931")
    paid = services.invoices.get(invoice.id)
    print(paid.status, paid.amount_paid_minor)  # paid 2900
```

### Grant credits

Credits are an append-only ledger per customer and currency:

```python
with billing.transaction() as services:
    services.credits.grant(customer.id, 1000, reason="referral bonus")
    services.credits.consume(customer.id, 290, reference_type="invoice", reference_id=invoice.id)
    print(services.credits.balance(customer.id))  # 710
```

---

## Part 6 — Report and audit

```python
with billing.transaction() as services:
    print(services.reports.overview("USD"))
    print(services.reports.subscription_counts())
    print(services.reports.revenue_by_plan("USD"))
    print(services.reports.outstanding_invoices())

    for entry in services.uow.audit.list(entity_type="subscription", limit=5):
        print(entry.created_at, entry.action, entry.entity_id)
```

Every mutation has a matching audit row with before/after snapshots, the actor,
the source (`embedded`, `rest`, `webhook`, `job`), and any reason. Audit rows are
**append-only** — the engine never updates or deletes them.

---

## Part 7 — Optional: sell through a partner

Partners are distributors, agents, or resellers. You allocate a pool of licenses
for a plan version, and issuing a license creates the end customer, starts their
subscription, draws down the allocation, and posts partner ledger entries.

```python
with billing.transaction() as services:
    partner = services.partners.create("Northwind Reseller", type="reseller")

    rule = services.partners.create_commission_rule(basis="flat", rate_bps=2000)  # 20%
    agreement = services.partners.create_agreement(
        partner.id, money_model="consignment", commission_rule_id=rule.id
    )
    allocation = services.licenses.allocate(
        partner.id, latest.id, quantity=500, agreement_id=agreement.id
    )

    license_ = services.licenses.issue(
        allocation.id, external_id="end-customer-7", email="sam@example.com"
    )

    print(services.licenses.available(services.licenses.get_allocation(allocation.id)))  # 499
    print(services.partner_accounts.balances(partner.id))  # {'receivable': 2900}
```

See [Partners & channel](../guides/partners.md) for the three money models,
commission bases, and settlement (statements, invoices, payouts).

---

## Recap

You now have a working billing layer:

| Concern | Where |
|---|---|
| Catalog & prices | `services.catalog` |
| Signups & lifecycle | `services.subscriptions` |
| Access control | `services.entitlements` |
| Invoices, payments, credits | `services.invoices`, `services.credits` |
| Channel sales | `services.partners`, `services.licenses`, `services.partner_accounts` |
| Metrics | `services.reports` |
| Trail | `services.uow.audit`, `services.uow.events` |

### Production checklist

- [ ] Point `dsn` at PostgreSQL or MySQL and install the driver.
- [ ] Run `billing migrate` as a deploy step (it is idempotent).
- [ ] Schedule `process_due()`.
- [ ] Add a webhook receiver if you use the outbox.
- [ ] Set `BILLING_API_KEY` if you run the standalone service.
- [ ] Back up the `acme_*` tables along with your own.

Next: [Deployment](../deployment/embedded.md), [REST endpoints](../reference/rest-api.md),
or [use the coding-agent skill](../guides/agent-skill.md).
