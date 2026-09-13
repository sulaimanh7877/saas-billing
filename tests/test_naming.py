import pytest

from billing_engine.domain.errors import ConfigurationError, ValidationError
from billing_engine.naming import PrefixNamer


def test_prefix_normalization() -> None:
    assert PrefixNamer("acme").prefix == "acme_"
    assert PrefixNamer("acme_").prefix == "acme_"
    assert PrefixNamer("acme__").prefix == "acme__"


def test_table_names() -> None:
    namer = PrefixNamer("acme_")
    assert namer.table("subscriptions") == "acme_subscriptions"
    assert namer.table("plan_versions") == "acme_plan_versions"


def test_constraint_names() -> None:
    namer = PrefixNamer("acme_")
    assert namer.index("subscriptions", "customer_id") == "acme_ix_subscriptions_customer_id"
    assert namer.unique("customers", "external_id") == "acme_uq_customers_external_id"
    assert namer.check("prices", "amount") == "acme_ck_prices_amount"
    assert namer.primary_key("subscriptions") == "acme_pk_subscriptions"
    assert (
        namer.foreign_key("subscriptions", "customer_id", referred_table="customers")
        == "acme_fk_subscriptions_customer_id_customers"
    )


def test_multi_column_index() -> None:
    namer = PrefixNamer("acme_")
    assert (
        namer.index("subscriptions", "customer_id", "status")
        == "acme_ix_subscriptions_customer_id_status"
    )


def test_logical_and_is_prefixed() -> None:
    namer = PrefixNamer("acme_")
    assert namer.logical("acme_subscriptions") == "subscriptions"
    assert namer.logical("other_subscriptions") == "other_subscriptions"
    assert namer.is_prefixed("acme_subscriptions") is True
    assert namer.is_prefixed("subscriptions") is False


@pytest.mark.parametrize("prefix", ["", "9bad", "has-dash", "Bad", "sp ace"])
def test_rejects_invalid_prefix(prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="table_prefix"):
        PrefixNamer(prefix)


@pytest.mark.parametrize("name", ["Subscriptions", "has-dash", "9starts", "with space", ""])
def test_rejects_invalid_identifiers(name: str) -> None:
    namer = PrefixNamer("acme_")
    with pytest.raises(ValidationError):
        namer.table(name)
