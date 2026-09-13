from fastapi.testclient import TestClient

from billing_engine import BillingEngine, EngineConfig
from billing_engine.adapters.api.app import create_app
from conftest import TEST_PREFIX

HEADERS = {"X-API-Key": "secret"}


def make_client(tmp_path) -> TestClient:
    engine = BillingEngine(
        EngineConfig(dsn=f"sqlite:///{tmp_path / 'api.sqlite3'}", table_prefix=TEST_PREFIX)
    )
    engine.create_all()
    return TestClient(create_app(engine, api_key="secret"))


def test_requires_api_key(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.get("/customers")
    assert response.status_code == 401


def test_full_flow(tmp_path) -> None:
    client = make_client(tmp_path)

    customer = client.post(
        "/customers", json={"external_id": "u1", "email": "u1@example.com"}, headers=HEADERS
    ).json()
    client.post("/features", json={"key": "reports"}, headers=HEADERS)
    plan = client.post("/plans", json={"key": "pro"}, headers=HEADERS).json()
    version = client.post(
        f"/plans/{plan['id']}/versions",
        json={
            "prices": [{"amount_minor": 2900, "currency": "USD", "interval": "month"}],
            "entitlements": [{"feature_key": "reports", "limit_value": 1}],
        },
        headers=HEADERS,
    ).json()
    subscription = client.post(
        "/subscriptions",
        json={"customer_id": customer["id"], "plan_version_id": version["id"]},
        headers=HEADERS,
    ).json()

    check = client.post(
        "/entitlements/check",
        json={"customer_id": customer["id"], "feature_key": "reports"},
        headers=HEADERS,
    ).json()
    assert check["allowed"] is True

    extended = client.post(
        f"/subscriptions/{subscription['id']}/extend", json={"days": 5}, headers=HEADERS
    ).json()
    assert extended["current_period_end"] > subscription["current_period_end"]

    invoice = client.post(
        "/invoices",
        json={
            "customer_id": customer["id"],
            "lines": [{"description": "Setup", "quantity": 1, "unit_amount_minor": 1000}],
            "finalize": True,
        },
        headers=HEADERS,
    ).json()
    payment = client.post(
        f"/invoices/{invoice['id']}/payments", json={"amount_minor": 1000}, headers=HEADERS
    ).json()
    assert payment["amount_minor"] == 1000

    overview = client.get("/reports/overview", headers=HEADERS).json()
    assert overview["mrr_minor"] == 2900
    assert overview["customers"] == 1

    logs = client.get("/audit-logs", params={"action": "customer.create"}, headers=HEADERS).json()
    assert len(logs) == 1
    assert logs[0]["entity_id"] == customer["id"]


def test_validation_error_maps_to_400(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.post("/customers", json={"external_id": "   "}, headers=HEADERS)
    assert response.status_code == 400


def test_not_found_maps_to_404(tmp_path) -> None:
    client = make_client(tmp_path)
    response = client.get("/customers/01HZZZZZZZZZZZZZZZZZZZZZZZ", headers=HEADERS)
    assert response.status_code == 404
