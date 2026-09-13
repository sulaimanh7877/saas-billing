"""Concurrency integration tests (PostgreSQL/MySQL only).

Run with ``BILLING_TEST_PG_DSN=postgresql://billing:billing@localhost/billing``
after ``docker compose up -d postgres``.
"""

from __future__ import annotations

import os
import threading

import pytest

from billing_engine import BillingEngine, EngineConfig
from billing_engine.domain.errors import AllocationExhaustedError, ConflictError

PG_DSN = os.environ.get("BILLING_TEST_PG_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_DSN, reason="set BILLING_TEST_PG_DSN to run"),
]


def _fresh_engine(tmp_path) -> BillingEngine:
    BillingEngine.reset_process_state()
    engine = BillingEngine(EngineConfig(dsn=PG_DSN, table_prefix="itg_"))
    engine.drop_all()
    engine.create_all()
    return engine


def test_c1_concurrent_license_issue_does_not_oversell(tmp_path) -> None:
    engine = _fresh_engine(tmp_path)
    try:
        with engine.transaction() as services:
            plan = services.catalog.create_plan("conc")
            version = services.catalog.create_plan_version(
                plan.id, prices=[{"amount_minor": 100, "currency": "USD", "interval": "month"}]
            )
            partner = services.partners.create("Concurrency partner")
            allocation = services.licenses.allocate(partner.id, version.id, 1)
            allocation_id = allocation.id

        barrier = threading.Barrier(2)
        results: list[str] = []

        def worker(external_id: str) -> None:
            barrier.wait()
            try:
                with engine.transaction() as services:
                    services.licenses.issue(allocation_id, external_id=external_id)
                results.append("issued")
            except AllocationExhaustedError:
                results.append("exhausted")

        threads = [
            threading.Thread(target=worker, args=("end-1",)),
            threading.Thread(target=worker, args=("end-2",)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(results) == ["exhausted", "issued"]
    finally:
        BillingEngine.reset_process_state()


def test_c2_concurrent_credit_consume_does_not_overdraw(tmp_path) -> None:
    engine = _fresh_engine(tmp_path)
    try:
        with engine.transaction() as services:
            customer = services.customers.create("conc-credit", currency="USD")
            services.credits.grant(customer.id, 100)
            customer_id = customer.id

        barrier = threading.Barrier(2)
        results: list[str] = []

        def worker() -> None:
            barrier.wait()
            try:
                with engine.transaction() as services:
                    services.credits.consume(customer_id, 100)
                results.append("consumed")
            except ConflictError:
                results.append("rejected")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(results) == ["consumed", "rejected"]
    finally:
        BillingEngine.reset_process_state()
