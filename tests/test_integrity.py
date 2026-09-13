"""Regression tests for the concurrency/integrity defects in issue #13 (C3-C5)."""

from __future__ import annotations

import pytest

import billing_engine.adapters.db.migrations as migrations_mod
from billing_engine import BillingEngine, EngineConfig
from billing_engine.adapters.db.base import Base
from billing_engine.adapters.db.migrations import Migrator
from billing_engine.domain.errors import ConfigurationError
from conftest import TEST_PREFIX


def test_c3_plan_version_has_a_unique_guard(engine) -> None:
    from sqlalchemy import inspect

    unique = inspect(engine).get_unique_constraints("test_plan_versions")
    assert any(set(item["column_names"]) == {"plan_id", "version"} for item in unique)


def test_c4_migration_record_shares_the_transaction(engine, monkeypatch) -> None:
    from sqlalchemy import text

    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE c4_marker (id INTEGER)"))

    def insert_marker(connection) -> None:
        connection.execute(text("INSERT INTO c4_marker (id) VALUES (1)"))

    marker = migrations_mod.Migration("9999", "marker", insert_marker)

    def explode(*args, **kwargs):
        raise RuntimeError("record insert failed")

    monkeypatch.setattr(migrations_mod, "MIGRATIONS", (marker,))
    monkeypatch.setattr(migrations_mod, "new_ulid", explode)

    with pytest.raises(RuntimeError):
        Migrator(engine).migrate()

    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM c4_marker")).scalar_one()
    assert count == 0


def test_c5_second_prefix_in_one_process_is_rejected(tmp_path) -> None:
    BillingEngine.reset_process_state()
    try:
        BillingEngine(EngineConfig(dsn=f"sqlite:///{tmp_path / 'a.sqlite3'}", table_prefix="alpha"))
        with pytest.raises(ConfigurationError, match="one table prefix"):
            BillingEngine(
                EngineConfig(dsn=f"sqlite:///{tmp_path / 'b.sqlite3'}", table_prefix="beta")
            )
    finally:
        BillingEngine.reset_process_state()


def test_c5_same_prefix_is_allowed(tmp_path) -> None:
    BillingEngine.reset_process_state()
    try:
        BillingEngine(
            EngineConfig(dsn=f"sqlite:///{tmp_path / 'a.sqlite3'}", table_prefix=TEST_PREFIX)
        )
        second = BillingEngine(
            EngineConfig(dsn=f"sqlite:///{tmp_path / 'b.sqlite3'}", table_prefix=TEST_PREFIX)
        )
        assert second.config.table_prefix == TEST_PREFIX
    finally:
        BillingEngine.reset_process_state()
