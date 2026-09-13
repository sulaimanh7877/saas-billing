from datetime import timedelta

import pytest

from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import add_months, utcnow
from helpers import make_customer, make_plan


def test_create_active_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    assert subscription.status == "active"
    assert subscription.trial_end is None
    assert subscription.current_period_end > subscription.current_period_start


def test_create_trialing_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services, trial_days=14)
    subscription = services.subscriptions.create(customer.id, version.id)
    assert subscription.status == "trialing"
    assert subscription.trial_end is not None


def test_extend_by_days(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    previous_end = subscription.current_period_end
    extended = services.subscriptions.extend(subscription.id, days=10, reason="goodwill")
    assert extended.current_period_end == previous_end + timedelta(days=10)
    adjustments = services.uow.subscriptions.list_adjustments(subscription.id)
    assert adjustments[-1].adjustment_type == "extend"
    assert adjustments[-1].reason == "goodwill"


def test_extend_by_months(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    previous_end = subscription.current_period_end
    extended = services.subscriptions.extend(subscription.id, months=2)
    assert extended.current_period_end == add_months(previous_end, 2)


def test_extend_must_move_forward(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    with pytest.raises(ValidationError):
        services.subscriptions.extend(subscription.id, days=-5)


def test_extend_requires_an_amount(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    with pytest.raises(ValidationError):
        services.subscriptions.extend(subscription.id)


def test_pause_and_resume(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    paused = services.subscriptions.pause(subscription.id, reason="vacation")
    assert paused.status == "paused"
    resumed = services.subscriptions.resume(subscription.id)
    assert resumed.status == "active"


def test_cancel_at_period_end(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    canceled = services.subscriptions.cancel(subscription.id, at_period_end=True)
    assert canceled.status == "active"
    assert canceled.cancel_at == canceled.current_period_end


def test_cancel_immediately_and_reactivate(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    canceled = services.subscriptions.cancel(subscription.id, at_period_end=False)
    assert canceled.status == "canceled"
    reactivated = services.subscriptions.reactivate(subscription.id)
    assert reactivated.status == "active"
    assert reactivated.canceled_at is None


def test_change_plan(services) -> None:
    customer = make_customer(services)
    first = make_plan(services, "basic", amount=900)
    second = make_plan(services, "pro", amount=2900)
    subscription = services.subscriptions.create(customer.id, first.id)
    changed = services.subscriptions.change_plan(subscription.id, second.id)
    assert changed.plan_version_id == second.id


def test_renew_advances_period(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    start = utcnow() - timedelta(days=40)
    subscription = services.subscriptions.create(customer.id, version.id, start_at=start)
    previous_end = subscription.current_period_end
    renewed = services.subscriptions.renew(subscription.id)
    assert renewed.current_period_end > previous_end


def test_process_due_expires_canceled_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    start = utcnow() - timedelta(days=40)
    subscription = services.subscriptions.create(customer.id, version.id, start_at=start)
    services.subscriptions.cancel(subscription.id, at_period_end=True)
    services.subscriptions.process_due()
    assert services.subscriptions.get(subscription.id).status == "expired"


def test_process_due_renews_active_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    start = utcnow() - timedelta(days=40)
    subscription = services.subscriptions.create(customer.id, version.id, start_at=start)
    services.subscriptions.process_due()
    assert services.subscriptions.get(subscription.id).current_period_end > utcnow()


def test_cannot_renew_canceled_subscription(services) -> None:
    customer = make_customer(services)
    version = make_plan(services)
    subscription = services.subscriptions.create(customer.id, version.id)
    services.subscriptions.cancel(subscription.id, at_period_end=False)
    with pytest.raises(ConflictError):
        services.subscriptions.renew(subscription.id)
