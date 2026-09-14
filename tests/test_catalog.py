import pytest

from billing_engine.domain.errors import NotFoundError, ValidationError
from helpers import make_customer, make_plan


def test_create_plan_version_with_prices(services) -> None:
    version = make_plan(services, "pro", amount=4900)
    prices = services.catalog.list_prices(version.id)
    assert len(prices) == 1
    assert prices[0].amount_minor == 4900
    assert prices[0].currency == "USD"
    assert prices[0].interval == "month"


def test_version_numbers_increment(services) -> None:
    plan = services.catalog.create_plan("pro")
    first = services.catalog.create_plan_version(
        plan.id, prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}]
    )
    second = services.catalog.create_plan_version(
        plan.id, prices=[{"amount_minor": 200, "currency": "USD", "interval": "month"}]
    )
    assert first.version == 1
    assert second.version == 2


def test_plan_version_requires_price(services) -> None:
    plan = services.catalog.create_plan("pro")
    with pytest.raises(ValidationError):
        services.catalog.create_plan_version(plan.id, prices=[])


def test_find_price_by_currency(services) -> None:
    plan = services.catalog.create_plan("pro")
    version = services.catalog.create_plan_version(
        plan.id,
        prices=[
            {"amount_minor": 1000, "currency": "USD", "interval": "month"},
            {"amount_minor": 900, "currency": "EUR", "interval": "month"},
        ],
    )
    assert services.catalog.find_price(version.id, currency="eur").amount_minor == 900
    with pytest.raises(NotFoundError):
        services.catalog.find_price(version.id, currency="GBP")


def test_custom_plan_is_scoped_to_customer(services) -> None:
    customer = make_customer(services, "user-1")
    make_plan(services, "base")
    version = services.catalog.create_custom_plan(
        customer.id,
        name="Enterprise deal",
        prices=[{"amount_minor": 99000, "currency": "USD", "interval": "year"}],
        entitlements=[{"feature_key": "sso", "limit_value": 1}],
    )
    assert version.scope == "customer_custom"
    assert version.customer_id == customer.id
    plan_keys = {plan.key for plan in services.catalog.list_plans()}
    assert "base" in plan_keys
    assert not any(key.startswith("custom-") for key in plan_keys)
    assert services.catalog.list_prices(version.id)[0].interval == "year"


def test_features_are_created_for_entitlements(services) -> None:
    make_plan(services, "pro", feature_keys=("reports", "api_access"))
    keys = {feature.key for feature in services.catalog.list_features()}
    assert {"reports", "api_access"} <= keys
