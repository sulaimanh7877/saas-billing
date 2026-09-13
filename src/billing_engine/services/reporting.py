"""Read-only reporting and analytics."""

from __future__ import annotations

from typing import Any

from billing_engine.services.base import Service


class ReportService(Service):
    def overview(self, currency: str | None = None) -> dict[str, Any]:
        """Return headline metrics."""
        return self.uow.reports.overview((currency or self.default_currency).upper())

    def subscription_counts(self) -> dict[str, int]:
        """Return subscription counts grouped by status."""
        return self.uow.reports.subscription_counts()

    def revenue_by_plan(self, currency: str | None = None) -> list[dict[str, Any]]:
        """Return monthly recurring revenue grouped by plan."""
        return self.uow.reports.revenue_by_plan((currency or self.default_currency).upper())

    def outstanding_invoices(self) -> dict[str, Any]:
        """Return open invoice count and outstanding amount."""
        return self.uow.reports.outstanding_invoices()

    def feature_adoption(self) -> list[dict[str, Any]]:
        """Return how often each feature appears in plans and overrides."""
        return self.uow.reports.feature_adoption()
