"""Tests for standalone server configuration (F11 / S3)."""

from __future__ import annotations

import pytest

from billing_engine.domain.errors import ConfigurationError
from billing_engine.server import create_server
from conftest import TEST_PREFIX


def test_create_server_wires_all_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BILLING_DSN", f"sqlite:///{tmp_path / 'server.sqlite3'}")
    monkeypatch.setenv("BILLING_TABLE_PREFIX", TEST_PREFIX)
    monkeypatch.setenv("BILLING_DEFAULT_CURRENCY", "eur")
    monkeypatch.setenv("BILLING_TRIAL_DAYS", "7")
    monkeypatch.setenv("BILLING_GRACE_PERIOD_DAYS", "3")

    app = create_server()
    config = app.state.engine.config
    assert config.default_currency == "EUR"
    assert config.trial_days == 7
    assert config.grace_period_days == 3


def test_create_server_rejects_non_integer_durations(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("BILLING_DSN", f"sqlite:///{tmp_path / 'server.sqlite3'}")
    monkeypatch.setenv("BILLING_TABLE_PREFIX", TEST_PREFIX)
    monkeypatch.setenv("BILLING_TRIAL_DAYS", "soon")
    with pytest.raises(ConfigurationError, match="BILLING_TRIAL_DAYS"):
        create_server()


def test_create_server_requires_dsn_and_prefix(monkeypatch) -> None:
    monkeypatch.delenv("BILLING_DSN", raising=False)
    monkeypatch.delenv("BILLING_TABLE_PREFIX", raising=False)
    with pytest.raises(ConfigurationError):
        create_server()
