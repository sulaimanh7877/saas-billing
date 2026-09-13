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

    Unset ``created_at``/``updated_at`` are filled on both the model and the
    entity so callers receive timestamps on freshly created or updated domain
    objects, not only on rows read back from the database.
    """
    is_update = sa_inspect(model).persistent
    now = utcnow()
    for field in fields(entity):
        name = field.name
        value = getattr(entity, name)
        if name in _MANAGED_TIMESTAMPS and value is None:
            if name == "created_at" and is_update:
                continue
            value = now
            setattr(entity, name, value)
        setattr(model, name, value)
