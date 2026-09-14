"""Dialect-neutral reporting queries.

Aggregations are computed in Python where cross-dialect SQL would be awkward,
keeping the queries portable across PostgreSQL, MySQL, and SQLite.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from billing_engine.adapters.db import models as m

_RECURRING_STATUSES = ("trialing", "active", "past_due")


def _monthly_minor(amount_minor: int, interval: str) -> int:
    if interval == "month":
        return amount_minor
    if interval == "year":
        return amount_minor // 12
    return 0


class SqlReportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def subscription_counts(self) -> dict[str, int]:
        rows = self.session.execute(
            select(m.Subscription.status, func.count()).group_by(m.Subscription.status)
        ).all()
        return {str(status): int(count) for status, count in rows}

    def outstanding_invoices(self) -> dict[str, Any]:
        rows = self.session.execute(
            select(
                func.count(),
                func.coalesce(func.sum(m.Invoice.total_minor - m.Invoice.amount_paid_minor), 0),
            ).where(m.Invoice.status == "open")
        ).one()
        return {"count": int(rows[0]), "total_minor": int(rows[1] or 0)}

    def _mrr_minor(self, currency: str) -> int:
        rows = self.session.execute(
            select(m.Price.amount_minor, m.Price.interval, m.Subscription.quantity)
            .join(m.Subscription, m.Subscription.price_id == m.Price.id)
            .where(
                m.Subscription.status.in_(_RECURRING_STATUSES),
                m.Price.currency == currency,
            )
        ).all()
        return sum(
            _monthly_minor(int(amount), str(interval)) * int(quantity)
            for amount, interval, quantity in rows
        )

    def overview(self, currency: str) -> dict[str, Any]:
        counts = self.subscription_counts()
        customers = self.session.scalar(select(func.count()).select_from(m.Customer)) or 0
        return {
            "currency": currency,
            "customers": int(customers),
            "subscriptions": counts,
            "active_subscriptions": counts.get("active", 0)
            + counts.get("trialing", 0)
            + counts.get("past_due", 0),
            "mrr_minor": self._mrr_minor(currency),
            "outstanding_invoices": self.outstanding_invoices(),
        }

    def revenue_by_plan(self, currency: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(
                m.Plan.id,
                m.Plan.key,
                m.Plan.name,
                m.Price.amount_minor,
                m.Price.interval,
                m.Subscription.quantity,
            )
            .join(m.Subscription, m.Subscription.price_id == m.Price.id)
            .join(m.PlanVersion, m.PlanVersion.id == m.Subscription.plan_version_id)
            .join(m.Plan, m.Plan.id == m.PlanVersion.plan_id)
            .where(
                m.Subscription.status.in_(_RECURRING_STATUSES),
                m.Price.currency == currency,
            )
        ).all()
        grouped: dict[str, dict[str, Any]] = {}
        for plan_id, key, name, amount, interval, quantity in rows:
            bucket = grouped.setdefault(
                str(plan_id),
                {
                    "plan_id": str(plan_id),
                    "plan_key": str(key),
                    "plan_name": name,
                    "subscriptions": 0,
                    "mrr_minor": 0,
                },
            )
            bucket["subscriptions"] += 1
            bucket["mrr_minor"] += _monthly_minor(int(amount), str(interval)) * int(quantity)
        return sorted(grouped.values(), key=lambda item: item["mrr_minor"], reverse=True)

    def feature_adoption(self) -> list[dict[str, Any]]:
        plan_rows = self.session.execute(
            select(m.Feature.key, func.count(m.PlanEntitlement.id))
            .join(m.PlanEntitlement, m.PlanEntitlement.feature_id == m.Feature.id)
            .group_by(m.Feature.key)
        ).all()
        override_rows = self.session.execute(
            select(m.Feature.key, func.count(m.EntitlementOverride.id))
            .join(
                m.EntitlementOverride,
                m.EntitlementOverride.feature_id == m.Feature.id,
            )
            .group_by(m.Feature.key)
        ).all()
        overrides = {str(key): int(count) for key, count in override_rows}
        plan_counts = {str(key): int(count) for key, count in plan_rows}
        keys = sorted(set(plan_counts) | set(overrides))
        return [
            {
                "feature_key": key,
                "plans": plan_counts.get(key, 0),
                "overrides": overrides.get(key, 0),
            }
            for key in keys
        ]

    def channel_revenue(self, currency: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(
                m.Partner.id,
                m.Partner.name,
                m.License.id,
                m.Price.amount_minor,
                m.PartnerAgreement.discount_bps,
            )
            .select_from(m.License)
            .join(m.Partner, m.Partner.id == m.License.partner_id)
            .join(m.Subscription, m.Subscription.id == m.License.subscription_id)
            .join(m.Price, m.Price.id == m.Subscription.price_id)
            .join(m.LicenseAllocation, m.LicenseAllocation.id == m.License.allocation_id)
            .outerjoin(
                m.PartnerAgreement,
                m.PartnerAgreement.id == m.LicenseAllocation.agreement_id,
            )
            .where(
                m.Price.currency == currency,
                m.License.status.in_(("issued", "active")),
            )
        ).all()
        grouped: dict[str, dict[str, Any]] = {}
        for partner_id, name, _license_id, amount, discount_bps in rows:
            bucket = grouped.setdefault(
                str(partner_id),
                {
                    "partner_id": str(partner_id),
                    "partner_name": name,
                    "licenses": 0,
                    "value_minor": 0,
                },
            )
            bucket["licenses"] += 1
            discount = int(discount_bps or 0)
            bucket["value_minor"] += int(amount) * (10_000 - discount) // 10_000
        return sorted(grouped.values(), key=lambda item: item["value_minor"], reverse=True)
