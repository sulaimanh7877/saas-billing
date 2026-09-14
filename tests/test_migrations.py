from sqlalchemy import inspect

from billing_engine.adapters.db import models  # noqa: F401
from billing_engine.adapters.db.base import Base, configure_metadata
from billing_engine.adapters.db.migrations import MIGRATIONS, Migrator
from conftest import TEST_PREFIX

EXPECTED_VERSIONS = [migration.version for migration in MIGRATIONS]


def test_migrate_creates_schema(engine) -> None:
    Base.metadata.drop_all(engine)
    migrator = Migrator(engine)
    applied = migrator.migrate()
    assert applied == EXPECTED_VERSIONS
    tables = set(inspect(engine).get_table_names())
    assert "test_subscriptions" in tables
    assert "test_migrations" in tables


def test_migrate_is_idempotent(engine) -> None:
    Base.metadata.drop_all(engine)
    migrator = Migrator(engine)
    migrator.migrate()
    assert migrator.migrate() == []
    assert migrator.applied_versions() == set(EXPECTED_VERSIONS)


def test_prefix_is_configurable() -> None:
    namer = configure_metadata("acme")
    assert namer.prefix == "acme_"
    assert Base.metadata.tables["customers"].name == "acme_customers"
    # Restore the shared test prefix for other tests.
    configure_metadata(TEST_PREFIX)
    assert Base.metadata.tables["customers"].name == "test_customers"
