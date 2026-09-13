"""Transactional outbox dispatch and webhook delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
import urllib.request
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from billing_engine.adapters.db.repositories import SqlUnitOfWork
from billing_engine.domain.entities import Event
from billing_engine.domain.value_objects import utcnow

EventHandler = Callable[[Event], None]


class EventDispatcher:
    """Delivers pending outbox events to a handler with retry/backoff."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handler: EventHandler,
        *,
        backoff_seconds: int = 60,
    ) -> None:
        self.session_factory = session_factory
        self.handler = handler
        self.backoff_seconds = backoff_seconds

    def dispatch_pending(self, limit: int = 100) -> int:
        """Deliver up to ``limit`` pending events; return the number delivered."""
        session = self.session_factory()
        try:
            uow = SqlUnitOfWork(session)
            delivered = 0
            for event in uow.events.list_pending(utcnow(), limit):
                try:
                    self.handler(event)
                except Exception as exc:
                    retry_at = utcnow() + timedelta(
                        seconds=self.backoff_seconds * max(1, event.attempts + 1)
                    )
                    uow.events.mark_failed(event.id, str(exc), retry_at)
                else:
                    uow.events.mark_delivered(event.id, utcnow())
                    delivered += 1
            session.commit()
            return delivered
        finally:
            session.close()


class WebhookSender:
    """Posts events to a webhook URL, optionally HMAC-signed."""

    def __init__(self, url: str, *, secret: str | None = None, timeout: float = 10.0) -> None:
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def __call__(self, event: Event) -> None:
        body = json.dumps(
            {
                "id": event.id,
                "type": event.event_type,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        if self.secret:
            signature = hmac.new(self.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            request.add_header("X-Billing-Signature", signature)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()
