from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.observability import get_observability_manager
from vendor_catalog_app.web.app import create_app


@pytest.fixture()
def _reset_observability_cache() -> None:
    get_observability_manager.cache_clear()
    yield
    get_observability_manager.cache_clear()


def test_api_error_response_is_structured(
    _reset_observability_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVENDOR_REQUEST_ID_HEADER_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_METRICS_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_METRICS_PROMETHEUS_ENABLED", "true")
    app = create_app()

    @app.get("/api/test-error-400")
    def _test_error_route() -> dict[str, bool]:
        raise ValueError("Sample validation failure.")

    client = TestClient(app)
    response = client.get("/api/test-error-400")

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "BAD_REQUEST"
    assert payload["error"]["message"] == "Sample validation failure."
    assert payload["request_id"]
    assert response.headers.get("X-Request-ID") == payload["request_id"]


def test_prometheus_metrics_endpoint_exports_core_metrics(
    _reset_observability_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVENDOR_METRICS_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_METRICS_PROMETHEUS_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_METRICS_PROMETHEUS_PATH", "/api/metrics")
    monkeypatch.setenv("TVENDOR_METRICS_ALLOW_UNAUTHENTICATED", "true")
    app = create_app()

    @app.get("/api/test-observe")
    def _test_observe_route() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    observed = client.get("/api/test-observe")
    assert observed.status_code == 200

    metrics = client.get("/api/metrics")
    assert metrics.status_code == 200
    text = metrics.text
    assert "tvendor_http_requests_total" in text
    assert "tvendor_http_request_duration_ms_bucket" in text
    assert 'path="/api/test-observe"' in text
