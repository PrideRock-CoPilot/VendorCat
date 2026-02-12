from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app
from vendor_catalog_app.web.security_controls import CSRF_HEADER, CSRF_SESSION_KEY


@pytest.fixture()
def _clear_app_caches() -> None:
    from vendor_catalog_app.observability import get_observability_manager
    from vendor_catalog_app.web.services import get_config, get_repo

    get_observability_manager.cache_clear()
    get_repo.cache_clear()
    get_config.cache_clear()
    yield
    get_observability_manager.cache_clear()
    get_repo.cache_clear()
    get_config.cache_clear()


def test_api_write_requires_csrf_when_enabled(
    _clear_app_caches: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVENDOR_CSRF_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_WRITE_RATE_LIMIT_ENABLED", "false")

    app = create_app()

    @app.get("/api/_test/csrf-token")
    def _csrf_token(request: Request) -> dict[str, str]:
        return {"token": str(request.session.get(CSRF_SESSION_KEY, ""))}

    @app.post("/api/_test/write")
    def _write_ok() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    seeded = client.get("/api/_test/csrf-token")
    assert seeded.status_code == 200
    token = str(seeded.json().get("token") or "")
    assert token

    blocked = client.post("/api/_test/write")
    assert blocked.status_code == 403
    blocked_payload = blocked.json()
    assert blocked_payload["ok"] is False
    assert blocked_payload["error"]["code"] == "FORBIDDEN"

    allowed = client.post("/api/_test/write", headers={CSRF_HEADER: token})
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True


def test_api_write_rate_limit_returns_429_when_exceeded(
    _clear_app_caches: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVENDOR_CSRF_ENABLED", "false")
    monkeypatch.setenv("TVENDOR_WRITE_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_WRITE_RATE_LIMIT_MAX_REQUESTS", "2")
    monkeypatch.setenv("TVENDOR_WRITE_RATE_LIMIT_WINDOW_SEC", "60")

    app = create_app()

    @app.post("/api/_test/rate")
    def _rate_write() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    assert client.post("/api/_test/rate").status_code == 200
    assert client.post("/api/_test/rate").status_code == 200

    blocked = client.post("/api/_test/rate")
    assert blocked.status_code == 429
    payload = blocked.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "TOO_MANY_REQUESTS"
    assert int(blocked.headers.get("Retry-After", "0")) >= 1


def test_security_headers_include_csp_by_default(
    _clear_app_caches: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TVENDOR_SECURITY_HEADERS_ENABLED", "true")
    monkeypatch.setenv("TVENDOR_CSP_ENABLED", "true")

    app = create_app()

    @app.get("/api/_test/csp")
    def _csp_ok() -> dict[str, bool]:
        return {"ok": True}

    client = TestClient(app)
    response = client.get("/api/_test/csp")
    assert response.status_code == 200
    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp

