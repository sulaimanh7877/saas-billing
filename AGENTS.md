# AGENTS.md

Guidance for coding agents and contributors working in this repository.
Read this before making changes. The authoritative design lives in
[`plan.md`](./plan.md); if code and plan disagree, fix one and note it.

## Project

`billing_engine` (repo `saas-billing`) — a self-hostable, MIT-licensed Python
engine that provides billing, subscriptions, entitlements, audit, analytics,
and channel/partner sales for any SaaS. It runs **on the host app's database**,
managing only its own **prefixed** tables, and ships as both an embeddable
library and a standalone FastAPI service.

Status: **pre-release / planning.** The source tree is scaffolded milestone by
milestone (see `plan.md` §7).

## Non-negotiable decisions

These are locked. Do not change them without updating `plan.md` and asking.

- Python 3.11+. Type hints everywhere; `mypy` clean.
- SQLAlchemy 2.0, **sync-first**. Do not introduce async DB code in v0.1.
- Databases: PostgreSQL, MySQL/MariaDB, SQLite. All three must stay supported;
  never write dialect-specific SQL without a portable fallback.
- Primary keys: **ULID strings**.
- Money: **integer minor units** + ISO 4217 currency code. **Never use floats
  for money.**
- All timestamps: **UTC**, timezone-aware.
- Every table, index, constraint, and FK is **prefixed** with the configured
  `table_prefix`. The prefix is **required** and has **no default**.
- FastAPI + Pydantic v2 for HTTP. Typer for CLI.
- Audit is **append-only** — never update or delete audit rows.
- v0.1 has **no live payment gateway**; only manual/invoice billing. Keep the
  provider seam open (Stripe is a stub).

## Architecture rules

```
domain/    pure logic — MUST NOT import SQLAlchemy, FastAPI, or I/O
services/  orchestration + business rules; depend on domain + repo interfaces
adapters/  db/ (SQLAlchemy models, repositories, migrations) and api/ (FastAPI)
events/    transactional outbox + webhook dispatch
sdk.py     BillingEngine facade
cli.py     Typer commands
```

- `domain` depends on nothing. `services` must not import adapters.
- Repositories are defined as interfaces in `domain`/`services` and implemented
  in `adapters/db`. Services depend on the interface, not the implementation.
- Keep business rules in `domain` and `services`, not in routers or models.
- API routers are thin: validate → call service → serialize.
- Anything that mutates data must go through a service and must write an audit
  row **in the same transaction**.

## Conventions

- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`,
  `test:`, `chore:`). One logical change per commit.
- **Style:** ruff format + ruff lint; line length 100; no comments unless they
  explain non-obvious intent.
- **Naming:** modules and files `snake_case`; classes `PascalCase`; table names
  `{prefix}{snake_case_plural}`; indexes `{prefix}ix_<table>_<cols>`;
  constraints `{prefix}ck_...` / `{prefix}uq_...` / `{prefix}fk_...`.
- **Errors:** raise typed errors from `domain/errors.py`; adapters translate them
  to HTTP or CLI output. Never leak DB errors to callers.
- **Config:** all runtime settings flow through `EngineConfig`. No global state
  or module-level DB connections.
- **Migrations:** prefix-aware. Never hard-code a table name; always interpolate
  the configured prefix. Track applied versions in the prefixed `migrations`
  table.

## Workflow (issue → branch → PR → merge)

Never commit directly to `main`. Every change follows this loop:

1. **Create an issue** describing the task, bug, or feature. Use the issue
   number as the anchor for the branch and commits.
2. **Branch from `main`** using the issue number and a short slug:
   - `feat/<issue>-<slug>` for features
   - `fix/<issue>-<slug>` for bugs
   - `docs/<issue>-<slug>`, `refactor/<issue>-<slug>`, `chore/<issue>-<slug>`
   Example: `feat/12-subscription-extension`.
3. **Commit** with Conventional Commits, referencing the issue
   (e.g. `feat: add subscription extension (#12)`). One logical change per
   commit.
4. **Open a PR into `main`.** Title follows Conventional Commits; the body
   summarizes the change, lists the issue (`Closes #12`), and notes testing
   done.
5. **Pass checks before merge:** `ruff check`, `mypy`, `pytest` (including
   integration where applicable) must be green, and the PR must be reviewed.
6. **Merge via PR** (squash merge preferred for a clean history). Do not
   fast-forward or push directly to `main`.
7. **Delete the branch** after merge.

If a fix is needed during review, push new commits to the same branch — never
amend or force-push a reviewed branch.

## Commands

These are the intended commands (available once M0 scaffolding lands):

```bash
ruff format .            # format
ruff check .             # lint
mypy src                 # typecheck
pytest                   # unit tests
pytest -m integration    # Postgres/MySQL/SQLite integration tests
billing migrate          # apply migrations (requires table_prefix)
billing seed             # seed demo data
```

Always run `ruff check`, `mypy`, and `pytest` before considering a task done.
If a command is missing, add it as part of the task that needs it.

## Definition of done

A change is complete only when:

1. It matches the design in `plan.md` (or `plan.md` was updated).
2. Types are complete and `mypy` passes.
3. `ruff check` passes with no new warnings.
4. Tests cover the new behavior, including edge cases.
5. Behavior that touches the DB is covered by integration tests that run on all
   three dialects where feasible.
6. Any data mutation writes an audit row in the same transaction.
7. Docs (`readme.md` / `plan.md` / docstrings) are updated if user-visible
   behavior changed.

## Testing expectations

- Unit tests for `domain` (no DB) — fast, pure.
- Service tests against SQLite in-memory for speed.
- Integration tests against real Postgres and MySQL (via docker-compose) for
  dialect-sensitive paths: migrations, DDL/prefixing, aggregate reporting,
  allocation-counter concurrency.
- Report SQL must be exercised on every supported dialect.
- Concurrency: test two simultaneous license issues against one allocation to
  prove the counter cannot oversell.

## Do / Don't

- **Do** keep `domain` pure and framework-free.
- **Do** interpolate `table_prefix` for every identifier.
- **Do** use integer minor units for all amounts.
- **Do** write audit + outbox rows inside the same transaction as the change.
- **Don't** use floats for money.
- **Don't** import SQLAlchemy or FastAPI from `domain`.
- **Don't** update or delete audit/ledger rows.
- **Don't** add a live payment gateway in v0.1.
- **Don't** commit secrets, `.env` files, or credentials.

## Milestones

Work proceeds in order (see `plan.md` §7). v0.1.0 = core (M0–M8).
v0.2.0 = channel & partners (P1–P4). Prefer finishing and hardening the current
milestone over starting the next.

## Repository layout (target)

```
src/billing_engine/   package
migrations/           prefix-aware migration files
tests/                unit + integration
examples/             embedded + standalone demos
docs/                 ADRs and guides
```
