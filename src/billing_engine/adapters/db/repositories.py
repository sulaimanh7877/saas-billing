"""Concrete repository implementations backed by a SQLAlchemy session."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
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

    def get_plan_by_key(self, key: str) -> e.Plan | None:
        model = self.session.scalar(select(m.Plan).where(m.Plan.key == key))
        return to_entity(model, e.Plan) if model else None

    def update_plan(self, plan: e.Plan) -> None:
        model = self.session.get(m.Plan, plan.id)
        if model is None:
            return
        apply_entity(model, plan)

    def list_plans(self, limit: int = 100, offset: int = 0) -> list[e.Plan]:
        models = self.session.scalars(
            select(m.Plan).order_by(m.Plan.created_at).limit(limit).offset(offset)
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
            select(m.Price).where(m.Price.plan_version_id == plan_version_id)
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
                m.Subscription.current_period_end.is_not(None),
                m.Subscription.current_period_end <= before,
                m.Subscription.status.in_(("trialing", "active", "past_due")),
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

    def balance(self, customer_id: str) -> int:
        total = self.session.scalar(
            select(func.coalesce(func.sum(m.CreditEntry.amount_minor), 0)).where(
                m.CreditEntry.customer_id == customer_id
            )
        )
        return int(total or 0)


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

    def mark_failed(self, event_id: str, error: str, retry_at: datetime) -> None:
        model = self.session.get(m.Event, event_id)
        if model is not None:
            model.status = "pending"
            model.attempts += 1
            model.last_error = error
            model.available_at = retry_at


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

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def flush(self) -> None:
        self.session.flush()
