from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.routers import dashboard as dashboard_router


def test_dashboard_returns_setup_page_when_schema_bootstrap_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()

    def _raise_bootstrap(_request):
        raise SchemaBootstrapRequiredError(
            "Databricks schema is not initialized or access is blocked. "
            "Run the bootstrap SQL manually before starting the app: setup/v1_schema/databricks/00_create_v1_schema.sql."
        )

    monkeypatch.setattr(dashboard_router, "get_user_context", _raise_bootstrap)
    client = TestClient(app)

    response = client.get("/dashboard")
    assert response.status_code == 503
    assert "Bootstrap Diagnostics" in response.text
    assert "setup/v1_schema/databricks/00_create_v1_schema.sql" in response.text
    assert "/bootstrap-diagnostics" in response.text
    assert "/api/bootstrap-diagnostics" in response.text
