"""Runtime configuration for the billing engine.

All settings flow through :class:`EngineConfig`; there is no global state and
no module-level database connection. Money is always handled as integer minor
units plus an ISO 4217 currency code, and every timestamp is UTC.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from billing_engine.domain.errors import ConfigurationError
from billing_engine.naming import PrefixNamer

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Configuration required to construct a billing engine.

    Provide exactly one of ``dsn`` or ``engine``. ``table_prefix`` is required
    and has no default; it is normalized to end with a single underscore.
    """

    table_prefix: str
    dsn: str | None = None
    engine: Engine | None = None
    default_currency: str = "USD"
    grace_period_days: int = 0
    trial_days: int = 0
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        raw_prefix = (
            self.table_prefix.strip() if isinstance(self.table_prefix, str) else self.table_prefix
        )
        namer = PrefixNamer(raw_prefix)
        object.__setattr__(self, "table_prefix", namer.prefix)

        dsn = self.dsn.strip() if isinstance(self.dsn, str) else self.dsn
        object.__setattr__(self, "dsn", dsn or None)

        if (self.dsn is None) == (self.engine is None):
            raise ConfigurationError("provide exactly one of 'dsn' or 'engine' to EngineConfig")

        currency = self.default_currency.strip().upper()
        if not _CURRENCY_RE.match(currency):
            raise ConfigurationError(
                f"invalid default_currency {self.default_currency!r}: expected a "
                "3-letter ISO 4217 code such as 'USD'"
            )
        object.__setattr__(self, "default_currency", currency)

        for field_name in ("grace_period_days", "trial_days"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ConfigurationError(f"{field_name} must be a non-negative integer")

        if self.timezone.upper() != "UTC":
            raise ConfigurationError(f"invalid timezone {self.timezone!r}: v0.1 supports UTC only")
        object.__setattr__(self, "timezone", "UTC")

    @property
    def namer(self) -> PrefixNamer:
        """A :class:`PrefixNamer` bound to this configuration's prefix."""
        return PrefixNamer(self.table_prefix)

    def build_engine(self) -> Engine:
        """Return the configured engine, creating one from the DSN if needed."""
        if self.engine is not None:
            return self.engine
        if self.dsn is None:  # pragma: no cover - guarded by __post_init__
            raise ConfigurationError("no dsn or engine configured")
        return create_engine(self.dsn)
