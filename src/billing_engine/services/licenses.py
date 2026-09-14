"""License allocation and issuance for channel partners."""

from __future__ import annotations

from datetime import datetime

from billing_engine.domain.commission import compute_commission
from billing_engine.domain.entities import License, LicenseAllocation, Price
from billing_engine.domain.enums import AccountType, AllocationStatus, MoneyModel
from billing_engine.domain.errors import (
    AllocationExhaustedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from billing_engine.domain.repositories import Repositories
from billing_engine.domain.value_objects import new_ulid, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor
from billing_engine.services.customers import CustomerService
from billing_engine.services.partner_accounts import PartnerAccountService
from billing_engine.services.partners import PartnerService
from billing_engine.services.subscriptions import SubscriptionService


class LicenseService(Service):
    def __init__(
        self,
        uow: Repositories,
        *,
        default_currency: str = "USD",
        grace_period_days: int = 0,
        trial_days: int = 0,
    ) -> None:
        super().__init__(
            uow,
            default_currency=default_currency,
            grace_period_days=grace_period_days,
            trial_days=trial_days,
        )
        self.partners = PartnerService(
            uow,
            default_currency=default_currency,
            grace_period_days=grace_period_days,
            trial_days=trial_days,
        )
        self.accounts = PartnerAccountService(
            uow,
            default_currency=default_currency,
            grace_period_days=grace_period_days,
            trial_days=trial_days,
        )
        self.customers = CustomerService(
            uow,
            default_currency=default_currency,
            grace_period_days=grace_period_days,
            trial_days=trial_days,
        )
        self.subscriptions = SubscriptionService(
            uow,
            default_currency=default_currency,
            grace_period_days=grace_period_days,
            trial_days=trial_days,
        )

    def available(self, allocation: LicenseAllocation) -> int:
        return max(allocation.quantity_allocated - allocation.quantity_issued, 0)

    def allocate(
        self,
        partner_id: str,
        plan_version_id: str,
        quantity: int,
        *,
        agreement_id: str | None = None,
        parent_allocation_id: str | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        actor: Actor | None = None,
    ) -> LicenseAllocation:
        """Authorize a partner with a pool of licenses for a plan version."""
        partner = require(self.uow.partners.get_partner(partner_id), "partner", partner_id)
        require(
            self.uow.catalog.get_plan_version(plan_version_id),
            "plan_version",
            plan_version_id,
        )
        if quantity < 1:
            raise ValidationError("quantity must be at least 1")
        if agreement_id is not None:
            agreement = require(
                self.uow.partners.get_agreement(agreement_id),
                "partner_agreement",
                agreement_id,
            )
            if agreement.partner_id != partner.id:
                raise ValidationError(
                    f"agreement {agreement_id!r} does not belong to partner {partner_id!r}"
                )
        if parent_allocation_id is not None:
            parent = require(
                self.uow.licenses.get_allocation(parent_allocation_id),
                "license_allocation",
                parent_allocation_id,
            )
            if parent.partner_id != partner.id:
                raise ValidationError(
                    f"parent allocation {parent_allocation_id!r} does not belong to "
                    f"partner {partner_id!r}"
                )
        allocation = LicenseAllocation(
            id=new_ulid(),
            partner_id=partner.id,
            plan_version_id=plan_version_id,
            quantity_allocated=quantity,
            agreement_id=agreement_id,
            parent_allocation_id=parent_allocation_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self.uow.licenses.add_allocation(allocation)
        self.uow.flush()
        self.audit.record(
            "license_allocation.create",
            "license_allocation",
            allocation.id,
            actor,
            after=allocation,
        )
        return allocation

    def get_allocation(self, allocation_id: str) -> LicenseAllocation:
        return require(
            self.uow.licenses.get_allocation(allocation_id),
            "license_allocation",
            allocation_id,
        )

    def list_allocations(self, partner_id: str) -> list[LicenseAllocation]:
        return self.uow.licenses.list_allocations(partner_id)

    def close_allocation(
        self, allocation_id: str, *, actor: Actor | None = None
    ) -> LicenseAllocation:
        allocation = self.get_allocation(allocation_id)
        allocation.status = AllocationStatus.CLOSED.value
        self.uow.licenses.update_allocation(allocation)
        self.uow.flush()
        self.audit.record(
            "license_allocation.close", "license_allocation", allocation.id, actor, after=allocation
        )
        return allocation

    def issue(
        self,
        allocation_id: str,
        *,
        customer_id: str | None = None,
        external_id: str | None = None,
        email: str | None = None,
        name: str | None = None,
        expires_at: datetime | None = None,
        actor: Actor | None = None,
    ) -> License:
        """Issue a license to an end customer, starting their subscription."""
        allocation = self.uow.licenses.get_allocation_for_update(allocation_id)
        if allocation is None:
            raise NotFoundError(f"license_allocation {allocation_id!r} was not found")
        if allocation.status != AllocationStatus.ACTIVE.value:
            raise ConflictError("license allocation is not active")
        if self.available(allocation) <= 0:
            raise AllocationExhaustedError(f"allocation {allocation.id} has no licenses left")

        partner = require(
            self.uow.partners.get_partner(allocation.partner_id),
            "partner",
            allocation.partner_id,
        )
        version = require(
            self.uow.catalog.get_plan_version(allocation.plan_version_id),
            "plan_version",
            allocation.plan_version_id,
        )
        agreement = (
            self.uow.partners.get_agreement(allocation.agreement_id)
            if allocation.agreement_id
            else None
        )
        if agreement is None:
            agreement = self.partners.default_agreement(partner.id, version.plan_id)
        money_model = agreement.money_model if agreement else MoneyModel.CONSIGNMENT.value
        currency = (agreement.currency if agreement else partner.currency).upper()

        if customer_id is not None:
            customer = require(self.uow.customers.get(customer_id), "customer", customer_id)
            if customer.partner_id != partner.id:
                customer = self.customers.update(customer.id, partner_id=partner.id, actor=actor)
        else:
            if not external_id:
                raise ValidationError("provide customer_id or external_id")
            customer = self.customers.create(
                external_id,
                email=email,
                name=name,
                currency=currency,
                partner_id=partner.id,
                actor=actor,
            )

        license_ = License(
            id=new_ulid(),
            allocation_id=allocation.id,
            partner_id=partner.id,
            plan_version_id=version.id,
            status="active",
            customer_id=customer.id,
            issued_at=utcnow(),
            expires_at=expires_at,
        )

        price = self._resolve_price(version.id, currency)
        gross = price.amount_minor
        discount_bps = agreement.discount_bps if agreement else 0
        wholesale = gross * (10_000 - discount_bps) // 10_000
        account_type = self.accounts.account_type_for(money_model)

        if money_model == MoneyModel.WHOLESALE_PREPAID.value:
            account = self.accounts.get_or_create_account(partner.id, currency, account_type)
            if account.balance_minor < wholesale:
                raise ConflictError("insufficient prepaid balance for this license")
            self.accounts.post(
                partner.id,
                currency,
                account_type,
                "charge",
                -wholesale,
                reason="license issued",
                reference_type="license",
                reference_id=license_.id,
                actor=actor,
            )
        else:
            self.accounts.post(
                partner.id,
                currency,
                account_type,
                "charge",
                wholesale if money_model == MoneyModel.CONSIGNMENT.value else gross,
                reason="license issued",
                reference_type="license",
                reference_id=license_.id,
                actor=actor,
            )
            if money_model == MoneyModel.AGENCY_COMMISSION.value and agreement is not None:
                rule = (
                    self.uow.partners.get_commission_rule(agreement.commission_rule_id)
                    if agreement.commission_rule_id
                    else None
                )
                if rule is not None:
                    commission = compute_commission(
                        gross,
                        basis=rule.basis,
                        rate_bps=rule.rate_bps,
                        tiers=rule.tiers,
                        levels=rule.levels,
                    )
                    if commission:
                        self.accounts.post(
                            partner.id,
                            currency,
                            AccountType.RECEIVABLE.value,
                            "commission_earned",
                            -commission,
                            reason="commission on license",
                            reference_type="license",
                            reference_id=license_.id,
                            actor=actor,
                        )

        subscription = self.subscriptions.create(
            customer.id, version.id, price_id=price.id, currency=currency, actor=actor
        )
        license_.subscription_id = subscription.id
        self.uow.licenses.add_license(license_)
        allocation.quantity_issued += 1
        self.uow.licenses.update_allocation(allocation)
        self.uow.flush()
        self.audit.record("license.issue", "license", license_.id, actor, after=license_)
        self.audit.emit("license.issued", {"license_id": license_.id, "partner_id": partner.id})
        return license_

    def _resolve_price(self, plan_version_id: str, currency: str) -> Price:
        prices = self.uow.catalog.list_prices(plan_version_id)
        if not prices:
            raise ValidationError("plan version has no price to charge")
        wanted = currency.upper()
        for price in prices:
            if price.currency == wanted:
                return price
        raise NotFoundError(f"no {wanted} price for plan version {plan_version_id!r}")

    def get(self, license_id: str) -> License:
        return require(self.uow.licenses.get_license(license_id), "license", license_id)

    def list_for_partner(self, partner_id: str) -> list[License]:
        return self.uow.licenses.list_licenses(partner_id)

    def list_for_allocation(self, allocation_id: str) -> list[License]:
        return self.uow.licenses.list_licenses_for_allocation(allocation_id)

    def revoke(
        self, license_id: str, *, reason: str | None = None, actor: Actor | None = None
    ) -> License:
        """Revoke an issued license (does not reverse ledger entries)."""
        license_ = self.get(license_id)
        if license_.status == "revoked":
            raise ConflictError("license already revoked")
        license_.status = "revoked"
        self.uow.licenses.update_license(license_)
        self.uow.flush()
        self.audit.record(
            "license.revoke", "license", license_.id, actor, after=license_, reason=reason
        )
        self.audit.emit("license.revoked", {"license_id": license_.id})
        return license_

    def expire(self, license_id: str, *, actor: Actor | None = None) -> License:
        license_ = self.get(license_id)
        license_.status = "expired"
        self.uow.licenses.update_license(license_)
        self.uow.flush()
        self.audit.record("license.expire", "license", license_.id, actor, after=license_)
        return license_
