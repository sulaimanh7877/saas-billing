"""Catalog management: products, plans, immutable versions, prices, features."""

from __future__ import annotations

from typing import Any

from billing_engine.domain.entities import (
    Feature,
    Plan,
    PlanEntitlement,
    PlanVersion,
    Price,
    Product,
)
from billing_engine.domain.enums import EntitlementValueType, PlanScope
from billing_engine.domain.errors import NotFoundError, ValidationError
from billing_engine.domain.value_objects import new_ulid
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor

_VALID_INTERVALS = {"month", "year", "one_time"}
_VALID_VALUE_TYPES = {member.value for member in EntitlementValueType}
_VALID_SCOPES = {member.value for member in PlanScope}
_VALID_RESET_PERIODS = {"day", "week", "month", "year"}


def _normalize_price(entry: dict[str, Any]) -> dict[str, Any]:
    try:
        amount = int(entry["amount_minor"])
        currency = str(entry.get("currency", "USD")).upper()
        interval = str(entry.get("interval", "month"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"invalid price entry: {entry!r}") from exc
    if amount < 0:
        raise ValidationError("price amount_minor must be non-negative")
    if len(currency) != 3 or not currency.isalpha():
        raise ValidationError(f"invalid currency in price entry: {currency!r}")
    if interval not in _VALID_INTERVALS:
        raise ValidationError(f"invalid interval {interval!r}; expected {_VALID_INTERVALS}")
    return {"amount_minor": amount, "currency": currency, "interval": interval}


class CatalogService(Service):
    def create_product(
        self, key: str, name: str | None = None, *, actor: Actor | None = None
    ) -> Product:
        """Create a product grouping."""
        cleaned = key.strip() if isinstance(key, str) else ""
        if not cleaned:
            raise ValidationError("product key is required")
        product = Product(id=new_ulid(), key=cleaned, name=name)
        self.uow.catalog.add_product(product)
        self.uow.flush()
        self.audit.record("product.create", "product", product.id, actor, after=product)
        return product

    def create_plan(
        self,
        key: str,
        name: str | None = None,
        *,
        product_id: str | None = None,
        actor: Actor | None = None,
    ) -> Plan:
        """Create a stable plan identity."""
        cleaned = key.strip() if isinstance(key, str) else ""
        if not cleaned:
            raise ValidationError("plan key is required")
        if self.uow.catalog.get_plan_by_key(cleaned) is not None:
            raise ValidationError(f"plan key {cleaned!r} already exists")
        if product_id is not None:
            require(self.uow.catalog.get_product(product_id), "product", product_id)
        plan = Plan(id=new_ulid(), key=cleaned, name=name, product_id=product_id)
        self.uow.catalog.add_plan(plan)
        self.uow.flush()
        self.audit.record("plan.create", "plan", plan.id, actor, after=plan)
        return plan

    def create_plan_version(
        self,
        plan_id: str,
        *,
        name: str | None = None,
        prices: list[dict[str, Any]],
        trial_days: int = 0,
        entitlements: list[dict[str, Any]] | None = None,
        scope: str = PlanScope.CATALOG.value,
        customer_id: str | None = None,
        is_published: bool = True,
        actor: Actor | None = None,
    ) -> PlanVersion:
        """Create an immutable plan version with prices and entitlements."""
        plan = require(self.uow.catalog.get_plan_for_update(plan_id), "plan", plan_id)
        if not prices:
            raise ValidationError("a plan version requires at least one price")
        if trial_days < 0:
            raise ValidationError("trial_days must be non-negative")
        if scope not in _VALID_SCOPES:
            raise ValidationError(f"invalid scope {scope!r}; expected {_VALID_SCOPES}")
        if scope == PlanScope.CUSTOMER_CUSTOM.value and not customer_id:
            raise ValidationError("customer-scoped plan versions require a customer_id")

        existing = self.uow.catalog.list_plan_versions(plan.id)
        version = PlanVersion(
            id=new_ulid(),
            plan_id=plan.id,
            version=(max((item.version for item in existing), default=0) + 1),
            name=name or plan.name,
            scope=scope,
            customer_id=customer_id,
            trial_days=trial_days,
            is_published=is_published,
        )
        self.uow.catalog.add_plan_version(version)

        for entry in prices:
            normalized = _normalize_price(entry)
            self.uow.catalog.add_price(
                Price(
                    id=new_ulid(),
                    plan_version_id=version.id,
                    currency=normalized["currency"],
                    amount_minor=normalized["amount_minor"],
                    interval=normalized["interval"],
                )
            )

        self.set_entitlements(version.id, entitlements or [], actor=actor)
        self.uow.flush()
        self.audit.record("plan_version.create", "plan_version", version.id, actor, after=version)
        return version

    def create_custom_plan(
        self,
        customer_id: str,
        *,
        name: str,
        prices: list[dict[str, Any]],
        entitlements: list[dict[str, Any]] | None = None,
        trial_days: int = 0,
        actor: Actor | None = None,
    ) -> PlanVersion:
        """Create a customer-specific plan version without touching the catalog."""
        require(self.uow.customers.get(customer_id), "customer", customer_id)
        plan = Plan(
            id=new_ulid(),
            key=f"custom-{customer_id}-{new_ulid()[:8]}",
            name=name,
        )
        self.uow.catalog.add_plan(plan)
        self.uow.flush()
        return self.create_plan_version(
            plan.id,
            name=name,
            prices=prices,
            trial_days=trial_days,
            entitlements=entitlements,
            scope=PlanScope.CUSTOMER_CUSTOM.value,
            customer_id=customer_id,
            actor=actor,
        )

    def create_feature(
        self,
        key: str,
        *,
        name: str | None = None,
        value_type: str = EntitlementValueType.BOOLEAN.value,
        default_value: int = 0,
        reset_period: str | None = None,
        actor: Actor | None = None,
    ) -> Feature:
        """Create a feature/module that plans can grant."""
        cleaned = key.strip() if isinstance(key, str) else ""
        if not cleaned:
            raise ValidationError("feature key is required")
        if value_type not in _VALID_VALUE_TYPES:
            raise ValidationError(f"invalid value_type {value_type!r}")
        if reset_period is not None and reset_period not in _VALID_RESET_PERIODS:
            raise ValidationError(f"invalid reset_period {reset_period!r}")
        if self.uow.catalog.get_feature_by_key(cleaned) is not None:
            raise ValidationError(f"feature key {cleaned!r} already exists")
        feature = Feature(
            id=new_ulid(),
            key=cleaned,
            name=name,
            value_type=value_type,
            default_value=default_value,
            reset_period=reset_period,
        )
        self.uow.catalog.add_feature(feature)
        self.uow.flush()
        self.audit.record("feature.create", "feature", feature.id, actor, after=feature)
        return feature

    def set_entitlements(
        self,
        plan_version_id: str,
        entitlements: list[dict[str, Any]],
        *,
        actor: Actor | None = None,
    ) -> list[PlanEntitlement]:
        """Replace the entitlements attached to a plan version."""
        require(
            self.uow.catalog.get_plan_version(plan_version_id),
            "plan_version",
            plan_version_id,
        )
        self.uow.catalog.clear_plan_entitlements(plan_version_id)
        created: list[PlanEntitlement] = []
        for entry in entitlements:
            feature_key = str(entry.get("feature_key", "")).strip()
            if not feature_key:
                raise ValidationError("entitlement entries require a feature_key")
            feature = self.uow.catalog.get_feature_by_key(feature_key)
            if feature is None:
                limit_value = entry.get("limit_value")
                feature = self.create_feature(
                    feature_key,
                    value_type=(
                        EntitlementValueType.LIMIT.value
                        if limit_value is not None
                        else EntitlementValueType.BOOLEAN.value
                    ),
                    actor=actor,
                )
            entitlement = PlanEntitlement(
                id=new_ulid(),
                plan_version_id=plan_version_id,
                feature_id=feature.id,
                value=int(entry.get("value", 1)),
                limit_value=(
                    int(entry["limit_value"]) if entry.get("limit_value") is not None else None
                ),
            )
            self.uow.catalog.add_plan_entitlement(entitlement)
            created.append(entitlement)
        self.uow.flush()
        self.audit.record(
            "plan_version.set_entitlements",
            "plan_version",
            plan_version_id,
            actor,
            after={"entitlements": [item.feature_id for item in created]},
        )
        return created

    def get_plan(self, plan_id: str) -> Plan:
        return require(self.uow.catalog.get_plan(plan_id), "plan", plan_id)

    def get_plan_by_key(self, key: str) -> Plan | None:
        return self.uow.catalog.get_plan_by_key(key)

    def get_plan_version(self, version_id: str) -> PlanVersion:
        return require(self.uow.catalog.get_plan_version(version_id), "plan_version", version_id)

    def list_plans(self, limit: int = 100, offset: int = 0) -> list[Plan]:
        return self.uow.catalog.list_plans(limit=limit, offset=offset)

    def list_prices(self, plan_version_id: str) -> list[Price]:
        return self.uow.catalog.list_prices(plan_version_id)

    def list_features(self) -> list[Feature]:
        return self.uow.catalog.list_features()

    def list_plan_entitlements(self, plan_version_id: str) -> list[PlanEntitlement]:
        return self.uow.catalog.list_plan_entitlements(plan_version_id)

    def find_price(
        self, plan_version_id: str, *, price_id: str | None = None, currency: str | None = None
    ) -> Price:
        """Return a price for a plan version, by id, currency, or first available."""
        if price_id is not None:
            price = self.uow.catalog.get_price(price_id)
            if price is None or price.plan_version_id != plan_version_id:
                raise NotFoundError(f"price {price_id!r} does not belong to the plan version")
            return price
        prices = self.uow.catalog.list_prices(plan_version_id)
        if not prices:
            raise NotFoundError(f"plan_version {plan_version_id!r} has no prices")
        if currency is not None:
            for price in prices:
                if price.currency == currency.upper():
                    return price
            raise NotFoundError(f"no {currency.upper()} price for plan version")
        return prices[0]
