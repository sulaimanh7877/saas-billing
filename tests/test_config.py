import pytest
from sqlalchemy import create_engine

from billing_engine.config import EngineConfig
from billing_engine.domain.errors import ConfigurationError


def test_accepts_dsn_and_normalizes_prefix() -> None:
    config = EngineConfig(table_prefix="acme", dsn="sqlite://")
    assert config.table_prefix == "acme_"
    assert config.dsn == "sqlite://"
    assert config.engine is None
    assert config.default_currency == "USD"
    assert config.timezone == "UTC"


def test_accepts_existing_engine() -> None:
    engine = create_engine("sqlite://")
    config = EngineConfig(table_prefix="acme_", engine=engine)
    assert config.engine is engine
    assert config.build_engine() is engine


def test_build_engine_from_dsn() -> None:
    config = EngineConfig(table_prefix="acme_", dsn="sqlite://")
    assert config.build_engine() is not config.build_engine()


@pytest.mark.parametrize("prefix", ["", "   "])
def test_rejects_empty_prefix(prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="table_prefix is required"):
        EngineConfig(table_prefix=prefix, dsn="sqlite://")


@pytest.mark.parametrize("prefix", ["9bad", "has-dash", "Bad", "sp ace"])
def test_rejects_invalid_prefix(prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="invalid table_prefix"):
        EngineConfig(table_prefix=prefix, dsn="sqlite://")


def test_requires_exactly_one_connection_source() -> None:
    with pytest.raises(ConfigurationError, match="exactly one"):
        EngineConfig(table_prefix="acme_")
    with pytest.raises(ConfigurationError, match="exactly one"):
        EngineConfig(table_prefix="acme_", dsn="sqlite://", engine=create_engine("sqlite://"))


def test_blank_dsn_is_treated_as_missing() -> None:
    with pytest.raises(ConfigurationError, match="exactly one"):
        EngineConfig(table_prefix="acme_", dsn="   ")


@pytest.mark.parametrize("currency", ["usd", "USD", "eur"])
def test_normalizes_currency(currency: str) -> None:
    config = EngineConfig(table_prefix="acme_", dsn="sqlite://", default_currency=currency)
    assert config.default_currency == currency.upper()


@pytest.mark.parametrize("currency", ["US", "USDD", "12A", ""])
def test_rejects_invalid_currency(currency: str) -> None:
    with pytest.raises(ConfigurationError, match="default_currency"):
        EngineConfig(table_prefix="acme_", dsn="sqlite://", default_currency=currency)


@pytest.mark.parametrize("field", ["grace_period_days", "trial_days"])
def test_rejects_negative_durations(field: str) -> None:
    with pytest.raises(ConfigurationError, match=field):
        EngineConfig(table_prefix="acme_", dsn="sqlite://", **{field: -1})


def test_rejects_non_utc_timezone() -> None:
    with pytest.raises(ConfigurationError, match="timezone"):
        EngineConfig(table_prefix="acme_", dsn="sqlite://", timezone="America/New_York")


def test_namer_is_bound_to_prefix() -> None:
    config = EngineConfig(table_prefix="acme", dsn="sqlite://")
    assert config.namer.table("subscriptions") == "acme_subscriptions"
