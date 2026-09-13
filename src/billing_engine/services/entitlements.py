"""Entitlement resolution, feature checks, and overrides."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from billing_engine.domain.entities import (
    EntitlementOverride,
    Feature,
    PlanEntitlement,
    Subscription,
)
from billing_engine.domain.enums import OverrideScope, SubscriptionStatus
from billing_engine.domain.errors import NotFoundError, ValidationError
from billing_engine.domain.lifecycle import grants_access
from billing_engine.domain.value_objects import new_ulid, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor


@dataclass(slots=True)
class ResolvedEntitlement:
    """The effective value of a feature for a customer."""

    feature_key: str
    value: int
    limit_value: int | None
    value_type: str
    source: str
    subscription_id: str | None = None


class EntitlementService(Service):
    def _active_subscription(self, customer_id: str) -> Subscription | None:
        subscriptions = [
            subscription
            for subscription in self.uow.subscriptions.list_for_customer(customer_id)
            if grants_access(SubscriptionStatus(subscription.status))
        ]
        if not subscriptions:
            return None
        subscriptions.sort(key=lambda item: item.current_period_end or utcnow(), reverse=True)
        return subscriptions[0]

    def _usable(self, override: EntitlementOverride | None) -> EntitlementOverride | None:
        if override is None:
            return None
        if override.expires_at is not None and override.expires_at <= utcnow():
            return None
        return override

    def _find_plan_entitlement(
        self, subscription: Subscription, feature_id: str
    ) -> PlanEntitlement | None:
        entitlements = self.uow.catalog.list_plan_entitlements(subscription.plan_version_id)
        matches = [item for item in entitlements if item.feature_id == feature_id]
        return matches[0] if matches else None

    def resolve(self, customer_id: str, feature_key: str) -> ResolvedEntitlement:
        """Resolve the effective entitlement using the fallback chain."""
        require(self.uow.customers.get(customer_id), "customer", customer_id)
        feature = self.uow.catalog.get_feature_by_key(feature_key)
        if feature is None:
            raise NotFoundError(f"feature {feature_key!r} was not found")

        subscription = self._active_subscription(customer_id)

        override = self._usable(
            self.uow.entitlements.get_customer_override(customer_id, feature.id)
        )
        if override is None and subscription is not None:
            override = self._usable(
                self.uow.entitlements.get_subscription_override(subscription.id, feature.id)
            )
        if override is not None:
            return ResolvedEntitlement(
                feature_key=feature_key,
                value=override.value,
                limit_value=override.limit_value,
                value_type=feature.value_type,
                source=override.scope,
                subscription_id=override.subscription_id,
            )

        if subscription is not None:
            plan_entitlement = self._find_plan_entitlement(subscription, feature.id)
            if plan_entitlement is not None:
                return ResolvedEntitlement(
                    feature_key=feature_key,
                    value=plan_entitlement.value,
                    limit_value=plan_entitlement.limit_value,
                    value_type=feature.value_type,
                    source="plan",
                    subscription_id=subscription.id,
                )

        return ResolvedEntitlement(
            feature_key=feature_key,
            value=feature.default_value,
            limit_value=None,
            value_type=feature.value_type,
            source="default",
        )

    def value(self, customer_id: str, feature_key: str) -> int:
        """Return the effective numeric value of a feature."""
        return self.resolve(customer_id, feature_key).value

    def limit(self, customer_id: str, feature_key: str) -> int | None:
        """Return the effective limit of a feature, if any."""
        resolved = self.resolve(customer_id, feature_key)
        if resolved.limit_value is not None:
            return resolved.limit_value
        if resolved.value_type == "boolean":
            return None
        return resolved.value

    def can(self, customer_id: str, feature_key: str) -> bool:
        """Return whether a customer currently has access to a feature."""
        resolved = self.resolve(customer_id, feature_key)
        effective = resolved.limit_value if resolved.limit_value is not None else resolved.value
        return effective > 0

    def list_for_customer(self, customer_id: str) -> dict[str, ResolvedEntitlement]:
        """Resolve every known feature for a customer."""
        return {
            feature.key: self.resolve(customer_id, feature.key)
            for feature in self.uow.catalog.list_features()
        }

    def _require_feature(self, feature_key: str) -> Feature:
        feature = self.uow.catalog.get_feature_by_key(feature_key)
        if feature is None:
            raise NotFoundError(f"feature {feature_key!r} was not found")
        return feature

    def set_customer_override(
        self,
        customer_id: str,
        feature_key: str,
        *,
        value: int = 1,
        limit_value: int | None = None,
        expires_at: datetime | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> EntitlementOverride:
        """Create or replace a customer-level entitlement override."""
        require(self.uow.customers.get(customer_id), "customer", customer_id)
        feature = self._require_feature(feature_key)
        existing = self.uow.entitlements.get_customer_override(customer_id, feature.id)
        if existing is not None:
            self.uow.entitlements.delete_override(existing.id)
        override = EntitlementOverride(
            id=new_ulid(),
            scope=OverrideScope.CUSTOMER.value,
            feature_id=feature.id,
            customer_id=customer_id,
            value=value,
            limit_value=limit_value,
            expires_at=expires_at,
        )
        self.uow.entitlements.add_override(override)
        self.uow.flush()
        self.audit.record(
            "entitlement.override.set",
            "customer",
            customer_id,
            actor,
            after=override,
            reason=reason,
        )
        return override

    def set_subscription_override(
        self,
        subscription_id: str,
        feature_key: str,
        *,
        value: int = 1,
        limit_value: int | None = None,
        expires_at: datetime | None = None,
        reason: str | None = None,
        actor: Actor | None = None,
    ) -> EntitlementOverride:
        """Create or replace a subscription-level entitlement override."""
        require(self.uow.subscriptions.get(subscription_id), "subscription", subscription_id)
        feature = self._require_feature(feature_key)
        existing = self.uow.entitlements.get_subscription_override(subscription_id, feature.id)
        if existing is not None:
            self.uow.entitlements.delete_override(existing.id)
        override = EntitlementOverride(
            id=new_ulid(),
            scope=OverrideScope.SUBSCRIPTION.value,
            feature_id=feature.id,
            subscription_id=subscription_id,
            value=value,
            limit_value=limit_value,
            expires_at=expires_at,
        )
        self.uow.entitlements.add_override(override)
        self.uow.flush()
        self.audit.record(
            "entitlement.override.set",
            "subscription",
            subscription_id,
            actor,
            after=override,
            reason=reason,
        )
        return override

    def remove_override(self, override_id: str, *, actor: Actor | None = None) -> None:
        """Delete an entitlement override by id."""
        if not override_id:
            raise ValidationError("override_id is required")
        override = require(self.uow.entitlements.get_override(override_id), "override", override_id)
        self.uow.entitlements.delete_override(override_id)
        self.uow.flush()
        self.audit.record(
            "entitlement.override.remove", "override", override_id, actor, before=override
        )
