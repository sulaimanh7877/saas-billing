"""Service registry: builds all services over one unit of work."""

from __future__ import annotations

from billing_engine.domain.repositories import Repositories
from billing_engine.services.catalog import CatalogService
from billing_engine.services.credits import CreditService
from billing_engine.services.customers import CustomerService
from billing_engine.services.entitlements import EntitlementService
from billing_engine.services.invoices import InvoiceService
from billing_engine.services.licenses import LicenseService
from billing_engine.services.partner_accounts import PartnerAccountService
from billing_engine.services.partners import PartnerService
from billing_engine.services.reporting import ReportService
from billing_engine.services.subscriptions import SubscriptionService


class Services:
    """A bundle of service instances sharing a single unit of work."""

    def __init__(
        self,
        uow: Repositories,
        *,
        default_currency: str = "USD",
        grace_period_days: int = 0,
    ) -> None:
        self.uow = uow
        self.default_currency = default_currency
        self.grace_period_days = grace_period_days
        self.customers = CustomerService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.catalog = CatalogService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.subscriptions = SubscriptionService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.entitlements = EntitlementService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.invoices = InvoiceService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.credits = CreditService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.reports = ReportService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.partners = PartnerService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.licenses = LicenseService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
        self.partner_accounts = PartnerAccountService(
            uow, default_currency=default_currency, grace_period_days=grace_period_days
        )
