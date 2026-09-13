"""Shared helpers for building test fixtures."""

from __future__ import annotations

from typing import Any

from billing_engine.domain.entities import Customer, PlanVersion
from billing_engine.services.registry import Services


def make_customer(services: Services, external_id: str = "user-1", **kwargs: Any) -> Customer:
    return services.customers.create(external_id, **kwargs)


def make_plan(
    services: Services,
    key: str = "pro",
    *,
    amount: int = 2900,
    interval: str = "month",
    trial_days: int = 0,
    feature_keys: tuple[str, ...] = ("reports",),
    entitlements: list[dict[str, Any]] | None = None,
) -> PlanVersion:
    plan = services.catalog.create_plan(key, key.title())
    entries = (
        entitlements
        if entitlements is not None
        else [{"feature_key": feature_key, "limit_value": 1} for feature_key in feature_keys]
    )
    return services.catalog.create_plan_version(
        plan.id,
        prices=[{"amount_minor": amount, "currency": "USD", "interval": interval}],
        trial_days=trial_days,
        entitlements=entries,
    )
