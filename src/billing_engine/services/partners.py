"""Channel partner management: partners, agreements, and commission rules."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from billing_engine.domain.entities import CommissionRule, Partner, PartnerAgreement
from billing_engine.domain.enums import CommissionBasis, MoneyModel, PartnerType
from billing_engine.domain.errors import ConflictError, ValidationError
from billing_engine.domain.value_objects import as_utc, new_ulid, normalize_currency, utcnow
from billing_engine.services.base import Service, require
from billing_engine.services.context import Actor

_VALID_TYPES = {member.value for member in PartnerType}
_VALID_MODELS = {member.value for member in MoneyModel}
_VALID_BASES = {member.value for member in CommissionBasis}


class PartnerService(Service):
    def create(
        self,
        name: str,
        *,
        type: str = PartnerType.AGENT.value,
        external_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        currency: str | None = None,
        parent_partner_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        actor: Actor | None = None,
    ) -> Partner:
        """Create a distributor, agent, or reseller."""
        cleaned = name.strip() if isinstance(name, str) else ""
        if not cleaned:
            raise ValidationError("partner name is required")
        if type not in _VALID_TYPES:
            raise ValidationError(f"invalid partner type {type!r}")
        if external_id and self.uow.partners.get_partner_by_external_id(external_id):
            raise ConflictError(f"partner external_id {external_id!r} already exists")
        if parent_partner_id is not None:
            require(
                self.uow.partners.get_partner(parent_partner_id),
                "partner",
                parent_partner_id,
            )
        partner = Partner(
            id=new_ulid(),
            name=cleaned,
            type=type,
            external_id=external_id,
            email=email,
            phone=phone,
            currency=normalize_currency(currency or self.default_currency),
            parent_partner_id=parent_partner_id,
            attributes=attributes or {},
        )
        self.uow.partners.add_partner(partner)
        self.uow.flush()
        self.audit.record("partner.create", "partner", partner.id, actor, after=partner)
        self.audit.emit("partner.created", {"partner_id": partner.id})
        return partner

    def get(self, partner_id: str) -> Partner:
        return require(self.uow.partners.get_partner(partner_id), "partner", partner_id)

    def get_by_external_id(self, external_id: str) -> Partner | None:
        return self.uow.partners.get_partner_by_external_id(external_id)

    def list_partners(self, limit: int = 100, offset: int = 0) -> list[Partner]:
        return self.uow.partners.list_partners(limit=limit, offset=offset)

    def set_status(self, partner_id: str, status: str, *, actor: Actor | None = None) -> Partner:
        partner = self.get(partner_id)
        if status not in {"active", "inactive"}:
            raise ValidationError(f"invalid partner status {status!r}")
        before = replace(partner)
        partner.status = status
        self.uow.partners.update_partner(partner)
        self.uow.flush()
        self.audit.record(
            "partner.update_status", "partner", partner.id, actor, before=before, after=partner
        )
        return partner

    def create_commission_rule(
        self,
        *,
        basis: str = CommissionBasis.FLAT.value,
        rate_bps: int = 0,
        tiers: list[dict[str, Any]] | None = None,
        levels: list[dict[str, Any]] | None = None,
        actor: Actor | None = None,
    ) -> CommissionRule:
        """Create a commission rule expressed in basis points."""
        if basis not in _VALID_BASES:
            raise ValidationError(f"invalid commission basis {basis!r}")
        if rate_bps < 0:
            raise ValidationError("rate_bps must be non-negative")
        rule = CommissionRule(
            id=new_ulid(), basis=basis, rate_bps=rate_bps, tiers=tiers, levels=levels
        )
        self.uow.partners.add_commission_rule(rule)
        self.uow.flush()
        self.audit.record("commission_rule.create", "commission_rule", rule.id, actor, after=rule)
        return rule

    def get_commission_rule(self, rule_id: str) -> CommissionRule:
        return require(self.uow.partners.get_commission_rule(rule_id), "commission_rule", rule_id)

    def list_commission_rules(self) -> list[CommissionRule]:
        """List every commission rule (rules are deployment-global in v0.2)."""
        return self.uow.partners.list_commission_rules()

    def create_agreement(
        self,
        partner_id: str,
        *,
        money_model: str = MoneyModel.CONSIGNMENT.value,
        currency: str | None = None,
        discount_bps: int = 0,
        plan_id: str | None = None,
        commission_rule_id: str | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        actor: Actor | None = None,
    ) -> PartnerAgreement:
        """Create an agreement describing pricing and money flow for a partner."""
        partner = self.get(partner_id)
        if money_model not in _VALID_MODELS:
            raise ValidationError(f"invalid money model {money_model!r}")
        if discount_bps < 0 or discount_bps > 10_000:
            raise ValidationError("discount_bps must be between 0 and 10000")
        if plan_id is not None:
            require(self.uow.catalog.get_plan(plan_id), "plan", plan_id)
        if (
            effective_from is not None
            and effective_to is not None
            and as_utc(effective_to) < as_utc(effective_from)
        ):
            raise ValidationError("effective_to must not precede effective_from")
        if commission_rule_id is not None:
            require(
                self.uow.partners.get_commission_rule(commission_rule_id),
                "commission_rule",
                commission_rule_id,
            )
        agreement = PartnerAgreement(
            id=new_ulid(),
            partner_id=partner.id,
            money_model=money_model,
            currency=normalize_currency(currency or partner.currency),
            discount_bps=discount_bps,
            plan_id=plan_id,
            commission_rule_id=commission_rule_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        self.uow.partners.add_agreement(agreement)
        self.uow.flush()
        self.audit.record(
            "partner_agreement.create", "partner_agreement", agreement.id, actor, after=agreement
        )
        return agreement

    def get_agreement(self, agreement_id: str) -> PartnerAgreement:
        return require(
            self.uow.partners.get_agreement(agreement_id), "partner_agreement", agreement_id
        )

    def list_agreements(self, partner_id: str) -> list[PartnerAgreement]:
        return self.uow.partners.list_agreements(partner_id)

    def default_agreement(
        self, partner_id: str, plan_id: str | None = None
    ) -> PartnerAgreement | None:
        """Return the most recent active agreement, preferring a plan match.

        Agreements outside their effective window are ignored so an expired or
        not-yet-started agreement is never selected.
        """
        now = utcnow()
        agreements = [
            item
            for item in self.uow.partners.list_agreements(partner_id)
            if item.status == "active"
            and (item.effective_from is None or as_utc(item.effective_from) <= now)
            and (item.effective_to is None or as_utc(item.effective_to) >= now)
        ]
        if plan_id is not None:
            matches = [item for item in agreements if item.plan_id == plan_id]
            if matches:
                return matches[-1]
        general = [item for item in agreements if item.plan_id is None]
        pool = general or agreements
        return pool[-1] if pool else None
