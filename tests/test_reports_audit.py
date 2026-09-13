from helpers import make_customer, make_plan


def test_overview_reports_mrr(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, amount=2900)
    services.subscriptions.create(customer.id, version.id)
    overview = services.reports.overview("USD")
    assert overview["customers"] == 1
    assert overview["mrr_minor"] == 2900
    assert overview["active_subscriptions"] == 1


def test_revenue_by_plan(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, "pro", amount=2900)
    services.subscriptions.create(customer.id, version.id)
    rows = services.reports.revenue_by_plan("USD")
    assert len(rows) == 1
    assert rows[0]["mrr_minor"] == 2900
    assert rows[0]["plan_key"] == "pro"


def test_outstanding_invoices(services) -> None:
    customer = make_customer(services)
    services.invoices.create(
        customer.id,
        lines=[{"description": "Plan", "quantity": 1, "unit_amount_minor": 1500}],
        finalize=True,
    )
    outstanding = services.reports.outstanding_invoices()
    assert outstanding["count"] == 1
    assert outstanding["total_minor"] == 1500


def test_feature_adoption(services) -> None:
    make_plan(services, feature_keys=("reports",))
    rows = services.reports.feature_adoption()
    assert any(row["feature_key"] == "reports" for row in rows)


def test_audit_log_filters(services) -> None:
    customer = make_customer(services)
    make_plan(services, "pro")
    entries = services.uow.audit.list(action="customer.create")
    assert len(entries) == 1
    assert entries[0].entity_id == customer.id
    assert services.uow.audit.list(action="plan.create")
