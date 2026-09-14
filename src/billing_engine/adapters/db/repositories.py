"""Concrete repository implementations backed by a SQLAlchemy session."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from billing_engine.adapters.db import models as m
from billing_engine.adapters.db.mappers import apply_entity, to_entity
from billing_engine.adapters.db.reporting import SqlReportRepository
from billing_engine.domain import entities as e
from billing_engine.domain.repositories import (
    AuditRepository,
    CatalogRepository,
    CreditRepository,
    CustomerRepository,
    EntitlementRepository,
    EventRepository,
    InvoiceRepository,
    LicenseRepository,
    PartnerAccountRepository,
    PartnerRepository,
    ReportRepository,
    SubscriptionRepository,
)


class _Repository:
    def __init__(self, session: Session) -> None:
        self.session = session


class SqlCustomerRepository(_Repository):
    def add(self, customer: e.Customer) -> None:
        model = m.Customer()
        apply_entity(model, customer)
        self.session.add(model)

    def get(self, customer_id: str) -> e.Customer | None:
        model = self.session.get(m.Customer, customer_id)
        return to_entity(model, e.Customer) if model else None

    def get_by_external_id(self, external_id: str) -> e.Customer | None:
        model = self.session.scalar(select(m.Customer).where(m.Customer.external_id == external_id))
        return to_entity(model, e.Customer) if model else None

    def update(self, customer: e.Customer) -> None:
        model = self.session.get(m.Customer, customer.id)
        if model is None:
            return
        apply_entity(model, customer)

    def list(self, limit: int = 100, offset: int = 0) -> list[e.Customer]:
        models = self.session.scalars(
            select(m.Customer).order_by(m.Customer.created_at).limit(limit).offset(offset)
        )
        return [to_entity(model, e.Customer) for model in models]


class SqlCatalogRepository(_Repository):
    def add_product(self, product: e.Product) -> None:
        model = m.Product()
        apply_entity(model, product)
        self.session.add(model)

    def get_product(self, product_id: str) -> e.Product | None:
        model = self.session.get(m.Product, product_id)
        return to_entity(model, e.Product) if model else None

    def add_plan(self, plan: e.Plan) -> None:
        model = m.Plan()
        apply_entity(model, plan)
        self.session.add(model)

    def get_plan(self, plan_id: str) -> e.Plan | None:
        model = self.session.get(m.Plan, plan_id)
        return to_entity(model, e.Plan) if model else None

    def get_plan_for_update(self, plan_id: str) -> e.Plan | None:
        model = self.session.get(m.Plan, plan_id, with_for_update=True)
        return to_entity(model, e.Plan) if model else None

    def get_plan_by_key(self, key: str) -> e.Plan | None:
        model = self.session.scalar(select(m.Plan).where(m.Plan.key == key))
        return to_entity(model, e.Plan) if model else None

    def update_plan(self, plan: e.Plan) -> None:
        model = self.session.get(m.Plan, plan.id)
        if model is None:
            return
        apply_entity(model, plan)

    def list_plans(self, limit: int = 100, offset: int = 0) -> list[e.Plan]:
        has_versions = select(m.PlanVersion.id).where(m.PlanVersion.plan_id == m.Plan.id).exists()
        has_catalog_version = (
            select(m.PlanVersion.id)
            .where(
                m.PlanVersion.plan_id == m.Plan.id,
                m.PlanVersion.scope != "customer_custom",
            )
            .exists()
        )
        models = self.session.scalars(
            select(m.Plan)
            .where(or_(~has_versions, has_catalog_version))
            .order_by(m.Plan.created_at)
            .limit(limit)
            .offset(offset)
        )
        return [to_entity(model, e.Plan) for model in models]

    def add_plan_version(self, version: e.PlanVersion) -> None:
        model = m.PlanVersion()
        apply_entity(model, version)
        self.session.add(model)

    def get_plan_version(self, version_id: str) -> e.PlanVersion | None:
        model = self.session.get(m.PlanVersion, version_id)
        return to_entity(model, e.PlanVersion) if model else None

    def list_plan_versions(self, plan_id: str) -> list[e.PlanVersion]:
        models = self.session.scalars(
            select(m.PlanVersion)
            .where(m.PlanVersion.plan_id == plan_id)
            .order_by(m.PlanVersion.version)
        )
        return [to_entity(model, e.PlanVersion) for model in models]

    def add_price(self, price: e.Price) -> None:
        model = m.Price()
        apply_entity(model, price)
        self.session.add(model)

    def get_price(self, price_id: str) -> e.Price | None:
        model = self.session.get(m.Price, price_id)
        return to_entity(model, e.Price) if model else None

    def list_prices(self, plan_version_id: str) -> list[e.Price]:
        models = self.session.scalars(
            select(m.Price)
            .where(m.Price.plan_version_id == plan_version_id)
            .order_by(m.Price.created_at, m.Price.id)
        )
        return [to_entity(model, e.Price) for model in models]

    def add_feature(self, feature: e.Feature) -> None:
        model = m.Feature()
        apply_entity(model, feature)
        self.session.add(model)

    def get_feature(self, feature_id: str) -> e.Feature | None:
        model = self.session.get(m.Feature, feature_id)
        return to_entity(model, e.Feature) if model else None

    def get_feature_by_key(self, key: str) -> e.Feature | None:
        model = self.session.scalar(select(m.Feature).where(m.Feature.key == key))
        return to_entity(model, e.Feature) if model else None

    def list_features(self) -> list[e.Feature]:
        models = self.session.scalars(select(m.Feature).order_by(m.Feature.key))
        return [to_entity(model, e.Feature) for model in models]

    def add_plan_entitlement(self, entitlement: e.PlanEntitlement) -> None:
        model = m.PlanEntitlement()
        apply_entity(model, entitlement)
        self.session.add(model)

    def list_plan_entitlements(self, plan_version_id: str) -> list[e.PlanEntitlement]:
        models = self.session.scalars(
            select(m.PlanEntitlement).where(m.PlanEntitlement.plan_version_id == plan_version_id)
        )
        return [to_entity(model, e.PlanEntitlement) for model in models]

    def clear_plan_entitlements(self, plan_version_id: str) -> None:
        models = self.session.scalars(
            select(m.PlanEntitlement).where(m.PlanEntitlement.plan_version_id == plan_version_id)
        )
        for model in models:
            self.session.delete(model)


class SqlSubscriptionRepository(_Repository):
    def add(self, subscription: e.Subscription) -> None:
        model = m.Subscription()
        apply_entity(model, subscription)
        self.session.add(model)

    def get(self, subscription_id: str) -> e.Subscription | None:
        model = self.session.get(m.Subscription, subscription_id)
        return to_entity(model, e.Subscription) if model else None

    def update(self, subscription: e.Subscription) -> None:
        model = self.session.get(m.Subscription, subscription.id)
        if model is None:
            return
        apply_entity(model, subscription)

    def list_for_customer(self, customer_id: str) -> list[e.Subscription]:
        models = self.session.scalars(
            select(m.Subscription)
            .where(m.Subscription.customer_id == customer_id)
            .order_by(m.Subscription.created_at)
        )
        return [to_entity(model, e.Subscription) for model in models]

    def list_due(self, before: datetime) -> list[e.Subscription]:
        models = self.session.scalars(
            select(m.Subscription)
            .where(
                m.Subscription.status.in_(("trialing", "active", "past_due", "paused")),
                or_(
                    and_(
                        m.Subscription.status.in_(("active", "past_due")),
                        m.Subscription.current_period_end.is_not(None),
                        m.Subscription.current_period_end <= before,
                    ),
                    and_(
                        m.Subscription.status == "trialing",
                        m.Subscription.trial_end.is_not(None),
                        m.Subscription.trial_end <= before,
                    ),
                    and_(
                        m.Subscription.status == "paused",
                        m.Subscription.paused_until.is_not(None),
                        m.Subscription.paused_until <= before,
                    ),
                ),
            )
            .order_by(m.Subscription.current_period_end)
        )
        return [to_entity(model, e.Subscription) for model in models]

    def add_adjustment(self, adjustment: e.SubscriptionAdjustment) -> None:
        model = m.SubscriptionAdjustment()
        apply_entity(model, adjustment)
        self.session.add(model)

    def list_adjustments(self, subscription_id: str) -> list[e.SubscriptionAdjustment]:
        models = self.session.scalars(
            select(m.SubscriptionAdjustment)
            .where(m.SubscriptionAdjustment.subscription_id == subscription_id)
            .order_by(m.SubscriptionAdjustment.created_at)
        )
        return [to_entity(model, e.SubscriptionAdjustment) for model in models]


class SqlEntitlementRepository(_Repository):
    def add_override(self, override: e.EntitlementOverride) -> None:
        model = m.EntitlementOverride()
        apply_entity(model, override)
        self.session.add(model)

    def get_override(self, override_id: str) -> e.EntitlementOverride | None:
        model = self.session.get(m.EntitlementOverride, override_id)
        return to_entity(model, e.EntitlementOverride) if model else None

    def get_customer_override(
        self, customer_id: str, feature_id: str
    ) -> e.EntitlementOverride | None:
        model = self.session.scalar(
            select(m.EntitlementOverride).where(
                m.EntitlementOverride.scope == "customer",
                m.EntitlementOverride.customer_id == customer_id,
                m.EntitlementOverride.feature_id == feature_id,
            )
        )
        return to_entity(model, e.EntitlementOverride) if model else None

    def get_subscription_override(
        self, subscription_id: str, feature_id: str
    ) -> e.EntitlementOverride | None:
        model = self.session.scalar(
            select(m.EntitlementOverride).where(
                m.EntitlementOverride.scope == "subscription",
                m.EntitlementOverride.subscription_id == subscription_id,
                m.EntitlementOverride.feature_id == feature_id,
            )
        )
        return to_entity(model, e.EntitlementOverride) if model else None

    def list_for_customer(self, customer_id: str) -> list[e.EntitlementOverride]:
        models = self.session.scalars(
            select(m.EntitlementOverride).where(m.EntitlementOverride.customer_id == customer_id)
        )
        return [to_entity(model, e.EntitlementOverride) for model in models]

    def list_for_subscription(self, subscription_id: str) -> list[e.EntitlementOverride]:
        models = self.session.scalars(
            select(m.EntitlementOverride).where(
                m.EntitlementOverride.subscription_id == subscription_id
            )
        )
        return [to_entity(model, e.EntitlementOverride) for model in models]

    def delete_override(self, override_id: str) -> None:
        model = self.session.get(m.EntitlementOverride, override_id)
        if model is not None:
            self.session.delete(model)


class SqlInvoiceRepository(_Repository):
    def add_invoice(self, invoice: e.Invoice) -> None:
        model = m.Invoice()
        apply_entity(model, invoice)
        self.session.add(model)

    def get_invoice(self, invoice_id: str) -> e.Invoice | None:
        model = self.session.get(m.Invoice, invoice_id)
        return to_entity(model, e.Invoice) if model else None

    def update_invoice(self, invoice: e.Invoice) -> None:
        model = self.session.get(m.Invoice, invoice.id)
        if model is None:
            return
        apply_entity(model, invoice)

    def list_invoices(self, customer_id: str) -> list[e.Invoice]:
        models = self.session.scalars(
            select(m.Invoice)
            .where(m.Invoice.customer_id == customer_id)
            .order_by(m.Invoice.created_at)
        )
        return [to_entity(model, e.Invoice) for model in models]

    def add_line(self, line: e.InvoiceLine) -> None:
        model = m.InvoiceLine()
        apply_entity(model, line)
        self.session.add(model)

    def list_lines(self, invoice_id: str) -> list[e.InvoiceLine]:
        models = self.session.scalars(
            select(m.InvoiceLine).where(m.InvoiceLine.invoice_id == invoice_id)
        )
        return [to_entity(model, e.InvoiceLine) for model in models]

    def add_payment(self, payment: e.Payment) -> None:
        model = m.Payment()
        apply_entity(model, payment)
        self.session.add(model)

    def list_payments(self, invoice_id: str) -> list[e.Payment]:
        models = self.session.scalars(select(m.Payment).where(m.Payment.invoice_id == invoice_id))
        return [to_entity(model, e.Payment) for model in models]


class SqlCreditRepository(_Repository):
    def add_entry(self, entry: e.CreditEntry) -> None:
        model = m.CreditEntry()
        apply_entity(model, entry)
        self.session.add(model)

    def list_entries(self, customer_id: str) -> list[e.CreditEntry]:
        models = self.session.scalars(
            select(m.CreditEntry)
            .where(m.CreditEntry.customer_id == customer_id)
            .order_by(m.CreditEntry.created_at)
        )
        return [to_entity(model, e.CreditEntry) for model in models]

    def balance(self, customer_id: str, currency: str) -> int:
        total = self.session.scalar(
            select(func.coalesce(func.sum(m.CreditEntry.amount_minor), 0)).where(
                m.CreditEntry.customer_id == customer_id,
                m.CreditEntry.currency == currency.upper(),
            )
        )
        return int(total or 0)

    def balance_for_update(self, customer_id: str, currency: str) -> int:
        rows = self.session.scalars(
            select(m.CreditEntry)
            .where(
                m.CreditEntry.customer_id == customer_id,
                m.CreditEntry.currency == currency.upper(),
            )
            .with_for_update()
        )
        return sum(entry.amount_minor for entry in rows)


class SqlAuditRepository(_Repository):
    def add(self, entry: e.AuditLog) -> None:
        model = m.AuditLog()
        apply_entity(model, entry)
        self.session.add(model)

    def list(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[e.AuditLog]:
        statement = select(m.AuditLog).order_by(m.AuditLog.created_at.desc())
        if entity_type is not None:
            statement = statement.where(m.AuditLog.entity_type == entity_type)
        if entity_id is not None:
            statement = statement.where(m.AuditLog.entity_id == entity_id)
        if action is not None:
            statement = statement.where(m.AuditLog.action == action)
        if actor_id is not None:
            statement = statement.where(m.AuditLog.actor_id == actor_id)
        if since is not None:
            statement = statement.where(m.AuditLog.created_at >= since)
        models = self.session.scalars(statement.limit(limit).offset(offset))
        return [to_entity(model, e.AuditLog) for model in models]


class SqlEventRepository(_Repository):
    def add(self, event: e.Event) -> None:
        model = m.Event()
        apply_entity(model, event)
        self.session.add(model)

    def list_pending(self, now: datetime, limit: int = 100) -> list[e.Event]:
        models = self.session.scalars(
            select(m.Event)
            .where(
                m.Event.status == "pending",
                (m.Event.available_at.is_(None)) | (m.Event.available_at <= now),
            )
            .order_by(m.Event.created_at)
            .limit(limit)
        )
        return [to_entity(model, e.Event) for model in models]

    def mark_delivered(self, event_id: str, delivered_at: datetime) -> None:
        model = self.session.get(m.Event, event_id)
        if model is not None:
            model.status = "delivered"
            model.delivered_at = delivered_at

    def mark_failed(
        self, event_id: str, error: str, retry_at: datetime, *, final: bool = False
    ) -> None:
        model = self.session.get(m.Event, event_id)
        if model is not None:
            model.status = "failed" if final else "pending"
            model.attempts += 1
            model.last_error = error
            model.available_at = retry_at


class SqlPartnerRepository(_Repository):
    def add_partner(self, partner: e.Partner) -> None:
        model = m.Partner()
        apply_entity(model, partner)
        self.session.add(model)

    def get_partner(self, partner_id: str) -> e.Partner | None:
        model = self.session.get(m.Partner, partner_id)
        return to_entity(model, e.Partner) if model else None

    def get_partner_by_external_id(self, external_id: str) -> e.Partner | None:
        model = self.session.scalar(select(m.Partner).where(m.Partner.external_id == external_id))
        return to_entity(model, e.Partner) if model else None

    def update_partner(self, partner: e.Partner) -> None:
        model = self.session.get(m.Partner, partner.id)
        if model is not None:
            apply_entity(model, partner)

    def list_partners(self, limit: int = 100, offset: int = 0) -> list[e.Partner]:
        models = self.session.scalars(
            select(m.Partner).order_by(m.Partner.created_at).limit(limit).offset(offset)
        )
        return [to_entity(model, e.Partner) for model in models]

    def add_agreement(self, agreement: e.PartnerAgreement) -> None:
        model = m.PartnerAgreement()
        apply_entity(model, agreement)
        self.session.add(model)

    def get_agreement(self, agreement_id: str) -> e.PartnerAgreement | None:
        model = self.session.get(m.PartnerAgreement, agreement_id)
        return to_entity(model, e.PartnerAgreement) if model else None

    def list_agreements(self, partner_id: str) -> list[e.PartnerAgreement]:
        models = self.session.scalars(
            select(m.PartnerAgreement)
            .where(m.PartnerAgreement.partner_id == partner_id)
            .order_by(m.PartnerAgreement.created_at, m.PartnerAgreement.effective_from)
        )
        return [to_entity(model, e.PartnerAgreement) for model in models]

    def add_commission_rule(self, rule: e.CommissionRule) -> None:
        model = m.CommissionRule()
        apply_entity(model, rule)
        self.session.add(model)

    def get_commission_rule(self, rule_id: str) -> e.CommissionRule | None:
        model = self.session.get(m.CommissionRule, rule_id)
        return to_entity(model, e.CommissionRule) if model else None

    def list_commission_rules(self) -> list[e.CommissionRule]:
        models = self.session.scalars(
            select(m.CommissionRule).order_by(m.CommissionRule.created_at)
        )
        return [to_entity(model, e.CommissionRule) for model in models]


class SqlLicenseRepository(_Repository):
    def add_allocation(self, allocation: e.LicenseAllocation) -> None:
        model = m.LicenseAllocation()
        apply_entity(model, allocation)
        self.session.add(model)

    def get_allocation(self, allocation_id: str) -> e.LicenseAllocation | None:
        model = self.session.get(m.LicenseAllocation, allocation_id)
        return to_entity(model, e.LicenseAllocation) if model else None

    def get_allocation_for_update(self, allocation_id: str) -> e.LicenseAllocation | None:
        model = self.session.get(m.LicenseAllocation, allocation_id, with_for_update=True)
        return to_entity(model, e.LicenseAllocation) if model else None

    def update_allocation(self, allocation: e.LicenseAllocation) -> None:
        model = self.session.get(m.LicenseAllocation, allocation.id)
        if model is not None:
            apply_entity(model, allocation)

    def list_allocations(self, partner_id: str) -> list[e.LicenseAllocation]:
        models = self.session.scalars(
            select(m.LicenseAllocation)
            .where(m.LicenseAllocation.partner_id == partner_id)
            .order_by(m.LicenseAllocation.created_at)
        )
        return [to_entity(model, e.LicenseAllocation) for model in models]

    def add_license(self, license_: e.License) -> None:
        model = m.License()
        apply_entity(model, license_)
        self.session.add(model)

    def get_license(self, license_id: str) -> e.License | None:
        model = self.session.get(m.License, license_id)
        return to_entity(model, e.License) if model else None

    def update_license(self, license_: e.License) -> None:
        model = self.session.get(m.License, license_.id)
        if model is not None:
            apply_entity(model, license_)

    def list_licenses(self, partner_id: str) -> list[e.License]:
        models = self.session.scalars(
            select(m.License)
            .where(m.License.partner_id == partner_id)
            .order_by(m.License.created_at)
        )
        return [to_entity(model, e.License) for model in models]

    def list_licenses_for_allocation(self, allocation_id: str) -> list[e.License]:
        models = self.session.scalars(
            select(m.License).where(m.License.allocation_id == allocation_id)
        )
        return [to_entity(model, e.License) for model in models]


class SqlPartnerAccountRepository(_Repository):
    def get_account(
        self, partner_id: str, currency: str, account_type: str
    ) -> e.PartnerAccount | None:
        model = self.session.scalar(
            select(m.PartnerAccount).where(
                m.PartnerAccount.partner_id == partner_id,
                m.PartnerAccount.currency == currency.upper(),
                m.PartnerAccount.account_type == account_type,
            )
        )
        return to_entity(model, e.PartnerAccount) if model else None

    def get_account_for_update(
        self, partner_id: str, currency: str, account_type: str
    ) -> e.PartnerAccount | None:
        model = self.session.scalar(
            select(m.PartnerAccount)
            .where(
                m.PartnerAccount.partner_id == partner_id,
                m.PartnerAccount.currency == currency.upper(),
                m.PartnerAccount.account_type == account_type,
            )
            .with_for_update()
        )
        return to_entity(model, e.PartnerAccount) if model else None

    def ensure_account(self, account: e.PartnerAccount) -> e.PartnerAccount:
        existing = self.get_account(account.partner_id, account.currency, account.account_type)
        if existing is not None:
            return existing
        try:
            with self.session.begin_nested():
                model = m.PartnerAccount()
                apply_entity(model, account)
                self.session.add(model)
                self.session.flush()
            return account
        except IntegrityError:
            existing = self.get_account(account.partner_id, account.currency, account.account_type)
            if existing is None:
                raise
            return existing

    def list_accounts(self, partner_id: str) -> list[e.PartnerAccount]:
        models = self.session.scalars(
            select(m.PartnerAccount).where(m.PartnerAccount.partner_id == partner_id)
        )
        return [to_entity(model, e.PartnerAccount) for model in models]

    def add_account(self, account: e.PartnerAccount) -> None:
        model = m.PartnerAccount()
        apply_entity(model, account)
        self.session.add(model)

    def update_account(self, account: e.PartnerAccount) -> None:
        model = self.session.get(m.PartnerAccount, account.id)
        if model is not None:
            apply_entity(model, account)

    def add_entry(self, entry: e.PartnerLedgerEntry) -> None:
        model = m.PartnerLedgerEntry()
        apply_entity(model, entry)
        self.session.add(model)

    def list_entries(
        self,
        partner_id: str,
        currency: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[e.PartnerLedgerEntry]:
        statement = select(m.PartnerLedgerEntry).where(
            m.PartnerLedgerEntry.partner_id == partner_id
        )
        if currency is not None:
            statement = statement.where(m.PartnerLedgerEntry.currency == currency.upper())
        if since is not None:
            statement = statement.where(m.PartnerLedgerEntry.created_at >= since)
        if until is not None:
            statement = statement.where(m.PartnerLedgerEntry.created_at <= until)
        models = self.session.scalars(statement.order_by(m.PartnerLedgerEntry.created_at))
        return [to_entity(model, e.PartnerLedgerEntry) for model in models]

    def add_invoice(self, invoice: e.PartnerInvoice) -> None:
        model = m.PartnerInvoice()
        apply_entity(model, invoice)
        self.session.add(model)

    def get_invoice(self, invoice_id: str) -> e.PartnerInvoice | None:
        model = self.session.get(m.PartnerInvoice, invoice_id)
        return to_entity(model, e.PartnerInvoice) if model else None

    def update_invoice(self, invoice: e.PartnerInvoice) -> None:
        model = self.session.get(m.PartnerInvoice, invoice.id)
        if model is not None:
            apply_entity(model, invoice)

    def list_invoices(self, partner_id: str) -> list[e.PartnerInvoice]:
        models = self.session.scalars(
            select(m.PartnerInvoice)
            .where(m.PartnerInvoice.partner_id == partner_id)
            .order_by(m.PartnerInvoice.created_at)
        )
        return [to_entity(model, e.PartnerInvoice) for model in models]

    def add_invoice_line(self, line: e.PartnerInvoiceLine) -> None:
        model = m.PartnerInvoiceLine()
        apply_entity(model, line)
        self.session.add(model)

    def list_invoice_lines(self, invoice_id: str) -> list[e.PartnerInvoiceLine]:
        models = self.session.scalars(
            select(m.PartnerInvoiceLine).where(
                m.PartnerInvoiceLine.partner_invoice_id == invoice_id
            )
        )
        return [to_entity(model, e.PartnerInvoiceLine) for model in models]

    def add_payment(self, payment: e.PartnerPayment) -> None:
        model = m.PartnerPayment()
        apply_entity(model, payment)
        self.session.add(model)

    def list_payments(self, partner_id: str) -> list[e.PartnerPayment]:
        models = self.session.scalars(
            select(m.PartnerPayment)
            .where(m.PartnerPayment.partner_id == partner_id)
            .order_by(m.PartnerPayment.created_at)
        )
        return [to_entity(model, e.PartnerPayment) for model in models]

    def add_payout(self, payout: e.PartnerPayout) -> None:
        model = m.PartnerPayout()
        apply_entity(model, payout)
        self.session.add(model)

    def get_payout(self, payout_id: str) -> e.PartnerPayout | None:
        model = self.session.get(m.PartnerPayout, payout_id)
        return to_entity(model, e.PartnerPayout) if model else None

    def update_payout(self, payout: e.PartnerPayout) -> None:
        model = self.session.get(m.PartnerPayout, payout.id)
        if model is not None:
            apply_entity(model, payout)

    def add_payout_line(self, line: e.PartnerPayoutLine) -> None:
        model = m.PartnerPayoutLine()
        apply_entity(model, line)
        self.session.add(model)

    def list_payout_lines(self, payout_id: str) -> list[e.PartnerPayoutLine]:
        models = self.session.scalars(
            select(m.PartnerPayoutLine).where(m.PartnerPayoutLine.payout_id == payout_id)
        )
        return [to_entity(model, e.PartnerPayoutLine) for model in models]

    def add_statement(self, statement: e.PartnerStatement) -> None:
        model = m.PartnerStatement()
        apply_entity(model, statement)
        self.session.add(model)

    def list_statements(self, partner_id: str) -> list[e.PartnerStatement]:
        models = self.session.scalars(
            select(m.PartnerStatement)
            .where(m.PartnerStatement.partner_id == partner_id)
            .order_by(m.PartnerStatement.period_start)
        )
        return [to_entity(model, e.PartnerStatement) for model in models]


class SqlUnitOfWork:
    """A session-backed unit of work exposing all repositories."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.customers: CustomerRepository = SqlCustomerRepository(session)
        self.catalog: CatalogRepository = SqlCatalogRepository(session)
        self.subscriptions: SubscriptionRepository = SqlSubscriptionRepository(session)
        self.entitlements: EntitlementRepository = SqlEntitlementRepository(session)
        self.invoices: InvoiceRepository = SqlInvoiceRepository(session)
        self.credits: CreditRepository = SqlCreditRepository(session)
        self.audit: AuditRepository = SqlAuditRepository(session)
        self.events: EventRepository = SqlEventRepository(session)
        self.reports: ReportRepository = SqlReportRepository(session)
        self.partners: PartnerRepository = SqlPartnerRepository(session)
        self.licenses: LicenseRepository = SqlLicenseRepository(session)
        self.partner_accounts: PartnerAccountRepository = SqlPartnerAccountRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()
