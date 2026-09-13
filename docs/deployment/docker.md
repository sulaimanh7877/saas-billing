# Docker

The repository ships a `Dockerfile` and a `docker-compose.yml` with PostgreSQL
and MySQL.

## Build and run

```bash
docker build -t billing-engine .

docker run --rm -p 8000:8000 \
  -e BILLING_DSN="postgresql+psycopg://billing:billing@host.docker.internal:5432/billing" \
  -e BILLING_TABLE_PREFIX="acme_" \
  -e BILLING_API_KEY="a-long-random-secret" \
  billing-engine
```

The container's default command runs the migrations on startup and serves the
FastAPI app on port `8000`.

## Compose

`docker-compose.yml` starts PostgreSQL on `5432` and MySQL on `3306` with
throwaway credentials for local development and integration tests.

```bash
docker compose up -d
```

| Service | Host | User / password | Database |
|---|---|---|---|
| `postgres` | `localhost:5432` | `billing` / `billing` | `billing` |
| `mysql` | `localhost:3306` | `billing` / `billing` | `billing` |

Point the engine at one of them:

```bash
export BILLING_DSN="postgresql+psycopg://billing:billing@localhost:5432/billing"
export BILLING_TABLE_PREFIX="acme_"
billing migrate
```

## Production notes

- **Run migrations as a deploy step**, not per replica, to avoid racing DDL.
  `billing migrate` is idempotent.
- Install the database driver for your engine — for PostgreSQL add
  `psycopg[binary]` to the image.
- Set a strong `BILLING_API_KEY`; the service has no user system of its own.
- Back up the prefixed tables (`acme_*`) along with the rest of the database.
- Run a single scheduler for `process_due()`; use your platform's cron or a
  worker, and make sure only one runs at a time.

## Next

- [Standalone & REST](rest.md)
- [Configuration](../reference/configuration.md)
