import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from billing_engine.adapters.db import models as _models  # noqa: F401  (register models)
from billing_engine.adapters.db.base import Base, configure_metadata, make_session_factory
from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.services.registry import Services

TEST_PREFIX = "test_"


@pytest.fixture()
def engine():
    configure_metadata(TEST_PREFIX)
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture()
def session_factory(engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture()
def services(session_factory) -> Services:
    session = session_factory()
    bundle = Services(SqlUnitOfWork(session), default_currency="USD")
    try:
        yield bundle
        session.commit()
    finally:
        session.close()
