"""Declarative base, prefix configuration, and session/DDL helpers.

Table objects are declared with logical (unprefixed) names. The prefix is
applied once per process by :func:`configure_metadata`, which re-stamps every
table, index, and constraint name. Naming-convention templates reference a
custom ``prefix`` token, so any constraint created later (at DDL time) is also
prefixed.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import MetaData
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from billing_engine.domain.errors import ConfigurationError
from billing_engine.naming import PrefixNamer

_prefix: str | None = None
_original_object_names: dict[int, str] = {}
_ORIGINAL_TABLE_KEY = "billing_original_name"


def _configured_prefix() -> str:
    return _prefix or ""


def _namer() -> PrefixNamer:
    if _prefix is None:
        raise ConfigurationError(
            "database metadata is not configured; call configure_metadata(prefix) "
            "before using the models"
        )
    return PrefixNamer(_prefix)


def _token_prefix(constraint: Any, table: Any) -> str:
    return _configured_prefix()


def _token_logical_table_name(constraint: Any, table: Any) -> str:
    name = str(table.name)
    prefix = _configured_prefix()
    if prefix and name.startswith(prefix):
        return name[len(prefix) :]
    return name


def _token_logical_referred_table_name(constraint: Any, table: Any) -> str:
    name = str(constraint.referred_table.name)
    prefix = _configured_prefix()
    if prefix and name.startswith(prefix):
        return name[len(prefix) :]
    return name


class Base(DeclarativeBase):
    """Declarative base for all engine models."""

    metadata = MetaData(
        naming_convention={
            "prefix": _token_prefix,
            "logical_table_name": _token_logical_table_name,
            "logical_referred_table_name": _token_logical_referred_table_name,
            "ix": "%(prefix)six_%(logical_table_name)s_%(column_0N_name)s",
            "uq": "%(prefix)suq_%(logical_table_name)s_%(column_0N_name)s",
            "fk": (
                "%(prefix)sfk_%(logical_table_name)s_%(column_0N_name)s"
                "_%(logical_referred_table_name)s"
            ),
            "pk": "%(prefix)spk_%(logical_table_name)s",
            "ck": "%(prefix)sck_%(logical_table_name)s_%(constraint_name)s",
        }
    )


def _restamp(named: Any) -> None:
    name = named.name
    if not name:
        return
    original = _original_object_names.setdefault(id(named), name)
    prefix = _configured_prefix()
    if prefix and not name.startswith(prefix):
        setattr(named, "name", f"{prefix}{original}")  # noqa: B010


def configure_metadata(prefix: str) -> PrefixNamer:
    """Bind ``prefix`` to the models, renaming tables, indexes, and constraints.

    Safe to call repeatedly. The prefix is process-wide; constructing engines
    with two different prefixes in one process is not supported in v0.1.
    """
    global _prefix
    namer = PrefixNamer(prefix)
    _prefix = namer.prefix

    for table in Base.metadata.tables.values():
        original_table = table.info.setdefault(_ORIGINAL_TABLE_KEY, table.name)
        expected_table = f"{namer.prefix}{original_table}"
        if table.name != expected_table:
            setattr(table, "name", expected_table)  # noqa: B010

        for index in table.indexes:
            _restamp(index)
        for constraint in table.constraints:
            _restamp(constraint)

    return namer


def current_prefix() -> str:
    """Return the configured prefix, or raise if not yet configured."""
    return _namer().prefix


def create_all(engine: Engine) -> None:
    """Create every engine table that does not already exist."""
    Base.metadata.create_all(engine)


def drop_all(engine: Engine) -> None:
    """Drop every engine table."""
    Base.metadata.drop_all(engine)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional session scope, committing or rolling back."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


__all__ = [
    "Base",
    "configure_metadata",
    "create_all",
    "current_prefix",
    "drop_all",
    "make_session_factory",
    "session_scope",
]
