# Audit & events

Two complementary records are written **inside the same transaction** as every
mutation: an append-only **audit log** for compliance, and a **transactional
outbox** for integration.

## Audit log

Each row captures who changed what, before and after, why, and from where.

```python
entries = services.uow.audit.list(
    entity_type="subscription",
    entity_id=subscription.id,
    action="subscription.extend",
    actor_id=None,
    limit=50,
    offset=0,
)
```

| Field | Meaning |
|---|---|
| `action` | Dotted verb, e.g. `subscription.cancel`, `invoice.payment.record` |
| `entity_type` / `entity_id` | What changed |
| `actor_type` / `actor_id` | `user`, `api_key`, or `system`; the id if supplied |
| `before` / `after` | JSON snapshots (or `None`) |
| `reason` | Free-text justification when the service accepts one |
| `source` | `embedded`, `rest`, `webhook`, or `job` |
| `ip` | Caller IP, when available |
| `created_at` | UTC timestamp |

!!! danger "Append-only"

    Audit rows are never updated or deleted. The engine has no method to mutate
    them, by design.

### Setting the actor

In embedded mode, pass an `Actor` to record who acted. The REST adapter builds
one from the request automatically (`api_key` + `X-Actor-Id`).

```python
from billing_engine.services.context import Actor

actor = Actor(type="user", id="admin-7", source="embedded", ip="10.0.0.4")
services.subscriptions.cancel(sub.id, reason="churn", actor=actor)
```

### CLI

```bash
billing audit --dsn "postgresql+psycopg://..." --prefix acme_ --entity-type subscription --limit 20
```

## Events (transactional outbox)

Services emit events such as:

| Event | Emitted by |
|---|---|
| `customer.created` | Customers |
| `subscription.created`, `.extended`, `.trial_extended`, `.paused`, `.resumed`, `.canceled`, `.reactivated`, `.plan_changed`, `.renewed`, `.expired`, `.past_due` | Subscriptions |
| `invoice.created`, `.finalized`, `.paid`, `.partially_paid`, `.voided` | Invoices |
| `partner.created`, `license.issued`, `license.revoked` | Partners & licenses |

Events land in the outbox in the same transaction as the change, then a
dispatcher delivers them with retry and backoff.

```python
from billing_engine.events.dispatcher import EventDispatcher, WebhookSender

dispatcher = EventDispatcher(
    engine.session_factory,
    WebhookSender("https://example.com/hooks/billing", secret="whsec_..."),
    backoff_seconds=60,
    max_attempts=5,
)

dispatcher.dispatch_pending(limit=100)   # returns how many were delivered
```

`WebhookSender` POSTs a JSON body:

```json
{
  "id": "01H...",
  "type": "subscription.canceled",
  "payload": {"subscription_id": "01H...", "customer_id": "01H..."},
  "created_at": "2026-09-13T12:00:00+00:00"
}
```

When a secret is configured, the body is signed with HMAC-SHA256 and the hex
digest is sent as the `X-Billing-Signature` header. Verify it by recomputing the
digest over the raw request body with the same secret and comparing in constant
time.

### Delivery semantics

- Event ids are ULIDs; treat delivery as **at-least-once** and make handlers
  **idempotent** (dedupe on `id`).
- Failed deliveries are retried with linear backoff
  (`backoff_seconds * attempt`) until `max_attempts`, then marked failed.
- The dispatcher commits delivery state after processing a batch.

### Reading pending events

```python
services.uow.events.list_pending(utcnow(), limit=100)
```

## Next

- [Errors](../reference/errors.md) — the typed error hierarchy your handlers should catch.
