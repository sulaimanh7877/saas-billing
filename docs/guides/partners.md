# Partners & channel

Sell through **distributors**, **agents**, and **resellers**. You authorize a
partner with a pool of **licenses** for a plan version; issuing a license creates
the end customer, starts their subscription, consumes allocation capacity, and
posts the right entries to the partner ledger.

## Partners

```python
partner = services.partners.create(
    "Northwind Reseller",
    type="reseller",                 # distributor | agent | reseller
    external_id=None,                # optional link to your CRM
    email=None,
    phone=None,
    currency="USD",                  # optional, defaults to the engine currency
    parent_partner_id=None,          # hierarchy-ready
)
```

```python
services.partners.get(partner.id)
services.partners.get_by_external_id("crm-991")
services.partners.list_partners(limit=100, offset=0)
services.partners.set_status(partner.id, "inactive")   # active | inactive
```

The `parent_partner_id` self-reference makes the model hierarchy-ready; v0.2
operations are single-level.

## Commission rules

Rules are deployment-global and expressed in **basis points** (`2000` = 20%).

```python
# 20% flat
rule = services.partners.create_commission_rule(basis="flat", rate_bps=2000)

# Tiered by volume
rule = services.partners.create_commission_rule(
    basis="tiered",
    tiers=[{"threshold": 100, "rate_bps": 1500}, {"threshold": 500, "rate_bps": 2500}],
)

# Multi-level split
rule = services.partners.create_commission_rule(
    basis="multi_level",
    levels=[{"level": 1, "rate_bps": 2000}, {"level": 2, "rate_bps": 500}],
)
```

| Basis | Computation |
|---|---|
| `flat` | `amount * rate_bps / 10000` |
| `tiered` | Rate chosen from the tier table by volume |
| `multi_level` | Rate per partner level |

## Agreements

An agreement describes the pricing and money flow for one partner (optionally
scoped to a plan).

```python
agreement = services.partners.create_agreement(
    partner.id,
    money_model="consignment",
    currency="USD",
    discount_bps=1000,               # 10% off list = wholesale price
    plan_id=None,                    # None = applies to any plan
    commission_rule_id=rule.id,
    effective_from=None,
    effective_to=None,
)
```

### Money models

=== "`wholesale_prepaid`"

    The partner prepays a block; issuing draws down the prepaid balance.

    ```python
    services.partner_accounts.prefund(partner.id, 100_000, reason="Q3 top-up")
    ```

    Issuing posts a **negative** charge to the **prepaid** account and fails with
    `ConflictError` if the balance cannot cover the wholesale price.

=== "`consignment`"

    Licenses are granted on credit; issuing posts a **positive** charge to a
    **receivable** account (the partner owes the wholesale amount).

=== "`agency_commission`"

    The partner sells at list and keeps a commission. Issuing posts the **gross**
    to receivable and a **negative commission** entry, netting the receivable to
    the amount owed to you.

The wholesale amount is `gross * (10000 - discount_bps) / 10000`; with
`discount_bps=0` it equals list price.

## Allocations

An allocation authorizes a partner with N licenses for a plan version.
`available = quantity_allocated - quantity_issued`.

```python
allocation = services.licenses.allocate(
    partner.id,
    version.id,
    quantity=500,
    agreement_id=agreement.id,
    parent_allocation_id=None,       # hierarchy-ready
    effective_from=None,
    effective_to=None,
)

services.licenses.available(allocation)          # 500
services.licenses.get_allocation(allocation.id)
services.licenses.list_allocations(partner.id)
services.licenses.close_allocation(allocation.id)
```

## Issuing a license

Pass either an existing `customer_id` or an `external_id` to create one on the
fly. New customers are **attributed** to the partner automatically.

```python
license_ = services.licenses.issue(
    allocation.id,
    external_id="end-customer-7",    # or customer_id="01H..."
    email="sam@example.com",
    name="Sam",
    expires_at=None,
)

print(license_.status)               # "active"
print(license_.subscription_id)      # the subscription that was started
```

Issuing, in order:

1. Validates allocation capacity (rejects with `AllocationExhaustedError`) and
   takes a row lock so two concurrent issues cannot oversell.
2. Finds or creates the attributed end customer.
3. Posts the ledger entry(ies) for the agreement's money model — including the
   commission when an `agency_commission` rule applies.
4. Creates the subscription on the allocated plan version.
5. Increments `quantity_issued` and records an audit row + outbox event.

### Revoke and expire

```python
services.licenses.revoke(license_.id, reason="chargeback")
services.licenses.expire(license_.id)
```

!!! warning "Revocation does not reverse the ledger"

    `revoke()` marks the license and stops it counting toward channel revenue,
    but it does **not** unwind ledger entries. Record an offsetting ledger entry
    (or a partner payment) for the financial side.

## Partner accounts & ledger

Every partner has per-currency accounts of type `prepaid`, `receivable`, or
`payable`. The ledger is append-only.

```python
services.partner_accounts.balances(partner.id)          # {'receivable': 2900}
services.partner_accounts.accounts(partner.id)
services.partner_accounts.entries(partner.id, currency="USD")

# Money in
services.partner_accounts.prefund(partner.id, 50_000)
services.partner_accounts.record_payment(partner.id, 10_000, method="transfer")
```

Sign is from the **vendor's** perspective: a positive receivable means the
partner owes you; a positive prepaid means the partner has credit with you.

## Settlement: statements, invoices, payouts

=== "Statements"

    Summarize ledger activity for a period.

    ```python
    statement = services.partner_accounts.generate_statement(
        partner.id, period_start, period_end, currency="USD"
    )
    print(statement.opening_balance_minor, statement.closing_balance_minor)
    services.partner_accounts.list_statements(partner.id)
    ```

=== "Partner invoices"

    Bill the partner at the agreed (wholesale/net) price.

    ```python
    invoice = services.partner_accounts.create_invoice(
        partner.id,
        lines=[{"description": "Q3 licenses", "quantity": 10, "unit_amount_minor": 9000}],
        finalize=True,
    )
    services.partner_accounts.record_invoice_payment(invoice.id, 90_000)
    ```

=== "Payouts"

    Pay commission or other amounts out to a partner.

    ```python
    payout = services.partner_accounts.create_payout(
        partner.id, lines=[{"description": "Commission", "amount_minor": 12_000}]
    )
    services.partner_accounts.pay_payout(payout.id, reference="ACH-2210")
    ```

## Channel reporting

```python
services.uow.reports.channel_revenue("USD")
# [{'partner_id': '01H...', 'licenses': 1, 'value_minor': 10000}, ...]
```

Revoked licenses are excluded. See [Reporting](reporting.md).

## Next

- [REST endpoints](../reference/rest-api.md) for the full partner HTTP surface.
- [Data model](../reference/data-model.md) for the partner tables.
