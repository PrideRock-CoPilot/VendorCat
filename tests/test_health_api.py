from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.core.config import AppConfig
from vendor_catalog_app.repository import SchemaBootstrapRequiredError
from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.routers.system import api_health as api_router


class _HealthyRepo:
    def ensure_runtime_tables(self) -> None:
        return


class _BrokenRepo:
    def ensure_runtime_tables(self) -> None:
        raise SchemaBootstrapRequiredError("schema missing")


class _DiagnosticsRepoHealthy:
    def _table(self, name: str) -> str:
        return f"a1_dlk.twvendor.{name}"

    def _probe_file(self, _relative_path: str, **_kwargs):
        return None


class _DiagnosticsRepoConnectivityBroken:
    def _table(self, name: str) -> str:
        return f"a1_dlk.twvendor.{name}"

    def _probe_file(self, relative_path: str, **_kwargs):
        if relative_path == "health/select_connectivity_check.sql":
            raise RuntimeError("cannot open session to SQL warehouse")
        return None


class _ObservabilityStub:
    def health_snapshot(self) -> dict[str, object]:
        return {
            "metrics_enabled": True,
            "prometheus_enabled": True,
            "prometheus_path": "/api/metrics",
            "statsd_enabled": False,
            "alerts_enabled": True,
            "active_alert_count": 0,
            "active_alerts": [],
            "alert_breaches_total": {
                "request_p95_ms": 0,
                "error_rate_pct": 0,
                "db_avg_ms": 0,
            },
            "window_sample_size": 0,
            "uptime_seconds": 1,
        }


def test_health_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
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


def test_health_live_ok() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "live"
    assert payload["service"] == "vendor_catalog_app"
    assert payload.get("timestamp")


def test_health_ready_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _HealthyRepo())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig("", "", "", use_local_db=False),
    )
    client = TestClient(app)

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "ready"
    assert payload["checks"]["runtime_tables"]["ok"] is True
    assert payload["checks"]["runtime_tables"]["error"] is None


def test_health_ready_reports_bootstrap_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _BrokenRepo())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig("", "", "", use_local_db=False),
    )
    client = TestClient(app)

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["status"] == "not_ready"
    assert "schema missing" in str(payload["checks"]["runtime_tables"]["error"])


def test_health_observability_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(api_router, "get_observability_manager", lambda: _ObservabilityStub())
    client = TestClient(app)

    response = client.get("/api/health/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "observability"
    assert payload["observability"]["prometheus_path"] == "/api/metrics"


def test_health_reports_bootstrap_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
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


def test_bootstrap_diagnostics_reports_connectivity_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _DiagnosticsRepoConnectivityBroken())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig(
            databricks_server_hostname="example.cloud.databricks.com",
            databricks_http_path="/sql/1.0/warehouses/abc",
            databricks_token="",
            use_local_db=False,
            catalog="a1_dlk",
            schema="twvendor",
        ),
    )
    client = TestClient(app)

    response = client.get("/api/bootstrap-diagnostics")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["schema"] == "a1_dlk.twvendor"
    checks = payload["checks"]
    assert checks[1]["name"] == "connectivity_probe"
    assert checks[1]["status"] == "fail"
    assert any("cannot open session to SQL warehouse" in detail for detail in checks[1]["details"])


def test_bootstrap_diagnostics_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TVENDOR_BOOTSTRAP_DIAGNOSTICS_ENABLED", "true")
    app = create_app()
    monkeypatch.setattr(api_router, "get_repo", lambda: _DiagnosticsRepoHealthy())
    monkeypatch.setattr(
        api_router,
        "get_config",
        lambda: AppConfig(
            databricks_server_hostname="example.cloud.databricks.com",
            databricks_http_path="/sql/1.0/warehouses/abc",
            databricks_token="",
            use_local_db=False,
            catalog="a1_dlk",
            schema="twvendor",
        ),
    )
    client = TestClient(app)

    response = client.get("/api/bootstrap-diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["schema"] == "a1_dlk.twvendor"
    assert any(check["name"] == "connectivity_probe" and check["status"] == "pass" for check in payload["checks"])
