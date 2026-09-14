import pytest

from billing_engine import BillingEngine, EngineConfig
from billing_engine.adapters.db.migrations import MIGRATIONS
from billing_engine.domain.errors import ConflictError
from conftest import TEST_PREFIX


def test_engine_migrate_and_transaction(tmp_path) -> None:
    dsn = f"sqlite:///{tmp_path / 'billing.sqlite3'}"
    engine = BillingEngine(EngineConfig(dsn=dsn, table_prefix=TEST_PREFIX))

    applied = engine.migrate()
    assert applied == [migration.version for migration in MIGRATIONS]

    with engine.transaction() as services:
        feature = services.catalog.create_feature("reports")
        plan = services.catalog.create_plan("pro")
        version = services.catalog.create_plan_version(
            plan.id,
            prices=[{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
            entitlements=[{"feature_key": feature.key, "limit_value": 1}],
        )
        customer = services.customers.create("sdk-user")
        services.subscriptions.create(customer.id, version.id)

    with engine.transaction() as services:
        assert services.entitlements.can(customer.id, "reports") is True
        overview = services.reports.overview("USD")
        assert overview["mrr_minor"] == 2900

    assert engine.migrate() == []


def test_transaction_rolls_back_on_error(tmp_path) -> None:
    dsn = f"sqlite:///{tmp_path / 'rollback.sqlite3'}"
    engine = BillingEngine(EngineConfig(dsn=dsn, table_prefix=TEST_PREFIX))
    engine.create_all()

    with pytest.raises(ConflictError), engine.transaction() as services:
        services.customers.create("user-1")
        services.customers.create("user-1")

    with engine.transaction() as services:
        assert services.uow.customers.get_by_external_id("user-1") is None
