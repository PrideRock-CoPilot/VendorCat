from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.config import AppConfig
from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.routers.system import diagnostics_pages as diagnostics_router


class _DiagnosticsRepoHealthy:
    def _table(self, name: str) -> str:
        return f"a1_dlk.twvendor.{name}"

    def _probe_file(self, _relative_path: str, **_kwargs):
        return None


def test_bootstrap_diagnostics_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(diagnostics_router, "get_repo", lambda: _DiagnosticsRepoHealthy())
    monkeypatch.setattr(
        diagnostics_router,
        "get_config",
        lambda: AppConfig(
            databricks_server_hostname="example.cloud.databricks.com",
            databricks_http_path="/sql/1.0/warehouses/abc",
            databricks_token="",
            catalog="a1_dlk",
            schema="twvendor",
            use_local_db=False,
        ),
    )
    monkeypatch.setattr(
        diagnostics_router,
        "resolve_databricks_request_identity",
        lambda _request: {"principal": "admin@example.com", "email": "admin@example.com", "network_id": ""},
    )

    client = TestClient(app)
    response = client.get("/bootstrap-diagnostics")

    assert response.status_code == 200
    assert "Bootstrap Diagnostics" in response.text
    assert "connectivity_probe" in response.text
    assert "/api/bootstrap-diagnostics" in response.text
