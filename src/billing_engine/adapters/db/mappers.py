"""Generic mapping between SQLAlchemy models and domain entities.

Entity field names mirror model attribute names, so mapping is field-name
driven. Timestamp fields are left to SQLAlchemy defaults when unset on the
entity.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from typing import Any, TypeVar

from sqlalchemy import inspect as sa_inspect

from billing_engine.adapters.db.base import Base
from billing_engine.domain.value_objects import utcnow

EntityT = TypeVar("EntityT")
ModelT = TypeVar("ModelT", bound=Base)

_MANAGED_TIMESTAMPS = frozenset({"created_at", "updated_at"})


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def to_entity(model: Base, entity_type: type[EntityT]) -> EntityT:
    """Build a domain entity from a model instance, normalizing timestamps."""
    field_names = entity_type.__dataclass_fields__  # type: ignore[attr-defined]
    values = {name: _normalize(getattr(model, name)) for name in field_names}
    return entity_type(**values)


def apply_entity(model: Any, entity: Any) -> None:
    """Copy entity fields onto a model instance in place.

    Managed timestamps are handled specially so they stay coherent:

    - On insert, unset ``created_at``/``updated_at`` are filled on both the
      model and the entity, so callers receive timestamps immediately.
    - On update, ``created_at`` is never overwritten and is backfilled onto the
      entity from the persisted row; ``updated_at`` is always advanced so the
      model's ``onupdate`` cannot be suppressed by a stale entity value.
    """
    is_update = sa_inspect(model).persistent
    now = utcnow()
    for field in fields(entity):
        name = field.name
        value = getattr(entity, name)
        if name in _MANAGED_TIMESTAMPS:
            if is_update:
                if name == "created_at":
                    if value is None:
                        existing = getattr(model, name)
                        setattr(
                            entity,
                            name,
                            _normalize(existing) if existing is not None else now,
                        )
                    continue
                setattr(model, name, now)
                setattr(entity, name, now)
                continue
            if value is None:
                value = now
                setattr(entity, name, value)
        setattr(model, name, value)
