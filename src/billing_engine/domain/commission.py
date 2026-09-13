"""Pure commission calculation for channel partners."""

from __future__ import annotations

from typing import Any

from billing_engine.domain.enums import CommissionBasis

_BPS_DENOMINATOR = 10_000


def _apply(amount_minor: int, rate_bps: int) -> int:
    return amount_minor * rate_bps // _BPS_DENOMINATOR


def _tier_rate(amount_minor: int, tiers: list[dict[str, Any]], fallback: int) -> int:
    rate = fallback
    for tier in sorted(tiers, key=lambda item: int(item.get("threshold_minor", 0))):
        if amount_minor >= int(tier.get("threshold_minor", 0)):
            rate = int(tier.get("rate_bps", rate))
    return rate


def compute_commission(
    amount_minor: int,
    *,
    basis: str,
    rate_bps: int = 0,
    tiers: list[dict[str, Any]] | None = None,
    levels: list[dict[str, Any]] | None = None,
    level: int = 1,
) -> int:
    """Return the commission, in minor units, for an amount.

    ``rate_bps`` is expressed in basis points (10_000 == 100%). ``tiered``
    selects the rate of the highest threshold the amount reaches.
    ``multi_level`` uses the configured rate for ``level`` (single-level v0.2).
    """
    if amount_minor <= 0:
        return 0
    if basis == CommissionBasis.FLAT.value:
        return _apply(amount_minor, rate_bps)
    if basis == CommissionBasis.TIERED.value:
        return _apply(amount_minor, _tier_rate(amount_minor, tiers or [], rate_bps))
    if basis == CommissionBasis.MULTI_LEVEL.value:
        for entry in levels or []:
            if int(entry.get("level", 0)) == level:
                return _apply(amount_minor, int(entry.get("rate_bps", 0)))
        return _apply(amount_minor, rate_bps)
    return 0


def level_rates(levels: list[dict[str, Any]] | None) -> list[tuple[int, int]]:
    """Return ``(level, rate_bps)`` pairs from a multi-level configuration."""
    return [(int(entry.get("level", 0)), int(entry.get("rate_bps", 0))) for entry in levels or []]
