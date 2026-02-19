from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.infrastructure.db import DataConnectionError  # noqa: E402
from vendor_catalog_app.web.app import create_app  # noqa: E402
from vendor_catalog_app.web.core.runtime import get_config, get_repo  # noqa: E402


def test_web_data_connection_error_renders_connection_page(monkeypatch) -> None:
    monkeypatch.setenv("TVENDOR_ENV", "prod")
    monkeypatch.setenv("TVENDOR_CATALOG", "a1_dlk")
    monkeypatch.setenv("TVENDOR_SCHEMA", "twvendor")
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "false")
    monkeypatch.setenv("TVENDOR_SESSION_SECRET", "test-session-secret")
    get_config.cache_clear()
    get_repo.cache_clear()
    app: FastAPI = create_app()

    @app.get("/_test/connection-error")
    def _connection_error() -> dict[str, str]:
        raise DataConnectionError("Failed to connect to Databricks SQL warehouse.")

    client = TestClient(app)
    response = client.get("/_test/connection-error")
    assert response.status_code == 503
    assert "Database Connection Issue" in response.text
    assert "Open Diagnostics" in response.text


def test_connection_lab_can_apply_and_clear_session_override(
    monkeypatch,
    isolated_local_db: Path,
) -> None:
    monkeypatch.setenv("TVENDOR_ENV", "dev")
    get_config.cache_clear()
    get_repo.cache_clear()
    app = create_app()

    @app.get("/_test/runtime-config")
    def _runtime_config() -> dict[str, str]:
        config = get_config()
        return {
            "host": str(config.databricks_server_hostname or ""),
            "http_path": str(config.databricks_http_path or ""),
            "token_present": "true" if bool(str(config.databricks_token or "").strip()) else "false",
        }

    client = TestClient(app)
    apply_response = client.post(
        "/connection-lab/apply",
        data={
            "next": "/_test/runtime-config",
            "databricks_server_hostname": "override.example.cloud.databricks.com",
            "databricks_http_path": "/sql/1.0/warehouses/override123",
            "auth_mode": "pat",
            "databricks_token": "dapi-test-token",
        },
        follow_redirects=False,
    )
    assert apply_response.status_code == 303
    assert str(apply_response.headers.get("location", "")) == "/_test/runtime-config"

    active_response = client.get("/_test/runtime-config")
    assert active_response.status_code == 200
    payload = active_response.json()
    assert payload["host"] == "override.example.cloud.databricks.com"
    assert payload["http_path"] == "/sql/1.0/warehouses/override123"
    assert payload["token_present"] == "true"

    clear_response = client.post(
        "/connection-lab/clear",
        data={"next": "/_test/runtime-config"},
        follow_redirects=False,
    )
    assert clear_response.status_code == 303
    assert str(clear_response.headers.get("location", "")) == "/_test/runtime-config"

    cleared_response = client.get("/_test/runtime-config")
    assert cleared_response.status_code == 200
    cleared_payload = cleared_response.json()
    assert cleared_payload["host"] != "override.example.cloud.databricks.com"
