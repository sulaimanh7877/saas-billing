"""Subscription lifecycle state machine."""

from __future__ import annotations

from billing_engine.domain.enums import SubscriptionStatus
from billing_engine.domain.errors import ConflictError

_ALLOWED: dict[SubscriptionStatus, frozenset[SubscriptionStatus]] = {
    SubscriptionStatus.TRIALING: frozenset(
        {
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.ACTIVE: frozenset(
        {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.PAST_DUE: frozenset(
        {
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.PAUSED: frozenset(
        {
            SubscriptionStatus.PAUSED,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.CANCELED: frozenset(
        {
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.EXPIRED,
        }
    ),
    SubscriptionStatus.EXPIRED: frozenset(
        {
            SubscriptionStatus.EXPIRED,
            SubscriptionStatus.ACTIVE,
        }
    ),
}

_ACCESS_STATUSES = frozenset(
    {
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
    }
)

_TERMINAL_STATUSES = frozenset({SubscriptionStatus.EXPIRED})


def can_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> bool:
    """Return whether a subscription may move from ``current`` to ``target``."""
    return target in _ALLOWED[current]


def ensure_transition(current: SubscriptionStatus, target: SubscriptionStatus) -> None:
    """Raise :class:`ConflictError` if the transition is not permitted."""
    if not can_transition(current, target):
        raise ConflictError(
            f"cannot transition subscription from {current.value!r} to {target.value!r}"
        )


def grants_access(status: SubscriptionStatus) -> bool:
    """Return whether a subscription in ``status`` grants feature access."""
    return status in _ACCESS_STATUSES


def is_terminal(status: SubscriptionStatus) -> bool:
    """Return whether no further automatic transitions are expected."""
    return status in _TERMINAL_STATUSES
