"""Service context helpers: actor identity, audit snapshots, and auditing."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from typing import Any

from billing_engine.domain.entities import AuditLog, Event
from billing_engine.domain.enums import ActorType, Source
from billing_engine.domain.repositories import Repositories
from billing_engine.domain.value_objects import new_ulid, utcnow


@dataclass(slots=True)
class Actor:
    """Who initiated a change, for the audit trail."""

    type: str = ActorType.SYSTEM.value
    id: str | None = None
    source: str = Source.EMBEDDED.value
    ip: str | None = None


def snapshot(value: Any) -> Any:
    """Serialize a value into a JSON-safe audit snapshot."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): snapshot(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [snapshot(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: snapshot(getattr(value, field.name)) for field in fields(value)}
    return str(value)


class AuditService:
    """Writes append-only audit rows and transactional outbox events."""

    def __init__(self, uow: Repositories) -> None:
        self.uow = uow

    def record(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: Actor | None = None,
        before: Any | None = None,
        after: Any | None = None,
        reason: str | None = None,
    ) -> None:
        """Append an audit entry for a mutation."""
        actor = actor or Actor()
        self.uow.audit.add(
            AuditLog(
                id=new_ulid(),
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor.type,
                actor_id=actor.id,
                before=snapshot(before),
                after=snapshot(after),
                reason=reason,
                source=actor.source,
                ip=actor.ip,
            )
        )

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        """Append a pending event to the transactional outbox."""
        self.uow.events.add(
            Event(
                id=new_ulid(),
                event_type=event_type,
                payload=payload,
                status="pending",
                available_at=utcnow(),
            )
        )
