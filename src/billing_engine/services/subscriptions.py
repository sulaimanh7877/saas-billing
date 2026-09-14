"""Subscription lifecycle: creation, extension, pause, cancel, and renewal."""

from __future__ import annotations

from datetime import datetime, timedelta

from billing_engine.domain.entities import (
    Price,
    Subscription,
    SubscriptionAdjustment,
)
from billing_engine.domain.enums import (
    AdjustmentType,
    BillingInterval,
    CollectionMethod,
    SubscriptionStatus,
)
from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from billing_engine.domain.lifecycle import ensure_transition
from billing_engine.domain.value_objects import add_months, as_utc, new_ulid, period_end, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor

_RENEWABLE = {
    SubscriptionStatus.TRIALING.value,
    SubscriptionStatus.ACTIVE.value,
    SubscriptionStatus.PAST_DUE.value,
}

_VALID_COLLECTION_METHODS = {member.value for member in CollectionMethod}


class SubscriptionService(Service):
    def _find_price(
        self,
        plan_version_id: str,
        price_id: str | None,
        currency: str | None,
    ) -> Price:
        prices = self.uow.catalog.list_prices(plan_version_id)
        if not prices:
            raise NotFoundError(f"plan_version {plan_version_id!r} has no prices")
        if price_id is not None:
            for price in prices:
                if price.id == price_id:
                    return price
            raise NotFoundError(f"price {price_id!r} does not belong to the plan version")
        if currency is not None:
            wanted = currency.upper()
            for price in prices:
                if price.currency == wanted:
                    return price
            raise NotFoundError(f"no {wanted} price for plan version {plan_version_id!r}")
        return prices[0]

    def create(
        self,
        customer_id: str,
        plan_version_id: str,
        *,
        price_id: str | None = None,
        currency: str | None = None,
        trial_days: int | None = None,
        quantity: int = 1,
        collection_method: str = "manual",
        start_at: datetime | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Start a subscription, in trial or active state."""
        customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
        version = require(
            self.uow.catalog.get_plan_version(plan_version_id),
            "plan_version",
            plan_version_id,
        )
        if quantity < 1:
            raise ValidationError("quantity must be at least 1")
        if collection_method not in _VALID_COLLECTION_METHODS:
            raise ValidationError(f"invalid collection_method {collection_method!r}")
        if not version.is_published:
            raise ConflictError(f"plan_version {version.id!r} is not published")
        if trial_days is not None:
            effective_trial = trial_days
        elif version.trial_days:
            effective_trial = version.trial_days
        else:
            effective_trial = self.trial_days
        if effective_trial < 0:
            raise ValidationError("trial_days must be non-negative")

        price = self._find_price(version.id, price_id, currency)
        interval = BillingInterval(price.interval)
        start = as_utc(start_at) if start_at is not None else utcnow()

        subscription = Subscription(
            id=new_ulid(),
            customer_id=customer.id,
            plan_version_id=version.id,
            price_id=price.id,
            quantity=quantity,
            status=SubscriptionStatus.TRIALING.value
            if effective_trial > 0
            else SubscriptionStatus.ACTIVE.value,
            current_period_start=start,
            current_period_end=period_end(start, interval),
            trial_end=start + timedelta(days=effective_trial) if effective_trial > 0 else None,
            collection_method=collection_method,
            partner_id=customer.partner_id,
        )
        self.uow.subscriptions.add(subscription)
        self.uow.flush()
        self.audit.record(
            "subscription.create", "subscription", subscription.id, actor, after=subscription
        )
        self.audit.emit(
            "subscription.created",
            {"subscription_id": subscription.id, "customer_id": customer.id},
        )
        return subscription

    def get(self, subscription_id: str) -> Subscription:
        return require(self.uow.subscriptions.get(subscription_id), "subscription", subscription_id)

    def list_for_customer(self, customer_id: str) -> list[Subscription]:
        return self.uow.subscriptions.list_for_customer(customer_id)

    def list_due(self, before: datetime | None = None) -> list[Subscription]:
        return self.uow.subscriptions.list_due(before or utcnow())

    def _apply(
        self,
        subscription: Subscription,
        adjustment_type: str,
        *,
        actor: Actor | None,
        reason: str | None,
        delta_days: int | None = None,
        previous_period_end: datetime | None = None,
        new_period_end: datetime | None = None,
        action: str,
        event: str | None = None,
    ) -> None:
        self.uow.subscriptions.update(subscription)
        self.uow.subscriptions.add_adjustment(
            SubscriptionAdjustment(
                id=new_ulid(),
                subscription_id=subscription.id,
                adjustment_type=adjustment_type,
                delta_days=delta_days,
                previous_period_end=previous_period_end,
                new_period_end=new_period_end,
                reason=reason,
                actor_type=(actor.type if actor else "system"),
                actor_id=actor.id if actor else None,
            )
        )
        self.uow.flush()
        self.audit.record(action, "subscription", subscription.id, actor, after=subscription)
        if event is not None:
            self.audit.emit(
                event, {"subscription_id": subscription.id, "customer_id": subscription.customer_id}
            )

    def extend(
        self,
        subscription_id: str,
        *,
        days: int | None = None,
        months: int | None = None,
        until: datetime | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Move the current period end forward by days, months, or a date."""
        subscription = self.get(subscription_id)
        base = as_utc(subscription.current_period_end or utcnow())
        if until is not None:
            new_end = as_utc(until)
        elif months is not None:
            new_end = add_months(base, months)
        elif days is not None:
            new_end = base + timedelta(days=days)
        else:
            raise ValidationError("specify one of days, months, or until")
        if new_end <= base:
            raise ValidationError("extension must move the period end forward")

        subscription.current_period_end = new_end
        if subscription.status == SubscriptionStatus.EXPIRED.value:
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.canceled_at = None
        self._apply(
            subscription,
            AdjustmentType.EXTEND.value,
            actor=actor,
            reason=reason,
            delta_days=days,
            previous_period_end=base,
            new_period_end=new_end,
            action="subscription.extend",
            event="subscription.extended",
        )
        return subscription

    def extend_trial(
        self,
        subscription_id: str,
        days: int,
        *,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Push out the trial end by additional days."""
        subscription = self.get(subscription_id)
        if days < 1:
            raise ValidationError("days must be at least 1")
        base = as_utc(subscription.trial_end or subscription.current_period_end or utcnow())
        new_end = base + timedelta(days=days)
        subscription.trial_end = new_end
        subscription.current_period_end = max(
            as_utc(subscription.current_period_end or new_end), new_end
        )
        self._apply(
            subscription,
            AdjustmentType.TRIAL_EXTEND.value,
            actor=actor,
            reason=reason,
            delta_days=days,
            previous_period_end=base,
            new_period_end=new_end,
            action="subscription.extend_trial",
            event="subscription.trial_extended",
        )
        return subscription

    def pause(
        self,
        subscription_id: str,
        *,
        until: datetime | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Pause a subscription, optionally until a date."""
        subscription = self.get(subscription_id)
        ensure_transition(SubscriptionStatus(subscription.status), SubscriptionStatus.PAUSED)
        subscription.status = SubscriptionStatus.PAUSED.value
        subscription.paused_until = as_utc(until) if until is not None else None
        self._apply(
            subscription,
            AdjustmentType.PAUSE.value,
            actor=actor,
            reason=reason,
            action="subscription.pause",
            event="subscription.paused",
        )
        return subscription

    def resume(
        self,
        subscription_id: str,
        *,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Resume a paused subscription."""
        subscription = self.get(subscription_id)
        if subscription.status != SubscriptionStatus.PAUSED.value:
            raise ConflictError("only a paused subscription can be resumed")
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.paused_until = None
        self._apply(
            subscription,
            AdjustmentType.RESUME.value,
            actor=actor,
            reason=reason,
            action="subscription.resume",
            event="subscription.resumed",
        )
        return subscription

    def cancel(
        self,
        subscription_id: str,
        *,
        at_period_end: bool = True,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Cancel immediately or at the end of the current period."""
        subscription = self.get(subscription_id)
        if at_period_end:
            subscription.cancel_at = as_utc(subscription.current_period_end or utcnow())
        else:
            ensure_transition(SubscriptionStatus(subscription.status), SubscriptionStatus.CANCELED)
            subscription.status = SubscriptionStatus.CANCELED.value
            subscription.canceled_at = utcnow()
            subscription.cancel_at = None
        self._apply(
            subscription,
            AdjustmentType.CANCEL.value,
            actor=actor,
            reason=reason,
            action="subscription.cancel",
            event="subscription.canceled",
        )
        return subscription

    def reactivate(
        self,
        subscription_id: str,
        *,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Reactivate a canceled or expired subscription."""
        subscription = self.get(subscription_id)
        ensure_transition(SubscriptionStatus(subscription.status), SubscriptionStatus.ACTIVE)
        now = utcnow()
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.canceled_at = None
        subscription.cancel_at = None
        subscription.paused_until = None
        if (
            subscription.current_period_end is None
            or as_utc(subscription.current_period_end) <= now
        ):
            price = self._find_price(subscription.plan_version_id, subscription.price_id, None)
            subscription.current_period_start = now
            subscription.current_period_end = period_end(now, BillingInterval(price.interval))
        self._apply(
            subscription,
            AdjustmentType.REACTIVATE.value,
            actor=actor,
            reason=reason,
            action="subscription.reactivate",
            event="subscription.reactivated",
        )
        return subscription

    def change_plan(
        self,
        subscription_id: str,
        plan_version_id: str,
        *,
        price_id: str | None = None,
        currency: str | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Switch a subscription to another plan version, without proration."""
        subscription = self.get(subscription_id)
        require(
            self.uow.catalog.get_plan_version(plan_version_id),
            "plan_version",
            plan_version_id,
        )
        price = self._find_price(plan_version_id, price_id, currency)
        subscription.plan_version_id = plan_version_id
        subscription.price_id = price.id
        self._apply(
            subscription,
            AdjustmentType.PLAN_CHANGE.value,
            actor=actor,
            reason=reason,
            action="subscription.change_plan",
            event="subscription.plan_changed",
        )
        return subscription

    def _interval(self, subscription: Subscription) -> BillingInterval:
        price = self._find_price(subscription.plan_version_id, subscription.price_id, None)
        return BillingInterval(price.interval)

    def renew(
        self,
        subscription_id: str,
        *,
        now: datetime | None = None,
        actor: Actor | None = None,
    ) -> Subscription:
        """Advance a due subscription into its next billing period."""
        subscription = self.get(subscription_id)
        if subscription.status not in _RENEWABLE:
            raise ConflictError(f"cannot renew subscription in status {subscription.status!r}")
        moment = as_utc(now) if now is not None else utcnow()
        interval = self._interval(subscription)
        if interval is BillingInterval.ONE_TIME:
            raise ConflictError("a one-time subscription has no next period to renew")
        trial_end = as_utc(subscription.trial_end) if subscription.trial_end is not None else None
        if subscription.status == SubscriptionStatus.TRIALING.value:
            if trial_end is not None and trial_end > moment:
                return subscription
            start = trial_end or as_utc(subscription.current_period_end or moment)
        else:
            start = as_utc(subscription.current_period_end or moment)
        subscription.current_period_start = start
        subscription.current_period_end = period_end(start, interval)
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.grace_until = None
        self._apply(
            subscription,
            AdjustmentType.RENEW.value,
            actor=actor,
            reason="renewal",
            previous_period_end=start,
            new_period_end=subscription.current_period_end,
            action="subscription.renew",
            event="subscription.renewed",
        )
        return subscription

    def _expire(self, subscription: Subscription, *, reason: str, actor: Actor | None) -> None:
        """Move a subscription past its grace window into expired."""
        previous_end = (
            as_utc(subscription.current_period_end)
            if subscription.current_period_end is not None
            else None
        )
        subscription.status = SubscriptionStatus.EXPIRED.value
        subscription.canceled_at = utcnow()
        subscription.cancel_at = None
        subscription.grace_until = None
        self.uow.subscriptions.update(subscription)
        self.uow.subscriptions.add_adjustment(
            SubscriptionAdjustment(
                id=new_ulid(),
                subscription_id=subscription.id,
                adjustment_type=AdjustmentType.EXPIRE.value,
                previous_period_end=previous_end,
                new_period_end=previous_end,
                reason=reason,
                actor_type=(actor.type if actor else "system"),
                actor_id=actor.id if actor else None,
            )
        )
        self.uow.flush()
        self.audit.record("subscription.expire", "subscription", subscription.id, actor)
        self.audit.emit("subscription.expired", {"subscription_id": subscription.id})

    def _enter_grace(
        self, subscription: Subscription, moment: datetime, actor: Actor | None = None
    ) -> bool:
        """Start the post-period grace window; return True while grace applies."""
        if self.grace_period_days <= 0:
            return False
        if subscription.grace_until is not None:
            return as_utc(subscription.grace_until) > moment
        subscription.status = SubscriptionStatus.PAST_DUE.value
        subscription.grace_until = moment + timedelta(days=self.grace_period_days)
        self.uow.subscriptions.update(subscription)
        self.uow.flush()
        self.audit.record(
            "subscription.past_due", "subscription", subscription.id, actor, after=subscription
        )
        self.audit.emit("subscription.past_due", {"subscription_id": subscription.id})
        return True

    def process_due(self, *, now: datetime | None = None, actor: Actor | None = None) -> list[str]:
        """Renew or expire every subscription whose period has ended."""
        moment = as_utc(now) if now is not None else utcnow()
        renewed: list[str] = []
        for subscription in self.uow.subscriptions.list_due(moment):
            interval = self._interval(subscription)
            if subscription.cancel_at is not None and as_utc(subscription.cancel_at) <= moment:
                if not self._enter_grace(subscription, moment, actor):
                    self._expire(subscription, reason="canceled at period end", actor=actor)
                continue
            if interval is BillingInterval.ONE_TIME:
                if not self._enter_grace(subscription, moment, actor):
                    self._expire(subscription, reason="one-time period ended", actor=actor)
                continue
            self.renew(subscription.id, now=moment, actor=actor)
            renewed.append(subscription.id)
        return renewed
