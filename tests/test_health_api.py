from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.routers import api as api_router


class _HealthyRepo:
    def ensure_runtime_tables(self) -> None:
        return


class _BrokenRepo:
    def ensure_runtime_tables(self) -> None:
        raise SchemaBootstrapRequiredError("schema missing")


def test_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _HealthyRepo())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig("", "", "", use_local_db=False),
    )
    client = TestClient(app)

    response = client.get(
        "/api/health",
        headers={"x-forwarded-preferred-username": "admin@example.com"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["principal"] == "admin@example.com"


def test_health_reports_bootstrap_error(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _BrokenRepo())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig("", "", "", use_local_db=False),
    )
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert "schema missing" in payload["error"]
