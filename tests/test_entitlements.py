from datetime import timedelta

from billing_engine.domain.value_objects import utcnow
from helpers import make_customer, make_plan


def test_plan_entitlement_is_resolved(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, feature_keys=("reports",))
    services.subscriptions.create(customer.id, version.id)
    assert services.entitlements.can(customer.id, "reports") is True
    assert services.entitlements.limit(customer.id, "reports") == 1


def test_default_when_no_subscription(services) -> None:
    customer = make_customer(services)
    make_plan(services, feature_keys=("reports",))
    assert services.entitlements.can(customer.id, "reports") is False


def test_customer_override_wins(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, feature_keys=("reports",))
    subscription = services.subscriptions.create(customer.id, version.id)
    services.entitlements.set_customer_override(customer.id, "reports", value=0)
    assert services.entitlements.can(customer.id, "reports") is False
    services.entitlements.set_subscription_override(subscription.id, "reports", value=1)
    # customer override still takes precedence per the resolution order
    assert services.entitlements.can(customer.id, "reports") is False


def test_subscription_override_used_without_customer_override(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, feature_keys=("reports",))
    subscription = services.subscriptions.create(customer.id, version.id)
    services.entitlements.set_subscription_override(subscription.id, "reports", value=5)
    assert services.entitlements.limit(customer.id, "reports") == 5


def test_expired_override_is_ignored(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, feature_keys=("reports",))
    services.subscriptions.create(customer.id, version.id)
    services.entitlements.set_customer_override(
        customer.id, "reports", value=0, expires_at=utcnow() - timedelta(days=1)
    )
    assert services.entitlements.can(customer.id, "reports") is True


def test_list_for_customer(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, feature_keys=("reports", "api_access"))
    services.subscriptions.create(customer.id, version.id)
    resolved = services.entitlements.list_for_customer(customer.id)
    assert set(resolved) == {"reports", "api_access"}
    assert all(item.source == "plan" for item in resolved.values())
