"""Pure value objects: identifiers, money, and time arithmetic.

Nothing here imports SQLAlchemy or performs I/O.
"""

from __future__ import annotations

import calendar
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from billing_engine.domain.enums import BillingInterval
from billing_engine.domain.errors import ValidationError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_LENGTH = 26
_ULID_TIME_CHARS = 10
_RANDOM_BYTES = 10
_ULID_MAX_TIMESTAMP = 1 << 48

_ULID_DECODE = {char: index for index, char in enumerate(_CROCKFORD)}


def utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    Naive datetimes are interpreted as UTC so callers never mix aware and naive
    values (which raises ``TypeError`` on comparison).
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _encode_ulid(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    if value:
        raise ValidationError("ULID value exceeds the encodable range")
    return "".join(reversed(chars))


def new_ulid(timestamp_ms: int | None = None, randomness: bytes | None = None) -> str:
    """Generate a 26-character, lexicographically sortable ULID string."""
    timestamp = int(time.time() * 1000) if timestamp_ms is None else timestamp_ms
    if not 0 <= timestamp < _ULID_MAX_TIMESTAMP:
        raise ValidationError("ULID timestamp must fit in 48 bits")
    entropy = os.urandom(_RANDOM_BYTES) if randomness is None else randomness
    if len(entropy) != _RANDOM_BYTES:
        raise ValidationError("ULID randomness must be exactly 10 bytes")
    value = (timestamp << 80) | int.from_bytes(entropy, "big")
    return _encode_ulid(value, _ULID_LENGTH)


def is_valid_ulid(value: str) -> bool:
    """Return whether ``value`` is a syntactically valid ULID string."""
    if not isinstance(value, str) or len(value) != _ULID_LENGTH:
        return False
    return all(char in _ULID_DECODE for char in value)


def ulid_timestamp_ms(value: str) -> int:
    """Extract the millisecond timestamp encoded in a ULID."""
    if not is_valid_ulid(value):
        raise ValidationError(f"{value!r} is not a valid ULID")
    timestamp = 0
    for char in value[:_ULID_TIME_CHARS]:
        timestamp = (timestamp << 5) | _ULID_DECODE[char]
    return timestamp


def add_months(moment: datetime, months: int) -> datetime:
    """Add calendar months, clamping the day to the target month's length."""
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def period_end(start: datetime, interval: BillingInterval, count: int = 1) -> datetime:
    """Return the end of the billing period beginning at ``start``."""
    if count < 1:
        raise ValidationError("period count must be at least 1")
    if interval is BillingInterval.MONTH:
        return add_months(start, count)
    if interval is BillingInterval.YEAR:
        return add_months(start, 12 * count)
    return start


@dataclass(frozen=True, slots=True)
class Money:
    """An amount of money held as integer minor units and an ISO 4217 code."""

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise ValidationError("Money.amount_minor must be an integer of minor units")
        currency = self.currency.strip().upper() if isinstance(self.currency, str) else ""
        if len(currency) != 3 or not currency.isalpha():
            raise ValidationError(
                f"invalid currency {self.currency!r}: expected a 3-letter ISO 4217 code"
            )
        object.__setattr__(self, "currency", currency)

    def _require_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValidationError(f"cannot combine {self.currency} with {other.currency}")

    def add(self, other: Money) -> Money:
        """Return the sum of two amounts in the same currency."""
        self._require_same_currency(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def subtract(self, other: Money) -> Money:
        """Return the difference of two amounts in the same currency."""
        self._require_same_currency(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def negate(self) -> Money:
        """Return the additive inverse."""
        return Money(-self.amount_minor, self.currency)

    def multiply(self, factor: int) -> Money:
        """Return the amount scaled by an integer factor."""
        return Money(self.amount_minor * factor, self.currency)

    @property
    def is_zero(self) -> bool:
        return self.amount_minor == 0

    @property
    def is_negative(self) -> bool:
        return self.amount_minor < 0
