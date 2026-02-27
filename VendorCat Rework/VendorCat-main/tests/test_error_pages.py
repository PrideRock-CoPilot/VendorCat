from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from vendor_catalog_app.web.app import create_app  # noqa: E402


def test_non_api_validation_error_renders_html_page() -> None:
    app: FastAPI = create_app()

    @app.get("/_test/validate")
    def _validate(required_number: int) -> dict[str, int]:
        return {"required_number": int(required_number)}

    client = TestClient(app)
    response = client.get("/_test/validate")
    assert response.status_code == 422
    assert "Validation Error" in response.text
    assert "text/html" in str(response.headers.get("content-type", "")).lower()


def test_api_validation_error_stays_json() -> None:
    app: FastAPI = create_app()

    @app.get("/api/_test/validate")
    def _validate(required_number: int) -> dict[str, int]:
        return {"required_number": int(required_number)}

    client = TestClient(app)
    response = client.get("/api/_test/validate")
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
