"""ASGI entry point for standalone deployment.

Run with an ASGI server, e.g.::

    uvicorn billing_engine.server:create_server --factory

Requires ``BILLING_DSN`` and ``BILLING_TABLE_PREFIX``; ``BILLING_API_KEY`` is
optional.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from billing_engine.adapters.api.app import create_app
from billing_engine.config import EngineConfig
from billing_engine.domain.errors import ConfigurationError
from billing_engine.sdk import BillingEngine


def create_server() -> FastAPI:
    """Build the standalone application from environment configuration."""
    dsn = os.environ.get("BILLING_DSN")
    prefix = os.environ.get("BILLING_TABLE_PREFIX")
    if not dsn or not prefix:
        raise ConfigurationError("BILLING_DSN and BILLING_TABLE_PREFIX are required")

    engine = BillingEngine(EngineConfig(dsn=dsn, table_prefix=prefix))
    engine.migrate()
    return create_app(engine, api_key=os.environ.get("BILLING_API_KEY"))
