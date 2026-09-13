"""Prefix-aware migration runner.

Migrations are ordinary Python callables executed in version order. Applied
versions are tracked in the prefixed ``migrations`` table. Table names are
resolved through the configured metadata prefix, so no identifier is hard-coded.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import Table, insert, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from billing_engine.adapters.db import models as m
from billing_engine.adapters.db.base import Base
from billing_engine.domain.value_objects import new_ulid, utcnow


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    description: str
    apply: Callable[[Connection], None]


def _initial_core_schema(connection: Connection) -> None:
    Base.metadata.create_all(connection, checkfirst=True)


MIGRATIONS: tuple[Migration, ...] = (
    Migration("0001", "initial core schema", _initial_core_schema),
)


class Migrator:
    """Applies pending migrations for a configured engine."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def _ensure_ledger(self) -> None:
        table = m.MigrationRecord.__table__
        if isinstance(table, Table):
            table.create(self.engine, checkfirst=True)

    def applied_versions(self) -> set[str]:
        """Return versions already recorded as applied."""
        self._ensure_ledger()
        with Session(self.engine) as session:
            return set(session.scalars(select(m.MigrationRecord.version)))

    def pending_versions(self) -> list[str]:
        """Return version identifiers that have not been applied yet."""
        applied = self.applied_versions()
        return [migration.version for migration in MIGRATIONS if migration.version not in applied]

    def migrate(self) -> list[str]:
        """Apply all pending migrations and return the versions applied."""
        applied = self.applied_versions()
        newly_applied: list[str] = []
        for migration in sorted(MIGRATIONS, key=lambda item: item.version):
            if migration.version in applied:
                continue
            # Apply the DDL and record the version in one transaction so a crash
            # between them cannot leave unrecorded schema changes.
            with self.engine.begin() as connection:
                migration.apply(connection)
                ledger = m.MigrationRecord.__table__
                if isinstance(ledger, Table):
                    connection.execute(
                        insert(ledger).values(
                            id=new_ulid(),
                            version=migration.version,
                            description=migration.description,
                            created_at=utcnow(),
                        )
                    )
            newly_applied.append(migration.version)
        return newly_applied
