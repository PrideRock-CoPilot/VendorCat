from __future__ import annotations

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def test_root_redirects_to_dashboard(client: Client) -> None:
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"] == "/dashboard"


def test_top_level_routes_render(client: Client) -> None:
    for path in [
        "/dashboard",
        "/vendor-360",
        "/projects",
        "/imports",
        "/workflows",
        "/reports",
        "/admin",
        "/contracts",
        "/demos",
        "/help",
    ]:
        response = client.get(path, follow=True)
        assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"


def test_health_endpoints_and_request_id_header(client: Client) -> None:
    live = client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "live"
    assert "X-Request-ID" in live

    ready = client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    runtime = client.get("/api/v1/runtime")
    assert runtime.status_code == 200
    assert "runtime_profile" in runtime.json()


def test_identity_endpoint(client: Client) -> None:
    response = client.get("/api/v1/identity", HTTP_X_FORWARDED_USER="user@example.com")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user_principal"] == "user@example.com"
