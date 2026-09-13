"""The embeddable ``BillingEngine`` facade."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from billing_engine.adapters.db import models as _models  # noqa: F401  (register models)
from billing_engine.adapters.db.base import (
    configure_metadata,
    create_all,
    drop_all,
    make_session_factory,
)
from billing_engine.adapters.db.migrations import Migrator
from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.config import EngineConfig
from billing_engine.domain.errors import ConfigurationError
from billing_engine.naming import PrefixNamer
from billing_engine.services.registry import Services

_active_prefixes: set[str] = set()


class BillingEngine:
    """Entry point for embedded use.

    Example::

        engine = BillingEngine(EngineConfig(dsn="sqlite://", table_prefix="acme_"))
        engine.migrate()
        with engine.transaction() as services:
            customer = services.customers.create(external_id="user-1")
    """

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        prefix = PrefixNamer(config.table_prefix).prefix
        if _active_prefixes and prefix not in _active_prefixes:
            raise ConfigurationError(
                "only one table prefix per process is supported in v0.1 (ADR 0001); "
                f"already using {sorted(_active_prefixes)[0]!r}, cannot add {prefix!r}"
            )
        _active_prefixes.add(prefix)
        self.namer: PrefixNamer = configure_metadata(config.table_prefix)
        self.engine: Engine = config.build_engine()
        self.session_factory: sessionmaker[Session] = make_session_factory(self.engine)

    @classmethod
    def reset_process_state(cls) -> None:
        """Clear the process-level prefix registry (test and tooling support)."""
        _active_prefixes.clear()

    def migrate(self) -> list[str]:
        """Apply all pending migrations and return the versions applied."""
        return Migrator(self.engine).migrate()

    def create_all(self) -> None:
        """Create the schema directly, for tests and throwaway databases."""
        create_all(self.engine)

    def drop_all(self) -> None:
        """Drop the engine's tables."""
        drop_all(self.engine)

    @contextmanager
    def transaction(self) -> Iterator[Services]:
        """Provide a transactional :class:`Services` bundle."""
        session = self.session_factory()
        uow = SqlUnitOfWork(session)
        services = Services(
            uow,
            default_currency=self.config.default_currency,
            grace_period_days=self.config.grace_period_days,
            trial_days=self.config.trial_days,
        )
        try:
            yield services
            uow.commit()
        except Exception:
            uow.rollback()
            raise
        finally:
            session.close()
