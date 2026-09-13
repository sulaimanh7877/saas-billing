from sqlalchemy import inspect

from billing_engine.adapters.db import models  # noqa: F401
from billing_engine.adapters.db.base import Base
from conftest import TEST_PREFIX


def test_all_tables_are_prefixed(engine) -> None:
    names = set(inspect(engine).get_table_names())
    assert "test_customers" in names
    assert "test_subscriptions" in names
    assert "test_audit_logs" in names
    assert "customers" not in names
    assert all(name.startswith(TEST_PREFIX) for name in names), names


def test_model_table_names_are_renamed(engine) -> None:
    for table in Base.metadata.tables.values():
        assert table.name.startswith(TEST_PREFIX)


def test_foreign_keys_are_prefixed(engine) -> None:
    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys("test_subscriptions")
    assert foreign_keys
    for fk in foreign_keys:
        name = fk.get("name")
        if name:
            assert name.startswith(TEST_PREFIX)


def test_crud_round_trip(engine) -> None:
    from sqlalchemy import text

    with engine.connect() as connection:
        connection.execute(
            text(
                "INSERT INTO test_customers (id, external_id, currency, attributes, "
                "created_at, updated_at) VALUES "
                "(:id, :external_id, 'USD', '{}', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": "01HZZZZZZZZZZZZZZZZZZZZZZZ", "external_id": "user-1"},
        )
        connection.commit()
        row = connection.execute(text("SELECT external_id FROM test_customers")).scalar_one()
    assert row == "user-1"
