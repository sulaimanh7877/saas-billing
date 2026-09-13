import pytest

from billing_engine.domain.errors import ConflictError, NotFoundError, ValidationError
from helpers import make_customer


def test_create_customer(services) -> None:
    customer = make_customer(services, "user-1", email="a@example.com")
    assert len(customer.id) == 26
    assert customer.external_id == "user-1"
    assert customer.currency == "USD"
    assert services.customers.get_by_external_id("user-1").id == customer.id


def test_duplicate_external_id_conflicts(services) -> None:
    make_customer(services, "user-1")
    with pytest.raises(ConflictError):
        make_customer(services, "user-1")


def test_blank_external_id_is_rejected(services) -> None:
    with pytest.raises(ValidationError):
        make_customer(services, "   ")


def test_update_customer(services) -> None:
    customer = make_customer(services, "user-1")
    updated = services.customers.update(customer.id, name="Ada", email="ada@example.com")
    assert updated.name == "Ada"
    assert updated.email == "ada@example.com"
    assert services.customers.get(customer.id).name == "Ada"


def test_missing_customer_raises(services) -> None:
    with pytest.raises(NotFoundError):
        services.customers.get("01HZZZZZZZZZZZZZZZZZZZZZZZ")


def test_customer_creation_is_audited(services) -> None:
    customer = make_customer(services, "user-1")
    entries = services.uow.audit.list(entity_type="customer")
    assert [entry.action for entry in entries] == ["customer.create"]
    assert entries[0].after["external_id"] == "user-1"
    assert entries[0].entity_id == customer.id
