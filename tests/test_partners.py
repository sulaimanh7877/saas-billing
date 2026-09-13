from datetime import timedelta

import pytest

from billing_engine.domain.errors import AllocationExhaustedError, ConflictError
from billing_engine.domain.value_objects import utcnow
from helpers import make_plan


def _consignment_partner(services, amount: int = 10000, quantity: int = 5):
    version = make_plan(services, "reseller-pro", amount=amount)
    partner = services.partners.create("Reseller A", type="reseller")
    agreement = services.partners.create_agreement(partner.id, money_model="consignment")
    allocation = services.licenses.allocate(
        partner.id, version.id, quantity, agreement_id=agreement.id
    )
    return partner, agreement, allocation


def test_allocate_and_issue_license(services) -> None:
    partner, _agreement, allocation = _consignment_partner(services)
    assert services.licenses.available(allocation) == 5

    license_ = services.licenses.issue(allocation.id, external_id="cust-1")
    assert license_.status == "active"
    assert license_.customer_id is not None
    assert license_.subscription_id is not None

    customer = services.customers.get(license_.customer_id)
    assert customer.partner_id == partner.id
    assert services.licenses.get_allocation(allocation.id).quantity_issued == 1
    assert services.partner_accounts.balances(partner.id)["receivable"] == 10000


def test_allocation_exhausted(services) -> None:
    _partner, _agreement, allocation = _consignment_partner(services, quantity=1)
    services.licenses.issue(allocation.id, external_id="cust-1")
    with pytest.raises(AllocationExhaustedError):
        services.licenses.issue(allocation.id, external_id="cust-2")


def test_wholesale_prepaid_drawdown(services) -> None:
    version = make_plan(services, "dist-pro", amount=10000)
    partner = services.partners.create("Distributor", type="distributor")
    agreement = services.partners.create_agreement(
        partner.id, money_model="wholesale_prepaid", discount_bps=2000
    )
    services.partner_accounts.prefund(partner.id, 8000)
    allocation = services.licenses.allocate(partner.id, version.id, 1, agreement_id=agreement.id)
    services.licenses.issue(allocation.id, external_id="cust-1")
    assert services.partner_accounts.balances(partner.id)["prepaid"] == 0


def test_wholesale_prepaid_insufficient(services) -> None:
    version = make_plan(services, "dist-pro", amount=10000)
    partner = services.partners.create("Distributor", type="distributor")
    agreement = services.partners.create_agreement(partner.id, money_model="wholesale_prepaid")
    services.partner_accounts.prefund(partner.id, 500)
    allocation = services.licenses.allocate(partner.id, version.id, 1, agreement_id=agreement.id)
    with pytest.raises(ConflictError):
        services.licenses.issue(allocation.id, external_id="cust-1")


def test_agency_commission_reduces_amount_owed(services) -> None:
    version = make_plan(services, "agent-pro", amount=10000)
    partner = services.partners.create("Agent", type="agent")
    rule = services.partners.create_commission_rule(basis="flat", rate_bps=2000)
    agreement = services.partners.create_agreement(
        partner.id, money_model="agency_commission", commission_rule_id=rule.id
    )
    allocation = services.licenses.allocate(partner.id, version.id, 1, agreement_id=agreement.id)
    services.licenses.issue(allocation.id, external_id="cust-1")
    assert services.partner_accounts.balances(partner.id)["receivable"] == 8000


def test_prefund_and_balance(services) -> None:
    partner = services.partners.create("P")
    services.partner_accounts.prefund(partner.id, 5000)
    assert services.partner_accounts.balances(partner.id)["prepaid"] == 5000


def test_statement_summarizes_ledger(services) -> None:
    partner, _agreement, allocation = _consignment_partner(services)
    services.licenses.issue(allocation.id, external_id="cust-1")
    statement = services.partner_accounts.generate_statement(
        partner.id, utcnow() - timedelta(days=1), utcnow() + timedelta(days=1)
    )
    assert statement.charges_minor == 10000
    assert statement.closing_balance_minor == 10000
    assert services.partner_accounts.list_statements(partner.id)


def test_partner_invoice_and_payment(services) -> None:
    partner = services.partners.create("P")
    invoice = services.partner_accounts.create_invoice(
        partner.id,
        lines=[{"description": "licenses", "quantity": 2, "unit_amount_minor": 1000}],
        finalize=True,
    )
    assert invoice.total_minor == 2000
    services.partner_accounts.record_invoice_payment(invoice.id, 2000)
    assert services.partner_accounts.balances(partner.id)["receivable"] == -2000


def test_payout_marks_paid(services) -> None:
    partner = services.partners.create("P")
    payout = services.partner_accounts.create_payout(
        partner.id, lines=[{"description": "commission", "amount_minor": 500}]
    )
    paid = services.partner_accounts.pay_payout(payout.id)
    assert paid.status == "paid"
    assert services.partner_accounts.balances(partner.id)["payable"] == -500


def test_channel_revenue_report(services) -> None:
    partner, _agreement, allocation = _consignment_partner(services)
    services.licenses.issue(allocation.id, external_id="cust-1")
    rows = services.uow.reports.channel_revenue("USD")
    assert rows
    assert rows[0]["partner_id"] == partner.id
    assert rows[0]["value_minor"] == 10000


def test_revoke_license(services) -> None:
    _partner, _agreement, allocation = _consignment_partner(services)
    license_ = services.licenses.issue(allocation.id, external_id="cust-1")
    revoked = services.licenses.revoke(license_.id, reason="chargeback")
    assert revoked.status == "revoked"
