"""Prefix strategy for every identifier the engine creates.

The engine runs on the host application's database, so every table, index,
constraint, and foreign key it owns must include the configured
``table_prefix`` to avoid colliding with the host's schema. Prefixes are
required, have no default, and are normalized to end with a single underscore.
"""

from __future__ import annotations

import re

from billing_engine.domain.errors import ConfigurationError, ValidationError

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _validate_identifier(value: str, kind: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValidationError(
            f"invalid {kind} name {value!r}: expected lowercase letters, digits, "
            "and underscores, not starting with a digit"
        )
    return value


class PrefixNamer:
    """Builds prefixed table and constraint names from a configured prefix."""

    def __init__(self, prefix: str) -> None:
        if not prefix:
            raise ConfigurationError(
                "table_prefix is required and has no default; provide the prefix "
                "used for the engine's tables"
            )
        normalized = prefix if prefix.endswith("_") else f"{prefix}_"
        normalized = re.sub(r"_+$", "_", normalized)
        if not _IDENTIFIER_RE.match(normalized):
            raise ConfigurationError(
                f"invalid table_prefix {prefix!r}: expected lowercase letters, "
                "digits, and underscores, not starting with a digit"
            )
        self._prefix = normalized

    @property
    def prefix(self) -> str:
        """The normalized prefix, always ending with a single underscore."""
        return self._prefix

    def table(self, name: str) -> str:
        """Return the physical table name, e.g. ``acme_subscriptions``."""
        return f"{self._prefix}{_validate_identifier(name, 'table')}"

    def index(self, table: str, *columns: str) -> str:
        """Return an index name, e.g. ``acme_ix_subscriptions_customer_id``."""
        return self._constrained("ix", table, *columns)

    def unique(self, table: str, *columns: str) -> str:
        """Return a unique-constraint name, e.g. ``acme_uq_customers_email``."""
        return self._constrained("uq", table, *columns)

    def foreign_key(self, table: str, *columns: str, referred_table: str) -> str:
        """Return a foreign-key name including the referred table."""
        parts = [table, *columns, referred_table]
        return self._constrained("fk", *parts)

    def check(self, table: str, name: str) -> str:
        """Return a check-constraint name, e.g. ``acme_ck_prices_amount``."""
        return f"{self._prefix}ck_{_validate_identifier(table, 'table')}_" + _validate_identifier(
            name, "constraint"
        )

    def primary_key(self, table: str) -> str:
        """Return a primary-key constraint name, e.g. ``acme_pk_subscriptions``."""
        return f"{self._prefix}pk_{_validate_identifier(table, 'table')}"

    def logical(self, prefixed_name: str) -> str:
        """Strip this namer's prefix from ``prefixed_name`` when present."""
        if prefixed_name.startswith(self._prefix):
            return prefixed_name[len(self._prefix) :]
        return prefixed_name

    def is_prefixed(self, name: str) -> bool:
        """Return whether ``name`` already carries this namer's prefix."""
        return name.startswith(self._prefix)

    def _constrained(self, kind: str, *parts: str) -> str:
        validated = "_".join(_validate_identifier(part, "name") for part in parts)
        return f"{self._prefix}{kind}_{validated}"
