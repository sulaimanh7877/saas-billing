"""FastAPI adapter: mountable router, standalone app, and API-key auth."""

from __future__ import annotations

import hmac
from collections.abc import Callable, Iterator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from billing_engine import __version__
from billing_engine.adapters.api import schemas
from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.config import EngineConfig
from billing_engine.domain.errors import (
    AllocationExhaustedError,
    BillingError,
    ConfigurationError,
    ConflictError,
    EntitlementError,
    NotFoundError,
    ValidationError,
)
from billing_engine.domain.value_objects import utcnow
from billing_engine.services.context import Actor, snapshot
from billing_engine.services.registry import Services

_ERROR_STATUS: dict[type[BillingError], int] = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    EntitlementError: status.HTTP_403_FORBIDDEN,
    AllocationExhaustedError: status.HTTP_409_CONFLICT,
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def get_engine(request: Request) -> Any:
    return request.app.state.engine


def get_actor(request: Request) -> Actor:
    api_key = getattr(request.app.state, "api_key", None)
    return Actor(
        type="api_key" if api_key else "system",
        id=request.headers.get("X-Actor-Id"),
        source="rest",
        ip=request.client.host if request.client else None,
    )


def get_services(request: Request) -> Iterator[Services]:
    """Return the request-scoped services bundle.

    Under :func:`create_app` the bundle (and its transaction) is owned by the
    middleware and simply reused here. When the bare ``router`` is mounted
    directly, this dependency opens its own session and commits or rolls back,
    so the documented mount-your-own-app path works without extra wiring.
    """
    existing = getattr(request.state, "services", None)
    if existing is not None:
        yield existing
        return

    engine = request.app.state.engine
    session = engine.session_factory()
    uow = SqlUnitOfWork(session)
    bundle = Services(
        uow,
        default_currency=engine.config.default_currency,
        grace_period_days=engine.config.grace_period_days,
        trial_days=engine.config.trial_days,
    )
    try:
        yield bundle
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        session.close()


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None),
) -> None:
    expected = getattr(request.app.state, "api_key", None)
    if expected is None:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")


def _build_router() -> Any:
    from fastapi import APIRouter

    api = APIRouter(dependencies=[Depends(require_api_key)])

    @api.post("/customers", tags=["customers"])
    def create_customer(
        body: schemas.CustomerCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        customer = services.customers.create(
            body.external_id,
            email=body.email,
            name=body.name,
            currency=body.currency,
            attributes=body.attributes,
            partner_id=body.partner_id,
            actor=actor,
        )
        return snapshot(customer)

    @api.get("/customers", tags=["customers"])
    def list_customers(
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.customers.list(limit=limit, offset=offset)]

    @api.get("/customers/{customer_id}", tags=["customers"])
    def get_customer(customer_id: str, services: Services = Depends(get_services)) -> Any:
        return snapshot(services.customers.get(customer_id))

    @api.patch("/customers/{customer_id}", tags=["customers"])
    def update_customer(
        customer_id: str,
        body: schemas.CustomerUpdate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.customers.update(
                customer_id,
                email=body.email,
                name=body.name,
                attributes=body.attributes,
                actor=actor,
            )
        )

    @api.post("/features", tags=["catalog"])
    def create_feature(
        body: schemas.FeatureCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.catalog.create_feature(
                body.key,
                name=body.name,
                value_type=body.value_type,
                default_value=body.default_value,
                reset_period=body.reset_period,
                actor=actor,
            )
        )

    @api.get("/features", tags=["catalog"])
    def list_features(services: Services = Depends(get_services)) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.catalog.list_features()]

    @api.post("/plans", tags=["catalog"])
    def create_plan(
        body: schemas.PlanCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.catalog.create_plan(
                body.key, body.name, product_id=body.product_id, actor=actor
            )
        )

    @api.get("/plans", tags=["catalog"])
    def list_plans(
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.catalog.list_plans(limit=limit, offset=offset)]

    @api.post("/plans/{plan_id}/versions", tags=["catalog"])
    def create_plan_version(
        plan_id: str,
        body: schemas.PlanVersionCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        version = services.catalog.create_plan_version(
            plan_id,
            name=body.name,
            prices=[item.model_dump() for item in body.prices],
            trial_days=body.trial_days,
            entitlements=[item.model_dump() for item in body.entitlements],
            is_published=body.is_published,
            actor=actor,
        )
        return snapshot(version)

    @api.get("/plans/{plan_id}/versions", tags=["catalog"])
    def list_plan_versions(
        plan_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.uow.catalog.list_plan_versions(plan_id)]

    @api.post("/custom-plans", tags=["catalog"])
    def create_custom_plan(
        body: schemas.CustomPlanCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.catalog.create_custom_plan(
                body.customer_id,
                name=body.name,
                prices=[item.model_dump() for item in body.prices],
                trial_days=body.trial_days,
                entitlements=[item.model_dump() for item in body.entitlements],
                actor=actor,
            )
        )

    @api.get("/plan-versions/{version_id}/prices", tags=["catalog"])
    def list_prices(
        version_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.catalog.list_prices(version_id)]

    @api.post("/plan-versions/{version_id}/entitlements", tags=["catalog"])
    def set_entitlements(
        version_id: str,
        body: schemas.EntitlementsUpdate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> list[dict[str, Any]]:
        created = services.catalog.set_entitlements(
            version_id,
            [item.model_dump() for item in body.entitlements],
            actor=actor,
        )
        return [snapshot(item) for item in created]

    @api.post("/subscriptions", tags=["subscriptions"])
    def create_subscription(
        body: schemas.SubscriptionCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.subscriptions.create(
                body.customer_id,
                body.plan_version_id,
                price_id=body.price_id,
                currency=body.currency,
                trial_days=body.trial_days,
                quantity=body.quantity,
                collection_method=body.collection_method,
                start_at=body.start_at,
                actor=actor,
            )
        )

    @api.get("/subscriptions/{subscription_id}", tags=["subscriptions"])
    def get_subscription(subscription_id: str, services: Services = Depends(get_services)) -> Any:
        return snapshot(services.subscriptions.get(subscription_id))

    @api.get("/customers/{customer_id}/subscriptions", tags=["subscriptions"])
    def list_subscriptions(
        customer_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.subscriptions.list_for_customer(customer_id)]

    @api.post("/subscriptions/{subscription_id}/extend", tags=["subscriptions"])
    def extend_subscription(
        subscription_id: str,
        body: schemas.ExtendRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.subscriptions.extend(
                subscription_id,
                days=body.days,
                months=body.months,
                until=body.until,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/subscriptions/{subscription_id}/extend-trial", tags=["subscriptions"])
    def extend_trial(
        subscription_id: str,
        body: schemas.ExtendTrialRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.subscriptions.extend_trial(
                subscription_id, body.days, reason=body.reason, actor=actor
            )
        )

    @api.post("/subscriptions/{subscription_id}/pause", tags=["subscriptions"])
    def pause_subscription(
        subscription_id: str,
        body: schemas.PauseRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        body = body or schemas.PauseRequest()
        return snapshot(
            services.subscriptions.pause(
                subscription_id, until=body.until, reason=body.reason, actor=actor
            )
        )

    @api.post("/subscriptions/{subscription_id}/resume", tags=["subscriptions"])
    def resume_subscription(
        subscription_id: str,
        body: schemas.ReasonRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        reason = body.reason if body else None
        return snapshot(services.subscriptions.resume(subscription_id, reason=reason, actor=actor))

    @api.post("/subscriptions/{subscription_id}/cancel", tags=["subscriptions"])
    def cancel_subscription(
        subscription_id: str,
        body: schemas.CancelRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        body = body or schemas.CancelRequest()
        return snapshot(
            services.subscriptions.cancel(
                subscription_id,
                at_period_end=body.at_period_end,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/subscriptions/{subscription_id}/reactivate", tags=["subscriptions"])
    def reactivate_subscription(
        subscription_id: str,
        body: schemas.ReasonRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        reason = body.reason if body else None
        return snapshot(
            services.subscriptions.reactivate(subscription_id, reason=reason, actor=actor)
        )

    @api.post("/subscriptions/{subscription_id}/change-plan", tags=["subscriptions"])
    def change_plan(
        subscription_id: str,
        body: schemas.ChangePlanRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.subscriptions.change_plan(
                subscription_id,
                body.plan_version_id,
                price_id=body.price_id,
                currency=body.currency,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/subscriptions/{subscription_id}/renew", tags=["subscriptions"])
    def renew_subscription(
        subscription_id: str,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(services.subscriptions.renew(subscription_id, actor=actor))

    @api.post("/subscriptions/process-due", tags=["subscriptions"])
    def process_due(
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return {"renewed": services.subscriptions.process_due(actor=actor)}

    @api.get("/customers/{customer_id}/entitlements", tags=["entitlements"])
    def list_entitlements(customer_id: str, services: Services = Depends(get_services)) -> Any:
        resolved = services.entitlements.list_for_customer(customer_id)
        return {
            key: {
                "value": item.value,
                "limit_value": item.limit_value,
                "value_type": item.value_type,
                "source": item.source,
            }
            for key, item in resolved.items()
        }

    @api.post("/entitlements/check", tags=["entitlements"])
    def check_entitlement(
        body: schemas.CheckRequest, services: Services = Depends(get_services)
    ) -> Any:
        resolved = services.entitlements.resolve(body.customer_id, body.feature_key)
        return {
            "customer_id": body.customer_id,
            "feature_key": body.feature_key,
            "allowed": services.entitlements.can(body.customer_id, body.feature_key),
            "value": resolved.value,
            "limit_value": resolved.limit_value,
            "source": resolved.source,
        }

    @api.post("/customers/{customer_id}/overrides", tags=["entitlements"])
    def set_customer_override(
        customer_id: str,
        body: schemas.OverrideRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.entitlements.set_customer_override(
                customer_id,
                body.feature_key,
                value=body.value,
                limit_value=body.limit_value,
                expires_at=body.expires_at,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/subscriptions/{subscription_id}/overrides", tags=["entitlements"])
    def set_subscription_override(
        subscription_id: str,
        body: schemas.OverrideRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.entitlements.set_subscription_override(
                subscription_id,
                body.feature_key,
                value=body.value,
                limit_value=body.limit_value,
                expires_at=body.expires_at,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/invoices", tags=["invoices"])
    def create_invoice(
        body: schemas.InvoiceCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.invoices.create(
                body.customer_id,
                lines=[item.model_dump() for item in body.lines],
                currency=body.currency,
                due_date=body.due_date,
                subscription_id=body.subscription_id,
                notes=body.notes,
                finalize=body.finalize,
                actor=actor,
            )
        )

    @api.get("/invoices/{invoice_id}", tags=["invoices"])
    def get_invoice(invoice_id: str, services: Services = Depends(get_services)) -> Any:
        return snapshot(services.invoices.get(invoice_id))

    @api.get("/customers/{customer_id}/invoices", tags=["invoices"])
    def list_invoices(
        customer_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.invoices.list_for_customer(customer_id)]

    @api.post("/invoices/{invoice_id}/finalize", tags=["invoices"])
    def finalize_invoice(
        invoice_id: str,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(services.invoices.finalize(invoice_id, actor=actor))

    @api.post("/invoices/{invoice_id}/void", tags=["invoices"])
    def void_invoice(
        invoice_id: str,
        body: schemas.ReasonRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        reason = body.reason if body else None
        return snapshot(services.invoices.void(invoice_id, reason=reason, actor=actor))

    @api.post("/invoices/{invoice_id}/payments", tags=["invoices"])
    def record_payment(
        invoice_id: str,
        body: schemas.PaymentCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.invoices.record_payment(
                invoice_id,
                body.amount_minor,
                method=body.method,
                reference=body.reference,
                actor=actor,
            )
        )

    @api.post("/customers/{customer_id}/credits", tags=["credits"])
    def grant_credit(
        customer_id: str,
        body: schemas.CreditCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.credits.grant(customer_id, body.amount_minor, reason=body.reason, actor=actor)
        )

    @api.get("/customers/{customer_id}/credits", tags=["credits"])
    def get_credits(customer_id: str, services: Services = Depends(get_services)) -> Any:
        return {
            "balance_minor": services.credits.balance(customer_id),
            "entries": [snapshot(item) for item in services.credits.list_entries(customer_id)],
        }

    @api.get("/reports/overview", tags=["reports"])
    def report_overview(
        currency: str | None = None, services: Services = Depends(get_services)
    ) -> Any:
        return services.reports.overview(currency)

    @api.get("/reports/revenue", tags=["reports"])
    def report_revenue(
        currency: str | None = None, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return services.reports.revenue_by_plan(currency)

    @api.get("/reports/subscriptions", tags=["reports"])
    def report_subscriptions(services: Services = Depends(get_services)) -> dict[str, int]:
        return services.reports.subscription_counts()

    @api.get("/reports/entitlements", tags=["reports"])
    def report_entitlements(services: Services = Depends(get_services)) -> list[dict[str, Any]]:
        return services.reports.feature_adoption()

    @api.get("/reports/payments", tags=["reports"])
    def report_payments(services: Services = Depends(get_services)) -> Any:
        return services.reports.outstanding_invoices()

    @api.get("/audit-logs", tags=["audit"])
    def list_audit_logs(
        entity_type: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        actor_id: str | None = None,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        entries = services.uow.audit.list(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            limit=limit,
            offset=offset,
        )
        return [snapshot(item) for item in entries]

    @api.get("/events", tags=["events"])
    def list_events(
        limit: int = Query(100, ge=1, le=500),
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.uow.events.list_pending(utcnow(), limit)]

    # --- Channel & Partners -------------------------------------------------

    @api.post("/partners", tags=["partners"])
    def create_partner(
        body: schemas.PartnerCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partners.create(
                body.name,
                type=body.type,
                external_id=body.external_id,
                email=body.email,
                phone=body.phone,
                currency=body.currency,
                parent_partner_id=body.parent_partner_id,
                attributes=body.attributes,
                actor=actor,
            )
        )

    @api.get("/partners", tags=["partners"])
    def list_partners(
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        return [
            snapshot(item) for item in services.partners.list_partners(limit=limit, offset=offset)
        ]

    @api.get("/partners/{partner_id}", tags=["partners"])
    def get_partner(partner_id: str, services: Services = Depends(get_services)) -> Any:
        return snapshot(services.partners.get(partner_id))

    @api.post("/commission-rules", tags=["partners"])
    def create_commission_rule(
        body: schemas.CommissionRuleCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partners.create_commission_rule(
                basis=body.basis,
                rate_bps=body.rate_bps,
                tiers=body.tiers,
                levels=body.levels,
                actor=actor,
            )
        )

    @api.get("/commission-rules", tags=["partners"])
    def list_commission_rules(services: Services = Depends(get_services)) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.partners.list_commission_rules()]

    @api.post("/partners/{partner_id}/agreements", tags=["partners"])
    def create_agreement(
        partner_id: str,
        body: schemas.AgreementCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partners.create_agreement(
                partner_id,
                money_model=body.money_model,
                currency=body.currency,
                discount_bps=body.discount_bps,
                plan_id=body.plan_id,
                commission_rule_id=body.commission_rule_id,
                effective_from=body.effective_from,
                effective_to=body.effective_to,
                actor=actor,
            )
        )

    @api.get("/partners/{partner_id}/agreements", tags=["partners"])
    def list_agreements(
        partner_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.partners.list_agreements(partner_id)]

    @api.post("/partners/{partner_id}/allocations", tags=["licenses"])
    def allocate_licenses(
        partner_id: str,
        body: schemas.AllocationCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.licenses.allocate(
                partner_id,
                body.plan_version_id,
                body.quantity,
                agreement_id=body.agreement_id,
                parent_allocation_id=body.parent_allocation_id,
                actor=actor,
            )
        )

    @api.get("/partners/{partner_id}/allocations", tags=["licenses"])
    def list_allocations(
        partner_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.licenses.list_allocations(partner_id)]

    @api.post("/allocations/{allocation_id}/licenses", tags=["licenses"])
    def issue_license(
        allocation_id: str,
        body: schemas.LicenseIssue,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.licenses.issue(
                allocation_id,
                customer_id=body.customer_id,
                external_id=body.external_id,
                email=body.email,
                name=body.name,
                actor=actor,
            )
        )

    @api.get("/partners/{partner_id}/licenses", tags=["licenses"])
    def list_licenses(
        partner_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.licenses.list_for_partner(partner_id)]

    @api.post("/licenses/{license_id}/revoke", tags=["licenses"])
    def revoke_license(
        license_id: str,
        body: schemas.ReasonRequest | None = None,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        reason = body.reason if body else None
        return snapshot(services.licenses.revoke(license_id, reason=reason, actor=actor))

    @api.post("/partners/{partner_id}/prefund", tags=["partner-accounts"])
    def prefund_partner(
        partner_id: str,
        body: schemas.PrefundRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.prefund(
                partner_id,
                body.amount_minor,
                currency=body.currency,
                reason=body.reason,
                actor=actor,
            )
        )

    @api.post("/partners/{partner_id}/payments", tags=["partner-accounts"])
    def record_partner_payment(
        partner_id: str,
        body: schemas.PartnerPaymentRequest,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.record_payment(
                partner_id,
                body.amount_minor,
                currency=body.currency,
                method=body.method,
                reference=body.reference,
                actor=actor,
            )
        )

    @api.get("/partners/{partner_id}/accounts", tags=["partner-accounts"])
    def partner_accounts(
        partner_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.partner_accounts.accounts(partner_id)]

    @api.get("/partners/{partner_id}/ledger", tags=["partner-accounts"])
    def partner_ledger(
        partner_id: str,
        currency: str | None = None,
        services: Services = Depends(get_services),
    ) -> list[dict[str, Any]]:
        return [
            snapshot(item)
            for item in services.partner_accounts.entries(partner_id, currency=currency)
        ]

    @api.post("/partners/{partner_id}/statements", tags=["partner-accounts"])
    def create_statement(
        partner_id: str,
        body: schemas.StatementCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.generate_statement(
                partner_id,
                body.period_start,
                body.period_end,
                currency=body.currency,
                actor=actor,
            )
        )

    @api.get("/partners/{partner_id}/statements", tags=["partner-accounts"])
    def list_statements(
        partner_id: str, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return [snapshot(item) for item in services.partner_accounts.list_statements(partner_id)]

    @api.post("/partners/{partner_id}/invoices", tags=["partner-accounts"])
    def create_partner_invoice(
        partner_id: str,
        body: schemas.PartnerInvoiceCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.create_invoice(
                partner_id,
                lines=[item.model_dump() for item in body.lines],
                currency=body.currency,
                due_date=body.due_date,
                notes=body.notes,
                finalize=body.finalize,
                actor=actor,
            )
        )

    @api.post("/partner-invoices/{invoice_id}/payments", tags=["partner-accounts"])
    def pay_partner_invoice(
        invoice_id: str,
        body: schemas.PaymentCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.record_invoice_payment(
                invoice_id,
                body.amount_minor,
                method=body.method,
                reference=body.reference,
                actor=actor,
            )
        )

    @api.post("/partners/{partner_id}/payouts", tags=["partner-accounts"])
    def create_payout(
        partner_id: str,
        body: schemas.PayoutCreate,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(
            services.partner_accounts.create_payout(
                partner_id,
                lines=body.lines,
                currency=body.currency,
                reference=body.reference,
                actor=actor,
            )
        )

    @api.post("/payouts/{payout_id}/pay", tags=["partner-accounts"])
    def pay_payout(
        payout_id: str,
        services: Services = Depends(get_services),
        actor: Actor = Depends(get_actor),
    ) -> Any:
        return snapshot(services.partner_accounts.pay_payout(payout_id, actor=actor))

    @api.get("/reports/channel", tags=["reports"])
    def report_channel(
        currency: str | None = None, services: Services = Depends(get_services)
    ) -> list[dict[str, Any]]:
        return services.uow.reports.channel_revenue((currency or services.default_currency).upper())

    return api


def _make_handler(status_code: int) -> Callable[..., Any]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


def create_app(
    config: EngineConfig | Any,
    *,
    api_key: str | None = None,
    title: str = "Billing Engine API",
) -> FastAPI:
    """Build a standalone FastAPI application."""
    from billing_engine.sdk import BillingEngine

    engine = config if isinstance(config, BillingEngine) else BillingEngine(config)
    app = FastAPI(title=title, version=__version__)
    app.state.engine = engine
    app.state.api_key = api_key

    for error_type, status_code in _ERROR_STATUS.items():
        app.add_exception_handler(error_type, _make_handler(status_code))

    @app.middleware("http")
    async def transaction_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
        """Commit or roll back the request transaction before the response is sent.

        FastAPI runs post-``yield`` dependency code after the response, so a
        failed commit there cannot be reported to the client. Committing in
        middleware guarantees success/failure is reflected in the response.
        """
        session = engine.session_factory()
        uow = SqlUnitOfWork(session)
        request.state.uow = uow
        request.state.services = Services(
            uow,
            default_currency=engine.config.default_currency,
            grace_period_days=engine.config.grace_period_days,
            trial_days=engine.config.trial_days,
        )
        try:
            response = await call_next(request)
        except Exception:
            uow.rollback()
            session.close()
            raise
        try:
            if response.status_code >= 400:
                uow.rollback()
            else:
                uow.commit()
        finally:
            session.close()
        return response

    app.include_router(_build_router())
    return app


router = _build_router()
