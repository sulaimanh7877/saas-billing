# Invoices & credits

v0.2 is **manual billing only** — there is no live payment gateway. You create
invoices, record offline payments (transfer, cash, other), and manage a customer
credit ledger. The provider seam is reserved for a future Stripe adapter.

## Invoices

### Create

=== "From a subscription"

    Builds an open invoice from the subscription's current plan and price.

    ```python
    invoice = services.invoices.create_from_subscription(
        subscription.id,
        quantity=None,               # defaults to subscription.quantity
        due_date=None,
        description=None,
    )
    print(invoice.status)  # "open"
    ```

=== "Manual / custom"

    ```python
    draft = services.invoices.create(
        customer.id,
        lines=[{"description": "Onboarding", "quantity": 1, "unit_amount_minor": 15000}],
        currency="USD",             # optional, defaults to the customer's currency
        due_date=datetime(2026, 10, 1, tzinfo=UTC),
        notes="PO 9931",
        finalize=False,             # keep it a draft for now
    )
    services.invoices.add_line(draft.id, "Extra seat", quantity=2, unit_amount_minor=500)
    services.invoices.finalize(draft.id)
    ```

Only `draft` invoices are editable. `create_from_subscription` finalizes for
you; `create` starts as a draft unless you pass `finalize=True`.

### Lifecycle

```
draft ──finalize──▶ open ──pay in full──▶ paid
  │                  │
  └──void──▶ void    ├──void──▶ void
                     └──mark_uncollectible──▶ uncollectible
```

| Method | From → to |
|---|---|
| `finalize(invoice_id)` | `draft` → `open` (stamps `issue_date`) |
| `void(invoice_id, reason=...)` | anything but `paid` → `void` |
| `mark_uncollectible(invoice_id)` | `open` → `uncollectible` |
| `record_payment(...)` | `open` → `paid` when fully paid |

### Record a payment

Only **open** invoices are payable, and overpayment is rejected:

```python
services.invoices.record_payment(
    invoice.id,
    1000,
    method="transfer",         # cash | transfer | other
    reference="WIRE-9931",
    received_at=None,          # defaults to now
)
```

Partial payments keep the invoice `open` and accumulate `amount_paid_minor`;
paying the remaining balance flips it to `paid` and stamps `paid_at`. Payments
are their own audited rows.

### Read

```python
services.invoices.get(invoice_id)
services.invoices.list_for_customer(customer.id)
services.invoices.list_lines(invoice_id)
services.invoices.list_payments(invoice_id)
```

## Credits

Credits are an append-only ledger per customer and currency, each entry storing
the resulting balance.

```python
# Grant
services.credits.grant(customer.id, 1000, reason="referral bonus")

# Spend (fails with ConflictError if the balance is insufficient)
services.credits.consume(
    customer.id, 290, reason="invoice offset",
    reference_type="invoice", reference_id=invoice.id,
)

# Return previously consumed or unused credit
services.credits.refund(customer.id, 100, reason="goodwill")

# Inspect
services.credits.balance(customer.id)
for entry in services.credits.list_entries(customer.id):
    print(entry.entry_type, entry.amount_minor, entry.balance_after_minor)
```

| Operation | Effect on balance |
|---|---|
| `grant` | `+amount` |
| `refund` | `+amount` |
| `consume` | `-amount` (must be covered) |

All amounts are **positive** in the call; `consume` stores the negative entry
internally.

## Errors

| Situation | Error |
|---|---|
| Adding a line to a non-draft invoice | `ConflictError` |
| Finalizing a non-draft invoice | `ConflictError` |
| Paying anything but an open invoice | `ConflictError` |
| Payment exceeds the remaining balance, or is non-positive | `ValidationError` |
| Voiding a paid invoice | `ConflictError` |
| Marking a non-open invoice uncollectible | `ConflictError` |
| Consuming more credit than available | `ConflictError` |

## Next

- [Partners & channel](partners.md) — partner invoices, payments, and payouts.
- [Reporting](reporting.md) — outstanding invoices and receivables.
