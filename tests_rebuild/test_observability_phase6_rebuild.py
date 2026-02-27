from __future__ import annotations

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


OBSERVER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "observer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "ops_observer",
}
VIEWER_HEADERS = {
    "HTTP_X_FORWARDED_USER": "viewer@example.com",
    "HTTP_X_FORWARDED_GROUPS": "vendor_viewer",
}


def test_metrics_endpoint_prometheus_contract() -> None:
    client = Client()
    response = client.get("/api/v1/metrics", **OBSERVER_HEADERS)
    assert response.status_code == 200
    text = response.content.decode("utf-8")
    assert "vc_http_request_total" in text
    assert "vc_http_request_duration_ms_bucket" in text
    assert "vc_db_query_total" in text
    assert "vc_db_query_duration_ms_bucket" in text


def test_diagnostics_bootstrap_endpoint_contains_required_fields() -> None:
    client = Client()
    response = client.get("/api/v1/diagnostics/bootstrap", **OBSERVER_HEADERS)
    assert response.status_code == 200
    payload = response.json()
    assert "runtime_profile" in payload
    assert "schema_version" in payload
    assert "config_issues" in payload
    assert "alert_threshold_evaluation" in payload
    assert "search" in payload["alert_threshold_evaluation"]
    assert "import_preview" in payload["alert_threshold_evaluation"]
    assert "report_preview" in payload["alert_threshold_evaluation"]


def test_observability_endpoints_require_permission() -> None:
    client = Client()
    metrics_denied = client.get("/api/v1/metrics", **VIEWER_HEADERS)
    assert metrics_denied.status_code == 403

    diagnostics_denied = client.get("/api/v1/diagnostics/bootstrap", **VIEWER_HEADERS)
    assert diagnostics_denied.status_code == 403
