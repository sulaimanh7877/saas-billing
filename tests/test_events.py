from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.domain.value_objects import new_ulid
from billing_engine.events.dispatcher import EventDispatcher
from billing_engine.services.registry import Services


def test_ulid_is_sortable_and_valid() -> None:
    first = new_ulid(timestamp_ms=1_000)
    second = new_ulid(timestamp_ms=2_000)
    assert len(first) == 26
    assert first < second
    from billing_engine.domain.value_objects import is_valid_ulid, ulid_timestamp_ms

    assert is_valid_ulid(first)
    assert ulid_timestamp_ms(first) == 1_000


def test_event_is_emitted_and_delivered(session_factory) -> None:
    session = session_factory()
    bundle = Services(SqlUnitOfWork(session))
    bundle.customers.create("user-1")
    session.commit()
    session.close()

    delivered = []
    dispatcher = EventDispatcher(session_factory, delivered.append)
    count = dispatcher.dispatch_pending()
    assert count >= 1
    assert any(event.event_type == "customer.created" for event in delivered)


def test_failed_delivery_is_retried(session_factory) -> None:
    session = session_factory()
    bundle = Services(SqlUnitOfWork(session))
    bundle.customers.create("user-2")
    session.commit()
    session.close()

    def boom(event) -> None:
        raise RuntimeError("webhook down")

    dispatcher = EventDispatcher(session_factory, boom, backoff_seconds=1)
    assert dispatcher.dispatch_pending() == 0

    from sqlalchemy import select

    from billing_engine.adapters.db import models as m

    session = session_factory()
    row = session.scalar(select(m.Event).where(m.Event.event_type == "customer.created"))
    assert row is not None
    assert row.attempts == 1
    assert row.last_error == "webhook down"
    assert row.available_at is not None
    session.close()


def test_money_arithmetic() -> None:
    from billing_engine.domain.value_objects import Money

    total = Money(1000, "usd").add(Money(500, "USD"))
    assert total.amount_minor == 1500
    assert total.currency == "USD"
    assert total.subtract(Money(250, "USD")).amount_minor == 1250
    assert Money(-5, "USD").is_negative


def test_subscription_status_grants_access() -> None:
    from billing_engine.domain.enums import SubscriptionStatus
    from billing_engine.domain.lifecycle import can_transition, grants_access

    assert grants_access(SubscriptionStatus.ACTIVE)
    assert not grants_access(SubscriptionStatus.CANCELED)
    assert can_transition(SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE)
    assert not can_transition(SubscriptionStatus.EXPIRED, SubscriptionStatus.TRIALING)
